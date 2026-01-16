from typing import Any, Dict, List

from langchain_core.embeddings import Embeddings

from src.rag.embedding.provider import EmbeddingProviderFactory
from src.rag.retrieval import RetrievalPipeline
from src.rag.retrieval.dto import ExpandedResult
from src.rag.retrieval.query import EmbeddingClientProtocol
from src.rag.shared.config import load_config as load_rag_config


class EmbeddingClientAdapter(EmbeddingClientProtocol):
    """Adapter to make LangChain Embeddings compatible with RAG protocol."""
    
    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings
        
    def embed_query(self, text: str) -> List[float]:
        return self._embeddings.embed_query(text)
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embeddings.embed_documents(texts)


class RagService:
    """
    Facade for RAG functionality.
    Exposes a simple API for searching the vector database.
    """

    def __init__(self) -> None:
        # 1. Load RAG configuration
        self.config = load_rag_config()

        # 2. Create embeddings via factory (respects EMBEDDING_PROVIDER env var)
        embeddings = EmbeddingProviderFactory.create(self.config)

        # 3. Create Adapter
        embedding_client = EmbeddingClientAdapter(embeddings)

        # 4. Initialize Pipeline
        self.pipeline = RetrievalPipeline(
            embeddings_client=embedding_client,
            config=self.config,
        )

    async def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for documents and return structured results.
        
        Args:
            query: The search query string.
            k: Number of results to return.
            
        Returns:
            List of dictionaries containing:
            - content: The document fragment content
            - metadata: Fragment metadata
            - similarity: Similarity score (0-1)
            - parent_content: Full content of the parent document (context)
            - parent_metadata: Metadata of the parent document
        """
        # Execute search via pipeline (retrieve is synchronous)
        results: List[ExpandedResult] = self.pipeline.retrieve(query, top_k=k)

        # Format results for the caller
        formatted_results = []
        for res in results:
            formatted_results.append({
                "content": res.result.content,
                "metadata": res.result.metadata,
                "similarity": res.result.similarity,
                "parent_content": res.parent_content,
                "parent_metadata": res.parent_metadata,
            })
            
        return formatted_results
