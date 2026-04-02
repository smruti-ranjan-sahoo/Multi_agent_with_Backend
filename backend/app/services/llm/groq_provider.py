from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.services.llm.base import BaseLLMProvider
from app.core.config import settings
from typing import AsyncGenerator


GROQ_MODELS = [
    "llama3-70b-8192",
    "llama3-8b-8192",
    "llama-3.1-70b-versatile",
    "qwen/qwen3-70b-8192",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "llama-3.2-11b-vision-preview",      # vision model
    "llama-4-scout-17b-16e-instruct",    # vision model
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "gemma-7b-it",
]


class GroqProvider(BaseLLMProvider):

    def _build_messages(self, messages: list[dict]):
        result = []
        for m in messages:
            if m["role"] == "system":
                result.append(SystemMessage(content=m["content"]))
            elif m["role"] == "user":
                result.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                result.append(AIMessage(content=m["content"]))
        return result

    async def chat(
        self,
        messages: list[dict],
        model: str = "llama3-70b-8192",
        **kwargs
    ) -> str:
        llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=model)
        response = await llm.ainvoke(self._build_messages(messages))
        return response.content

    async def stream_chat(
        self,
        messages: list[dict],
        model: str = "llama3-70b-8192",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        llm = ChatGroq(
            api_key=settings.GROQ_API_KwhEY,
            model=model,
            streaming=True
        )
        async for chunk in llm.astream(self._build_messages(messages)):
            if chunk.content:
                yield chunk.content

    def get_available_models(self) -> list[str]:
        return GROQ_MODELS