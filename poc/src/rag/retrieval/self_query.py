"""Self-query retrieval using LangChain SelfQueryRetriever.

Automatically extracts metadata filters from natural language queries.

Rules:
- PKG-RET-001: Search pipeline orchestration (MUST)
- DEP-RET-ALLOW-001~004: MAY import domain, storage, embedding, shared
"""

import os
from typing import Any, Dict, Optional

from langchain_classic.chains.query_constructor.base import AttributeInfo
from langchain_classic.retrievers.self_query.base import SelfQueryRetriever
from langchain_core.language_models import BaseChatModel
from langchain_postgres import PGVector
from loguru import logger

from src.adapters import BaseLLMAdapter, get_adapter
from src.rag.shared.config import EmbeddingConfig

from .dto import ExtractedQuery, OptimizedQueryResult
from .query import EmbeddingClientProtocol


# Metadata schema definition for LangChain SelfQueryRetriever
METADATA_FIELD_INFO = [
    AttributeInfo(
        name="view",
        description="Content type: 'text' for explanatory documentation, 'code' for code snippets and examples",
        type="string",
    ),
    AttributeInfo(
        name="lang",
        description="Programming language of code content: 'python', 'javascript', 'java', 'typescript', 'go', etc. Only applicable when view is 'code'",
        type="string",
    ),
]

DOCUMENT_CONTENT_DESCRIPTION = """
Technical documentation and code examples from OCR-processed PDFs.
Contains explanatory text about programming concepts and code snippets in various languages.
"""


class NoOpQueryOptimizer:
    """No-op query optimizer (fallback when DB/API unavailable).

    Returns the original query without any optimization.
    Used when SelfQueryRetriever cannot be initialized.
    """

    def optimize(self, query: str) -> OptimizedQueryResult:
        """Return original query without modification.

        Args:
            query: Original user query

        Returns:
            OptimizedQueryResult with only original_query set
        """
        return OptimizedQueryResult(original_query=query)


class SelfQueryRetrieverWrapper:
    """LangChain SelfQueryRetriever integration for automatic metadata filtering.

    Implements QueryOptimizerProtocol to extract metadata filters from natural language.
    Used by RetrievalPipeline to optimize queries before vector search.

    Example:
        >>> wrapper = SelfQueryRetrieverWrapper(vectorstore, llm)
        >>> optimized = wrapper.optimize("Python 데코레이터 코드 예제")
        >>> print(optimized.view_filter)  # "code"
        >>> print(optimized.language_filter)  # "python"
    """
    
    def __init__(
        self,
        vectorstore: PGVector,
        llm: BaseChatModel,
        *,
        enable_limit: bool = True,
        verbose: bool = False,
    ) -> None:
        """Initialize SelfQueryRetriever wrapper.
        
        Args:
            vectorstore: LangChain PGVector instance
            llm: LangChain-compatible LLM (e.g., ChatGoogleGenerativeAI)
            enable_limit: Allow LLM to specify result limit
            verbose: Print debug information
        """
        self.vectorstore = vectorstore
        self.llm = llm
        self.verbose = verbose
        
        self.retriever = SelfQueryRetriever.from_llm(
            llm=llm,
            vectorstore=vectorstore,
            document_contents=DOCUMENT_CONTENT_DESCRIPTION.strip(),
            metadata_field_info=METADATA_FIELD_INFO,
            enable_limit=enable_limit,
            verbose=verbose,
        )
    
    def optimize(self, query: str) -> OptimizedQueryResult:
        """Optimize query using SelfQueryRetriever.

        Extracts rewritten query and metadata filters from natural language.

        Args:
            query: Natural language query

        Returns:
            OptimizedQueryResult with rewritten query and extracted filters
        """
        extracted = self._extract_query_and_filters(query)

        # Convert extracted filters to OptimizedQueryResult format
        view_filter = None
        language_filter = None
        metadata_filters = None

        if extracted.filters:
            view_filter = extracted.filters.get("view")
            language_filter = extracted.filters.get("lang")
            # Keep other filters in metadata_filters
            metadata_filters = {
                k: v for k, v in extracted.filters.items()
                if k not in ("view", "lang")
            }
            if not metadata_filters:
                metadata_filters = None

        return OptimizedQueryResult(
            original_query=query,
            rewritten_query=extracted.rewritten_query,
            view_filter=view_filter,
            language_filter=language_filter,
            metadata_filters=metadata_filters,
        )

    def _extract_query_and_filters(self, query: str) -> ExtractedQuery:
        """Extract rewritten query and metadata filters using SelfQueryRetriever's query_constructor.

        LangChain의 StructuredQuery에서 query(LLM이 재작성한 쿼리)와 filter를 모두 추출.

        Args:
            query: Natural language query

        Returns:
            ExtractedQuery with rewritten_query and filters
        """
        try:
            # Use the query_constructor to get structured query
            structured_query = self.retriever.query_constructor.invoke({"query": query})

            # Extract rewritten query from structured query
            rewritten_query = None
            if structured_query and hasattr(structured_query, "query"):
                rewritten_query = structured_query.query
                if rewritten_query and rewritten_query.strip():
                    rewritten_query = rewritten_query.strip()
                else:
                    rewritten_query = None

            # Extract filter from structured query
            filters = None
            if structured_query and hasattr(structured_query, 'filter') and structured_query.filter:
                filters = self._convert_filter_to_dict(structured_query.filter)

            if self.verbose and (rewritten_query or filters):
                rewrite_len = len(rewritten_query) if rewritten_query else 0
                logger.debug(
                    "[self_query] extracted filters=%s rewrite_len=%s",
                    filters,
                    rewrite_len,
                )

            return ExtractedQuery(rewritten_query=rewritten_query, filters=filters)

        except Exception as e:
            if self.verbose:
                logger.warning(f"Filter extraction failed: {e}")
            return ExtractedQuery(rewritten_query=None, filters=None)
    
    def _convert_filter_to_dict(self, filter_obj: Any) -> Dict[str, Any]:
        """Convert LangChain filter object to dictionary for PGVector.
        
        Args:
            filter_obj: LangChain filter object (Comparison, Operation, etc.)
            
        Returns:
            Dictionary suitable for PGVector filtering
        """
        # Handle different filter types from langchain_core.structured_query
        filter_dict = {}
        
        try:
            # Simple Comparison (e.g., view == "code")
            if hasattr(filter_obj, 'attribute') and hasattr(filter_obj, 'value'):
                filter_dict[filter_obj.attribute] = filter_obj.value
                return filter_dict
            
            # Operation with multiple comparisons (AND, OR)
            if hasattr(filter_obj, 'arguments') and hasattr(filter_obj, 'operator'):
                # Fallback for OR operator (not supported flattened)
                op = str(filter_obj.operator).lower()
                if "or" in op:
                     if self.verbose:
                         logger.warning(f"Ignored OR filter: {filter_obj}")
                     return {}

                for arg in filter_obj.arguments:
                    if hasattr(arg, 'attribute') and hasattr(arg, 'value'):
                        filter_dict[arg.attribute] = arg.value
                return filter_dict
                
        except Exception as e:
            if self.verbose:
                logger.warning(f"Filter conversion error: {e}")
        
        return filter_dict
    
def create_self_query_retriever(
    config: EmbeddingConfig,
    embeddings_client: EmbeddingClientProtocol,
    adapter: Optional[BaseLLMAdapter] = None,
    llm: Optional[BaseChatModel] = None,
    verbose: bool = False,
) -> SelfQueryRetrieverWrapper:
    """Factory function to create SelfQueryRetrieverWrapper.

    Args:
        config: Embedding configuration with PG connection
        embeddings_client: Embedding provider (Gemini or Voyage AI)
        adapter: LLM adapter for creating LLM instance (preferred over llm)
        llm: Optional pre-created LangChain-compatible LLM (deprecated, use adapter)
        verbose: Enable verbose logging

    Returns:
        Configured SelfQueryRetrieverWrapper

    Note:
        Adapter pattern is preferred. If both adapter and llm are None,
        a default GeminiAdapter will be used.
    """
    # Create PGVector store
    vectorstore = PGVector(
        connection=config.pg_conn,
        embeddings=embeddings_client,
        collection_name=config.collection_name,
        distance_strategy="cosine",  # lowercase required by langchain-postgres
        use_jsonb=True,
        embedding_length=config.embedding_dim,
    )

    # Create LLM using adapter pattern
    if llm is None:
        if adapter is None:
            # Use explicit LLM_PROVIDER config (default: gemini)
            llm_provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
            adapter = get_adapter(llm_provider)
            
            if llm_provider == "openai":
                model = os.environ.get("LLM_MODEL", "gpt-4o")
            else:
                model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
        else:
            # Adapter provided, use Gemini model as default
            model = "gemini-2.0-flash"

        llm = adapter.create_llm(
            model=model,
            temperature=0.0,  # Deterministic for query parsing
            max_tokens=2048,
        )

    return SelfQueryRetrieverWrapper(
        vectorstore=vectorstore,
        llm=llm,
        verbose=verbose,
    )


__all__ = [
    "SelfQueryRetrieverWrapper",
    "NoOpQueryOptimizer",
    "ExtractedQuery",
    "create_self_query_retriever",
    "METADATA_FIELD_INFO",
]
