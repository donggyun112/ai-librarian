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


class GeminiLLMClient:
    """Gemini LLM client using google-generativeai.

    Uses the same library pattern as GeminiEmbeddings (embedding/provider.py).

    Example:
        >>> client = GeminiLLMClient()
        >>> response = client.generate("Explain Python decorators")
        >>> print(response.content)
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
    ) -> None:
        """Initialize Gemini LLM client.

        Args:
            model: Gemini model to use (default: gemini-2.0-flash)
            api_key: Obsolete (handled by adapter/config). Kept for compatibility.
        """
        # Get Gemini adapter from centralized registry
        self.adapter = get_adapter("gemini")
        self._model_name = model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Generate response using Gemini Adapter.

        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Generation temperature (0-1)
            max_tokens: Maximum output tokens

        Returns:
            LLMResponse with generated content
        """
        try:
            # Create LLM instance via adapter
            llm = self.adapter.create_llm(
                model=self._model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Build messages

            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            # Invoke LLM
            response = llm.invoke(messages)

            # Parse usage if available (LangChain standard metadata)
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
            logger.exception(f"LLM generation failed via adapter: {e}")
            return LLMResponse(
                content="응답을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
                model=self._model_name,
            )

    def _should_retry(self, error: Exception) -> bool:
        # Retry logic is now handled by Adapter/LangChain built-ins if configured,
        # but for this client wrapper we rely on simple exception handling.
        # LangChain's ChatGoogleGenerativeAI has internal retries by default.
        return False

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name


__all__ = ["LLMClientProtocol", "GeminiLLMClient", "LLMResponse"]
