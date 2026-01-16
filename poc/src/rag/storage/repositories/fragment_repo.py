"""Fragment repository implementation.

Provides CRUD operations for Fragment entities.

Rules:
- PKG-STO-001: Repository interface implementation
- DEP-STO-ALLOW-001~002: MAY import domain, shared
- PKG-STO-BAN-001: MUST NOT enforce domain rules (validation is domain's job)
"""

import json
from typing import Any, List, Optional, Tuple

from src.rag.domain import Fragment, View
from src.rag.shared.config import EmbeddingConfig

from ..db import DatabaseUtil
from .base import BaseRepository


class FragmentRepository(BaseRepository[Fragment]):
    """Repository for Fragment entities.

    Handles persistence of Fragment entities (embeddable content units) to PostgreSQL.
    Fragments are the children of Concepts and the targets for embedding.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.db = DatabaseUtil(config)

    def save(self, fragment: Fragment) -> Fragment:
        """Save a Fragment entity.

        Note: This does NOT validate FRAG-LEN-001 or other domain rules.
        Domain validation must be done before calling save().
        """
        self.db.execute(
            """
            INSERT INTO fragments (id, concept_id, content, view, language, "order", metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET
              concept_id = EXCLUDED.concept_id,
              content = EXCLUDED.content,
              view = EXCLUDED.view,
              language = EXCLUDED.language,
              "order" = EXCLUDED."order",
              metadata = fragments.metadata || EXCLUDED.metadata,
              updated_at = now()
            """,
            (
                fragment.id,
                fragment.concept_id,
                fragment.content,
                fragment.view.value,
                fragment.language,
                fragment.order,
                json.dumps(fragment.metadata or {}),
            ),
        )
        return fragment

    def find_by_id(self, entity_id: str) -> Optional[Fragment]:
        """Find a Fragment by ID."""
        row = self.db.fetch_one(
            'SELECT id, concept_id, content, view, language, "order", metadata FROM fragments WHERE id = %s',
            (entity_id,),
        )
        return self._to_entity(row) if row else None

    def find_by_concept_id(self, concept_id: str) -> List[Fragment]:
        """Find all Fragments belonging to a Concept (for CASCADE-002)."""
        rows = self.db.fetch_all(
            'SELECT id, concept_id, content, view, language, "order", metadata FROM fragments WHERE concept_id = %s ORDER BY "order"',
            (concept_id,),
        )
        return [self._to_entity(row) for row in rows]

    def find_all(self) -> List[Fragment]:
        """Find all Fragments."""
        rows = self.db.fetch_all(
            'SELECT id, concept_id, content, view, language, "order", metadata FROM fragments ORDER BY concept_id, "order"'
        )
        return [self._to_entity(row) for row in rows]

    def delete(self, entity_id: str) -> None:
        """Delete a Fragment by ID (does NOT cascade to embeddings)."""
        self.db.execute("DELETE FROM fragments WHERE id = %s", (entity_id,))

    def exists(self, entity_id: str) -> bool:
        """Check if a Fragment exists."""
        return self.db.exists("SELECT 1 FROM fragments WHERE id = %s", (entity_id,))

    def ensure_table(self) -> None:
        """Create fragments table if it doesn't exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS fragments (
              id          TEXT PRIMARY KEY,
              concept_id  TEXT NOT NULL,
              content     TEXT NOT NULL,
              view        TEXT NOT NULL,
              language    TEXT,
              "order"     INTEGER NOT NULL,
              metadata    JSONB DEFAULT '{}'::jsonb,
              created_at  TIMESTAMPTZ DEFAULT now(),
              updated_at  TIMESTAMPTZ DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_fragments_concept_id ON fragments (concept_id);
            CREATE INDEX IF NOT EXISTS idx_fragments_view ON fragments (view);
            CREATE INDEX IF NOT EXISTS idx_fragments_language ON fragments (language)
        """)

    @staticmethod
    def _to_entity(row: Tuple[Any, ...]) -> Fragment:
        """Map database row to Fragment entity."""
        return Fragment(
            id=row[0],
            concept_id=row[1],
            content=row[2],
            view=View(row[3]),
            language=row[4],
            order=row[5],
            metadata=row[6] or {},
        )


__all__ = ["FragmentRepository"]
