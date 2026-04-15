from langchain_core.messages import AIMessage
from app.agents.state.state import AgentState
from app.services.llm.factory import get_llm_provider
from app.services.redis.redis_services import redis_service
from app.core.config import settings
from app.agents.tools.web_search import build_search_context, search_web, should_use_web_search
import ast
import json
import re


PLANNER_PROMPT = """You are a senior AI task planner.
Given the user request, produce a short execution plan with 3-6 concrete steps.

Rules:
- Keep steps practical and action-oriented.
- Avoid generic statements.
- Output plain text with numbered steps only.
"""


GENERAL_PLANNER_PROMPT = """You are a research and answer-planning assistant.
Given the user request, produce a short plan for a non-coding response.

Rules:
- Focus on understanding the question, identifying needed evidence, and organizing the answer.
- Keep it practical and concise.
- If web search is useful, identify the key evidence areas to verify.
- If this is a follow-up, preserve the previous topic and continue from it.
- Output plain text with numbered steps only.
"""


EXECUTOR_PROMPT = """You are an autonomous coding and problem-solving agent.
You must execute the plan and produce a high-quality answer.

Rules:
- Be precise and practical.
- Include code snippets when useful.
- Mention assumptions clearly.
- If there is risk, call it out briefly.
"""


GENERAL_EXECUTOR_PROMPT = """You are an autonomous research and decision-support agent.
You must execute the plan and produce a high-quality response for non-coding requests.

Rules:
- Be detailed, practical, and well structured.
- Do not answer in short keywords or one-line summaries.
- Write in complete sentences and explain the reasoning behind each point.
- Prefer domain insights, options, trade-offs, and recommendations.
- Include examples, implications, limitations, and next steps when helpful.
- If web context exists, synthesize it into a clear narrative instead of listing links only.
- Mention assumptions and uncertainty clearly.
- Use recent conversation context to answer follow-up questions directly and consistently.
"""


REVIEWER_PROMPT = """You are a strict reviewer.
Review the draft answer for correctness, completeness, and clarity.
Then output an improved final answer in strict JSON format.

Rules:
- Keep all correct technical details.
- Remove fluff.
- Ensure actionable steps.
- Return ONLY valid JSON using this schema:
{
  "summary": "one short paragraph",
  "plan_steps": ["step 1", "step 2"],
    "improved_code": "implementation code only (NO tests), plain text",
    "test_cases": "concise tests only (pytest/checklist), plain text",
  "final_answer": "final polished answer"
}
"""


GENERAL_REVIEWER_PROMPT = """You are a strict reviewer for non-coding responses.
Review the draft for correctness, completeness, and clarity.
Then output an improved final answer in strict JSON format.

Rules:
- Keep all correct domain details.
- Remove fluff.
- Ensure actionability.
- Expand brief points into full explanations where needed.
- Prefer a rich, helpful answer over a terse one.
- Ensure final_answer is detailed (target 250-600 words unless user asks for brevity).
- Preserve continuity with prior conversation turns and avoid resetting the topic.
- For non-coding tasks, set improved_code and test_cases to empty strings.
- Include 3-5 concise key_points if useful.
- Return ONLY valid JSON using this schema:
{
    "summary": "one short paragraph",
    "key_points": ["point 1", "point 2"],
    "plan_steps": ["step 1", "step 2"],
    "improved_code": "",
    "test_cases": "",
    "final_answer": "final polished answer"
}
"""


TEST_BLOCK_PATTERNS = [
        r"(?ms)^def\s+test_[\w_]*\s*\([^)]*\):\n(?:^[ \t].*\n|^\n)*",
        r"(?ms)^async\s+def\s+test_[\w_]*\s*\([^)]*\):\n(?:^[ \t].*\n|^\n)*",
        r"(?ms)^class\s+Test[\w_]*\s*\([^)]*\):\n(?:^[ \t].*\n|^\n)*",
        r"(?ms)^class\s+Test[\w_]*\s*:\n(?:^[ \t].*\n|^\n)*",
]


def _is_coding_request(text: str) -> bool:
    value = str(text or "")
    if not value.strip():
        return False

    if re.search(r"```[\s\S]*```", value):
        return True

    strong_signals = [
        r"\bpython\b", r"\bjavascript\b", r"\btypescript\b", r"\bjava\b", r"\bc\+\+\b", r"\bc#\b",
        r"\bapi endpoint\b", r"\bwrite code\b", r"\bimplement\b", r"\bdebug\b", r"\brefactor\b",
        r"\bunit test\b", r"\bpytest\b", r"\bjest\b", r"\bstack trace\b", r"\bsql query\b",
    ]
    syntax_signal = re.search(
        r"\b(def\s+\w+|class\s+\w+|function\s+\w+|const\s+\w+|let\s+\w+|var\s+\w+|import\s+\w+|from\s+\w+\s+import|SELECT\s+.+\s+FROM|CREATE\s+TABLE|INSERT\s+INTO)\b",
        value,
        flags=re.IGNORECASE,
    )

    return bool(syntax_signal or any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in strong_signals))


def _extract_json(text: str) -> dict:
    raw = str(text or "").strip()
    if not raw:
        return {}

    try:
        return json.loads(raw)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            try:
                parsed = ast.literal_eval(candidate)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

    # Fallback for python-dict-like outputs that are not strict JSON.
    try:
        parsed = ast.literal_eval(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_plan_steps(value) -> list[str]:
    if isinstance(value, list):
        return [str(step).strip() for step in value if str(step).strip()]

    text = str(value or "").strip()
    if not text:
        return []

    steps = []
    for line in text.splitlines():
        clean = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if clean:
            steps.append(clean)
    return steps


def _format_recent_history(history: list[dict], max_messages: int = 8) -> str:
    recent = history[-max_messages:] if history else []
    if not recent:
        return "No prior conversation context available."

    lines: list[str] = []
    for message in recent:
        role = str(message.get("role", "user")).strip().lower()
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        role_label = "User" if role == "user" else "Assistant" if role == "assistant" else role.title()
        lines.append(f"{role_label}: {content}")

    return "\n".join(lines) if lines else "No prior conversation context available."


def _structured_dict_to_text(data: dict) -> str:
    """Convert arbitrary structured dict output into readable markdown-like text."""
    if not isinstance(data, dict) or not data:
        return ""

    blocks: list[str] = []
    for key, value in data.items():
        key_text = str(key).replace("_", " ").strip().title()

        if isinstance(value, list):
            if not value:
                continue
            if all(isinstance(item, dict) for item in value):
                lines = []
                for item in value:
                    parts = [f"{k}: {v}" for k, v in item.items() if v not in (None, "", [], {})]
                    if parts:
                        lines.append("- " + "; ".join(parts))
                body = "\n".join(lines)
            else:
                body = "\n".join(f"- {item}" for item in value)
            if body:
                blocks.append(f"## {key_text}\n{body}")
            continue

        if isinstance(value, dict):
            parts = [f"- {k}: {v}" for k, v in value.items() if v not in (None, "", [], {})]
            if parts:
                blocks.append(f"## {key_text}\n" + "\n".join(parts))
            continue

        value_text = str(value).strip()
        if value_text:
            blocks.append(f"## {key_text}\n{value_text}")

    return "\n\n".join(blocks).strip()


def _split_code_and_tests(improved_code: str, test_cases: str) -> tuple[str, str]:
    code_text = str(improved_code or "").strip()
    tests_text = str(test_cases or "").strip()
    extracted_tests: list[str] = []

    if not code_text:
        return code_text, tests_text

    for pattern in TEST_BLOCK_PATTERNS:
        for match in re.findall(pattern, code_text):
            snippet = str(match or "").strip()
            if snippet:
                extracted_tests.append(snippet)
        code_text = re.sub(pattern, "", code_text)

    code_text = re.sub(r"\n{3,}", "\n\n", code_text).strip()

    if extracted_tests:
        merged = "\n\n".join(extracted_tests).strip()
        tests_text = f"{tests_text}\n\n{merged}".strip() if tests_text else merged

    return code_text, tests_text


def _build_response_data(
    final_answer: str,
    plan: str,
    draft: str,
    provider: str,
    model: str,
    structured: dict,
    sources: list[dict] | None = None,
    execution_mode: str = "general",
) -> dict:
    summary = str(structured.get("summary") or "Agentic execution completed with planning and review.").strip()
    final_text = str(structured.get("final_answer") or final_answer).strip()
    improved_code = str(structured.get("improved_code") or "").strip()
    test_cases = str(structured.get("test_cases") or "").strip()
    key_points = structured.get("key_points") or []
    improved_code, test_cases = _split_code_and_tests(improved_code, test_cases)
    plan_steps = _normalize_plan_steps(structured.get("plan_steps") or plan)

    if execution_mode == "coding":
        payload = {
            "kind": "multi_agent",
            "summary": summary,
            "answer": final_text,
            "plan_steps": plan_steps,
            "improved_code": improved_code,
            "test_cases": test_cases,
            "sections": [
                {"title": "Plan", "body": "\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(plan_steps)) or plan},
                {"title": "Improved Code", "body": improved_code or draft},
                {"title": "Test Cases", "body": test_cases or "Add test coverage for success and failure cases."},
                {"title": "Final", "body": final_text},
            ],
            "provider": provider,
            "model": model,
            "execution_mode": execution_mode,
        }
    else:
        key_points_list = _normalize_plan_steps(key_points)
        payload = {
            "kind": "multi_agent",
            "summary": summary,
            "answer": final_text,
            "key_points": key_points_list,
            "sections": [
                {"title": "Summary", "body": summary},
                {"title": "Answer", "body": final_text},
            ],
            "provider": provider,
            "model": model,
            "execution_mode": execution_mode,
        }

        if key_points_list:
            payload["sections"].append({
                "title": "Key Points",
                "body": "\n".join(f"- {item}" for item in key_points_list),
            })

        if not key_points_list and final_text:
            payload["sections"].append({
                "title": "Detailed View",
                "body": final_text,
            })

    if sources:
        payload["sources"] = sources
        payload["result_count"] = len(sources)
        payload["sections"].append({
            "title": "Sources",
            "body": "\n".join(
                f"[{item.get('rank', idx + 1)}] {item.get('title', 'Untitled')} - {item.get('url', '')}"
                for idx, item in enumerate(sources)
            ),
        })
    elif execution_mode != "coding":
        payload["references_note"] = "No web references found for this query. Try adding specific keywords (topic, region, date, source type)."

    return payload


async def multi_agent_node(state: AgentState) -> AgentState:
    """
    Multi-agent style workflow:
    1) Plan
    2) Execute draft
    3) Review and refine
    """

    try:
        provider_name = state.get("provider", settings.DEFAULT_LLM_PROVIDER)
        model = state.get("model", settings.DEFAULT_GROQ_MODEL)
        provider = get_llm_provider(provider_name)

        history = await redis_service.get_history(state["conversation_id"])

        user_message = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content
                break
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        context_messages = history[-10:] if history else []
        context_blob = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in context_messages
        )
        recent_history_block = _format_recent_history(history, max_messages=8)
        is_coding_request = _is_coding_request(user_message)
        planner_prompt = PLANNER_PROMPT if is_coding_request else GENERAL_PLANNER_PROMPT
        executor_prompt = EXECUTOR_PROMPT if is_coding_request else GENERAL_EXECUTOR_PROMPT
        reviewer_prompt = REVIEWER_PROMPT if is_coding_request else GENERAL_REVIEWER_PROMPT

        web_sources: list[dict] = []
        web_context = ""
        if not is_coding_request and should_use_web_search(user_message):
            try:
                web_sources = await search_web(user_message, max_results=5)
                web_context = build_search_context(web_sources)
            except Exception:
                web_sources = []
                web_context = ""

        await redis_service.append_message(
            state["conversation_id"],
            {"role": "user", "content": user_message},
        )

        web_context_block = (
            f"\n\nWeb search results (optional context):\n{web_context}" if web_context else ""
        )

        conversation_context_block = (
            f"\n\nRecent conversation context:\n{recent_history_block}"
            if recent_history_block else ""
        )

        plan = await provider.chat(
            messages=[
                {"role": "system", "content": planner_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Conversation context:\n{context_blob}\n\n"
                        f"Follow-up memory:\n{recent_history_block}\n\n"
                        f"User request:\n{user_message}"
                        f"{conversation_context_block}"
                        f"{web_context_block}"
                    ),
                },
            ],
            model=model,
        )

        draft = await provider.chat(
            messages=[
                {"role": "system", "content": executor_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Recent conversation context:\n{recent_history_block}\n\n"
                        f"User request:\n{user_message}\n\n"
                        f"Execution plan:\n{plan}\n\n"
                        f"Additional web context:\n{web_context or 'None'}\n\n"
                        "Produce the best possible draft answer now."
                    ),
                },
            ],
            model=model,
        )

        reviewed_output = await provider.chat(
            messages=[
                {"role": "system", "content": reviewer_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Recent conversation context:\n{recent_history_block}\n\n"
                        f"Original request:\n{user_message}\n\n"
                        f"Plan:\n{plan}\n\n"
                        f"Draft answer:\n{draft}\n\n"
                        f"Available sources:\n{web_context or 'None'}"
                    ),
                },
            ],
            model=model,
        )

        structured = _extract_json(reviewed_output)

        final_answer = ""
        if structured:
            final_answer = str(structured.get("final_answer") or "").strip()
            if not final_answer:
                final_answer = _structured_dict_to_text(structured)

        if not final_answer:
            final_answer = str(reviewed_output).strip()

        # Non-coding answers should stay rich; fallback to draft when review output is too terse.
        if not is_coding_request and len(final_answer) < 380 and len(str(draft).strip()) > len(final_answer):
            final_answer = str(draft).strip()

        await redis_service.append_message(
            state["conversation_id"],
            {"role": "assistant", "content": final_answer},
        )

        response_data = _build_response_data(
            final_answer=final_answer,
            plan=plan,
            draft=draft,
            provider=provider_name,
            model=model,
            structured=structured,
            sources=web_sources,
            execution_mode="coding" if is_coding_request else "general",
        )

        return {
            **state,
            "final_response": final_answer,
            "response_data": response_data,
            "messages": state["messages"] + [AIMessage(content=final_answer)],
            "error": None,
        }
    except Exception as e:
        error_msg = f"Multi-agent error: {str(e)}"
        return {
            **state,
            "final_response": error_msg,
            "error": error_msg,
        }
