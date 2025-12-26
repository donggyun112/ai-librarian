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

    def test_contains_current_year(self):
        """현재 연도가 포함되는지 확인"""
        prompt = get_system_prompt()
        current_year = datetime.now().strftime("%Y")
        assert current_year in prompt

    def test_contains_think_tool_required(self):
        """think 도구가 REQUIRED로 표시되는지 확인"""
        prompt = get_system_prompt()
        assert "think (REQUIRED)" in prompt
        assert "MUST call" in prompt

    def test_contains_clarifying_question_instruction(self):
        """모호한 질문시 clarifying question 지침이 있는지 확인"""
        prompt = get_system_prompt()
        assert "clarifying question" in prompt

    def test_contains_korean_cultural_query_guide(self):
        """한국 문화 쿼리 가이드가 있는지 확인"""
        prompt = get_system_prompt()
        assert "K-pop" in prompt or "Korean fashion" in prompt

    def test_contains_ambiguous_request_handling(self):
        """모호한 요청 처리 섹션이 있는지 확인"""
        prompt = get_system_prompt()
        assert "Ambiguous" in prompt or "ambiguous" in prompt


class TestSystemPromptTemplate:
    """SYSTEM_PROMPT_TEMPLATE 상수 테스트"""

    def test_has_placeholders(self):
        """필요한 placeholder가 있는지 확인"""
        assert "{current_date}" in SYSTEM_PROMPT_TEMPLATE
        assert "{current_year}" in SYSTEM_PROMPT_TEMPLATE

    def test_tools_section_exists(self):
        """도구 섹션이 있는지 확인"""
        assert "## think" in SYSTEM_PROMPT_TEMPLATE
        assert "## arag_search" in SYSTEM_PROMPT_TEMPLATE
        assert "## aweb_search" in SYSTEM_PROMPT_TEMPLATE
