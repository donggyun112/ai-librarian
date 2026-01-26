"""LangChain adapter for converting domain entities to/from LangChain Documents.

Isolates LangChain dependency to the storage layer.

Rules:
- DEP-STO-ALLOW-001: MAY import domain
- This is the ONLY place where domain entities are converted to LangChain Documents
"""

from typing import Dict, Optional

from langchain_core.documents import Document

from src.rag.domain import Fragment, View


class LangChainAdapter:
    """Adapter for converting between domain entities and LangChain Documents.

    This adapter isolates the LangChain dependency to the storage layer,
    allowing the rest of the system to work with pure domain entities.

    Example:
        >>> adapter = LangChainAdapter()
        >>> fragment = Fragment(id="frag-1", concept_id="concept-1", content="text", view=View.TEXT, language=None, order=0)
        >>> doc = adapter.fragment_to_document(fragment)
        >>> reconstructed = adapter.document_to_fragment(doc)
    """

    @staticmethod
    def fragment_to_document(
        fragment: Fragment,
        doc_id: Optional[str] = None,
        additional_metadata: Optional[Dict] = None,
    ) -> Document:
        """Convert domain Fragment to LangChain Document.

        Args:
            fragment: Domain Fragment entity
            doc_id: Optional deterministic doc_id (EMBED-ID-002)
            additional_metadata: Additional metadata to merge

        Returns:
            LangChain Document with Fragment content and metadata
        """
        metadata = {
            "fragment_id": fragment.id,
            "parent_id": fragment.concept_id,  # HIER-003: parent_id is required
            "view": fragment.view.value,
            "lang": fragment.language,
            "order": fragment.order,
        }

        # Add doc_id if provided (deterministic hash)
        if doc_id:
            metadata["doc_id"] = doc_id

        # Merge fragment metadata
        if fragment.metadata:
            metadata.update(fragment.metadata)

        # Merge additional metadata
        if additional_metadata:
            metadata.update(additional_metadata)

        return Document(
            page_content=fragment.content,
            metadata=metadata,
        )

    @staticmethod
    def document_to_fragment(doc: Document) -> Fragment:
        """Convert LangChain Document back to domain Fragment.

        Args:
            doc: LangChain Document

        Returns:
            Domain Fragment entity

        Raises:
            ValueError: If required metadata is missing
        """
        metadata = doc.metadata

        # Extract required fields
        fragment_id = metadata.get("fragment_id")
        concept_id = metadata.get("parent_id")
        view_str = metadata.get("view", "text")
        language = metadata.get("lang")
        order = metadata.get("order", 0)

        if not fragment_id:
            raise ValueError("Missing fragment_id in Document metadata")
        if not concept_id:
            raise ValueError("Missing parent_id in Document metadata (HIER-003 violation)")

        # Convert view string to View enum
        try:
            view = View(view_str)
        except ValueError:
            view = View.TEXT  # Default fallback

        # Extract fragment-specific metadata (exclude adapter metadata)
        fragment_metadata = {
            k: v
            for k, v in metadata.items()
            if k not in {"fragment_id", "parent_id", "view", "lang", "order", "doc_id"}
        }

        return Fragment(
            id=fragment_id,
            concept_id=concept_id,
            content=doc.page_content,
            view=view,
            language=language,
            order=order,
            metadata=fragment_metadata if fragment_metadata else None,
        )

    @staticmethod
    def extract_doc_id(doc: Document) -> Optional[str]:
        """Extract doc_id from LangChain Document metadata.

        Args:
            doc: LangChain Document

        Returns:
            doc_id if present, None otherwise
        """
        return doc.metadata.get("doc_id")


__all__ = ["LangChainAdapter"]
