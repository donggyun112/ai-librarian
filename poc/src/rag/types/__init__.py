"""RAG system Data Transfer Objects (DTOs).

Defines common data structures shared across different layers (Retrieval, Generation)
to avoid circular imports.

Rules:
- MUST NOT depend on logic layers (retrieval, generation, storage).
- MAY depend on domain entities/enum (View, ContentHash).
- SHOULD be pure data classes.
"""

from dataclasses import dataclass
from typing import Optional

from src.rag.domain import View


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


__all__ = ["SearchResult", "ExpandedResult"]
