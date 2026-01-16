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
        args.dry_run = False
        args.force_ocr = False

        # Mock IngestUseCase
        with patch("src.rag.api.cli.ingest.IngestUseCase") as MockUseCase:
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
            MockUseCase.assert_called_once()
            instance.execute.assert_called_once_with(["pyproject.toml"])

    def test_ingest_cli_dry_run(self):
        """Test ingest command with --dry-run."""
        args = MagicMock(spec=argparse.Namespace)
        args.files = ["pyproject.toml"]
        args.dry_run = True
        args.force_ocr = False

        # Mock IngestUseCase
        with patch("src.rag.api.cli.ingest.IngestUseCase") as MockUseCase:
            instance = MockUseCase.return_value
            instance.execute.return_value = IngestResult(0, 0, 0, 0)

            # Execution
            exit_code = ingest_main(args)

            # Assertions
            assert exit_code == 0
            # Check if dry_run was passed to constructor
            call_args = MockUseCase.call_args
            assert call_args.kwargs.get("dry_run") is True

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

        # Mock SearchUseCase
        with patch("src.rag.api.cli.search.SearchUseCase") as MockUseCase:
            instance = MockUseCase.return_value
            # Return empty list for simplicity
            instance.execute.return_value = []

            # Execution
            exit_code = search_main(args)

            # Assertions
            assert exit_code == 0
            MockUseCase.assert_called_once()
            instance.execute.assert_called_once()
