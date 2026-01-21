"""RagWorker context formatting tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.rag.worker import RagWorker
from src.rag.retrieval import ExpandedResult, SearchResult
from src.rag.domain import View


class TestRagWorkerFormatContext:
    """Tests for _format_context method."""

    def setup_method(self):
        """Create RagWorker instance."""
        self.worker = RagWorker()

    def _create_result(self, content, source, view=View.TEXT, lang=None, similarity=0.9, parent_content=None):
        return ExpandedResult(
            result=SearchResult(
                fragment_id="f1",
                parent_id="p1", 
                view=view,
                content=content,
                similarity=similarity,
                metadata={"source": source, "file_name": source},
                language=lang
            ),
            parent_content=parent_content
        )

    def test_format_context_basic_structure(self):
        """Check basic context format structure."""
        results = [
            self._create_result(
                content="Python decorator example",
                source="guide.pdf", 
                view=View.CODE,
                lang="python",
                similarity=0.92
            )
        ]
        
        formatted = self.worker._format_context(results)
        
        assert "[Source 1: guide.pdf]" in formatted
        assert "(Score: 0.92)" in formatted
        assert "Matched Content [CODE (python)]:" in formatted
        assert "Python decorator example" in formatted

    def test_format_context_includes_parent_content(self):
        """Check if parent_content is included."""
        results = [
            self._create_result(
                content="specific fragment",
                source="doc.pdf",
                view=View.TEXT,
                parent_content="This is the broader context explaining the concept in detail.",
                similarity=0.85
            )
        ]
        
        formatted = self.worker._format_context(results)
        
        assert "Context:" in formatted
        assert "broader context explaining" in formatted
        assert "Matched Content [TEXT]:" in formatted
        assert "specific fragment" in formatted

    def test_format_context_truncates_long_parent(self):
        """Check if parent_content > 800 chars is truncated."""
        long_parent = "A" * 1000
        results = [
            self._create_result(
                content="fragment",
                source="doc.pdf",
                parent_content=long_parent,
                similarity=0.8
            )
        ]
        
        formatted = self.worker._format_context(results)
        
        # 800 chars + "..." 
        assert "A" * 800 in formatted
        assert "..." in formatted
        # Full 1000 chars should not be present
        assert "A" * 900 not in formatted

    def test_format_context_shows_view_without_language(self):
        """Check format when language is missing."""
        results = [
            self._create_result(
                content="text content",
                source="doc.pdf",
                view=View.TEXT,
                lang=None,
                similarity=0.75
            )
        ]
        
        formatted = self.worker._format_context(results)
        
        assert "Matched Content [TEXT]:" in formatted
        # (lang) should not be present
        assert "TEXT (" not in formatted

    def test_format_context_multiple_results(self):
        """Check formatting of multiple results."""
        results = [
            self._create_result(
                content="first result",
                source="a.pdf",
                view=View.TEXT,
                similarity=0.9
            ),
            self._create_result(
                content="second result",
                source="b.pdf",
                view=View.CODE,
                lang="javascript",
                similarity=0.8
            )
        ]
        
        formatted = self.worker._format_context(results)
        
        assert "[Source 1: a.pdf]" in formatted
        assert "[Source 2: b.pdf]" in formatted
        assert "first result" in formatted
        assert "second result" in formatted
        assert "========================================" in formatted

    def test_format_context_defaults(self):
        """Check metadata defaults."""
        # Manually create result with minimal fields to test defaults
        res = ExpandedResult(
            result=SearchResult(
                fragment_id="f1",
                parent_id="p1", 
                view=View.TEXT,
                content="content without metadata",
                similarity=0.5,
                metadata={}, # Empty metadata
                language=None
            ),
            parent_content=None
        )
        
        formatted = self.worker._format_context([res])
        
        assert "[Source 1: unknown]" in formatted
        assert "Matched Content [TEXT]:" in formatted


class TestRagWorkerExecute:
    """Tests for execute method."""

    def setup_method(self):
        """Create RagWorker instance."""
        self.worker = RagWorker()

    @pytest.mark.asyncio
    async def test_execute_returns_formatted_result(self):
        """execute should return formatted result string in content."""
        # Use helper to create DTO
        expanded_result = ExpandedResult(
            result=SearchResult(
                fragment_id="f1",
                parent_id="p1", 
                view=View.TEXT,
                content="test content",
                similarity=0.88,
                metadata={"source": "test.pdf", "file_name": "test.pdf"},
                language="python"
            ),
            parent_content="parent context here"
        )
        
        mock_use_case = MagicMock()
        mock_use_case.execute = MagicMock(return_value=[expanded_result])
        
        with patch.object(self.worker, "_get_use_case", return_value=mock_use_case):
            result = await self.worker.execute("test query")
        
        assert "test.pdf" in result.content
        assert "test content" in result.content
        assert "Context:" in result.content
        assert result.confidence == 0.88
        assert "test.pdf" in result.sources

    @pytest.mark.asyncio
    async def test_execute_no_results(self):
        """Handle no results."""
        mock_use_case = MagicMock()
        mock_use_case.execute = MagicMock(return_value=[])
        
        with patch.object(self.worker, "_get_use_case", return_value=mock_use_case):
            result = await self.worker.execute("no match query")
        
        assert result.content == "No results found."
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_execute_uses_max_similarity_as_confidence(self):
        """confidence should be max similarity."""
        r1 = ExpandedResult(result=SearchResult(fragment_id="1", parent_id="p", view=View.TEXT, content="a", similarity=0.7, metadata={}, language=None))
        r2 = ExpandedResult(result=SearchResult(fragment_id="2", parent_id="p", view=View.TEXT, content="b", similarity=0.95, metadata={}, language=None))
        r3 = ExpandedResult(result=SearchResult(fragment_id="3", parent_id="p", view=View.TEXT, content="c", similarity=0.8, metadata={}, language=None))

        mock_use_case = MagicMock()
        mock_use_case.execute = MagicMock(return_value=[r1, r2, r3])
        
        with patch.object(self.worker, "_get_use_case", return_value=mock_use_case):
            result = await self.worker.execute("query")
        
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_execute_db_not_configured_returns_clear_message(self):
        """Worker should return clear message when DB is not configured."""
        from src.rag.shared.exceptions import DatabaseNotConfiguredError

        mock_use_case = MagicMock()
        mock_use_case.execute = MagicMock(
            side_effect=DatabaseNotConfiguredError("Database not configured")
        )

        with patch.object(self.worker, "_get_use_case", return_value=mock_use_case):
            result = await self.worker.execute("test query")

        # Should return clear error message, not crash
        assert "사용 불가" in result.content
        assert "데이터베이스" in result.content
        assert result.confidence == 0.0
        # Verify success/error flags
        assert result.success is False
        assert result.error is not None
        assert "DatabaseNotConfiguredError" in result.error

    @pytest.mark.asyncio
    async def test_execute_general_exception_returns_failure(self):
        """Worker should return success=False on general exception."""
        mock_use_case = MagicMock()
        mock_use_case.execute = MagicMock(
            side_effect=Exception("Unexpected error")
        )

        with patch.object(self.worker, "_get_use_case", return_value=mock_use_case):
            result = await self.worker.execute("test query")

        assert "오류가 발생했습니다" in result.content
        assert result.confidence == 0.0
        assert result.success is False
        assert result.error is not None
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_execute_success_returns_true(self):
        """Worker should return success=True on successful execution."""
        expanded_result = ExpandedResult(
            result=SearchResult(
                fragment_id="f1",
                parent_id="p1",
                view=View.TEXT,
                content="test content",
                similarity=0.88,
                metadata={"source": "test.pdf"},
                language=None
            ),
            parent_content=None
        )

        mock_use_case = MagicMock()
        mock_use_case.execute = MagicMock(return_value=[expanded_result])

        with patch.object(self.worker, "_get_use_case", return_value=mock_use_case):
            result = await self.worker.execute("test query")

        assert result.success is True
        assert result.error is None
        assert result.confidence == 0.88

    @pytest.mark.asyncio
    async def test_execute_no_results_returns_success_true(self):
        """No results should still be success=True (not an error)."""
        mock_use_case = MagicMock()
        mock_use_case.execute = MagicMock(return_value=[])

        with patch.object(self.worker, "_get_use_case", return_value=mock_use_case):
            result = await self.worker.execute("no match query")

        assert result.content == "No results found."
        assert result.success is True
        assert result.error is None


class TestVectorSearchEngineDbNotConfigured:
    """Tests for VectorSearchEngine when DB is not configured."""

    def test_search_raises_error_when_db_not_configured(self):
        """search() should raise DatabaseNotConfiguredError when pg_conn is empty."""
        from src.rag.retrieval.search import VectorSearchEngine
        from src.rag.retrieval.dto import QueryPlan
        from src.rag.shared.config import EmbeddingConfig
        from src.rag.shared.exceptions import DatabaseNotConfiguredError

        # Create config with empty pg_conn
        config = EmbeddingConfig(
            pg_conn="",  # Empty - DB not configured
            collection_name="test",
            embedding_model="test",
            embedding_dim=768,
            embedding_provider="gemini",
            gemini_model="test",
            custom_schema_write=False,
            rate_limit_rpm=0,
            max_chars_per_request=0,
            max_items_per_request=0,
            max_docs_to_embed=0,
            parent_mode="unit",
            page_regex="",
            section_regex="",
            enable_auto_ocr=False,
            force_ocr=False,
            ocr_languages="eng",
            pdf_parser="pymupdf",
            enable_image_ocr=False,
            gemini_ocr_model="test",
            parent_context_limit=2000,
            text_unit_threshold=500,
        )

        engine = VectorSearchEngine(config)
        
        # Create a dummy query plan
        query_plan = QueryPlan(
            query_text="test",
            query_embedding=[0.1] * 768,
            top_k=5,
        )

        with pytest.raises(DatabaseNotConfiguredError) as exc_info:
            engine.search(query_plan)
        
        assert "PG_CONN" in str(exc_info.value)


class TestParentContextEnricherDbNotConfigured:
    """Tests for ParentContextEnricher when DB is not configured."""

    def test_expand_raises_error_when_db_not_configured(self):
        """expand() should raise DatabaseNotConfiguredError when pg_conn is empty."""
        from src.rag.retrieval.context import ParentContextEnricher
        from src.rag.shared.config import EmbeddingConfig
        from src.rag.shared.exceptions import DatabaseNotConfiguredError

        # Create config with empty pg_conn
        config = EmbeddingConfig(
            pg_conn="",  # Empty - DB not configured
            collection_name="test",
            embedding_model="test",
            embedding_dim=768,
            embedding_provider="gemini",
            gemini_model="test",
            custom_schema_write=False,
            rate_limit_rpm=0,
            max_chars_per_request=0,
            max_items_per_request=0,
            max_docs_to_embed=0,
            parent_mode="unit",
            page_regex="",
            section_regex="",
            enable_auto_ocr=False,
            force_ocr=False,
            ocr_languages="eng",
            pdf_parser="pymupdf",
            enable_image_ocr=False,
            gemini_ocr_model="test",
            parent_context_limit=2000,
            text_unit_threshold=500,
        )

        enricher = ParentContextEnricher(config)
        
        # Create dummy search results
        results = [
            SearchResult(
                fragment_id="f1",
                parent_id="p1",
                view=View.TEXT,
                content="test",
                similarity=0.9,
                metadata={},
                language=None,
            )
        ]

        with pytest.raises(DatabaseNotConfiguredError) as exc_info:
            enricher.expand(results)
        
        assert "not configured" in str(exc_info.value).lower()

