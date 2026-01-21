"""LLM client abstraction for generation layer.

Provides unified interface for LLM providers, starting with Gemini.
Uses the same google-generativeai library as embedding/provider.py.
"""

from typing import Optional, Protocol

from loguru import logger

from .dto import LLMResponse
from src.adapters import get_adapter
from langchain_core.messages import HumanMessage, SystemMessage

class LLMClientProtocol(Protocol):
    """Protocol for LLM clients (dependency inversion)."""

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Generate response from prompt."""
        ...


class AdapterLLMClient:
    """LLM client that uses configured provider (OpenAI or Gemini).

    Uses the centralized adapter registry based on explicit provider configuration.

    Example:
        >>> client = AdapterLLMClient(provider="gemini", model="gemini-2.0-flash")
        >>> response = client.generate("Explain Python decorators")
        >>> print(response.content)
    """

    def __init__(
        self,
        provider: str = "gemini",
        model: Optional[str] = None,
    ) -> None:
        """Initialize LLM client with specified provider.

        Args:
            provider: LLM provider ("openai" | "gemini")
            model: Model name (if None, uses default for provider)
        """
        self.adapter = get_adapter(provider)
        
        # Set default model based on provider
        if model is None:
            if provider == "openai":
                model = "gpt-4o"
            else:
                model = "gemini-2.0-flash"
        
        self._model_name = model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Generate response using auto-detected provider.

        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Generation temperature (0-1)
            max_tokens: Maximum output tokens

        Returns:
            LLMResponse with generated content
        """
        try:
            llm = self.adapter.create_llm(
                model=self._model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = llm.invoke(messages)

            usage = None
            if hasattr(response, "response_metadata"):
                token_usage = response.response_metadata.get("token_usage", {})
                if token_usage:
                    usage = {
                        "prompt_tokens": token_usage.get("prompt_tokens", 0),
                        "completion_tokens": token_usage.get("candidates_tokens", 0) or token_usage.get("completion_tokens", 0),
                        "total_tokens": token_usage.get("total_tokens", 0),
                    }

            return LLMResponse(
                content=str(response.content).strip(),
                model=self._model_name,
                usage=usage,
            )

        except Exception as e:
            logger.exception(f"LLM generation failed: {e}")
            return LLMResponse(
                content="응답을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
                model=self._model_name,
            )

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name


__all__ = ["LLMClientProtocol", "AdapterLLMClient", "LLMResponse"]
