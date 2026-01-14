"""Database connection pool singleton.

Provides a shared connection pool for all database operations,
reducing connection overhead and improving performance.

Rules:
- DEP-SHARED-001: Shared utilities for all packages
"""

from typing import Optional, Tuple

import psycopg_pool  # type: ignore

from src.rag.shared.config import EmbeddingConfig
from src.rag.storage.schema import DbSchemaManager

# Module-level singleton
_pool: Optional[psycopg_pool.ConnectionPool] = None
_pool_key: Optional[Tuple[str, int, int]] = None
_tuning_attempted: set[str] = set()


def get_pool(config: EmbeddingConfig) -> psycopg_pool.ConnectionPool:
    """Get or create connection pool singleton.

    The pool is created once and reused across all database operations.
    DB tuning is applied once when the pool is first created.

    Args:
        config: Embedding configuration with database connection string

    Returns:
        Connection pool instance

    Raises:
        ValueError: If pg_conn is not configured
    """
    global _pool, _pool_key, _tuning_attempted

    if not config.pg_conn:
        raise ValueError("pg_conn is not configured")

    # Convert SQLAlchemy-style connection string to psycopg format
    conn_str = config.pg_conn.replace("postgresql+psycopg", "postgresql")
    min_size = max(0, config.pg_pool_min_size)
    max_size = max(min_size, max(1, config.pg_pool_max_size))
    key = (conn_str, min_size, max_size)

    if _pool is None or _pool.closed or _pool_key != key:
        if _pool is not None:
            _pool.close()
        _pool = psycopg_pool.ConnectionPool(
            conn_str,
            min_size=min_size,
            max_size=max_size,
            open=True,
        )
        _pool_key = key
        print(f"[pool] Connection pool created (min={min_size}, max={max_size})")

    # Apply DB tuning once per connection string
    if conn_str not in _tuning_attempted:
        _apply_tuning(config)
        _tuning_attempted.add(conn_str)

    return _pool


def _apply_tuning(config: EmbeddingConfig) -> None:
    """Apply DB-level tuning once at pool creation.

    This runs ALTER DATABASE SET commands for pgvector tuning parameters.
    Called only once when the pool is first created.

    Args:
        config: Embedding configuration with tuning parameters
    """
    try:
        DbSchemaManager(config).apply_db_level_tuning()
    except Exception as exc:
        print(f"[pool] DB tuning failed (non-fatal): {exc}")


def close_pool() -> None:
    """Close connection pool and release resources.

    Should be called at application shutdown.
    """
    global _pool, _pool_key, _tuning_attempted

    if _pool is not None:
        _pool.close()
        _pool = None
        _pool_key = None
        _tuning_attempted = set()
        print("[pool] Connection pool closed")


__all__ = ["get_pool", "close_pool"]
