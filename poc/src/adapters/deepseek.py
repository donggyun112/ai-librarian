"""DeepSeek LLM Adapter (OpenRouter + Thinking Mode)"""
from typing import Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai.chat_models.base import (
    _convert_message_to_dict,
    _convert_from_v1_to_chat_completions,
)

from .base import BaseLLMAdapter, NormalizedChunk, ToolChoiceType
from config import config


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ChatOpenAIWithThinking(ChatOpenAI):
    """OpenRouter DeepSeek Thinking Mode 지원

    - 스트리밍 시 reasoning 필드를 additional_kwargs에 포함
    - 메시지 변환 시 reasoning_content 보존
    """

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """OpenRouter reasoning 필드를 additional_kwargs에 추가"""
        # 부모 클래스의 변환 로직 호출
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )

        if generation_chunk is None:
            return None

        # OpenRouter reasoning 필드 추출
        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            reasoning = delta.get("reasoning")
            if reasoning:
                # additional_kwargs에 reasoning_content로 추가
                generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning

        return generation_chunk

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        """메시지 변환 시 reasoning_content 추가"""
        messages = self._convert_input(input_).to_messages()
        if stop is not None:
            kwargs["stop"] = stop

        payload = {**self._default_params, **kwargs}

        # 메시지 변환 (reasoning_content 포함)
        payload["messages"] = []
        for m in messages:
            if isinstance(m, AIMessage):
                msg_dict = _convert_message_to_dict(
                    _convert_from_v1_to_chat_completions(m)
                )
            else:
                msg_dict = _convert_message_to_dict(m)

            # AIMessage인 경우 reasoning_content 추가
            if isinstance(m, AIMessage):
                reasoning = m.additional_kwargs.get("reasoning_content")
                if reasoning:
                    msg_dict["reasoning_content"] = reasoning

            payload["messages"].append(msg_dict)

        return payload


class DeepSeekAdapter(BaseLLMAdapter):
    """DeepSeek LLM Adapter (OpenRouter)

    Thinking Mode + Tool Calling 동시 지원:
    - OpenRouter API 사용 (https://openrouter.ai/api/v1)
    - deepseek/deepseek-chat 모델 사용
    - extra_body={"thinking": {"type": "enabled"}}로 thinking 활성화
    - ChatOpenAIWithThinking으로 reasoning_content 자동 전달
    """

    def __init__(self, enable_thinking: bool = True):
        """
        Args:
            enable_thinking: True면 thinking mode 활성화
        """
        self.enable_thinking = enable_thinking

    def create_llm(
        self,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        extra_body = None

        # OpenRouter reasoning mode 활성화
        if self.enable_thinking:
            extra_body = {"reasoning": {"enabled": True}, "include_reasoning": True}

        return ChatOpenAIWithThinking(
            model=model or config.OPENROUTER_MODEL,
            api_key=config.OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            extra_body=extra_body,
        )

    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """DeepSeek 청크 정규화

        Thinking Mode:
        - chunk.additional_kwargs.reasoning_content에 사고 과정
        - chunk.content에 최종 답변
        """
        content = chunk.content if chunk else ""
        thinking = None

        # reasoning_content 추출 (thinking mode)
        if hasattr(chunk, 'additional_kwargs'):
            reasoning = chunk.additional_kwargs.get('reasoning_content')
            if reasoning:
                thinking = reasoning

        if isinstance(content, str):
            return NormalizedChunk(text=content, thinking=thinking)

        return NormalizedChunk(
            text=str(content) if content else "",
            thinking=thinking
        )

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def bind_tools(
        self,
        llm: BaseChatModel,
        tools: List[Any],
        tool_choice: Optional[ToolChoiceType] = None
    ) -> BaseChatModel:
        """DeepSeek tool binding (OpenAI 호환)"""
        if tool_choice:
            return llm.bind_tools(tools, tool_choice=tool_choice)
        return llm.bind_tools(tools)
