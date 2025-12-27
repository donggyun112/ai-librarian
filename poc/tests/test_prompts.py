"""prompts.py 테스트"""
import pytest
from datetime import datetime
from src.supervisor.prompts import get_system_prompt, SYSTEM_PROMPT_TEMPLATE


class TestGetSystemPrompt:
    """get_system_prompt 함수 테스트"""

    def test_returns_string(self):
        """문자열을 반환하는지 확인"""
        prompt = get_system_prompt()
        assert isinstance(prompt, str)

    def test_contains_current_date(self):
        """현재 날짜가 포함되는지 확인"""
        prompt = get_system_prompt()
        current_date = datetime.now().strftime("%Y-%m-%d")
        assert current_date in prompt

    def test_contains_think_tool(self):
        """think 도구 사용 지침이 있는지 확인"""
        prompt = get_system_prompt()
        assert "think" in prompt
        assert "REQUIRED" in prompt or "ALWAYS" in prompt

    def test_contains_workflow_steps(self):
        """워크플로우 단계가 있는지 확인"""
        prompt = get_system_prompt()
        assert "Step 1" in prompt or "step 1" in prompt.lower()
        assert "Search" in prompt

    def test_contains_korean_query_guide(self):
        """한국어 쿼리 가이드가 있는지 확인"""
        prompt = get_system_prompt()
        assert "Korean" in prompt or "한국" in prompt

    def test_contains_quality_check(self):
        """품질 체크 지침이 있는지 확인"""
        prompt = get_system_prompt()
        assert "Quality" in prompt or "specific" in prompt.lower()

    def test_contains_good_bad_example(self):
        """좋은/나쁜 예시가 있는지 확인"""
        prompt = get_system_prompt()
        assert "GOOD" in prompt or "BAD" in prompt


class TestSystemPromptTemplate:
    """SYSTEM_PROMPT_TEMPLATE 상수 테스트"""

    def test_has_date_placeholder(self):
        """날짜 placeholder가 있는지 확인"""
        assert "{current_date}" in SYSTEM_PROMPT_TEMPLATE

    def test_tools_mentioned(self):
        """도구들이 언급되어 있는지 확인"""
        assert "think" in SYSTEM_PROMPT_TEMPLATE
        assert "arag_search" in SYSTEM_PROMPT_TEMPLATE
        assert "aweb_search" in SYSTEM_PROMPT_TEMPLATE
