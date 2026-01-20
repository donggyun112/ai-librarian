"""Tests for IngestUseCase including PDF parser selection."""

from unittest.mock import MagicMock, patch

import pytest

from src.rag.shared.config import EmbeddingConfig


def create_test_config(**overrides) -> EmbeddingConfig:
    """Create minimal test configuration."""
    defaults = {
        "pg_conn": "postgresql://test:test@localhost/test",
        "collection_name": "test",
        "embedding_model": "test",
        "embedding_dim": 768,
        "embedding_provider": "openai",
        "gemini_model": "test",
        "custom_schema_write": False,
        "rate_limit_rpm": 0,
        "max_chars_per_request": 0,
        "max_items_per_request": 0,
        "max_docs_to_embed": 0,
        "parent_mode": "unit",
        "page_regex": "",
        "section_regex": "",
        "enable_auto_ocr": False,
        "force_ocr": False,
        "ocr_languages": "eng",
        "pdf_parser": "pymupdf",
        "enable_image_ocr": False,
        "gemini_ocr_model": "test",
        "parent_context_limit": 2000,
        "text_unit_threshold": 500,
    }
    defaults.update(overrides)
    return EmbeddingConfig(**defaults)


class TestPdfParserSelection:
    """Test PDF parser selection via config."""

    def test_pymupdf_parser_selected_by_default(self):
        """PyMuPDF parser should be used by default."""
        config = create_test_config(pdf_parser="pymupdf")

        # Mock all dependencies to avoid DB/API connections
        with patch("src.rag.api.use_cases.ingest.DocumentRepository"), \
             patch("src.rag.api.use_cases.ingest.ConceptRepository"), \
             patch("src.rag.api.use_cases.ingest.FragmentRepository"), \
             patch("src.rag.api.use_cases.ingest.EmbeddingRepository"), \
             patch("src.rag.api.use_cases.ingest.DbSchemaManager"), \
             patch("src.rag.api.use_cases.ingest.CascadeDeleter"), \
             patch("src.rag.api.use_cases.ingest.EmbeddingProviderFactory"), \
             patch("src.rag.api.use_cases.ingest.VectorStoreWriter"), \
             patch("src.rag.api.use_cases.ingest.ParentDocumentStore"):

            from src.rag.api.use_cases import IngestUseCase
            from src.rag.ingestion import PyMuPdfParser

            use_case = IngestUseCase(config)

            assert isinstance(use_case.pdf_parser, PyMuPdfParser)

    def test_pdfminer_parser_selected_when_configured(self):
        """PdfParser (pdfminer) should be used when configured."""
        config = create_test_config(pdf_parser="pdfminer")

        # Mock all dependencies to avoid DB/API connections
        with patch("src.rag.api.use_cases.ingest.DocumentRepository"), \
             patch("src.rag.api.use_cases.ingest.ConceptRepository"), \
             patch("src.rag.api.use_cases.ingest.FragmentRepository"), \
             patch("src.rag.api.use_cases.ingest.EmbeddingRepository"), \
             patch("src.rag.api.use_cases.ingest.DbSchemaManager"), \
             patch("src.rag.api.use_cases.ingest.CascadeDeleter"), \
             patch("src.rag.api.use_cases.ingest.EmbeddingProviderFactory"), \
             patch("src.rag.api.use_cases.ingest.VectorStoreWriter"), \
             patch("src.rag.api.use_cases.ingest.ParentDocumentStore"):

            from src.rag.api.use_cases import IngestUseCase
            from src.rag.ingestion import PdfParser

            use_case = IngestUseCase(config)

            assert isinstance(use_case.pdf_parser, PdfParser)


class TestIngestUseCaseExecute:
    """Test IngestUseCase.execute with mocked dependencies."""

    def test_execute_calls_parse_and_embed(self, tmp_path):
        """Execute should parse files, create concepts, and generate embeddings."""
        config = create_test_config()

        # Create test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nSome content here for testing.")

        # Mock all dependencies
        with patch("src.rag.api.use_cases.ingest.DocumentRepository") as MockDocRepo, \
             patch("src.rag.api.use_cases.ingest.ConceptRepository") as MockConceptRepo, \
             patch("src.rag.api.use_cases.ingest.FragmentRepository") as MockFragmentRepo, \
             patch("src.rag.api.use_cases.ingest.EmbeddingRepository"), \
             patch("src.rag.api.use_cases.ingest.DbSchemaManager") as MockSchema, \
             patch("src.rag.api.use_cases.ingest.CascadeDeleter") as MockCascade, \
             patch("src.rag.api.use_cases.ingest.EmbeddingProviderFactory"), \
             patch("src.rag.api.use_cases.ingest.VectorStoreWriter") as MockWriter, \
             patch("src.rag.api.use_cases.ingest.ParentDocumentStore"):

            MockWriter.return_value.upsert_batch.return_value = 1

            from src.rag.api.use_cases import IngestUseCase

            use_case = IngestUseCase(config)
            result = use_case.execute([str(test_file)])

            # Verify file was processed
            assert result.documents_processed == 1
            # Document repo should be called
            MockDocRepo.return_value.save.assert_called()
            # Schema manager should ensure indexes
            MockSchema.return_value.ensure_indexes.assert_called()
