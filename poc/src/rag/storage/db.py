"""Database helper for reducing repository boilerplate.

Provides common database operations like connection management and query execution.

Rules:
- PKG-STO-004: Transaction management
- DEP-STO-ALLOW-002: MAY import shared
"""

from contextlib import contextmanager
from typing import Any, Generator, List, Optional, Tuple, Union

import psycopg  # type: ignore

from src.rag.shared.config import EmbeddingConfig


class DatabaseUtil:
    """Helper class for common database operations.

    Reduces boilerplate in repository implementations by providing:
    - Connection string management
    - Context-managed connections
    - Common query execution patterns

    Example:
        >>> db = DatabaseUtil(config)
        >>> row = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
        >>> rows = db.fetch_all("SELECT * FROM users")
        >>> db.execute("INSERT INTO users (id) VALUES (%s)", (user_id,))
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config

    @property
    def conn_str(self) -> str:
        """Get PostgreSQL connection string (psycopg format)."""
        return (self.config.pg_conn or "").replace("postgresql+psycopg", "postgresql")

    @property
    def is_configured(self) -> bool:
        """Check if database connection is configured."""
        return bool(self.config.pg_conn)

    @contextmanager
    def connection(self, autocommit: bool = False) -> Generator[Optional[psycopg.Connection], None, None]:
        """Context manager for database connections.

        Args:
            autocommit: Enable autocommit mode for write operations

        Yields:
            Connection object, or None if not configured
        """
        if not self.is_configured:
            yield None
            return

        with psycopg.connect(self.conn_str, autocommit=autocommit) as conn:
            yield conn

    def fetch_one(
        self,
        sql: str,
        params: Union[Tuple, List] = (),
    ) -> Optional[Tuple[Any, ...]]:
        """Execute query and fetch single row.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            Single row tuple, or None if not found/not configured
        """
        if not self.is_configured:
            return None

        with psycopg.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()

    def fetch_all(
        self,
        sql: str,
        params: Union[Tuple, List] = (),
    ) -> List[Tuple[Any, ...]]:
        """Execute query and fetch all rows.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of row tuples, empty list if not configured
        """
        if not self.is_configured:
            return []

        with psycopg.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def execute(
        self,
        sql: str,
        params: Union[Tuple, List] = (),
    ) -> None:
        """Execute write operation (INSERT/UPDATE/DELETE).

        Args:
            sql: SQL query string
            params: Query parameters
        """
        if not self.is_configured:
            return

        with psycopg.connect(self.conn_str, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)

    def exists(self, sql: str, params: Union[Tuple, List] = ()) -> bool:
        """Check if a record exists.

        Args:
            sql: SQL query that returns at least one row if exists
            params: Query parameters

        Returns:
            True if record exists, False otherwise
        """
        return self.fetch_one(sql, params) is not None


__all__ = ["DatabaseUtil"]
