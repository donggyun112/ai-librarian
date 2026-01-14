"""RagWorker 컨텍스트 포맷팅 테스트"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.rag.worker import RagWorker


class TestRagWorkerFormatContext:
    """_format_context 메서드 테스트"""

    def setup_method(self):
        """테스트 전 RagWorker 인스턴스 생성"""
        self.worker = RagWorker()

    def test_format_context_basic_structure(self):
        """기본 컨텍스트 포맷 구조 확인"""
        results = [{
            "content": "Python decorator example",
            "metadata": {"source": "guide.pdf", "view": "code", "lang": "python"},
            "similarity": 0.92,
        }]
        
        formatted = self.worker._format_context(results)
        
        assert "[Source 1: guide.pdf]" in formatted
        assert "(Score: 0.92)" in formatted
        assert "Matched Content [CODE (python)]:" in formatted
        assert "Python decorator example" in formatted

    def test_format_context_includes_parent_content(self):
        """parent_content가 포함되는지 확인"""
        results = [{
            "content": "specific fragment",
            "parent_content": "This is the broader context explaining the concept in detail.",
            "metadata": {"source": "doc.pdf", "view": "text"},
            "similarity": 0.85,
        }]
        
        formatted = self.worker._format_context(results)
        
        assert "Context:" in formatted
        assert "broader context explaining" in formatted
        assert "Matched Content [TEXT]:" in formatted
        assert "specific fragment" in formatted

    def test_format_context_truncates_long_parent(self):
        """800자 초과 parent_content가 잘리는지 확인"""
        long_parent = "A" * 1000
        results = [{
            "content": "fragment",
            "parent_content": long_parent,
            "metadata": {"source": "doc.pdf"},
            "similarity": 0.8,
        }]
        
        formatted = self.worker._format_context(results)
        
        # 800자 + "..." 
        assert "A" * 800 in formatted
        assert "..." in formatted
        # 전체 1000자가 포함되지 않음
        assert "A" * 900 not in formatted

    def test_format_context_shows_view_without_language(self):
        """언어 정보 없을 때 view만 표시"""
        results = [{
            "content": "text content",
            "metadata": {"source": "doc.pdf", "view": "text"},
            "similarity": 0.75,
        }]
        
        formatted = self.worker._format_context(results)
        
        assert "Matched Content [TEXT]:" in formatted
        # (lang)이 없어야 함
        assert "TEXT (" not in formatted

    def test_format_context_multiple_results(self):
        """여러 결과 포맷 확인"""
        results = [
            {
                "content": "first result",
                "metadata": {"source": "a.pdf", "view": "text"},
                "similarity": 0.9,
            },
            {
                "content": "second result",
                "metadata": {"source": "b.pdf", "view": "code", "lang": "javascript"},
                "similarity": 0.8,
            },
        ]
        
        formatted = self.worker._format_context(results)
        
        assert "[Source 1: a.pdf]" in formatted
        assert "[Source 2: b.pdf]" in formatted
        assert "first result" in formatted
        assert "second result" in formatted
        assert "========================================" in formatted

    def test_format_context_defaults(self):
        """메타데이터 기본값 처리 확인"""
        results = [{
            "content": "content without metadata",
            "metadata": {},
            "similarity": 0.5,
        }]
        
        formatted = self.worker._format_context(results)
        
        assert "[Source 1: unknown]" in formatted
        assert "Matched Content [TEXT]:" in formatted


class TestRagWorkerExecute:
    """execute 메서드 테스트"""

    def setup_method(self):
        """테스트 전 RagWorker 인스턴스 생성"""
        self.worker = RagWorker()

    @pytest.mark.asyncio
    async def test_execute_returns_formatted_result(self):
        """execute가 포맷된 결과를 반환하는지 확인"""
        mock_service = MagicMock()
        mock_service.search = AsyncMock(return_value=[{
            "content": "test content",
            "parent_content": "parent context here",
            "metadata": {"source": "test.pdf", "view": "text"},
            "similarity": 0.88,
        }])
        
        with patch.object(self.worker, "_get_service", return_value=mock_service):
            result = await self.worker.execute("test query")
        
        assert "test.pdf" in result.content
        assert "test content" in result.content
        assert "Context:" in result.content
        assert result.confidence == 0.88
        assert "test.pdf" in result.sources

    @pytest.mark.asyncio
    async def test_execute_no_results(self):
        """결과 없을 때 처리 확인"""
        mock_service = MagicMock()
        mock_service.search = AsyncMock(return_value=[])
        
        with patch.object(self.worker, "_get_service", return_value=mock_service):
            result = await self.worker.execute("no match query")
        
        assert result.content == "No results found."
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_execute_uses_max_similarity_as_confidence(self):
        """confidence가 최대 similarity 값인지 확인"""
        mock_service = MagicMock()
        mock_service.search = AsyncMock(return_value=[
            {"content": "a", "metadata": {}, "similarity": 0.7},
            {"content": "b", "metadata": {}, "similarity": 0.95},
            {"content": "c", "metadata": {}, "similarity": 0.8},
        ])
        
        with patch.object(self.worker, "_get_service", return_value=mock_service):
            result = await self.worker.execute("query")
        
        assert result.confidence == 0.95
