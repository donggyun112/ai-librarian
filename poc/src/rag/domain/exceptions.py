"""Domain-specific exceptions for OCR Vector DB.

These exceptions enforce domain invariants defined in docs/DOMAIN_RULES.md.
"""


class DomainError(Exception):
    """Base exception for domain layer."""

    pass


class OrphanEntityError(DomainError):
    """
    Raised when an entity violates ownership hierarchy.

    Examples:
    - Fragment created without valid concept_id (HIER-003)
    - Concept created without valid document_id (HIER-002)
    """

    pass


class FragmentTooShortError(DomainError):
    """
    Raised when attempting to embed a fragment shorter than minimum length.

    Rule: FRAG-LEN-001 - Fragments must be >= 10 characters to be embedded.
    """

    pass


class InvalidParentIdError(DomainError):
    """
    Raised when parent_id is modified after creation.

    Rule: FRAG-IMMUT-001 - parent_id must be immutable.
    """

    pass


class DuplicateEmbeddingError(DomainError):
    """
    Raised when attempting to create duplicate embedding.

    Rule: EMBED-DUP-001 - Duplicate embeddings should be discarded.
    """

    pass


__all__ = [
    "DomainError",
    "OrphanEntityError",
    "FragmentTooShortError",
    "InvalidParentIdError",
    "DuplicateEmbeddingError",
]
