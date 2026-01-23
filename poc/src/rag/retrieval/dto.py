"""Retrieval layer Data Transfer Objects.

Defines output schemas for the retrieval pipeline.

Rules:
- MUST NOT depend on logic layers (retrieval internals, generation, storage).
- MAY depend on domain entities/enum (View, ContentHash).
- SHOULD be pure data classes.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.rag.domain import View

# Maximum allowed top_k to prevent excessive resource usage
MAX_TOP_K = 100


@dataclass
class QueryPlan:
    """Parsed query with filters and embedding.

    Attributes:
        query_text: Original query string
        query_embedding: Vector embedding of query
        view_filter: Optional view filter (text, code, image, etc.)
        language_filter: Optional language filter (python, javascript, etc.)
        top_k: Number of results to retrieve (capped at MAX_TOP_K)
        metadata_filters: Additional metadata filters for dynamic WHERE clause
    """

    query_text: str
    query_embedding: List[float]
    view_filter: Optional[View] = None
    language_filter: Optional[str] = None
    top_k: int = 10
    metadata_filters: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate and cap top_k to prevent excessive resource usage."""
        if self.top_k > MAX_TOP_K:
            self.top_k = MAX_TOP_K
        elif self.top_k < 1:
            self.top_k = 1


@dataclass
class SearchResult:
    """Result from vector similarity search.

    Attributes:
        fragment_id: ID of matching Fragment
        parent_id: ID of parent Concept (for context expansion)
        view: View type (text, code, image, etc.)
        language: Language (python, javascript, etc.)
        content: Fragment content
        similarity: Cosine similarity score (0-1)
        metadata: Additional metadata
    """

    fragment_id: str
    parent_id: str
    view: View
    language: Optional[str]
    content: str
    similarity: float
    metadata: dict


@dataclass
class ExpandedResult:
    """Search result with parent context.

    Attributes:
        result: Original search result (Fragment)
        parent_content: Parent Concept content for context
        parent_metadata: Parent metadata
    """

    result: SearchResult
    parent_content: Optional[str] = None
    parent_metadata: Optional[dict] = None


@dataclass
class SelfQueryResult:
    """Result from self-query retrieval.

    Attributes:
        content: Document content
        metadata: Document metadata including view, lang, parent_id
        score: Relevance score (cosine similarity)
    """

    content: str
    metadata: dict
    score: Optional[float] = None
    rewritten_query: Optional[str] = None


__all__ = [
    "QueryPlan",
    "SearchResult",
    "ExpandedResult",
    "SelfQueryResult",
    "OptimizedQueryResult",
    "MAX_TOP_K",
]

@dataclass
class ExtractedQuery:
    rewritten_query: Optional[str]
    filters: Optional[Dict[str, Any]]


@dataclass
class OptimizedQueryResult:
    """Query optimization result.

    Attributes:
        original_query: Original user query
        rewritten_query: LLM-rewritten query (e.g., from self-query)
        view_filter: Optional view filter extracted
        language_filter: Optional language filter extracted
        metadata_filters: Additional metadata filters
    """
    original_query: str
    rewritten_query: Optional[str] = None
    view_filter: Optional[str] = None
    language_filter: Optional[str] = None
    metadata_filters: Optional[Dict[str, Any]] = None

    @property
    def effective_query(self) -> str:
        """Return the query to use for search (rewritten or original)."""
        return self.rewritten_query or self.original_query
    