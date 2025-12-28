"""OpenAI LLM Adapter"""
from typing import Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from .base import BaseLLMAdapter, NormalizedChunk, ToolChoiceType
from config import config


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI LLM Adapter

    특징:
    - chunk.content가 str 형식
    - 인스턴스 재사용 가능 (캐싱 OK)
    - 이벤트 루프 문제 없음
    """

    def create_llm(
        self,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        return ChatOpenAI(
            model=model or config.OPENAI_MODEL,
            temperature=temperature,
            api_key=config.OPENAI_API_KEY,
            max_tokens=max_tokens,
            streaming=True
        )

    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """OpenAI 청크 정규화

        OpenAI 형식: chunk.content = "텍스트" (str)
        """
        content = chunk.content if chunk else ""

        if isinstance(content, str):
            return NormalizedChunk(text=content)

        # 예상치 못한 형식 처리
        return NormalizedChunk(text=str(content) if content else "")

    @property
    def provider_name(self) -> str:
        return "openai"

    def bind_tools(
        self,
        llm: BaseChatModel,
        tools: List[Any],
        tool_choice: Optional[ToolChoiceType] = None
    ) -> BaseChatModel:
        """OpenAI는 tool_choice를 그대로 지원"""
        if tool_choice:
            return llm.bind_tools(tools, tool_choice=tool_choice)
        return llm.bind_tools(tools)
