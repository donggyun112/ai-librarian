"""Deterministic doc_id generation for embeddings.

Rule: EMBED-ID-002 - doc_id = hash(parent_id + view + lang + content)
"""

from src.rag.domain import ContentHash, Fragment
from src.rag.shared.hashing import HashingService


def compute_doc_id(fragment: Fragment) -> str:
    """
    Generate deterministic doc_id for a Fragment.

    This implements EMBED-ID-002: doc_id is a deterministic hash based on
    parent_id, view, language, and content.

    Args:
        fragment: Fragment entity to generate doc_id for

    Returns:
        doc_id string in format "doc:{hash}"

    Examples:
        >>> from domain import Fragment, View
        >>> import uuid
        >>> frag = Fragment(
        ...     id=str(uuid.uuid4()),
        ...     concept_id="concept-123",
        ...     content="Sample content",
        ...     view=View.TEXT,
        ...     language=None,
        ...     order=0
        ... )
        >>> doc_id = compute_doc_id(frag)
        >>> assert doc_id.startswith("doc:")
        >>> assert len(doc_id) == 36  # "doc:" + 32 hex chars
    """
    content_hash = ContentHash.compute(
        parent_id=fragment.concept_id,
        view=fragment.view,
        lang=fragment.language,
        content=fragment.content,
    )
    return content_hash.to_doc_id()


def compute_doc_id_from_parts(
    parent_id: str,
    view: str,
    lang: str,
    content: str,
) -> str:
    """
    Generate deterministic doc_id from individual parts.

    This is a lower-level function for when you have the parts but not
    a Fragment object. Prefer compute_doc_id(fragment) when possible.

    Args:
        parent_id: Concept ID (parent_id)
        view: View type string (e.g., "text", "code")
        lang: Language code (use empty string for None)
        content: Fragment content

    Returns:
        doc_id string in format "doc:{hash}"
    """
    hash_value = HashingService.content_hash(
        pid=parent_id,
        view=view,
        lang=lang,
        content=content,
    )
    return f"doc:{hash_value}"


__all__ = ["compute_doc_id", "compute_doc_id_from_parts"]
