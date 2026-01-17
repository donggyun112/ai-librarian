"""Retrieval layer for OCR Vector DB.

Handles search pipeline, query interpretation, context expansion, and result grouping.

Rules:
- PKG-RET-001~005: Search pipeline, query interpretation, context expansion, grouping, reranking
- PKG-RET-BAN-001~003: MUST NOT do embedding generation, file parsing, or schema manipulation
- DEP-RET-001~002: MUST NOT import ingestion, api
- DEP-RET-ALLOW-001~004: MAY import domain, storage, embedding (clients), shared
"""

from .context import ParentContextEnricher
from .dto import ExpandedResult, QueryPlan, SearchResult, SelfQueryResult
from .grouping import ResultGrouper
from .pipeline import RetrievalPipeline
from .query import QueryInterpreter
from .search import VectorSearchEngine
from .self_query import SelfQueryRetrieverWrapper, create_self_query_retriever

__all__ = [
    # DTOs
    "QueryPlan",
    "SearchResult",
    "ExpandedResult",
    "SelfQueryResult",
    # Query
    "QueryInterpreter",
    # Search
    "VectorSearchEngine",
    # Context
    "ParentContextEnricher",
    # Grouping
    "ResultGrouper",
    # Pipeline
    "RetrievalPipeline",
    # Self-Query
    "SelfQueryRetrieverWrapper",
    "create_self_query_retriever",
]
