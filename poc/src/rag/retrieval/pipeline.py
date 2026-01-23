"""Retrieval pipeline orchestration.

Coordinates query interpretation, search, context expansion, and grouping.

Rules:
- PKG-RET-001: Search pipeline orchestration (MUST)
- DEP-RET-ALLOW-001~004: MAY import domain, storage, embedding, shared
"""

import os
from typing import List, Optional

from loguru import logger

from src.rag.shared.config import EmbeddingConfig

from .context import ParentContextEnricher, ExpandedResult
from .grouping import ResultGrouper
from .protocols import QueryOptimizerProtocol
from .query import EmbeddingClientProtocol, QueryInterpreter
from .search import SearchResult, VectorSearchEngine
from .self_query import create_self_query_retriever, NoOpQueryOptimizer


class RetrievalPipeline:
    """Orchestrates the complete retrieval pipeline.

    Pipeline stages:
    1. Query optimization (QueryOptimizer - auto-extracts metadata filters)
    2. Query interpretation (QueryInterpreter)
    3. Vector similarity search (VectorSearchEngine)
    4. Context expansion (ParentContextEnricher)
    5. Result grouping (ResultGrouper)

    Example:
        >>> pipeline = RetrievalPipeline(embeddings_client, config)
        >>> results = pipeline.retrieve("python list comprehension", view="code", top_k=5)

        # With custom QueryOptimizer:
        >>> optimizer = SelfQueryRetrieverWrapper(...)
        >>> pipeline = RetrievalPipeline(embeddings_client, config, query_optimizer=optimizer)
        >>> results = pipeline.retrieve("Python decorator code examples")
        # Automatically extracts: view="code", lang="python"
    """

    def __init__(
        self,
        embeddings_client: EmbeddingClientProtocol,
        config: EmbeddingConfig,
        query_optimizer: Optional[QueryOptimizerProtocol] = None,
        verbose: bool = False,
    ) -> None:
        self.config = config
        self.embeddings_client = embeddings_client
        self.verbose = verbose
        self.query_interpreter = QueryInterpreter(embeddings_client, config)
        self.search_engine = VectorSearchEngine(config)
        self.context_expander = ParentContextEnricher(config)
        self.grouper = ResultGrouper()

        # Query optimizer (auto-extracts metadata filters from natural language)
        if query_optimizer is not None:
            self.query_optimizer = query_optimizer
            logger.info("Using provided QueryOptimizer")
        else:
            # Auto-create SelfQueryRetriever when DB and GOOGLE_API_KEY are available
            if not config.pg_conn:
                logger.info("QueryOptimizer: Using NoOp (DB not configured)")
                self.query_optimizer = NoOpQueryOptimizer()
            elif not os.getenv("GOOGLE_API_KEY"):
                logger.info("QueryOptimizer: Using NoOp (GOOGLE_API_KEY not set)")
                self.query_optimizer = NoOpQueryOptimizer()
            else:
                try:
                    self.query_optimizer = create_self_query_retriever(
                        config=config,
                        embeddings_client=embeddings_client,
                        verbose=verbose,
                    )
                    logger.info("QueryOptimizer: Using SelfQueryRetriever")
                except Exception as e:
                    logger.warning(f"SelfQueryRetriever initialization failed, using NoOp: {e}")
                    self.query_optimizer = NoOpQueryOptimizer()


    def retrieve(
        self,
        query: str,
        view: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 10,
        expand_context: bool = True,
        deduplicate: bool = True,
    ) -> List[ExpandedResult]:
        """Execute complete retrieval pipeline.

        Args:
            query: User query string
            view: Optional view filter (text, code, image, etc.)
            language: Optional language filter (python, javascript, etc.)
            top_k: Number of results to retrieve
            expand_context: Whether to fetch parent context
            deduplicate: Whether to remove duplicate results

        Returns:
            List of search results with optional parent context
        """
        # Stage 0: Query optimization (auto-extracts filters from query)
        # Explicit filters take precedence over query optimizer auto-extraction
        has_explicit_filters = view is not None or language is not None

        if not has_explicit_filters:
            try:
                # Use query optimizer to extract filters and rewrite query
                optimized = self.query_optimizer.optimize(query)

                # Use optimized filters if no explicit filters provided
                if not view and optimized.view_filter:
                    view = optimized.view_filter
                if not language and optimized.language_filter:
                    language = optimized.language_filter

                # Use rewritten query if available
                search_query = optimized.effective_query

            except Exception as e:
                logger.warning(f"Query optimization failed, using original query: {e}")
                search_query = query
        else:
            search_query = query

        # Stage 1: Query interpretation
        query_plan = self.query_interpreter.interpret(
            query=search_query,
            view=view,
            language=language,
            top_k=top_k,
        )

        # Stage 2: Vector similarity search
        search_results = self.search_engine.search(query_plan)

        # Optional: Deduplicate
        if deduplicate:
            search_results = self.grouper.deduplicate_by_content(search_results)

        # Stage 3: Context expansion
        if expand_context:
            expanded_results = self.context_expander.expand(search_results)
        else:
            expanded_results = [ExpandedResult(result=r) for r in search_results]

        return expanded_results

    def retrieve_raw(
        self,
        query: str,
        view: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 10,
    ) -> List[SearchResult]:
        """Execute search without context expansion.

        Lighter version of retrieve() that returns only Fragment results.

        Args:
            query: User query string
            view: Optional view filter
            language: Optional language filter
            top_k: Number of results to retrieve

        Returns:
            List of Fragment search results
        """
        query_plan = self.query_interpreter.interpret(
            query=query,
            view=view,
            language=language,
            top_k=top_k,
        )
        return self.search_engine.search(query_plan)


__all__ = ["RetrievalPipeline"]
