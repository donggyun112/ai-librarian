import asyncio
import traceback
from typing import Any, Dict, List, Optional

from langchain_core.tools import Tool

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker

from .service import RagService


class RagWorker(BaseWorker):
    """
    Worker for RAG (Retrieval Augmented Generation) search.
    Wraps RagService to be used as a tool in the Supervisor agent.
    """
    
    def __init__(self):
        self._service: Optional[RagService] = None

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.RAG_SEARCH

    def _get_service(self) -> RagService:
        """Lazy initialization of RagService"""
        if self._service is None:
            self._service = RagService()
        return self._service

    async def execute(self, query: str) -> WorkerResult:
        """
        Execute RAG search.
        """
        try:
            service = self._get_service()
            results = await service.search(query)
            
            if not results:
                return self._create_result(
                    query=query,
                    content="No results found.",
                    confidence=0.0,
                    sources=["RAG"]
                )
            
            # Format context using enhanced formatter
            formatted_content = self._format_context(results)
            sources = list({
                item.get("metadata", {}).get("source") 
                or item.get("metadata", {}).get("file_name") 
                or "RAG" 
                for item in results
            })
            
            # Use max similarity as confidence
            max_similarity = max(
                (item.get("similarity", 0.0) for item in results),
                default=0.0
            )
            
            return self._create_result(
                query=query,
                content=formatted_content,
                confidence=max_similarity,
                sources=sources
            )
            
        except Exception as e:
            traceback.print_exc()
            return self._create_result(
                query=query,
                content=f"Error during RAG search: {str(e)}",
                confidence=0.0,
                sources=[]
            )

    def _format_context(self, results: List[Dict[str, Any]]) -> str:
        """Format RAG results with parent context for Supervisor LLM.
        
        Applies GenerationPipeline's PromptTemplate.build_context() structure:
        - Parent context (broader context, truncated to 800 chars)
        - Matched fragment with view/language labels
        - Source citations [Source N: filename]
        """
        context_parts = []
        
        for i, item in enumerate(results, 1):
            meta = item.get("metadata", {})
            source = meta.get("source") or meta.get("file_name") or "unknown"
            view = meta.get("view", "text").upper()
            lang = meta.get("lang")
            similarity = item.get("similarity", 0.0)
            
            # Build context entry
            entry = f"[Source {i}: {source}] (Score: {similarity:.2f})\n"
            
            # Parent context (broader document context)
            parent_content = item.get("parent_content")
            if parent_content:
                parent_preview = parent_content[:800]
                if len(parent_content) > 800:
                    parent_preview += "..."
                entry += f"Context:\n{parent_preview}\n\n"
            
            # Matched fragment with view/language label
            view_label = f"{view} ({lang})" if lang else view
            entry += f"Matched Content [{view_label}]:\n{item['content'].strip()}\n"
            
            context_parts.append(entry)
        
        # Join with separator
        separator = "\n" + "=" * 40 + "\n"
        return separator + separator.join(context_parts)

    def _create_result(self, query: str, content: str, confidence: float, sources: List[str]) -> WorkerResult:
        return WorkerResult(
            worker=self.worker_type,
            query=query,
            content=content,
            confidence=confidence,
            sources=sources
        )


def create_rag_tool() -> Tool:
    """Create a LangChain Tool for RAG Search."""
    worker = RagWorker()
    
    async def _asearch(query: str) -> str:
        result = await worker.execute(query)
        return result.content
        
    return Tool(
        name="rag_search",
        # We must provide a sync func or handle async properly.
        # Tool supports `coroutine` argument for async tools.
        func=lambda q: "This tool is async only",
        coroutine=_asearch,
        description="Search technical documentation/codebase using RAG."
    )
