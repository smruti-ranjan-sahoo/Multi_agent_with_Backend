import os
import tempfile
from app.services.rag.document_loader import load_and_chunk
from app.services.rag.pinecone_store import create_vector_store, similarity_search, delete_namespace
from app.services.rag.embeddings import get_default_embedding_model
from app.services.llm.factory import get_llm_provider
from app.core.config import settings


class RAGService:

    # ── Upload & Index Document ────────────────────
    async def index_document(self, file_bytes: bytes, filename: str, namespace: str) -> dict:
        """Save file temporarily → chunk → embed → store in Pinecone"""

        # save to temp file
        suffix = "." + filename.split(".")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            chunks = load_and_chunk(tmp_path)
            create_vector_store(chunks, namespace=namespace)
            return {
                "status": "indexed",
                "filename": filename,
                "chunks": len(chunks),
                "namespace": namespace
            }
        finally:
            os.unlink(tmp_path)   # always delete temp file

    # ── RAG Query ─────────────────────────────────
    async def query(
        self,
        question: str,
        namespace: str,
        provider: str = None,
        model: str = None,
        chat_history: list[dict] = None
    ) -> str:
        """Search Pinecone → build prompt → get LLM answer"""

        provider = provider or settings.DEFAULT_LLM_PROVIDER
        model    = model    or settings.DEFAULT_GROQ_MODEL

        # Step 1 — retrieve relevant chunks
        docs = similarity_search(question, namespace=namespace, k=4)

        if not docs:
            context = "No relevant documents found."
        else:
            context = "\n\n".join([doc.page_content for doc in docs])

        # Step 2 — build messages
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer the user's question "
                    "using ONLY the provided context. If the answer is not in "
                    "the context, say 'I don't have enough information to answer that.'\n\n"
                    f"Context:\n{context}"
                )
            }
        ]

        # Step 3 — add chat history if provided
        if chat_history:
            messages.extend(chat_history[-6:])   # last 3 turns (6 messages)

        # Step 4 — add current question
        messages.append({"role": "user", "content": question})

        # Step 5 — get LLM response
        llm = get_llm_provider(provider)
        return await llm.chat(messages, model)

    # ── Delete Document Namespace ──────────────────
    async def delete_document(self, namespace: str):
        """Remove all vectors for a namespace"""
        delete_namespace(namespace)
        return {"status": "deleted", "namespace": namespace}


# ── Singleton ──────────────────────────────────────
rag_service = RAGService()