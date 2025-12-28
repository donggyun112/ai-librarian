"""Gemini LLM Adapter"""
from typing import Any, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel

from .base import BaseLLMAdapter, NormalizedChunk, ToolChoiceType
from config import config


# Native Thinking 설정
DEFAULT_THINKING_BUDGET = 2000  # 기본 thinking 토큰 예산


class GeminiAdapter(BaseLLMAdapter):
    """Google Gemini LLM Adapter

    특징:
    - chunk.content가 list[dict] 형식: [{"type": "text", "text": "..."}]
    - Native Thinking 지원 (Gemini 2.5+)
    - httpx 클라이언트가 첫 번째 이벤트 루프에 바인딩됨
    - Streamlit 환경에서 매 요청마다 새 인스턴스 필요
    """

    def __init__(self, thinking_budget: int = DEFAULT_THINKING_BUDGET):
        """
        Args:
            thinking_budget: Native Thinking 토큰 예산 (0이면 비활성화)
        """
        self.thinking_budget = thinking_budget

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
            thinking_budget=self.thinking_budget,  # Native Thinking 활성화
            include_thoughts=True,  # Thinking 내용 응답에 포함
        )

    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """Gemini 청크 정규화

        Gemini 형식:
        - 일반: chunk.content = [{"type": "text", "text": "..."}]
        - Thinking: chunk.content = [{"type": "thinking", "thinking": "..."}]
        """
        content = chunk.content if chunk else ""

        if isinstance(content, str):
            return NormalizedChunk(text=content)

        if isinstance(content, list):
            texts = []
            thinking_texts = []

            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type", "text")
                    if item_type == "thinking":
                        # Native Thinking 콘텐츠
                        thinking_texts.append(item.get("thinking", ""))
                    else:
                        # 일반 텍스트
                        texts.append(item.get("text", ""))

            return NormalizedChunk(
                text="".join(texts),
                thinking="".join(thinking_texts) if thinking_texts else None
            )

        # 예상치 못한 형식 처리
        return NormalizedChunk(text=str(content) if content else "")

    @property
    def provider_name(self) -> str:
        return "gemini"

    def bind_tools(
        self,
        llm: BaseChatModel,
        tools: List[Any],
        tool_choice: Optional[ToolChoiceType] = None
    ) -> BaseChatModel:
        """Gemini tool_choice 지원

        Gemini는 tool_choice 형식이 다름:
        - "auto" → None (기본)
        - "required" → "any"
        - "none" → "none"
        - 특정 도구 → {"function_calling_config": {"mode": "any", "allowed_function_names": ["tool_name"]}}

        Note: gemini-2.5-flash에서는 function_calling_config가 정상 작동함.
        (gemini-3-flash-preview에서는 블로킹 이슈가 있었음)
        """
        if tool_choice is None or tool_choice == "auto":
            return llm.bind_tools(tools)

        if tool_choice == "required":
            return llm.bind_tools(tools, tool_choice="any")

        if tool_choice == "none":
            return llm.bind_tools(tools, tool_choice="none")

        # 특정 도구 강제: {"type": "function", "function": {"name": "think"}}
        if isinstance(tool_choice, dict):
            tool_name = tool_choice.get("function", {}).get("name")
            if tool_name:
                return llm.bind_tools(
                    tools,
                    tool_choice={
                        "function_calling_config": {
                            "mode": "any",
                            "allowed_function_names": [tool_name]
                        }
                    }
                )

        return llm.bind_tools(tools)
