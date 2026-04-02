from langchain_core.messages import HumanMessage
from app.agents.graph.graph import agent_graph
from app.agents.state.state import AgentState
from app.core.config import settings


class AgentService:

    async def run(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str,
        provider: str = None,
        model: str = None,
        usecase: str = "auto",
        has_documents: bool = False,
        namespace: str = None,
    ) -> dict:
        """
        Main entry point — builds initial state and runs LangGraph
        """

        provider = provider or settings.DEFAULT_LLM_PROVIDER
        model    = model    or settings.DEFAULT_GROQ_MODEL
        namespace = namespace or f"conv_{conversation_id}"

        # ── Build Initial State ────────────────────
        initial_state: AgentState = {
            "messages":        [HumanMessage(content=user_message)],
            "user_id":         user_id,
            "conversation_id": conversation_id,
            "provider":        provider,
            "model":           model,
            "usecase":         usecase,
            "next_node":       None,
            "namespace":       namespace,
            "retrieved_docs":  None,
            "has_documents":   has_documents,
            "final_response":  None,
            "error":           None,
        }

        # ── Run Graph ─────────────────────────────
        result = await agent_graph.ainvoke(initial_state)

        return {
            "response":        result.get("final_response", "No response generated"),
            "conversation_id": conversation_id,
            "provider":        provider,
            "model":           model,
            "usecase":         result.get("next_node", usecase),
            "error":           result.get("error")
        }


# ── Singleton ──────────────────────────────────────
agent_service = AgentService()