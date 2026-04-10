from langgraph.graph import StateGraph, END
from app.agents.state.state import AgentState
from app.agents.nodes.router import router_node
from app.agents.nodes.chat import chat_node
from app.agents.nodes.rag import rag_node
from app.agents.nodes.multi_agent import multi_agent_node


def route_decision(state: AgentState) -> str:
    """Edge function — reads next_node from state to decide routing"""
    return state.get("next_node", "basic_chat")


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # ── Add Nodes ─────────────────────────────────
    graph.add_node("router",     router_node)
    graph.add_node("basic_chat", chat_node)
    graph.add_node("document_qa", rag_node)
    graph.add_node("multi_agent", multi_agent_node)

    # ── Entry Point ───────────────────────────────
    graph.set_entry_point("router")

    # ── Conditional Edges from Router ─────────────
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "basic_chat":  "basic_chat",
            "document_qa": "document_qa",
            "multi_agent": "multi_agent",
        }
    )

    # ── All nodes end after responding ────────────
    graph.add_edge("basic_chat",  END)
    graph.add_edge("document_qa", END)
    graph.add_edge("multi_agent", END)

    return graph.compile()


# ── Singleton compiled graph ───────────────────────
agent_graph = build_graph()