"""Parent document storage for context expansion.

Stores parent (Concept) documents in docstore_parent table for context retrieval.

Rules:
- PKG-STO-001: Repository pattern implementation
- SEARCH-SEP-003: Parent documents provide context for search results
"""

import json

import psycopg  # type: ignore

from src.rag.shared.config import EmbeddingConfig


class ParentDocumentStore:
    """Stores parent (Concept) documents for context retrieval.

    Parent documents are stored in the docstore_parent table and linked
    to Fragment embeddings via parent_id (concept_id).
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config

    @property
    def _pg_conn(self) -> str:
        """Get PostgreSQL connection string."""
        return (self.config.pg_conn or "").replace("postgresql+psycopg", "postgresql")

    def upsert_parent(self, parent_id: str, content: str, metadata: dict) -> None:
        """Upsert parent document to docstore_parent table.

        Args:
            parent_id: Concept ID (unique identifier)
            content: Parent document content (synthesized from fragments)
            metadata: Additional metadata (document_id, order, etc.)

        Note:
            Uses ON CONFLICT DO UPDATE for idempotent upserts.
            Metadata is merged (||) not replaced.
        """
        if not self.config.pg_conn:
            return

        sql = """
        INSERT INTO docstore_parent (id, content, metadata)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
          content = EXCLUDED.content,
          metadata = docstore_parent.metadata || EXCLUDED.metadata,
          updated_at = now();
        """

        with psycopg.connect(self._pg_conn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (parent_id, content, json.dumps(metadata)))


__all__ = ["ParentDocumentStore"]
