"""Document repository implementation.

Provides CRUD operations for Document entities.

Rules:
- PKG-STO-001: Repository interface implementation
- DEP-STO-ALLOW-001~002: MAY import domain, shared
- PKG-STO-BAN-001: MUST NOT enforce domain rules (validation is domain's job)
"""

import json
from typing import Any, List, Optional, Tuple

from src.rag.domain import Document
from src.rag.shared.config import EmbeddingConfig

from ..db import DatabaseHelper
from .base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document entities.

    Handles persistence of Document entities to PostgreSQL.
    Uses a simple documents table for metadata storage.
    """

    def __init__(self, config: EmbeddingConfig):
        self.db = DatabaseHelper(config)

    def save(self, document: Document) -> Document:
        """Save a Document entity."""
        self.db.execute(
            """
            INSERT INTO documents (id, source_path, metadata, created_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET
              source_path = EXCLUDED.source_path,
              metadata = documents.metadata || EXCLUDED.metadata,
              updated_at = now()
            """,
            (document.id, document.source_path, json.dumps(document.metadata or {})),
        )
        return document

    def find_by_id(self, entity_id: str) -> Optional[Document]:
        """Find a Document by ID."""
        row = self.db.fetch_one(
            "SELECT id, source_path, metadata FROM documents WHERE id = %s",
            (entity_id,),
        )
        return self._to_entity(row) if row else None

    def find_all(self) -> List[Document]:
        """Find all Documents."""
        rows = self.db.fetch_all("SELECT id, source_path, metadata FROM documents")
        return [self._to_entity(row) for row in rows]

    def delete(self, entity_id: str) -> None:
        """Delete a Document by ID (does NOT cascade to Concepts)."""
        self.db.execute("DELETE FROM documents WHERE id = %s", (entity_id,))

    def exists(self, entity_id: str) -> bool:
        """Check if a Document exists."""
        return self.db.exists("SELECT 1 FROM documents WHERE id = %s", (entity_id,))

    def ensure_table(self) -> None:
        """Create documents table if it doesn't exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
              id          TEXT PRIMARY KEY,
              source_path TEXT NOT NULL,
              metadata    JSONB DEFAULT '{}'::jsonb,
              created_at  TIMESTAMPTZ DEFAULT now(),
              updated_at  TIMESTAMPTZ DEFAULT now()
            )
        """)

    @staticmethod
    def _to_entity(row: Tuple[Any, ...]) -> Document:
        """Map database row to Document entity."""
        return Document(
            id=row[0],
            source_path=row[1],
            metadata=row[2] or {},
        )


__all__ = ["DocumentRepository"]
