"""Embedding layer for OCR Vector DB.

Handles vector generation and doc_id computation.

Rules:
- PKG-EMB-001~005: Vector generation, deterministic doc_id, provider abstraction,
  min length validation, duplicate checking
- PKG-EMB-BAN-001~003: MUST NOT do file parsing, search, or schema management
- DEP-EMB-001~003: MUST NOT import ingestion, retrieval, api
- DEP-EMB-ALLOW-001~003: MAY import domain, shared, storage repositories
"""

from .doc_id import compute_doc_id, compute_doc_id_from_parts
from .provider import EmbeddingProviderFactory, GeminiEmbeddings, validate_embedding_dimension
from .validators import EmbeddingValidator

__all__ = [
    # Provider
    "EmbeddingProviderFactory",
    "GeminiEmbeddings",
    "validate_embedding_dimension",
    # Doc ID
    "compute_doc_id",
    "compute_doc_id_from_parts",
    # Validators
    "EmbeddingValidator",
]
