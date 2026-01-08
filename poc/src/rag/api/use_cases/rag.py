"""RAG use case orchestration.

Implements PKG-API-004: Orchestrate packages for RAG use case.

Rules:
- DEP-API-ALLOW-003: MAY import embedding
- DEP-API-ALLOW-004: MAY import retrieval
- DEP-API-ALLOW-006: MAY import shared
- DEP-API-ALLOW-007: MAY import generation
- PKG-API-BAN-001: MUST NOT implement business logic directly
- PKG-API-BAN-002: MUST NOT access database directly
"""

from typing import List, Optional, Protocol

from generation import (
    Conversation,
    GeneratedResponse,
    GenerationPipeline,
    GeminiLLMClient,
)
from retrieval import RetrievalPipeline
from src.rag.shared.config import EmbeddingConfig, GenerationConfig


class EmbeddingClientProtocol(Protocol):
    """Protocol for embedding client (dependency inversion)."""

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query string."""
        ...


class RAGUseCase:
    """Orchestrates the full RAG pipeline.

    Implements PKG-API-004 (orchestration).

    Pipeline:
    1. Retrieve relevant context (retrieval layer with SelfQueryRetriever)
       - SelfQueryRetriever automatically extracts metadata filters (view, language)
    2. Generate response (generation layer)
    3. Format with source attribution

    Example:
        >>> use_case = RAGUseCase(embeddings_client, embed_config, gen_config)
        >>> response = use_case.execute("How do I use Python decorators?")
        >>> print(response.answer)
        >>> print(response.format_with_sources())
    """

    def __init__(
        self,
        embeddings_client: EmbeddingClientProtocol,
        embed_config: EmbeddingConfig,
        gen_config: GenerationConfig,
    ):
        """Initialize RAGUseCase.

        Args:
            embeddings_client: Client for generating query embeddings
            embed_config: Embedding/retrieval configuration
            gen_config: Generation configuration
        """
        # Retrieval pipeline with SelfQueryRetriever (auto-extracts view/language filters)
        # use_self_query=True by default, creates its own LLM internally
        self.retrieval = RetrievalPipeline(
            embeddings_client,
            embed_config,
            use_self_query=True,  # Enable SelfQueryRetriever
        )

        # LLM client for generation
        self.llm_client = GeminiLLMClient(model=gen_config.llm_model)

        # Generation pipeline
        self.generation = GenerationPipeline(
            self.llm_client,
            temperature=gen_config.temperature,
            max_tokens=gen_config.max_tokens,
        )

        # Conversation state (optional)
        self.conversation = Conversation() if gen_config.enable_conversation else None
        self.gen_config = gen_config

    def execute(
        self,
        query: str,
        *,
        view: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 5,
        use_conversation: bool = False,
    ) -> GeneratedResponse:
        """Execute full RAG pipeline.

        Args:
            query: User question
            view: Optional view filter (explicit override, otherwise auto-detected)
            language: Optional language filter (explicit override, otherwise auto-detected)
            top_k: Number of results to retrieve
            use_conversation: Whether to use conversation history

        Returns:
            Generated response with sources
        """
        # Stage 1: Retrieval with SelfQueryRetriever
        # SelfQueryRetriever automatically extracts view/language filters from the query
        # Explicit view/language parameters override auto-detection
        results = self.retrieval.retrieve(
            query=query,
            view=view,
            language=language,
            top_k=top_k,
            expand_context=True,
            use_self_query=True,  # Use SelfQueryRetriever
        )

        # Stage 2: Generation
        conversation = None
        if use_conversation and self.conversation:
            conversation = self.conversation

        response = self.generation.generate(
            query=query,
            results=results,
            conversation=conversation,
        )

        # Track conversation
        if use_conversation and self.conversation:
            self.conversation.add_turn(query, response)

        return response

    def clear_conversation(self) -> None:
        """Reset conversation history."""
        if self.conversation:
            self.conversation.clear()


__all__ = ["RAGUseCase"]
