"""Search use case orchestration.

Orchestrates the retrieval pipeline for search operations.
"""

from typing import Any, List, Optional, Protocol

from src.rag.retrieval import RetrievalPipeline
from src.rag.retrieval.dto import ExpandedResult
from src.rag.shared.config import EmbeddingConfig


class EmbeddingClientProtocol(Protocol):
    """Protocol for embedding client (dependency inversion)."""

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query string."""
        ...


class SearchUseCase:
    """Orchestrates the search pipeline.

    Pipeline:
    1. Validate query (validators.py)
    2. Retrieve with SelfQueryRetriever (auto-extracts filters)
    3. Expand context (retrieval layer)
    4. Format results (formatters.py)

    Example:
        >>> use_case = SearchUseCase(embeddings_client, config)
        >>> results = use_case.execute("python list comprehension", view="code", top_k=5)
    """

    def __init__(
        self,
        embeddings_client: EmbeddingClientProtocol,
        config: EmbeddingConfig,
        llm_client: Optional[Any] = None,  # Deprecated, kept for backwards compatibility
    ) -> None:
        # SelfQueryRetriever is enabled by default (creates its own LLM)
        self.pipeline = RetrievalPipeline(
            embeddings_client,
            config,
            use_self_query=True,
        )

    def execute(
        self,
        query: str,
        view: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 10,
        expand_context: bool = True,
        optimize_query: bool = True,  # Deprecated, ignored (SelfQueryRetriever handles this)
    ) -> List[ExpandedResult]:
        """Execute search pipeline.

        Args:
            query: Search query string
            view: Optional view filter (text, code, image, etc.)
            language: Optional language filter (python, javascript, etc.)
            top_k: Number of results to retrieve
            expand_context: Whether to fetch parent context
            optimize_query: Deprecated, ignored (SelfQueryRetriever auto-extracts)

        Returns:
            List of search results with optional context
        """
        # Delegate to retrieval pipeline (SelfQueryRetriever handles query optimization)
        return self.pipeline.retrieve(
            query=query,
            view=view,
            language=language,
            top_k=top_k,
            expand_context=expand_context,
        )


__all__ = ["SearchUseCase"]
