"""Domain layer for OCR Vector DB.

Pure domain entities with no infrastructure dependencies.

Rules:
- PKG-DOM-001: Contains pure domain entities ONLY
- PKG-DOM-BAN-001~004: MUST NOT import DB, APIs, file I/O, or config
- DEP-DOM-001: MUST NOT import other project packages (except shared/)
"""

from .entities import Concept, Document, Embedding, Fragment
from .exceptions import (
    DomainError,
    DuplicateEmbeddingError,
    FragmentTooShortError,
    InvalidParentIdError,
    OrphanEntityError,
)
from .value_objects import ContentHash, View

__all__ = [
    # Entities
    "Document",
    "Concept",
    "Fragment",
    "Embedding",
    # Value Objects
    "View",
    "ContentHash",
    # Exceptions
    "DomainError",
    "OrphanEntityError",
    "FragmentTooShortError",
    "InvalidParentIdError",
    "DuplicateEmbeddingError",
]
