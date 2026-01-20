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
    """

    query_text: str
    query_embedding: List[float]
    view_filter: Optional[View] = None
    language_filter: Optional[str] = None
    top_k: int = 10

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
    "MAX_TOP_K",
]

@dataclass
class ExtractedQuery:
    rewritten_query: Optional[str]
    filters: Optional[Dict[str, Any]]
    