"""Use case orchestration for OCR Vector DB.

Implements PKG-API-004: Orchestrate other packages for use cases.
"""

from .dto import IngestResult
from .ingest import IngestUseCase
from .rag import RAGUseCase
from .search import SearchUseCase

__all__ = ["IngestUseCase", "IngestResult", "SearchUseCase", "RAGUseCase"]
