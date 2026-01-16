"""Use case layer Data Transfer Objects.

Defines output schemas for RAG use cases.

Rules:
- MUST NOT depend on logic layers (use case implementations).
- SHOULD be pure data classes.
"""

from dataclasses import dataclass


@dataclass
class IngestResult:
    """Result of ingestion operation.

    Attributes:
        documents_processed: Number of documents ingested
        concepts_created: Number of concepts created
        fragments_created: Number of fragments created
        embeddings_generated: Number of embeddings generated
    """

    documents_processed: int
    concepts_created: int
    fragments_created: int
    embeddings_generated: int
