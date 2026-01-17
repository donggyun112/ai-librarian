"""Context expansion for search results.

Retrieves parent Concept documents to provide context for Fragment search results.

Rules:
- PKG-RET-003: Context expansion logic (MUST)
- SEARCH-SEP-003: Context from Parent documents (MUST)
- DEP-RET-ALLOW-002: MAY import storage
- DEP-RET-ALLOW-004: MAY import shared
"""

from typing import Dict, List, Optional

from loguru import logger
import psycopg_pool

from src.rag.shared.config import EmbeddingConfig
from src.rag.shared.db_pool import get_pool
from src.rag.shared.exceptions import DatabaseNotConfiguredError
from .dto import ExpandedResult, SearchResult


class ParentContextEnricher:
    """Expands search results with parent document context.

    Implements PKG-RET-003 (context expansion) and SEARCH-SEP-003 (parent context).

    Example:
        >>> expander = ParentContextEnricher(config)
        >>> results = [SearchResult(...), ...]
        >>> expanded = expander.expand(results)
        >>> expanded[0].parent_content  # Full parent document
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self._pool: Optional[psycopg_pool.ConnectionPool] = None

    def _get_pool(self) -> Optional[psycopg_pool.ConnectionPool]:
        """Get pool lazily, return None if DB not configured."""
        if self._pool is None and self.config.pg_conn:
            try:
                self._pool = get_pool(self.config)
            except ValueError as e:
                logger.warning(f"Failed to initialize DB pool: {e}")
        return self._pool

    def expand(self, results: List[SearchResult]) -> List[ExpandedResult]:
        """Expand search results with parent context.

        Retrieves parent Concept documents from docstore_parent table.

        Args:
            results: List of Fragment search results

        Returns:
            List of results with parent context attached
        """
        if not results:
            return []

        pool = self._get_pool()
        if pool is None:
            # Unreachable in practice: VectorSearchEngine fails first
            raise DatabaseNotConfiguredError("Database not configured")

        # Extract unique parent IDs
        parent_ids = list({r.parent_id for r in results})

        # Fetch parent documents
        parent_map = self._fetch_parents(parent_ids, pool)

        # Attach parent context to results
        expanded = []
        for result in results:
            parent = parent_map.get(result.parent_id)
            if parent:
                expanded.append(
                    ExpandedResult(
                        result=result,
                        parent_content=parent.get("content"),
                        parent_metadata=parent.get("metadata"),
                    )
                )
            else:
                # Parent not found - include without context
                expanded.append(ExpandedResult(result=result))

        return expanded

    def _fetch_parents(
        self, parent_ids: List[str], pool: psycopg_pool.ConnectionPool
    ) -> Dict[str, dict]:
        """Fetch parent documents from docstore_parent table.

        Args:
            parent_ids: List of parent IDs to fetch
            pool: Connection pool to use

        Returns:
            Dictionary mapping parent_id to {content, metadata}
        """
        if not parent_ids:
            return {}

        sql = """
        SELECT id, content, metadata
        FROM docstore_parent
        WHERE id = ANY(%s)
        """

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (parent_ids,))
                rows = cur.fetchall()

        return {
            row[0]: {
                "content": row[1],
                "metadata": row[2] or {},
            }
            for row in rows
        }


__all__ = ["ParentContextEnricher", "ExpandedResult"]
