"""Embedding quality metrics sourced from the vector store."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from src.rag.shared.config import EmbeddingConfig

from .db import DatabaseHelper


@dataclass
class EmbeddingMetrics:
    """Summary metrics for embeddings stored in PGVector."""

    total_embeddings: int = 0
    missing_doc_id: int = 0
    missing_parent_id: int = 0
    missing_fragment_id: int = 0
    short_content: int = 0
    duplicate_doc_id_groups: int = 0
    view_counts: List[Tuple[str, int]] = field(default_factory=list)
    lang_counts: List[Tuple[str, int]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class EmbeddingMetricsService:
    """Compute basic embedding quality metrics from the DB."""

    def __init__(self, config: EmbeddingConfig):
        self.db = DatabaseHelper(config)

    def summarize(self, limit: int = 10, min_content_len: int = 10) -> EmbeddingMetrics:
        metrics = EmbeddingMetrics()
        if not self.db.is_configured:
            metrics.errors.append("PG_CONN is not configured")
            return metrics

        if not self._table_exists("langchain_pg_embedding"):
            metrics.errors.append("langchain_pg_embedding table not found")
            return metrics

        try:
            metrics.total_embeddings = self._fetch_int(
                "SELECT COUNT(*) FROM langchain_pg_embedding"
            )
            metrics.missing_doc_id = self._fetch_int(
                "SELECT COUNT(*) FROM langchain_pg_embedding "
                "WHERE COALESCE(cmetadata->>'doc_id', '') = ''"
            )
            metrics.missing_parent_id = self._fetch_int(
                "SELECT COUNT(*) FROM langchain_pg_embedding "
                "WHERE COALESCE(cmetadata->>'parent_id', '') = ''"
            )
            metrics.missing_fragment_id = self._fetch_int(
                "SELECT COUNT(*) FROM langchain_pg_embedding "
                "WHERE COALESCE(cmetadata->>'fragment_id', '') = ''"
            )
            metrics.short_content = self._fetch_int(
                "SELECT COUNT(*) FROM langchain_pg_embedding "
                "WHERE LENGTH(COALESCE(document, '')) < %s",
                (min_content_len,),
            )
            metrics.duplicate_doc_id_groups = self._fetch_int(
                """
                SELECT COUNT(*) FROM (
                  SELECT cmetadata->>'doc_id' AS doc_id, COUNT(*) AS cnt
                  FROM langchain_pg_embedding
                  WHERE COALESCE(cmetadata->>'doc_id', '') <> ''
                  GROUP BY cmetadata->>'doc_id'
                  HAVING COUNT(*) > 1
                ) t
                """
            )
            metrics.view_counts = self._fetch_counts(
                """
                SELECT COALESCE(cmetadata->>'view', '<missing>') AS view, COUNT(*)
                FROM langchain_pg_embedding
                GROUP BY view
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """,
                (limit,),
            )
            metrics.lang_counts = self._fetch_counts(
                """
                SELECT COALESCE(cmetadata->>'lang', '<missing>') AS lang, COUNT(*)
                FROM langchain_pg_embedding
                GROUP BY lang
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """,
                (limit,),
            )
        except Exception as exc:
            metrics.errors.append(str(exc))
        return metrics

    def sample_short_content(
        self,
        min_content_len: int = 10,
        limit: int = 5,
    ) -> List[Tuple[str, str, str, str]]:
        """Return short-content samples for manual inspection."""
        if not self.db.is_configured or not self._table_exists("langchain_pg_embedding"):
            return []
        sql = """
        SELECT
          COALESCE(cmetadata->>'fragment_id', '') AS fragment_id,
          COALESCE(cmetadata->>'parent_id', '') AS parent_id,
          COALESCE(cmetadata->>'view', '') AS view,
          COALESCE(document, '') AS content
        FROM langchain_pg_embedding
        WHERE LENGTH(COALESCE(document, '')) < %s
        ORDER BY LENGTH(COALESCE(document, '')) ASC
        LIMIT %s
        """
        return self.db.fetch_all(sql, (min_content_len, limit))

    def _table_exists(self, name: str) -> bool:
        row = self.db.fetch_one("SELECT to_regclass(%s)", (f"public.{name}",))
        return bool(row and row[0])

    def _fetch_int(self, sql: str, params: Tuple = ()) -> int:
        row = self.db.fetch_one(sql, params)
        return int(row[0]) if row else 0

    def _fetch_counts(self, sql: str, params: Tuple = ()) -> List[Tuple[str, int]]:
        rows = self.db.fetch_all(sql, params)
        return [(str(row[0]), int(row[1])) for row in rows]


__all__ = ["EmbeddingMetrics", "EmbeddingMetricsService"]
