"""Vector store operations for LangChain PGVector.

Handles batch upserts to LangChain PGVector store with rate limiting and retry logic.

Rules:
- PKG-STO-001: Repository pattern implementation
- PKG-STO-BAN-002: MUST NOT perform embedding generation
"""

import time
from typing import List

from langchain_core.documents import Document
from langchain_postgres import PGVector
from loguru import logger

from src.rag.shared.batching import iter_by_char_budget
from src.rag.shared.config import EmbeddingConfig
from src.rag.embedding.provider import EmbeddingsProtocol


class VectorStoreWriter:
    """Handles batch upserts to PGVector store with rate limiting and retry logic.

    Reuses patterns from app/storage.py:VectorStoreWriter.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config

    def create_store(self, embeddings_client: EmbeddingsProtocol) -> PGVector:
        """Create LangChain PGVector store instance.

        Args:
            embeddings_client: Embedding provider (Gemini or Voyage AI)

        Returns:
            Configured PGVector store
        """
        return PGVector(
            connection=self.config.pg_conn,
            embeddings=embeddings_client,
            collection_name=self.config.collection_name,
            distance_strategy="cosine",
            use_jsonb=True,
            embedding_length=self.config.embedding_dim,
        )

    def upsert_batch(
        self,
        store: PGVector,
        docs: List[Document],
        batch_size: int = 64,
    ) -> int:
        """Batch upsert documents to PGVector.

        Features:
        - Deduplicate by doc_id
        - Rate limiting with exponential backoff
        - Retry on rate limit errors

        Args:
            store: PGVector store instance
            docs: List of LangChain Documents with doc_id in metadata
            batch_size: Documents per batch (default: 64)

        Returns:
            Number of documents written
        """
        if not docs:
            return 0

        # 1. Deduplicate by doc_id
        unique: dict[str, Document] = {}
        for doc in docs:
            doc_id = doc.metadata.get("doc_id")
            if not doc_id:
                raise ValueError("Document missing doc_id in metadata")
            unique.setdefault(doc_id, doc)
        deduped = list(unique.values())

        # 2. Character-budget-aware batching
        # Uses config settings to avoid exceeding model token limits
        char_budget = self.config.max_chars_per_request if self.config.max_chars_per_request > 0 else 0
        max_items = self.config.max_items_per_request if self.config.max_items_per_request > 0 else batch_size

        groups = list(iter_by_char_budget(
            deduped,
            char_budget=char_budget,
            max_batch_size=batch_size,
            max_items_per_request=max_items,
        ))
        if not groups:
            return 0

        # 3. Rate limiting setup
        interval = (60.0 / self.config.rate_limit_rpm) if self.config.rate_limit_rpm > 0 else 0.0
        total_groups = len(groups)
        total_written = 0

        # 4. Process batches with retry logic
        for index, batch in enumerate(groups, 1):
            logger.info(f"Storing batch {index}/{total_groups} ({len(batch)} docs)")
            ids = [doc.metadata["doc_id"] for doc in batch]
            attempt = 0
            max_attempts = 6
            backoff = max(20.0, interval) or 20.0

            while True:
                try:
                    # Try with explicit IDs first
                    try:
                        store.add_documents(batch, ids=ids)
                    except TypeError:
                        # Fallback for older LangChain versions
                        store.add_documents(batch)
                    logger.info(f"Batch {index}/{total_groups} inserted {len(batch)} docs")
                    break
                except Exception as exc:
                    message = str(exc).lower()
                    rate_limited = any(
                        token in message for token in ("ratelimit", "rate limit", "rpm", "tpm")
                    )
                    if not rate_limited or attempt >= max_attempts - 1:
                        logger.error(f"Batch {index}/{total_groups} failed: {exc}")
                        raise
                    attempt += 1
                    sleep_for = backoff * (1.5**attempt)
                    logger.warning(
                        f"Rate-limit retry {attempt}/{max_attempts} in {int(sleep_for)}s "
                        f"(batch {index}/{total_groups})"
                    )
                    time.sleep(sleep_for)

            total_written += len(batch)

            # Rate limiting delay between batches
            if interval > 0 and index < total_groups:
                time.sleep(interval)

        return total_written


__all__ = ["VectorStoreWriter"]
