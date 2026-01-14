"""Ingestion layer for OCR Vector DB.

Handles file parsing and semantic segmentation.

Rules:
- PKG-ING-001~004: File parsing, segmentation, view detection, concept boundaries
- PKG-ING-BAN-001~003: MUST NOT do embedding, DB storage, or search
- DEP-ING-001~004: MUST NOT import embedding, retrieval, storage, api
"""

from .chunking import TextChunker
from .concept_builder import SegmentToConceptTransformer
from .dto import RawSegment, UnitizedSegment
from .parsers import (
    BaseSegmentParser,
    GeminiVisionOcr,
    MarkdownParser,
    OcrParser,
    PdfExtractor,
    PdfParser,
    PyMuPdfParser,
)
from .segmentation import SemanticUnitGrouper

__all__ = [
    # DTOs
    "RawSegment",
    "UnitizedSegment",
    # Parsers
    "BaseSegmentParser",
    "OcrParser",
    "MarkdownParser",
    "PdfExtractor",
    "PdfParser",
    "GeminiVisionOcr",
    "PyMuPdfParser",
    # Segmentation
    "SemanticUnitGrouper",
    # Chunking
    "TextChunker",
    # Concept Building
    "SegmentToConceptTransformer",
]
