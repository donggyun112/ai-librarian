"""Retrieval pipeline orchestration.

Coordinates query interpretation, search, context expansion, and grouping.

Rules:
- PKG-RET-001: Search pipeline orchestration (MUST)
- DEP-RET-ALLOW-001~004: MAY import domain, storage, embedding, shared
"""

import os
from typing import List, Optional

from loguru import logger

from src.rag.domain import View
from src.rag.shared.config import EmbeddingConfig

from .context import ParentContextEnricher, ExpandedResult
from .dto import SelfQueryResult
from .grouping import ResultGrouper
from .query import EmbeddingClientProtocol, QueryInterpreter
from .search import SearchResult, VectorSearchEngine
from .self_query import create_self_query_retriever


class RetrievalPipeline:
    """Orchestrates the complete retrieval pipeline.

    Pipeline stages:
    1. Query optimization (SelfQueryRetriever - auto-extracts metadata filters)
    2. Query interpretation (QueryInterpreter)
    3. Vector similarity search (VectorSearchEngine)
    4. Context expansion (ParentContextEnricher)
    5. Result grouping (ResultGrouper)

    Example:
        >>> pipeline = RetrievalPipeline(embeddings_client, config)
        >>> results = pipeline.retrieve("python list comprehension", view="code", top_k=5)
        
        # With SelfQueryRetriever (default, recommended):
        >>> pipeline = RetrievalPipeline(embeddings_client, config, use_self_query=True)
        >>> results = pipeline.retrieve("Python decorator code examples")
        # Automatically extracts: view="code", lang="python"
    """

    def __init__(
        self,
        embeddings_client: EmbeddingClientProtocol,
        config: EmbeddingConfig,
        use_self_query: bool = True,
        verbose: bool = False,
    ) -> None:
        self.config = config
        self.embeddings_client = embeddings_client
        self.verbose = verbose
        self.query_interpreter = QueryInterpreter(embeddings_client, config)
        self.search_engine = VectorSearchEngine(config)
        self.context_expander = ParentContextEnricher(config)
        self.grouper = ResultGrouper()

        # SelfQueryRetriever (auto-extracts metadata filters from natural language)
        self.self_query_retriever = None

        # SelfQuery auto-enables when DB and GOOGLE_API_KEY are available
        if use_self_query:
            if not config.pg_conn:
                logger.info("SelfQueryRetriever skipped: DB not configured")
            elif not os.getenv("GOOGLE_API_KEY"):
                logger.info("SelfQueryRetriever skipped: GOOGLE_API_KEY not set")
            else:
                try:
                    self.self_query_retriever = create_self_query_retriever(
                        config=config,
                        embeddings_client=embeddings_client,
                        verbose=verbose,
                    )
                    logger.info("SelfQueryRetriever enabled")
                except Exception as e:
                    logger.warning(f"SelfQueryRetriever initialization failed: {e}")


    def retrieve(
        self,
        query: str,
        view: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 10,
        expand_context: bool = True,
        deduplicate: bool = True,
        use_self_query: bool = True,  # Use SelfQueryRetriever for this request
    ) -> List[ExpandedResult]:
        """Execute complete retrieval pipeline.

        Args:
            query: User query string
            view: Optional view filter (text, code, image, etc.)
            language: Optional language filter (python, javascript, etc.)
            top_k: Number of results to retrieve
            expand_context: Whether to fetch parent context
            deduplicate: Whether to remove duplicate results
            use_self_query: Whether to use SelfQueryRetriever (if available)

        Returns:
            List of search results with optional parent context
        """
        # Stage 0: SelfQueryRetriever path (auto-extracts filters from query)
        # Explicit filters take precedence over SelfQuery auto-extraction
        has_explicit_filters = view is not None or language is not None

        if use_self_query and self.self_query_retriever and not has_explicit_filters:
            try:
                self_query_results = self.self_query_retriever.retrieve(query, k=top_k)
                
                if self_query_results:
                    rewritten = self_query_results[0].rewritten_query if self_query_results else None
                    
                    # Convert SelfQueryResult to SearchResult format
                    search_results = self._convert_self_query_results(self_query_results)
                    
                    # Optional: Deduplicate
                    if deduplicate:
                        search_results = self.grouper.deduplicate_by_content(search_results)
                    
                    # Stage 3: Context expansion
                    if expand_context:
                        return self.context_expander.expand(search_results)
                    else:
                        return [ExpandedResult(result=r) for r in search_results]
            except Exception as e:
                logger.warning(f"SelfQuery failed, falling back to standard search: {e}")

        
        # Stage 1: Query interpretation
        query_plan = self.query_interpreter.interpret(
            query=query,
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

    def _convert_self_query_results(self, self_query_results: List[SelfQueryResult]) -> List[SearchResult]:
        """Convert SelfQueryResult to SearchResult format.

        Args:
            self_query_results: List of SelfQueryResult from SelfQueryRetriever

        Returns:
            List of SearchResult compatible with existing pipeline
        """
        results = []
        for i, sqr in enumerate(self_query_results):
            # Parse view from metadata
            view_str = sqr.metadata.get("view", "text")
            try:
                view = View(view_str) if view_str else View.TEXT
            except ValueError:
                view = View.TEXT
            
            results.append(SearchResult(
                fragment_id=sqr.metadata.get("fragment_id", f"sq_{i}"),
                parent_id=sqr.metadata.get("parent_id", "unknown"),
                view=view,
                language=sqr.metadata.get("lang"),
                content=sqr.content,
                similarity=sqr.score if sqr.score is not None else 0.9,  # Default high score
                metadata=sqr.metadata,
            ))
        
        return results

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
