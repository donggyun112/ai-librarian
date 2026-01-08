"""Retrieval pipeline orchestration.

Coordinates query interpretation, search, context expansion, and grouping.

Rules:
- PKG-RET-001: Search pipeline orchestration (MUST)
- DEP-RET-ALLOW-001~004: MAY import domain, storage, embedding, shared
"""

from typing import List, Optional

from src.rag.shared.config import EmbeddingConfig

from .context import ContextExpander, ExpandedResult
from .grouping import ResultGrouper
from .query import EmbeddingClientProtocol, QueryInterpreter
from .search import SearchResult, VectorSearchEngine


class RetrievalPipeline:
    """Orchestrates the complete retrieval pipeline.

    Pipeline stages:
    1. Query optimization (SelfQueryRetriever or QueryOptimizer) - optional
    2. Query interpretation (QueryInterpreter)
    3. Vector similarity search (VectorSearchEngine)
    4. Context expansion (ContextExpander)
    5. Result grouping (ResultGrouper)

    Example:
        >>> pipeline = RetrievalPipeline(embeddings_client, config)
        >>> results = pipeline.retrieve("python list comprehension", view="code", top_k=5)
        
        # With SelfQueryRetriever (recommended):
        >>> pipeline = RetrievalPipeline(embeddings_client, config, llm_client=llm, use_self_query=True)
        >>> results = pipeline.retrieve("Python ?곗퐫?덉씠??肄붾뱶 ?덉젣留?蹂댁뿬以?)
        # Automatically extracts: view="code", lang="python"
    """

    def __init__(
        self,
        embeddings_client: EmbeddingClientProtocol,
        config: EmbeddingConfig,
        llm_client=None,  # Optional LLM client for legacy QueryOptimizer
        use_self_query: bool = True,  # Use SelfQueryRetriever (recommended)
    ):
        self.config = config
        self.embeddings_client = embeddings_client
        self.query_interpreter = QueryInterpreter(embeddings_client, config)
        self.search_engine = VectorSearchEngine(config)
        self.context_expander = ContextExpander(config)
        self.grouper = ResultGrouper()
        
        # SelfQueryRetriever (preferred, auto-extracts metadata filters)
        self.self_query_retriever = None
        # Legacy QueryOptimizer (deprecated, kept for backwards compatibility)
        self.query_optimizer = None
        
        # Initialize SelfQueryRetriever (creates its own LLM internally)
        if use_self_query:
            try:
                from .self_query import create_self_query_retriever
                self.self_query_retriever = create_self_query_retriever(
                    config=config,
                    embeddings_client=embeddings_client,
                    llm=None,  # Will create LangChain LLM internally
                    verbose=False,
                )
                print("[pipeline] SelfQueryRetriever enabled for automatic filter extraction")
            except Exception as e:
                print(f"[pipeline] SelfQueryRetriever unavailable: {e}")
                # Fall through to legacy QueryOptimizer if available
                if llm_client is not None:
                    try:
                        from generation import QueryOptimizer
                        self.query_optimizer = QueryOptimizer(llm_client)
                        print("[pipeline] Falling back to QueryOptimizer (legacy mode)")
                    except ImportError:
                        pass
        elif llm_client is not None:
            # Explicitly disabled SelfQueryRetriever, use legacy QueryOptimizer
            try:
                from generation import QueryOptimizer
                self.query_optimizer = QueryOptimizer(llm_client)
                print("[pipeline] QueryOptimizer enabled (legacy mode)")
            except ImportError:
                pass


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
        if use_self_query and self.self_query_retriever:
            try:
                self_query_results = self.self_query_retriever.retrieve(query, k=top_k)
                
                if self_query_results:
                    print(f"[self_query] Retrieved {len(self_query_results)} results with auto-filters")
                    
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
                print(f"[self_query] Falling back to standard search: {e}")
        
        # Legacy path: QueryOptimizer or direct search
        search_query = query
        optimized_view = view
        optimized_language = language
        
        # Stage 0 (legacy): Query optimization
        if self.query_optimizer:
            try:
                optimized = self.query_optimizer.optimize(query)
                search_query = optimized.rewritten
                
                # Use optimizer hints if not explicitly provided
                if not view and optimized.view_hint:
                    optimized_view = optimized.view_hint
                if not language and optimized.language_hint:
                    optimized_language = optimized.language_hint
                    
                print(f"[optimize] '{query}' -> '{search_query}'")
                if optimized.keywords:
                    print(f"[optimize] Keywords: {optimized.keywords}")
            except Exception as e:
                print(f"[optimize] Fallback to original query: {e}")
        
        # Stage 1: Query interpretation
        query_plan = self.query_interpreter.interpret(
            query=search_query,
            view=optimized_view,
            language=optimized_language,
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

    def _convert_self_query_results(self, self_query_results) -> List[SearchResult]:
        """Convert SelfQueryResult to SearchResult format.
        
        Args:
            self_query_results: List of SelfQueryResult from SelfQueryRetriever
            
        Returns:
            List of SearchResult compatible with existing pipeline
        """
        from domain import View
        
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
