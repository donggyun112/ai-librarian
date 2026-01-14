"""Generation pipeline for RAG responses.

Orchestrates LLM generation from retrieved context with source attribution.
"""

from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.rag.retrieval import ExpandedResult

from .client import LLMClientProtocol
from .models import Conversation, GeneratedResponse, OptimizedQuery
from .prompts import PromptTemplate


class GenerationPipeline:
    """Orchestrates LLM generation from retrieved context.

    Pipeline stages:
    1. Context assembly (from ExpandedResult)
    2. Prompt construction
    3. LLM generation
    4. Response formatting with source attribution

    Example:
        >>> pipeline = GenerationPipeline(llm_client)
        >>> response = pipeline.generate(query, search_results)
        >>> print(response.answer)
        >>> print(response.format_with_sources())
    """

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        """Initialize GenerationPipeline.

        Args:
            llm_client: LLM client for generation
            temperature: Generation temperature (0-1)
            max_tokens: Maximum output tokens
        """
        self.llm_client = llm_client
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(
        self,
        query: str,
        results: List[ExpandedResult],
        *,
        conversation: Optional[Conversation] = None,
        optimized_query: Optional[OptimizedQuery] = None,
    ) -> GeneratedResponse:
        """Generate response from retrieved results.

        Args:
            query: User query
            results: Expanded search results with context
            conversation: Optional conversation history
            optimized_query: Optional query optimization result

        Returns:
            Generated response with source attribution
        """
        # Handle empty results
        if not results:
            return GeneratedResponse(
                query=query,
                answer=self._get_no_results_message(query),
                sources=[],
                model=getattr(self.llm_client, "model_name", "unknown"),
                optimized_query=optimized_query,
            )

        # Stage 1: Context assembly
        context = PromptTemplate.build_context(results)

        # Stage 2: Prompt construction
        prompt = PromptTemplate.format_rag_prompt(query, context)

        # Add conversation history if available (structured format)
        if conversation and conversation.turns:
            history = conversation.get_history_context()
            prompt = (
                f"=== Previous Conversation ===\n{history}\n\n"
                f"=== Current Question ===\n{prompt}"
            )

        # Stage 3: LLM generation
        llm_response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=PromptTemplate.SYSTEM_PROMPT,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # Stage 4: Response formatting
        return GeneratedResponse(
            query=query,
            answer=llm_response.content,
            sources=results,
            model=llm_response.model,
            optimized_query=optimized_query,
        )

    def _get_no_results_message(self, query: str) -> str:
        """Get message for when no results are found.

        Args:
            query: User query

        Returns:
            Appropriate "no results" message
        """
        # Detect language (Korean vs English)
        has_korean = any("\uac00" <= c <= "\ud7a3" for c in query)

        if has_korean:
            return (
                "죄송합니다. 질문에 관련된 정보를 찾을 수 없습니다. "
                "다른 키워드로 검색하거나 질문을 다시 작성해 주세요."
            )
        return (
            "I couldn't find relevant information to answer your question. "
            "Please try different keywords or rephrase your question."
        )


__all__ = ["GenerationPipeline"]
