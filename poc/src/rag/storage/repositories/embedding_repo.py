"""Embedding repository implementation.

Provides operations for managing embeddings in the vector database.

Rules:
- PKG-STO-001: Repository interface implementation
- DEP-STO-ALLOW-002: MAY import shared
- PKG-STO-BAN-002: MUST NOT perform embedding generation (that's embedding layer's job)
"""

from src.rag.shared.config import EmbeddingConfig

from ..db import DatabaseUtil


class EmbeddingRepository:
    """Repository for managing embeddings in PGVector.

    Note: This repository does NOT follow the BaseRepository pattern because
    embeddings are stored in LangChain's PGVector tables and have a different
    structure than domain entities.

    This repository provides operations for:
    - Deleting embeddings by fragment_id (for CASCADE-003)
    - Checking if embeddings exist
    """

    def __init__(self, config: EmbeddingConfig):
        self.db = DatabaseUtil(config)

    def delete_by_fragment_id(self, fragment_id: str) -> None:
        """Delete all embeddings for a Fragment (CASCADE-003)."""
        self.db.execute(
            "DELETE FROM langchain_pg_embedding WHERE cmetadata->>'fragment_id' = %s",
            (fragment_id,),
        )

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Delete embedding by doc_id."""
        self.db.execute(
            "DELETE FROM langchain_pg_embedding WHERE cmetadata->>'doc_id' = %s",
            (doc_id,),
        )

    def exists_by_doc_id(self, doc_id: str) -> bool:
        """Check if an embedding exists by doc_id."""
        return self.db.exists(
            "SELECT 1 FROM langchain_pg_embedding WHERE cmetadata->>'doc_id' = %s LIMIT 1",
            (doc_id,),
        )

    def count_by_fragment_id(self, fragment_id: str) -> int:
        """Count embeddings for a Fragment."""
        row = self.db.fetch_one(
            "SELECT COUNT(*) FROM langchain_pg_embedding WHERE cmetadata->>'fragment_id' = %s",
            (fragment_id,),
        )
        return row[0] if row else 0


__all__ = ["EmbeddingRepository"]
