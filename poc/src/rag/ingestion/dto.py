"""Ingestion layer Data Transfer Objects.

Defines output schemas for the ingestion pipeline stages.

Rules:
- MUST NOT depend on other layers (retrieval, generation, storage).
- SHOULD be pure data classes.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class RawSegment:
    """
    Raw parsed content unit from file parsers.

    This represents a piece of content extracted from a file before
    any semantic grouping or concept identification.
    """

    kind: str  # "text" | "code" | "image" | "table"
    content: str
    language: Optional[str]  # e.g., "python", "javascript", "image"
    order: int
    page: Optional[int] = None  # Page number (0-indexed)
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)


@dataclass
class UnitizedSegment:
    """
    Segment grouped into semantic units.

    unit_id groups related segments together (e.g., pre-text + code + post-text).
    """

    unit_id: Optional[str]  # UUID for semantic unit, None for ungrouped
    role: str  # "pre_text", "python", "post_text", "javascript", "bridge_text", "other"
    segment: RawSegment


__all__ = ["RawSegment", "UnitizedSegment"]
