"""Shared utilities and configuration for OCR Vector DB.

Note: db_pool is NOT re-exported here to avoid circular imports.
Use `from src.rag.shared.db_pool import get_pool, close_pool` directly.
"""

from .config import load_config
from .exceptions import SharedError
from .hashing import HashingService, Slugifier, format_vector_literal
from .text_utils import TextPreprocessor

__all__ = [
    "load_config",
    "SharedError",
    "HashingService",
    "Slugifier",
    "format_vector_literal",
    "TextPreprocessor",
]
