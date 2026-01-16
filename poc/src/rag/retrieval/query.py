"""Query interpretation and embedding for retrieval.

Handles query parsing, embedding generation, and filter extraction.

Rules:
- PKG-RET-002: Query interpretation logic (MUST)
- DEP-RET-ALLOW-003: MAY import embedding (for embedding clients)
- DEP-RET-ALLOW-004: MAY import shared
"""

from typing import List, Optional, Protocol

from src.rag.domain import View
from src.rag.shared.config import EmbeddingConfig

from .dto import QueryPlan


class EmbeddingClientProtocol(Protocol):
    """Protocol for embedding client (dependency inversion)."""

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query string."""
        ...


class QueryInterpreter:
    """Interprets user queries and generates embeddings.

    Implements PKG-RET-002: Query interpretation logic.

    Example:
        >>> interpreter = QueryInterpreter(embeddings_client, config)
        >>> plan = interpreter.interpret("python list comprehension", view="code", top_k=5)
        >>> plan.query_embedding  # List[float]
    """

    def __init__(self, embeddings_client: EmbeddingClientProtocol, config: EmbeddingConfig) -> None:
        self.embeddings_client = embeddings_client
        self.config = config

    def interpret(
        self,
        query: str,
        view: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 10,
    ) -> QueryPlan:
        """Interpret a user query and generate a query plan.

        Args:
            query: User query string
            view: Optional view filter (text, code, image, caption, table, figure)
            language: Optional language filter (python, javascript, etc.)
            top_k: Number of results to retrieve

        Returns:
            QueryPlan with embedding and filters

        Raises:
            ValueError: If view is invalid
        """
        # Generate query embedding (delegates to embedding layer)
        query_embedding = self.embeddings_client.embed_query(query)

        # Parse view filter
        view_enum = None
        if view:
            try:
                view_enum = View(view.lower())
            except ValueError:
                raise ValueError(f"Invalid view: {view}. Must be one of {[v.value for v in View]}")

        # Normalize language filter
        language_normalized = language.lower() if language else None

        return QueryPlan(
            query_text=query,
            query_embedding=query_embedding,
            view_filter=view_enum,
            language_filter=language_normalized,
            top_k=top_k,
        )


__all__ = ["QueryInterpreter", "QueryPlan"]
