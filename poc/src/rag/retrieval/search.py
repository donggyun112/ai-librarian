"""Vector similarity search engine.

Handles Fragment embedding search using pgvector.

Rules:
- PKG-RET-001: Search pipeline (MUST)
- SEARCH-SEP-002: Search targets Fragment embeddings (MUST)
- DEP-RET-ALLOW-002: MAY import storage
- DEP-RET-ALLOW-004: MAY import shared
"""

from dataclasses import dataclass
from typing import List, Optional

from loguru import logger
import psycopg_pool

from src.rag.domain import View
from src.rag.shared.config import EmbeddingConfig
from src.rag.shared.db_pool import get_pool
from src.rag.shared.exceptions import DatabaseNotConfiguredError
from .dto import QueryPlan, SearchResult


class VectorSearchEngine:
    """Vector similarity search using pgvector.

    Implements PKG-RET-001 (search pipeline) and SEARCH-SEP-002 (Fragment targeting).

    Example:
        >>> engine = VectorSearchEngine(config)
        >>> plan = QueryPlan(query_text="...", query_embedding=[...], top_k=10)
        >>> results = engine.search(plan)
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

    def search(
        self,
        query_plan: QueryPlan,
        collection_name: Optional[str] = None,
    ) -> List[SearchResult]:
        """Execute vector similarity search.

        Searches Fragment embeddings in langchain_pg_embedding table,
        scoped to a specific collection.

        Args:
            query_plan: Parsed query with embedding and filters
            collection_name: Collection to search within (uses config default if None)

        Returns:
            List of search results ordered by similarity (highest first)
        """
        pool = self._get_pool()
        if pool is None:
            raise DatabaseNotConfiguredError(
                "Database not configured. Set PG_CONN environment variable."
            )

        # Use provided collection_name or fall back to config
        target_collection = collection_name or self.config.collection_name

        # Build WHERE clause for filters
        where_clauses = []
        where_params: List = []
        vector = self._format_vector(query_plan.query_embedding)

        if query_plan.view_filter:
            where_clauses.append("e.cmetadata->>'view' = %s")
            where_params.append(query_plan.view_filter.value)

        if query_plan.language_filter:
            where_clauses.append("e.cmetadata->>'lang' = %s")
            where_params.append(query_plan.language_filter)

        # Dynamic metadata filters from SelfQueryRetriever
        # Whitelisted keys based on schema.py BTREE indexes for SQL injection prevention
        if query_plan.metadata_filters:
            allowed_keys = {"unit_id", "parent_id", "section", "source", "unit_role"}
            for key, value in query_plan.metadata_filters.items():
                if key in allowed_keys:
                    where_clauses.append(f"e.cmetadata->>'{key}' = %s")
                    where_params.append(str(value))
                else:
                    logger.warning(f"Ignoring disallowed metadata filter key: {key}")

        where_sql = " AND " + " AND ".join(where_clauses) if where_clauses else ""

        sql = f"""
        SELECT
            e.cmetadata->>'fragment_id' AS fragment_id,
            e.cmetadata->>'parent_id' AS parent_id,
            e.cmetadata->>'view' AS view,
            e.cmetadata->>'lang' AS lang,
            e.document AS content,
            1 - (e.embedding <=> %s::vector) AS similarity,
            e.cmetadata AS metadata
        FROM langchain_pg_embedding e
        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
        WHERE c.name = %s{where_sql}
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
        """

        # Params order must match SQL: vector, collection_name, filters..., vector, limit
        params: List = [vector, target_collection]
        params.extend(where_params)
        params.append(vector)
        params.append(query_plan.top_k)

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        results = []
        for row in rows:
            fragment_id, parent_id, view_str, lang, content, similarity, metadata = row

            # Parse view
            try:
                view = View(view_str) if view_str else View.TEXT
            except ValueError:
                view = View.TEXT

            results.append(
                SearchResult(
                    fragment_id=fragment_id or "unknown",
                    parent_id=parent_id or "unknown",
                    view=view,
                    language=lang,
                    content=content or "",
                    similarity=float(similarity) if similarity is not None else 0.0,
                    metadata=metadata or {},
                )
            )

        return results

    @staticmethod
    def _format_vector(vector: List[float]) -> str:
        """Format vector for PostgreSQL literal.

        Args:
            vector: List of floats

        Returns:
            PostgreSQL vector literal string
        """
        return "[" + ",".join(str(float(x)) for x in vector) + "]"


__all__ = ["VectorSearchEngine", "SearchResult"]
