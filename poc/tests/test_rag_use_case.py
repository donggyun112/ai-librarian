"""Unit tests for RAGUseCase orchestration."""

from unittest.mock import MagicMock, Mock 
import pytest

from src.rag.api.use_cases.rag import RAGUseCase
from src.rag.shared.config import EmbeddingConfig, GenerationConfig
from src.rag.generation import GeneratedResponse
from src.rag.retrieval import SearchResult, ExpandedResult
from src.rag.domain import View

class TestRAGUseCase:
    """Test RAG orchestration logic."""

    @pytest.fixture
    def mock_deps(self):
        """Prepare mock dependencies."""
        mock_embedding_client = Mock()
        mock_embed_config = Mock(spec=EmbeddingConfig)
        mock_embed_config.pg_conn = "postgresql://user:pass@localhost:5432/db"
        mock_embed_config.collection_name = "test_collection"
        mock_embed_config.text_unit_threshold = 500
        
        mock_gen_config = Mock(spec=GenerationConfig)
        
        # Defaults
        mock_gen_config.enable_conversation = False
        mock_gen_config.llm_provider = "openai"
        mock_gen_config.llm_model = "gpt-4o"
        mock_gen_config.temperature = 0.0
        mock_gen_config.max_tokens = 1000

        return mock_embedding_client, mock_embed_config, mock_gen_config

    def test_execute_happy_path(self, mock_deps):
        """Test successful RAG execution flow."""
        client, e_conf, g_conf = mock_deps
        
        # Setup mocks
        use_case = RAGUseCase(client, e_conf, g_conf)
        
        # Mock retrieval pipeline
        use_case.retrieval = Mock()
        search_result = SearchResult(
            fragment_id="frag_1",
            parent_id="doc_1",
            view=View.TEXT,
            language="en",
            content="test content",
            similarity=0.9,
            metadata={}
        )
        mock_results = [ExpandedResult(result=search_result)]
        use_case.retrieval.retrieve.return_value = mock_results
        
        # Mock generation pipeline
        use_case.generation = Mock()
        mock_response = GeneratedResponse(
            query="test query",
            answer="Bot answer",
            sources=mock_results,
            model="gpt-4o"
        )
        use_case.generation.generate.return_value = mock_response

        # Execute
        result = use_case.execute("test query")

        # Verify orchestration
        assert result == mock_response
        use_case.retrieval.retrieve.assert_called_once_with(
            query="test query",
            top_k=5,
            expand_context=True,
        )
        use_case.generation.generate.assert_called_once_with(
            query="test query",
            results=mock_results,
            conversation=None
        )

    def test_execute_retrieval_failure(self, mock_deps):
        """Test handling of retrieval failure."""
        client, e_conf, g_conf = mock_deps
        use_case = RAGUseCase(client, e_conf, g_conf)
        
        # Simulate retrieval error
        use_case.retrieval = Mock()
        use_case.retrieval.retrieve.side_effect = RuntimeError("Vector DB down")

        # Execute should propagate error
        with pytest.raises(RuntimeError, match="Vector DB down"):
            use_case.execute("test query")

    def test_execute_with_custom_top_k(self, mock_deps):
        """Test execution with custom top_k parameter."""
        client, e_conf, g_conf = mock_deps
        use_case = RAGUseCase(client, e_conf, g_conf)
        
        use_case.retrieval = Mock()
        use_case.generation = Mock()
        
        use_case.execute(
            "test query", 
            top_k=10
        )
        
        use_case.retrieval.retrieve.assert_called_once_with(
            query="test query",
            top_k=10,
            expand_context=True,
        )
