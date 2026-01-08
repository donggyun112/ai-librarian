from typing import List, Dict, Any, Optional
import asyncio
from langchain_core.tools import Tool

from src.workers.base import BaseWorker
from src.schemas.models import WorkerType, WorkerResult
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
            # Run in thread pool if service is sync, but RagService.search appears async
            # service.search IS async def, so we await it directly on the event loop
            service = self._get_service()
            
            # The service.pipeline.run might be blocking or async? 
            # In service.py we defined async def search, calling await pipeline.run
            # So this is correct.
            results = await service.search(query)
            
            if not results:
                return self._create_result(
                    query=query,
                    content="No results found.",
                    confidence=0.0,
                    sources=["RAG"]
                )
            
            # Format content for minimal token usage but high visibility
            content_parts = []
            sources = set()
            
            for idx, item in enumerate(results, 1):
                meta = item.get("metadata", {})
                source = meta.get("source") or meta.get("file_name") or "Unknown"
                sources.add(source)
                
                # Context formatting
                # We show the fragment content mainly, maybe hint at parent context if short
                text = item["content"].strip()
                similarity = item.get("similarity", 0.0)
                
                content_parts.append(f"[{idx}] Source: {source} (Score: {similarity:.2f})\n{text}")
                
            formatted_content = "\n\n".join(content_parts)
            
            return self._create_result(
                query=query,
                content=formatted_content,
                confidence=0.8, # Placeholder confidence
                sources=list(sources)
            )
            
        except Exception as e:
            # Log error
            import traceback
            traceback.print_exc()
            return self._create_result(
                query=query,
                content=f"Error during RAG search: {str(e)}",
                confidence=0.0,
                sources=[]
            )

    def _create_result(self, query: str, content: str, confidence: float, sources: List[str]) -> WorkerResult:
        return WorkerResult(
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
