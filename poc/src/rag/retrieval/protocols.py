"""Protocols for retrieval layer.

Defines interfaces for query optimization and other retrieval components.

Rules:
- PKG-RET-001: Define protocols for retrieval abstraction (MUST)
- DEP-RET-ALLOW-001: MAY import domain
"""

from typing import Protocol

from .dto import OptimizedQueryResult


class QueryOptimizerProtocol(Protocol):
    """Protocol for query optimization implementations.

    Implementations can include:
    - SelfQueryRetriever (extracts metadata filters from natural language)
    - HyDE (Hypothetical Document Embeddings)
    - Query expansion
    - Query rewriting
    """

    def optimize(self, query: str) -> OptimizedQueryResult:
        """Optimize query for better retrieval.

        Args:
            query: Original user query

        Returns:
            OptimizedQueryResult with rewritten query and extracted filters
        """
        ...


__all__ = ["QueryOptimizerProtocol"]
