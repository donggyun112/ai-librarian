"""tools.py 테스트"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.supervisor.tools import think, arag_search, aweb_search, TOOLS


class TestThinkTool:
    """think 도구 테스트"""

    @pytest.mark.asyncio
    async def test_returns_input_thought(self):
        """입력한 생각을 그대로 반환하는지 확인"""
        thought = "이것은 테스트 생각입니다."
        result = await think.ainvoke({"thought": thought})
        assert result == thought

    @pytest.mark.asyncio
    async def test_empty_thought(self):
        """빈 생각도 처리하는지 확인"""
        result = await think.ainvoke({"thought": ""})
        assert result == ""


class TestToolsList:
    """TOOLS 리스트 테스트"""

    def test_contains_required_tools(self):
        """필수 도구들이 포함되어 있는지 확인"""
        tool_names = [t.name for t in TOOLS]
        assert "think" in tool_names
        assert "arag_search" in tool_names
        assert "aweb_search" in tool_names

    def test_tools_count(self):
        """도구 개수 확인"""
        assert len(TOOLS) == 3


class TestAragSearch:
    """arag_search 도구 테스트"""

    @pytest.mark.asyncio
    async def test_returns_rag_result_format(self):
        """RAG 검색 결과 포맷 확인"""
        with patch("src.supervisor.tools._get_rag_worker") as mock_get_worker:
            mock_worker = MagicMock()
            mock_result = MagicMock()
            mock_result.content = "테스트 RAG 결과"
            mock_worker.execute = AsyncMock(return_value=mock_result)
            mock_get_worker.return_value = mock_worker

            result = await arag_search.ainvoke({"query": "테스트 쿼리"})

            assert "[RAG 검색 결과]" in result
            assert "테스트 RAG 결과" in result


class TestAwebSearch:
    """aweb_search 도구 테스트"""

    @pytest.mark.asyncio
    async def test_returns_web_result_format(self):
        """웹 검색 결과 포맷 확인"""
        with patch("src.supervisor.tools._get_web_worker") as mock_get_worker:
            mock_worker = MagicMock()
            mock_result = MagicMock()
            mock_result.content = "테스트 웹 결과"
            mock_worker.execute = AsyncMock(return_value=mock_result)
            mock_get_worker.return_value = mock_worker

            result = await aweb_search.ainvoke({"query": "테스트 쿼리"})

            assert "[웹 검색 결과]" in result
            assert "테스트 웹 결과" in result


class TestWorkerLazyInitialization:
    """워커 lazy initialization 테스트"""

    def test_get_rag_worker_creates_instance(self):
        """_get_rag_worker가 인스턴스 생성"""
        import src.supervisor.tools as tools_module

        # Reset global state
        tools_module._rag_worker = None

        with patch("src.supervisor.tools.RAGWorker") as MockRAGWorker:
            mock_instance = MagicMock()
            MockRAGWorker.return_value = mock_instance

            from src.supervisor.tools import _get_rag_worker
            result = _get_rag_worker()

            MockRAGWorker.assert_called_once()
            assert result == mock_instance

    def test_get_rag_worker_reuses_instance(self):
        """_get_rag_worker가 기존 인스턴스 재사용"""
        import src.supervisor.tools as tools_module

        mock_instance = MagicMock()
        tools_module._rag_worker = mock_instance

        from src.supervisor.tools import _get_rag_worker
        result = _get_rag_worker()

        assert result is mock_instance

    def test_get_web_worker_creates_instance(self):
        """_get_web_worker가 인스턴스 생성"""
        import src.supervisor.tools as tools_module

        tools_module._web_worker = None

        with patch("src.supervisor.tools.WebSearchWorker") as MockWebWorker:
            mock_instance = MagicMock()
            MockWebWorker.return_value = mock_instance

            from src.supervisor.tools import _get_web_worker
            result = _get_web_worker()

            MockWebWorker.assert_called_once()
            assert result == mock_instance

    def test_get_web_worker_reuses_instance(self):
        """_get_web_worker가 기존 인스턴스 재사용"""
        import src.supervisor.tools as tools_module

        mock_instance = MagicMock()
        tools_module._web_worker = mock_instance

        from src.supervisor.tools import _get_web_worker
        result = _get_web_worker()

        assert result is mock_instance


class TestToolDescriptions:
    """도구 설명 테스트"""

    def test_think_has_description(self):
        """think 도구에 설명이 있음"""
        assert think.description
        assert "생각" in think.description

    def test_arag_search_has_description(self):
        """arag_search 도구에 설명이 있음"""
        assert arag_search.description
        assert "문서" in arag_search.description or "검색" in arag_search.description

    def test_aweb_search_has_description(self):
        """aweb_search 도구에 설명이 있음"""
        assert aweb_search.description
        assert "웹" in aweb_search.description
