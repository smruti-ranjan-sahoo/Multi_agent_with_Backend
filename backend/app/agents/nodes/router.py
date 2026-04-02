from app.agents.state.state import AgentState
from app.services.llm.factory import get_llm_provider
from app.core.config import settings


ROUTER_PROMPT = """You are a routing assistant. Based on the user's message, decide which agent should handle it.

Available agents:
- basic_chat     → general conversation, questions, coding help, anything NOT document related
- document_qa    → when user asks about uploaded documents, files, PDFs, CSVs
- multi_agent    → complex tasks needing research, web search, multi-step reasoning

Reply with ONLY one of these exact words: basic_chat, document_qa, multi_agent
No explanation. Just the agent name."""


async def router_node(state: AgentState) -> AgentState:
    """
    Decides which node handles the user message.
    If usecase is already set → respect it.
    If has_documents → lean toward document_qa.
    Otherwise → ask LLM to decide.
    """

    # if usecase explicitly set by user → use it directly
    if state.get("usecase") and state["usecase"] != "auto":
        next_node = state["usecase"]
        return {**state, "next_node": next_node}

    # if conversation has documents → default to document_qa
    if state.get("has_documents"):
        return {**state, "next_node": "document_qa"}

    # ask LLM to decide based on last user message
    last_message = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            last_message = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_message = msg["content"]
            break

    try:
        provider = get_llm_provider(state.get("provider", settings.DEFAULT_LLM_PROVIDER))
        model    = state.get("model", settings.DEFAULT_GROQ_MODEL)

        decision = await provider.chat(
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user",   "content": last_message}
            ],
            model=model
        )

        decision = decision.strip().lower()
        if decision not in ["basic_chat", "document_qa", "multi_agent"]:
            decision = "basic_chat"

    except Exception:
        decision = "basic_chat"   # fallback on error

    return {**state, "next_node": decision}