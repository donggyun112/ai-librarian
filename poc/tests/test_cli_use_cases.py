"""Test CLI use cases (ingest/search)."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from src.rag.api.cli.ingest import main as ingest_main
from src.rag.api.cli.search import main as search_main
from src.rag.api.use_cases import IngestResult
from src.rag.retrieval import ExpandedResult, SearchResult
from src.rag.domain import View


class TestCliUseCases:
    """Test CLI commands."""

    def test_ingest_cli_success(self):
        """Test ingest command success path."""
        args = MagicMock(spec=argparse.Namespace)
        args.files = ["pyproject.toml"]
        args.force_ocr = False

        # Mock IngestUseCase and load_config
        with patch("src.rag.api.cli.ingest.IngestUseCase") as MockUseCase, \
             patch("src.rag.api.cli.ingest.load_config") as mock_load_config:
            
            # Setup config mock
            mock_load_config.return_value = MagicMock()
            
            instance = MockUseCase.return_value
            instance.execute.return_value = IngestResult(
                documents_processed=1,
                concepts_created=2,
                fragments_created=3,
                embeddings_generated=4,
            )

            # Execution
            exit_code = ingest_main(args)

            # Assertions
            assert exit_code == 0
            mock_load_config.assert_called_once()
            MockUseCase.assert_called_once()
            instance.execute.assert_called_once_with(["pyproject.toml"])


    def test_search_cli_success(self):
        """Test search command success path."""
        args = MagicMock(spec=argparse.Namespace)
        args.query = "python"
        args.view = None
        args.language = None
        args.top_k = 5
        args.no_context = False
        args.json = False
        args.optimize = False

        # Mock SearchUseCase, EmbeddingProviderFactory, and load_config
        with patch("src.rag.api.cli.search.SearchUseCase") as MockUseCase, \
             patch("src.rag.api.cli.search.EmbeddingProviderFactory") as MockFactory, \
             patch("src.rag.api.cli.search.load_config") as mock_load_config:
            
            # Setup defaults
            mock_load_config.return_value = MagicMock()
            MockFactory.create.return_value = MagicMock()
            
            instance = MockUseCase.return_value
            # Return empty list for simplicity
            instance.execute.return_value = []

            # Execution
            exit_code = search_main(args)

            # Assertions
            assert exit_code == 0
            MockUseCase.assert_called_once()
            instance.execute.assert_called_once()
