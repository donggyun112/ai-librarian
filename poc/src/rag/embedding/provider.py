"""Embedding provider abstraction for multiple backends."""

import os
from typing import Any, List, Optional, Protocol, Union

import google.generativeai as genai
from loguru import logger
from langchain_openai import OpenAIEmbeddings
from langchain_voyageai import VoyageAIEmbeddings

from src.rag.shared.config import EmbeddingConfig


class EmbeddingsProtocol(Protocol):
    """Protocol for embedding clients."""

    def embed_query(self, text: str) -> List[float]:
        """Embed a query string."""
        ...

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        ...


# Type alias for embedding clients
EmbeddingsClient = Union["GeminiEmbeddings", OpenAIEmbeddings, VoyageAIEmbeddings]


class GeminiEmbeddings:
    """Thin adapter around Google Gemini embedding endpoints."""

    def __init__(self, model: str = "text-embedding-004", api_key: Optional[str] = None) -> None:
        key = api_key or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is required for GEMINI embeddings")
        genai.configure(api_key=key)
        self._genai = genai
        self._model = model

    @staticmethod
    def _extract_vec(response: Any) -> List[float]:
        if isinstance(response, dict):
            embedding = response.get("embedding") or (response.get("data") or {}).get("embedding")
        else:
            embedding = getattr(response, "embedding", None)
        if not isinstance(embedding, (list, tuple)):
            raise RuntimeError("Gemini embedding response missing 'embedding'")
        return [float(x) for x in embedding]

    def _embed_one(self, text: str, task: str) -> List[float]:
        response = self._genai.embed_content(model=self._model, content=text, task_type=task)
        return self._extract_vec(response)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents using batch API when possible."""
        if not texts:
            return []
        
        # Try batch processing first
        try:
            response = self._genai.embed_content(
                model=self._model,
                content=texts,  # Pass as list for batch processing
                task_type="retrieval_document"
            )
            # Handle batch response format
            if isinstance(response, dict):
                if "embeddings" in response:
                    # Batch response format
                    return [[float(x) for x in emb] for emb in response["embeddings"]]
                elif "embedding" in response:
                    # Single item was passed, wrap result
                    return [self._extract_vec(response)]
            # Fallback: response might have embeddings attribute
            if hasattr(response, "embeddings"):
                return [[float(x) for x in emb] for emb in response.embeddings]
        except Exception:
            pass  # Fall through to sequential processing
        
        # Fallback to sequential processing
        return [self._embed_one(text, task="retrieval_document") for text in texts]

    def embed_query(self, text: str) -> List[float]:
        """Embed a query string."""
        return self._embed_one(text, task="retrieval_query")


class EmbeddingProviderFactory:
    """Factory for producing embedding clients based on configuration."""

    @staticmethod
    def create(config: EmbeddingConfig) -> EmbeddingsClient:
        """
        Create embedding client based on config.

        Args:
            config: EmbeddingConfig with provider settings

        Returns:
            Embedding client (OpenAI, VoyageAI, or GeminiEmbeddings)
        """
        if config.embedding_provider == "gemini":
            return GeminiEmbeddings(model=config.gemini_model)
        
        if config.embedding_provider == "openai":
            # Pass dimensions for text-embedding-3 models that support dimension reduction
            return OpenAIEmbeddings(
                model=config.embedding_model,
                dimensions=config.embedding_dim,
            )

        # Default: VoyageAI (also supports OpenAI models via langchain_voyageai)
        # VoyageAI doesn't support dimensions param, but if using OpenAI models via voyage provider,
        # we need to handle it differently
        return VoyageAIEmbeddings(model=config.embedding_model)


def validate_embedding_dimension(
    embeddings: EmbeddingsProtocol,
    expected: int,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """
    Validate that embedding dimensions match expected configuration.

    Args:
        embeddings: Embedding client
        expected: Expected dimension
        provider: Provider name for error messages
        model: Model name for error messages
    """
    label_parts = []
    if provider:
        label_parts.append(provider)
    if model:
        label_parts.append(model)
    label = ":".join(label_parts) if label_parts else "embedding-provider"
    try:
        vectors = embeddings.embed_documents(["__dim_check__"])
        if not vectors or not isinstance(vectors, list) or not isinstance(vectors[0], (list, tuple)):
            logger.warning("Unable to validate embedding dimension (unexpected response)")
            return
        actual = len(vectors[0])
        if actual != expected:
            logger.warning(
                f"EMBEDDING_DIM mismatch for {label}: expected {expected}, received {actual}"
            )
    except Exception as exc:
        logger.warning(f"Skipping dimension validation for {label}: {exc}")


__all__ = [
    "EmbeddingProviderFactory",
    "EmbeddingsClient",
    "EmbeddingsProtocol",
    "GeminiEmbeddings",
    "validate_embedding_dimension",
]
