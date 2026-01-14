"""Context expansion for search results.

Retrieves parent Concept documents to provide context for Fragment search results.

Rules:
- PKG-RET-003: Context expansion logic (MUST)
- SEARCH-SEP-003: Context from Parent documents (MUST)
- DEP-RET-ALLOW-002: MAY import storage
- DEP-RET-ALLOW-004: MAY import shared
"""

from typing import Dict, List, Optional

from src.rag.shared.config import EmbeddingConfig
from src.rag.shared.db_pool import get_pool
from src.rag.types import ExpandedResult, SearchResult


class ContextExpander:
    """Expands search results with parent document context.

    Implements PKG-RET-003 (context expansion) and SEARCH-SEP-003 (parent context).

    Example:
        >>> expander = ContextExpander(config)
        >>> results = [SearchResult(...), ...]
        >>> expanded = expander.expand(results)
        >>> expanded[0].parent_content  # Full parent document
    """

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._pool = get_pool(config)

    def expand(self, results: List[SearchResult]) -> List[ExpandedResult]:
        """Expand search results with parent context.

        Retrieves parent Concept documents from docstore_parent table.

        Args:
            results: List of Fragment search results

        Returns:
            List of results with parent context attached
        """
        if not results or not self.config.pg_conn:
            return [ExpandedResult(result=r) for r in results]

        # Extract unique parent IDs
        parent_ids = list({r.parent_id for r in results})

        # Fetch parent documents
        parent_map = self._fetch_parents(parent_ids)

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

    def _fetch_parents(self, parent_ids: List[str]) -> Dict[str, dict]:
        """Fetch parent documents from docstore_parent table.

        Args:
            parent_ids: List of parent IDs to fetch

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

        with self._pool.connection() as conn:
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


__all__ = ["ContextExpander", "ExpandedResult"]
