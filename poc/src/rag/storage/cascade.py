"""Cascade deletion logic for entity hierarchy.

Implements CASCADE-001~004 rules:
- CASCADE-001: Document deletion ??all child Concepts deleted
- CASCADE-002: Concept deletion ??all child Fragments deleted
- CASCADE-003: Fragment deletion ??all embeddings deleted
- CASCADE-004: No orphan entities after cascade deletion

Rules:
- PKG-STO-003: CASCADE logic implementation responsibility
- DEP-STO-ALLOW-001: MAY import domain
"""

from typing import List, Protocol

from src.rag.domain import Concept, Document, Fragment


class ConceptRepositoryProtocol(Protocol):
    """Protocol for Concept repository (dependency inversion)."""

    def find_by_document_id(self, document_id: str) -> List[Concept]:
        """Find all Concepts belonging to a Document."""
        ...

    def delete(self, concept_id: str) -> None:
        """Delete a Concept by ID."""
        ...


class FragmentRepositoryProtocol(Protocol):
    """Protocol for Fragment repository (dependency inversion)."""

    def find_by_concept_id(self, concept_id: str) -> List[Fragment]:
        """Find all Fragments belonging to a Concept."""
        ...

    def delete(self, fragment_id: str) -> None:
        """Delete a Fragment by ID."""
        ...


class EmbeddingRepositoryProtocol(Protocol):
    """Protocol for Embedding repository (dependency inversion)."""

    def delete_by_fragment_id(self, fragment_id: str) -> None:
        """Delete all embeddings for a Fragment."""
        ...


class DocumentRepositoryProtocol(Protocol):
    """Protocol for Document repository (dependency inversion)."""

    def delete(self, document_id: str) -> None:
        """Delete a Document by ID."""
        ...


class CascadeDeleter:
    """Handles cascade deletion across entity hierarchy.

    Implements the cascade deletion rules (CASCADE-001~004) ensuring that
    when a parent entity is deleted, all child entities are also deleted
    to prevent orphan entities.

    Example:
        >>> deleter = CascadeDeleter(doc_repo, concept_repo, fragment_repo, embedding_repo)
        >>> deleter.delete_document("doc-123")  # Deletes doc + concepts + fragments + embeddings
    """

    def __init__(
        self,
        document_repo: DocumentRepositoryProtocol,
        concept_repo: ConceptRepositoryProtocol,
        fragment_repo: FragmentRepositoryProtocol,
        embedding_repo: EmbeddingRepositoryProtocol,
    ):
        self.document_repo = document_repo
        self.concept_repo = concept_repo
        self.fragment_repo = fragment_repo
        self.embedding_repo = embedding_repo

    def delete_document(self, document_id: str) -> None:
        """Delete Document and all child entities (CASCADE-001).

        Cascade order:
        1. Find all Concepts for this Document
        2. Delete each Concept (triggers CASCADE-002)
        3. Delete the Document itself

        Args:
            document_id: ID of Document to delete

        Ensures:
            - No orphan Concepts remain (CASCADE-004)
            - No orphan Fragments remain (CASCADE-004)
            - No orphan Embeddings remain (CASCADE-004)
        """
        # CASCADE-001: Find all child Concepts
        concepts = self.concept_repo.find_by_document_id(document_id)

        # Cascade delete each Concept (triggers CASCADE-002)
        for concept in concepts:
            self.delete_concept(concept.id)

        # Finally delete the Document itself
        self.document_repo.delete(document_id)

    def delete_concept(self, concept_id: str) -> None:
        """Delete Concept and all child Fragments (CASCADE-002).

        Cascade order:
        1. Find all Fragments for this Concept
        2. Delete each Fragment (triggers CASCADE-003)
        3. Delete the Concept itself

        Args:
            concept_id: ID of Concept to delete

        Ensures:
            - No orphan Fragments remain (CASCADE-004)
            - No orphan Embeddings remain (CASCADE-004)
        """
        # CASCADE-002: Find all child Fragments
        fragments = self.fragment_repo.find_by_concept_id(concept_id)

        # Cascade delete each Fragment (triggers CASCADE-003)
        for fragment in fragments:
            self.delete_fragment(fragment.id)

        # Finally delete the Concept itself
        self.concept_repo.delete(concept_id)

    def delete_fragment(self, fragment_id: str) -> None:
        """Delete Fragment and all embeddings (CASCADE-003).

        Cascade order:
        1. Delete all embeddings for this Fragment
        2. Delete the Fragment itself

        Args:
            fragment_id: ID of Fragment to delete

        Ensures:
            - No orphan Embeddings remain (CASCADE-004)
        """
        # CASCADE-003: Delete all embeddings first
        self.embedding_repo.delete_by_fragment_id(fragment_id)

        # Finally delete the Fragment itself
        self.fragment_repo.delete(fragment_id)


__all__ = ["CascadeDeleter"]
