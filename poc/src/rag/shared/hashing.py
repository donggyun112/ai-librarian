import hashlib
import re
import unicodedata
from typing import Sequence


class ContentHashUtil:
    """Utility for deterministic content hashing (deduplication)."""

    @staticmethod
    def hash(pid: str, view: str, lang: str, content: str) -> str:
        """
        Generate deterministic MD5 hash for content.

        Args:
            pid: Parent ID (concept_id)
            view: View type (text, code, image, etc.)
            lang: Language (optional, use empty string if None)
            content: Actual content

        Returns:
            MD5 hash as hexadecimal string
        """
        key = f"{pid}|{view}|{lang}|{content}".encode("utf-8", errors="ignore")
        return hashlib.md5(key).hexdigest()


class SlugifyUtil:
    """Utility for normalizing strings into URL-safe slug identifiers."""

    @staticmethod
    def slugify(value: str) -> str:
        if not value:
            return ""
        value = unicodedata.normalize("NFKD", value)
        value = value.encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"[^\w\s-]", "", value).strip().lower()
        value = re.sub(r"[-\s]+", "-", value)
        return value


def format_vector_literal(vector: Sequence[float]) -> str:
    """Represent a numeric vector as a Postgres-compatible literal."""
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


__all__ = ["ContentHashUtil", "SlugifyUtil", "format_vector_literal"]
