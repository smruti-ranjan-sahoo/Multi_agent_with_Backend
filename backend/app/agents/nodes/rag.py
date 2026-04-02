from app.agents.state.state import AgentState
from app.services.rag.rag_services import rag_service
from app.services.redis.redis_services import redis_service
from app.core.config import settings
from langchain_core.messages import AIMessage


async def rag_node(state: AgentState) -> AgentState:
    """
    Document QA node — searches Pinecone and answers from document context.
    """

    try:
        # Step 1 — get namespace
        namespace = state.get("namespace") or f"conv_{state['conversation_id']}"

        # Step 2 — extract user question
        question = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, "type") and msg.type == "human":
                question = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                question = msg["content"]
                break

        if not question:
            return {
                **state,
                "final_response": "No question found.",
                "error": "No user message in state"
            }

        # Step 3 — get chat history from Redis
        history = await redis_service.get_history(state["conversation_id"])

        # Step 4 — run RAG pipeline
        answer = await rag_service.query(
            question=question,
            namespace=namespace,
            provider=state.get("provider", settings.DEFAULT_LLM_PROVIDER),
            model=state.get("model", settings.DEFAULT_GROQ_MODEL),
            chat_history=history[-6:]   # last 3 turns
        )

        # Step 5 — save to Redis
        await redis_service.append_message(
            state["conversation_id"],
            {"role": "user",      "content": question}
        )
        await redis_service.append_message(
            state["conversation_id"],
            {"role": "assistant", "content": answer}
        )

        return {
            **state,
            "final_response": answer,
            "messages": state["messages"] + [AIMessage(content=answer)],
            "error": None
        }

    except Exception as e:
        error_msg = f"RAG error: {str(e)}"
        return {
            **state,
            "final_response": error_msg,
            "error": error_msg
        }