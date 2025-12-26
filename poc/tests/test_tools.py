"""tools.py 테스트"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.supervisor.tools import think, arag_search, aweb_search, TOOLS


class TestThinkTool:
    """think 도구 테스트"""

    async def test_returns_input_thought(self):
        """입력한 생각을 그대로 반환하는지 확인"""
        thought = "이것은 테스트 생각입니다."
        result = await think.ainvoke({"thought": thought})
        assert result == thought

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
