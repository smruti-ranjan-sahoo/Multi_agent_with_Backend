from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Central state passed between all LangGraph nodes.
    add_messages = appends new messages instead of overwriting
    """

    # ── Core ──────────────────────────────────────
    messages        : Annotated[list, add_messages]  # full chat history
    user_id         : str                            # who is chatting
    conversation_id : str                            # which conversation

    # ── LLM Config ────────────────────────────────
    provider        : str                            # groq | openai | anthropic | gemini
    model           : str                            # llama-3.3-70b-versatile etc

    # ── Routing ───────────────────────────────────
    usecase         : str                            # basic_chat | document_qa | multi_agent
    next_node       : Optional[str]                  # which node to call next

    # ── RAG ───────────────────────────────────────
    namespace       : Optional[str]                  # Pinecone namespace
    retrieved_docs  : Optional[list]                 # retrieved chunks
    has_documents   : Optional[bool]                 # does conversation have docs?

    # ── Response ──────────────────────────────────
    final_response  : Optional[str]                  # final answer to return
    error           : Optional[str]                  # error message if any