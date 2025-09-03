"""
LangChain tool for vector database search.
"""

from typing import Dict, List, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging

from ...services.vector_store import VectorStore
from ...services.embedding_service import EmbeddingService
from ...models.question import Question

logger = logging.getLogger(__name__)


class VectorSearchInput(BaseModel):
    """Input schema for vector search tool."""
    query: str = Field(description="Search query for vector database")
    top_k: int = Field(default=5, description="Number of top results to return")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity threshold")


class VectorSearchTool(BaseTool):
    """LangChain tool for searching vector database."""
    
    name: str = "vector_search"
    description: str = """
    Search the vector database for relevant documents based on semantic similarity.
    Use this tool when you need to find factual information, technical explanations,
    or detailed knowledge from the document corpus.
    
    Input should be a clear, specific query about the topic you want to search for.
    """
    args_schema: type[BaseModel] = VectorSearchInput
    vector_store: VectorStore
    embedding_service: EmbeddingService
    
    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService, **kwargs):
        super().__init__(vector_store=vector_store, embedding_service=embedding_service, **kwargs)
        
    def _run(self, query: str, top_k: int = 5, similarity_threshold: float = 0.7) -> Dict[str, Any]:
        """Execute vector search."""
        try:
            logger.info(f"Executing vector search for query: {query[:50]}...")
            
            # Convert query to embedding
            query_embedding = self.embedding_service.embed_text(query)
            
            if not query_embedding:
                return {
                    "success": False,
                    "message": "Failed to generate query embedding",
                    "documents": [],
                    "processing_time": 0
                }
            
            # Perform vector search
            results = self.vector_store.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=top_k,
                score_threshold=similarity_threshold
            )
            
            if not results:
                return {
                    "success": False,
                    "message": "No relevant documents found",
                    "documents": [],
                    "total_results": 0
                }
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result.get("content", ""),
                    "similarity_score": result.get("similarity", 0.0),
                    "metadata": result.get("metadata", {}),
                    "document_id": result.get("id", "")
                })
            
            logger.info(f"Vector search completed: {len(formatted_results)} results found")
            
            return {
                "success": True,
                "documents": formatted_results,
                "total_results": len(formatted_results),
                "query": query,
                "search_metadata": {
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                    "average_similarity": sum(r["similarity_score"] for r in formatted_results) / len(formatted_results) if formatted_results else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            return {
                "success": False,
                "message": f"Vector search error: {str(e)}",
                "documents": [],
                "total_results": 0
            }
    
    async def _arun(self, query: str, top_k: int = 5, similarity_threshold: float = 0.7) -> Dict[str, Any]:
        """Async execution (fallback to sync for now)."""
        return self._run(query, top_k, similarity_threshold)