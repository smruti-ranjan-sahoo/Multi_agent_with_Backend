from langchain_community.embeddings import JinaEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings
from dotenv import load_dotenv
load_dotenv()  # force reload .env
import os
print("ENV KEY:", os.getenv("PINECONE_API_KEY", "NOT FOUND"))


def get_pinecone_client() -> Pinecone:
    return Pinecone(api_key=settings.PINECONE_API_KEY)


def ensure_index_exists():
    """Create Pinecone index if it doesn't exist"""
    pc = get_pinecone_client()
    if settings.PINECONE_INDEX_NAME not in pc.list_indexes().names():
        pc.create_index(
            name=settings.PINECONE_INDEX_NAME,
            dimension=settings.EMBEDDING_DIMENSION,   # 1024 for jina-v3
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region=settings.PINECONE_ENVIRONMENT  # us-east-1
            )
        )


def get_embeddings():
    return JinaEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        jina_api_key=settings.JINA_API_KEY
    )


def create_vector_store(chunks, namespace: str) -> PineconeVectorStore:
    """Embed and store document chunks in Pinecone"""
    ensure_index_exists()

    vector_store = PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        index_name=settings.PINECONE_INDEX_NAME,
        namespace=namespace        # isolate per user/conversation
    )
    return vector_store


def get_vector_store(namespace: str) -> PineconeVectorStore:
    """Get existing vector store for similarity search"""
    ensure_index_exists()

    return PineconeVectorStore(
        index_name=settings.PINECONE_INDEX_NAME,
        embedding=get_embeddings(),
        namespace=namespace
    )


def similarity_search(query: str, namespace: str, k: int = 4) -> list:
    """Search for similar documents"""
    store = get_vector_store(namespace)
    return store.similarity_search(query, k=k)


def delete_namespace(namespace: str):
    """Delete all vectors for a conversation/user"""
    pc = get_pinecone_client()
    index = pc.Index(settings.PINECONE_INDEX_NAME)
    index.delete(delete_all=True, namespace=namespace)