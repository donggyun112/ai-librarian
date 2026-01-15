"""LLM client abstraction for generation layer.

Provides unified interface for LLM providers, starting with Gemini.
Uses the same google-generativeai library as embedding/provider.py.
"""

import os
import time
from typing import Optional, Protocol

import google.generativeai as genai
from loguru import logger

from .dto import LLMResponse

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds (exponential backoff)


class LLMClientProtocol(Protocol):
    """Protocol for LLM clients (dependency inversion)."""

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
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
    ):
        """Initialize Gemini LLM client.

        Args:
            model: Gemini model to use (default: gemini-2.0-flash)
            api_key: Google API key (falls back to GOOGLE_API_KEY env var)
        """
        key = api_key or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is required for Gemini LLM")

        genai.configure(api_key=key)
        self._genai = genai
        self._model = genai.GenerativeModel(model)
        self._model_name = model
        self._current_system_prompt: Optional[str] = None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Generate response using Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Generation temperature (0-1)
            max_tokens: Maximum output tokens

        Returns:
            LLMResponse with generated content
        """
        # Update model if system_prompt changed (Gemini's system_instruction)
        if system_prompt != self._current_system_prompt:
            self._model = self._genai.GenerativeModel(
                self._model_name,
                system_instruction=system_prompt,
            )
            self._current_system_prompt = system_prompt

        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                # Handle blocked or empty responses
                if not response.candidates:
                    return LLMResponse(
                        content="I couldn't generate a response. Please try rephrasing your question.",
                        model=self._model_name,
                    )

                # Extract text from response
                text = response.text if hasattr(response, "text") else ""

                # Extract token usage if available
                usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    usage = {
                        "prompt_tokens": getattr(
                            response.usage_metadata, "prompt_token_count", 0
                        ),
                        "completion_tokens": getattr(
                            response.usage_metadata, "candidates_token_count", 0
                        ),
                        "total_tokens": getattr(
                            response.usage_metadata, "total_token_count", 0
                        ),
                    }

                return LLMResponse(
                    content=text.strip(),
                    model=self._model_name,
                    usage=usage,
                )

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1 and self._should_retry(e):
                    logger.warning(f"LLM retry {attempt + 1}/{MAX_RETRIES}: {e}")
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                break

        logger.error(f"LLM generation failed: {last_error}")
        return LLMResponse(
            content=f"Generation error: {str(last_error)}",
            model=self._model_name,
        )

    def _should_retry(self, error: Exception) -> bool:
        """Determine if the error is retryable.

        Args:
            error: The exception that occurred

        Returns:
            True if the request should be retried
        """
        error_str = str(error).lower()
        # Retry on rate limits, server errors, and transient issues
        retryable_patterns = [
            "429",  # Rate limit
            "500",  # Internal server error
            "503",  # Service unavailable
            "rate limit",
            "quota",
            "temporarily unavailable",
            "resource exhausted",
        ]
        return any(pattern in error_str for pattern in retryable_patterns)

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name


__all__ = ["LLMClientProtocol", "GeminiLLMClient", "LLMResponse"]
