"""Domain value objects for OCR Vector DB."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.rag.shared.hashing import HashingService


class View(Enum):
    """
    Content view type for fragments.

    View is an ATTRIBUTE of Fragment, not an independent entity (FRAG-VIEW-001).
    """

    TEXT = "text"
    CODE = "code"
    IMAGE = "image"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"


@dataclass(frozen=True)
class ContentHash:
    """
    Immutable content-based hash for deterministic doc_id generation.

    Rule: EMBED-ID-002 - doc_id = hash(parent_id + view + lang + content)
    """

    value: str

    @classmethod
    def compute(
        cls,
        parent_id: str,
        view: View,
        lang: Optional[str],
        content: str,
    ) -> "ContentHash":
        """
        Generate deterministic content hash.

        Args:
            parent_id: Concept ID (semantic parent)
            view: View type
            lang: Language code (optional)
            content: Fragment content

        Returns:
            ContentHash instance
        """
        lang_str = lang or ""
        hash_value = HashingService.content_hash(
            pid=parent_id,
            view=view.value,
            lang=lang_str,
            content=content,
        )
        return cls(value=hash_value)

    def to_doc_id(self) -> str:
        """Convert hash to doc_id format."""
        return f"doc:{self.value}"


__all__ = ["View", "ContentHash"]
