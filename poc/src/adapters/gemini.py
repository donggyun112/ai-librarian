"""Gemini LLM Adapter"""
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel

from .base import BaseLLMAdapter, NormalizedChunk
from config import config


class GeminiAdapter(BaseLLMAdapter):
    """Google Gemini LLM Adapter

    특징:
    - chunk.content가 list[dict] 형식: [{"type": "text", "text": "..."}]
    - httpx 클라이언트가 첫 번째 이벤트 루프에 바인딩됨
    - Streamlit 환경에서 매 요청마다 새 인스턴스 필요
    """

    def create_llm(
        self,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        return ChatGoogleGenerativeAI(
            model=model or config.GEMINI_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """Gemini 청크 정규화

        Gemini 형식: chunk.content = [{"type": "text", "text": "..."}] (list)
        """
        content = chunk.content if chunk else ""

        if isinstance(content, str):
            return NormalizedChunk(text=content)

        if isinstance(content, list):
            # Gemini 형식: [{"type": "text", "text": "..."}]
            texts = []
            for item in content:
                if isinstance(item, dict):
                    texts.append(item.get("text", ""))
            return NormalizedChunk(text="".join(texts))

        # 예상치 못한 형식 처리
        return NormalizedChunk(text=str(content) if content else "")

    @property
    def provider_name(self) -> str:
        return "gemini"
