"""Concept repository implementation.

Provides CRUD operations for Concept entities.

Rules:
- PKG-STO-001: Repository interface implementation
- DEP-STO-ALLOW-001~002: MAY import domain, shared
- PKG-STO-BAN-001: MUST NOT enforce domain rules (validation is domain's job)
"""

import json
from typing import Any, List, Optional, Tuple

from src.rag.domain import Concept
from src.rag.shared.config import EmbeddingConfig

from ..db import DatabaseUtil
from .base import BaseRepository


class ConceptRepository(BaseRepository[Concept]):
    """Repository for Concept entities.

    Handles persistence of Concept entities (semantic parents) to PostgreSQL.
    Concepts group related Fragments together.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.db = DatabaseUtil(config)

    def save(self, concept: Concept) -> Concept:
        """Save a Concept entity."""
        self.db.execute(
            """
            INSERT INTO concepts (id, document_id, "order", content, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET
              document_id = EXCLUDED.document_id,
              "order" = EXCLUDED."order",
              content = EXCLUDED.content,
              metadata = concepts.metadata || EXCLUDED.metadata,
              updated_at = now()
            """,
            (
                concept.id,
                concept.document_id,
                concept.order,
                concept.content,
                json.dumps(concept.metadata or {}),
            ),
        )
        return concept

    def find_by_id(self, entity_id: str) -> Optional[Concept]:
        """Find a Concept by ID."""
        row = self.db.fetch_one(
            'SELECT id, document_id, "order", content, metadata FROM concepts WHERE id = %s',
            (entity_id,),
        )
        return self._to_entity(row) if row else None

    def find_by_document_id(self, document_id: str) -> List[Concept]:
        """Find all Concepts belonging to a Document (for CASCADE-001)."""
        rows = self.db.fetch_all(
            'SELECT id, document_id, "order", content, metadata FROM concepts WHERE document_id = %s ORDER BY "order"',
            (document_id,),
        )
        return [self._to_entity(row) for row in rows]

    def find_all(self) -> List[Concept]:
        """Find all Concepts."""
        rows = self.db.fetch_all(
            'SELECT id, document_id, "order", content, metadata FROM concepts ORDER BY document_id, "order"'
        )
        return [self._to_entity(row) for row in rows]

    def delete(self, entity_id: str) -> None:
        """Delete a Concept by ID (does NOT cascade to Fragments)."""
        self.db.execute("DELETE FROM concepts WHERE id = %s", (entity_id,))

    def exists(self, entity_id: str) -> bool:
        """Check if a Concept exists."""
        return self.db.exists("SELECT 1 FROM concepts WHERE id = %s", (entity_id,))

    def ensure_table(self) -> None:
        """Create concepts table if it doesn't exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS concepts (
              id          TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              "order"     INTEGER NOT NULL DEFAULT 0,
              content     TEXT,
              metadata    JSONB DEFAULT '{}'::jsonb,
              created_at  TIMESTAMPTZ DEFAULT now(),
              updated_at  TIMESTAMPTZ DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_concepts_document_id ON concepts (document_id)
        """)

    @staticmethod
    def _to_entity(row: Tuple[Any, ...]) -> Concept:
        """Map database row to Concept entity."""
        return Concept(
            id=row[0],
            document_id=row[1],
            order=row[2] or 0,
            content=row[3],
            metadata=row[4] or {},
        )


__all__ = ["ConceptRepository"]
