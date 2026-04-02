from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):

    # ── App ───────────────────────────────────────
    APP_NAME: str = "Multi-Agent-Chatbot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── JWT ───────────────────────────────────────
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ── Database ──────────────────────────────────
    DATABASE_URL: str

    # ── Redis ─────────────────────────────────────
    REDIS_URL: str

    # ── LLM Providers ─────────────────────────────
    DEFAULT_LLM_PROVIDER: str = "groq"

    # Groq Models
    GROQ_API_KEY: str = ""
    DEFAULT_GROQ_MODEL: str = "llama3-70b-8192"

    # All Available Groq Models (no key needed, just model names)
    GROQ_MODELS: list = [
    "llama-3.3-70b-versatile",        # replaces llama3-70b-8192
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "qwen-qwen3-70b",
    "llama-3.2-11b-vision-preview",   # vision model
    "llama-4-scout-17b-16e-instruct", # vision model
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "gemma-7b-it",
]

    # OpenAI Models
    OPENAI_API_KEY: str = ""
    DEFAULT_OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MODELS: list = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]

    # Anthropic Models
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"
    ANTHROPIC_MODELS: list = [
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ]

    # Gemini Models
    GEMINI_API_KEY: str = ""
    DEFAULT_GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_MODELS: list = [
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.0-pro",
    ]
        # ── All Providers List ─────────────────────────
    LLM_PROVIDERS: list = ["groq", "openai", "anthropic", "gemini"]

    # ── Usecases ──────────────────────────────────
    USECASES: list = [
        "Basic Chatbot",
        "Document QA",
        "Multi-Agent Chatbot",
    ]

    # ── Pinecone ──────────────────────────────────
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "chatbot"
    PINECONE_ENVIRONMENT: str = "us-east-1-aws"
    # ── Embeddings ────────────────────────────────────
    JINA_API_KEY: str = ""
    EMBEDDING_PROVIDER: str = "jina"
    EMBEDDING_MODEL: str = "jina-embeddings-v2-base-en"   # ← match your old working model
    EMBEDDING_DIMENSION: int = 768                         # ← jina-v2 = 768 dims

    # ── Cloudinary ────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # ── LangSmith ─────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "multi-agent-chatbot"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
def get_models_for_provider(provider: str) -> list:
    """Returns model list for given provider"""
    model_map = {
        "groq":      settings.GROQ_MODELS,
        "openai":    settings.OPENAI_MODELS,
        "anthropic": settings.ANTHROPIC_MODELS,
        "gemini":    settings.GEMINI_MODELS,
    }
    return model_map.get(provider, settings.GROQ_MODELS)


def get_default_model(provider: str) -> str:
    """Returns default model for given provider"""
    default_map = {
        "groq":      settings.DEFAULT_GROQ_MODEL,
        "openai":    settings.DEFAULT_OPENAI_MODEL,
        "anthropic": settings.DEFAULT_ANTHROPIC_MODEL,
        "gemini":    settings.DEFAULT_GEMINI_MODEL,
    }
    return default_map.get(provider, settings.DEFAULT_GROQ_MODEL)
# TEMP DEBUG — remove after testing
print(">>> PINECONE_API_KEY loaded:", repr(settings.PINECONE_API_KEY[:10] if settings.PINECONE_API_KEY else "EMPTY"))