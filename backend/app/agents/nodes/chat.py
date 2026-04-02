from app.agents.state.state import AgentState
from app.services.llm.factory import get_llm_provider
from app.services.redis.redis_services import redis_service
from app.core.config import settings
from langchain_core.messages import AIMessage


SYSTEM_PROMPT = """You are a helpful, intelligent AI assistant. 
You can help with coding, analysis, writing, math, and general questions.
Be concise, accurate, and friendly."""


async def chat_node(state: AgentState) -> AgentState:
    """
    Basic chat node — handles general conversation.
    Pulls history from Redis, calls LLM, saves response back.
    """

    try:
        provider = get_llm_provider(state.get("provider", settings.DEFAULT_LLM_PROVIDER))
        model    = state.get("model", settings.DEFAULT_GROQ_MODEL)

        # Step 1 — get conversation history from Redis
        history = await redis_service.get_history(state["conversation_id"])

        # Step 2 — build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-10:])   # last 5 turns

        # Step 3 — add current user message
        for msg in state["messages"]:
            if hasattr(msg, "type") and msg.type == "human":
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, dict) and msg.get("role") == "user":
                messages.append(msg)

        # Step 4 — call LLM
        response = await provider.chat(messages, model)

        # Step 5 — save to Redis history
        await redis_service.append_message(
            state["conversation_id"],
            {"role": "assistant", "content": response}
        )

        return {
            **state,
            "final_response": response,
            "messages": state["messages"] + [AIMessage(content=response)],
            "error": None
        }

    except Exception as e:
        error_msg = f"Chat error: {str(e)}"
        return {
            **state,
            "final_response": error_msg,
            "error": error_msg
        }