"""Core domain entities for OCR Vector DB.

Entity hierarchy (docs/ARCHITECTURE.md):
    Document ??Concept ??Fragment ??Embedding

All entities must follow domain rules defined in docs/DOMAIN_RULES.md.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .exceptions import OrphanEntityError
from .value_objects import ContentHash, View


@dataclass
class Document:
    """
    Top-level input unit representing a file.

    A Document is the source of truth for all downstream Concepts.
    """

    id: str
    source_path: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def validate(self) -> None:
        """Validate document invariants."""
        if not self.id:
            raise ValueError("Document ID cannot be empty")
        if not self.source_path:
            raise ValueError("Document source_path cannot be empty")


@dataclass
class Concept:
    """
    Semantically cohesive information unit (Semantic Parent).

    A Concept groups related Fragments (text + code + image views of same topic).

    Rules:
    - HIER-002: Must belong to exactly ONE Document
    - HIER-004: document_id is immutable after creation
    """

    id: str
    document_id: str
    order: int = 0
    content: Optional[str] = None  # Parent document content for context
    metadata: dict = field(default_factory=dict)
    fragments: List["Fragment"] = field(default_factory=list)

    def validate(self) -> None:
        """
        Validate concept invariants.

        Raises:
            OrphanEntityError: If document_id is missing (HIER-002)
        """
        if not self.document_id:
            raise OrphanEntityError(
                f"Concept {self.id} violates HIER-002: Must belong to a Document"
            )


@dataclass
class Fragment:
    """
    Individual information chunk within a Concept.

    Fragments are the primary search target and embedding unit.

    Rules:
    - HIER-003: Must have valid concept_id (no orphans)
    - FRAG-IMMUT-001: concept_id is immutable after creation
    - FRAG-LEN-001: Content must be >= 10 characters to be embedded
    - FRAG-VIEW-001: View is an attribute, not an independent entity
    """

    id: str
    concept_id: str  # parent_id in legacy code
    content: str
    view: View
    language: Optional[str]
    order: int
    metadata: dict = field(default_factory=dict)

    def validate(self) -> None:
        """
        Validate fragment invariants.

        Raises:
            OrphanEntityError: If concept_id is missing (HIER-003)
        """
        if not self.concept_id:
            raise OrphanEntityError(
                f"Fragment {self.id} violates HIER-003: Must belong to a Concept"
            )

    def is_embeddable(self) -> bool:
        """
        Check if fragment meets minimum requirements for embedding.

        Returns:
            True if fragment content >= 10 characters
        """
        return len(self.content) >= 10

    def compute_doc_id(self) -> str:
        """
        Generate deterministic doc_id for this fragment.

        Rule: EMBED-ID-002 - doc_id = hash(parent_id + view + lang + content)

        Returns:
            doc_id string in format "doc:{hash}"
        """
        content_hash = ContentHash.compute(
            parent_id=self.concept_id,
            view=self.view,
            lang=self.language,
            content=self.content,
        )
        return content_hash.to_doc_id()


@dataclass
class Embedding:
    """
    Vector representation of a Fragment for similarity search.

    Rules:
    - EMBED-OWN-001: Must belong to exactly ONE Fragment
    - EMBED-ID-002: doc_id is deterministic based on content
    """

    doc_id: str  # Deterministic: hash(parent_id + view + lang + content)
    fragment_id: str
    vector: List[float]
    metadata: dict = field(default_factory=dict)

    def validate(self) -> None:
        """
        Validate embedding invariants.

        Raises:
            OrphanEntityError: If fragment_id is missing
            ValueError: If vector is empty
        """
        if not self.fragment_id:
            raise OrphanEntityError(
                f"Embedding {self.doc_id} violates EMBED-OWN-001: "
                f"Must belong to a Fragment"
            )
        if not self.vector:
            raise ValueError(f"Embedding {self.doc_id} has empty vector")


__all__ = ["Document", "Concept", "Fragment", "Embedding"]
