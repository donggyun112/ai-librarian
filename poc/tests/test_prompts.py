"""prompts.py 테스트"""
from datetime import datetime
from unittest.mock import MagicMock
from src.supervisor.prompts import (
    get_system_prompt,
    get_tools_description,
    SYSTEM_PROMPT_TEMPLATE,
    ToolInfo,
)


class TestGetToolsDescription:
    """get_tools_description 함수 테스트"""

    def test_extracts_tool_info(self):
        """도구 정보를 올바르게 추출하는지 확인"""
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "This is a test tool\nWith multiple lines"

        result = get_tools_description([mock_tool])

        assert "test_tool" in result
        assert "This is a test tool" in result
        assert "With multiple lines" not in result  # 첫 줄만 사용

    def test_multiple_tools(self):
        """여러 도구를 처리하는지 확인"""
        tool1 = MagicMock()
        tool1.name = "tool_a"
        tool1.description = "Description A"

        tool2 = MagicMock()
        tool2.name = "tool_b"
        tool2.description = "Description B"

        result = get_tools_description([tool1, tool2])

        assert "tool_a" in result
        assert "tool_b" in result
        assert "Description A" in result
        assert "Description B" in result


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
        assert "ALWAYS" in prompt

    def test_contains_workflow_steps(self):
        """워크플로우 단계가 있는지 확인"""
        prompt = get_system_prompt()
        assert "Step 1" in prompt or "step 1" in prompt.lower()
        assert "Search" in prompt

    def test_contains_language_placeholder(self):
        """언어 설정이 적용되는지 확인"""
        prompt = get_system_prompt(language="English")
        assert "English" in prompt

        prompt_kr = get_system_prompt(language="Korean")
        assert "Korean" in prompt_kr

    def test_contains_persona(self):
        """페르소나가 적용되는지 확인"""
        prompt = get_system_prompt(persona="Test Agent")
        assert "Test Agent" in prompt

    def test_contains_description(self):
        """설명이 적용되는지 확인"""
        prompt = get_system_prompt(description="a helpful test assistant")
        assert "a helpful test assistant" in prompt

    def test_tools_injection(self):
        """도구 정보가 동적으로 주입되는지 확인"""
        mock_tool = MagicMock()
        mock_tool.name = "custom_search"
        mock_tool.description = "Custom search tool"

        prompt = get_system_prompt(tools=[mock_tool])

        assert "custom_search" in prompt
        assert "Custom search tool" in prompt

    def test_default_tools_used_when_none(self):
        """도구가 없을 때 기본 도구 설명이 사용되는지 확인"""
        prompt = get_system_prompt(tools=None)
        assert "arag_search" in prompt
        assert "aweb_search" in prompt

    def test_contains_quality_check(self):
        """품질 체크 지침이 있는지 확인"""
        prompt = get_system_prompt()
        # Claude 4.x 베스트 프랙티스: investigate_before_answering
        assert "investigate" in prompt.lower() or "verify" in prompt.lower()


class TestSystemPromptTemplate:
    """SYSTEM_PROMPT_TEMPLATE 상수 테스트"""

    def test_has_required_placeholders(self):
        """필수 placeholder가 있는지 확인"""
        assert "{current_date}" in SYSTEM_PROMPT_TEMPLATE
        assert "{current_year}" in SYSTEM_PROMPT_TEMPLATE
        assert "{language}" in SYSTEM_PROMPT_TEMPLATE
        assert "{persona}" in SYSTEM_PROMPT_TEMPLATE
        assert "{description}" in SYSTEM_PROMPT_TEMPLATE
        assert "{tools_description}" in SYSTEM_PROMPT_TEMPLATE

    def test_has_xml_sections(self):
        """Claude 4.x 스타일 XML 섹션이 있는지 확인"""
        assert "<core_principles>" in SYSTEM_PROMPT_TEMPLATE
        assert "<available_tools>" in SYSTEM_PROMPT_TEMPLATE
        assert "<workflow>" in SYSTEM_PROMPT_TEMPLATE
        assert "<response_formatting>" in SYSTEM_PROMPT_TEMPLATE

    def test_has_action_guidance(self):
        """액션 가이드가 있는지 확인 (Claude 4.x 베스트 프랙티스)"""
        assert "<default_to_action>" in SYSTEM_PROMPT_TEMPLATE
        assert "<investigate_before_answering>" in SYSTEM_PROMPT_TEMPLATE


class TestToolInfo:
    """ToolInfo 데이터클래스 테스트"""

    def test_default_category(self):
        """기본 카테고리가 'general'인지 확인"""
        tool_info = ToolInfo(name="test", description="test desc")
        assert tool_info.category == "general"

    def test_custom_category(self):
        """커스텀 카테고리가 설정되는지 확인"""
        tool_info = ToolInfo(name="test", description="test desc", category="search")
        assert tool_info.category == "search"
