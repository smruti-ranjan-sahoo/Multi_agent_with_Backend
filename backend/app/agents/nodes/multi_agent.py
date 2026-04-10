from langchain_core.messages import AIMessage
from app.agents.state.state import AgentState
from app.services.llm.factory import get_llm_provider
from app.services.redis.redis_services import redis_service
from app.core.config import settings
import json
import re


PLANNER_PROMPT = """You are a senior AI task planner.
Given the user request, produce a short execution plan with 3-6 concrete steps.

Rules:
- Keep steps practical and action-oriented.
- Avoid generic statements.
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


TEST_BLOCK_PATTERNS = [
        r"(?ms)^def\s+test_[\w_]*\s*\([^)]*\):\n(?:^[ \t].*\n|^\n)*",
        r"(?ms)^async\s+def\s+test_[\w_]*\s*\([^)]*\):\n(?:^[ \t].*\n|^\n)*",
        r"(?ms)^class\s+Test[\w_]*\s*\([^)]*\):\n(?:^[ \t].*\n|^\n)*",
        r"(?ms)^class\s+Test[\w_]*\s*:\n(?:^[ \t].*\n|^\n)*",
]


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
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}
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
) -> dict:
    summary = str(structured.get("summary") or "Agentic execution completed with planning and review.").strip()
    final_text = str(structured.get("final_answer") or final_answer).strip()
    improved_code = str(structured.get("improved_code") or "").strip()
    test_cases = str(structured.get("test_cases") or "").strip()
    improved_code, test_cases = _split_code_and_tests(improved_code, test_cases)
    plan_steps = _normalize_plan_steps(structured.get("plan_steps") or plan)

    return {
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
    }


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

        plan = await provider.chat(
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Conversation context:\n{context_blob}\n\n"
                        f"User request:\n{user_message}"
                    ),
                },
            ],
            model=model,
        )

        draft = await provider.chat(
            messages=[
                {"role": "system", "content": EXECUTOR_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{user_message}\n\n"
                        f"Execution plan:\n{plan}\n\n"
                        "Produce the best possible draft answer now."
                    ),
                },
            ],
            model=model,
        )

        reviewed_output = await provider.chat(
            messages=[
                {"role": "system", "content": REVIEWER_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Original request:\n{user_message}\n\n"
                        f"Plan:\n{plan}\n\n"
                        f"Draft answer:\n{draft}"
                    ),
                },
            ],
            model=model,
        )

        structured = _extract_json(reviewed_output)
        final_answer = str(structured.get("final_answer") or reviewed_output).strip()

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
