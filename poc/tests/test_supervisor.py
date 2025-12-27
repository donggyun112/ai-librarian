"""supervisor.py 테스트"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.supervisor.supervisor import (
    Supervisor,
    AgentState,
    SEARCH_TOOLS,
    THINK_TOOL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MAX_STEPS,
)
from src.schemas.models import StreamEventType


class TestSupervisorConstants:
    """상수 테스트"""

    def test_search_tools(self):
        """검색 도구 목록 확인"""
        assert "arag_search" in SEARCH_TOOLS
        assert "aweb_search" in SEARCH_TOOLS

    def test_think_tool(self):
        """think 도구 이름 확인"""
        assert THINK_TOOL == "think"

    def test_default_values(self):
        """기본값 확인"""
        assert DEFAULT_MAX_TOKENS == 4096
        assert DEFAULT_MAX_STEPS == 10


class TestSupervisorInit:
    """Supervisor 초기화 테스트"""

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_default_initialization(self, mock_chat):
        """기본 초기화 테스트"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor()

        assert supervisor.max_steps == DEFAULT_MAX_STEPS
        assert supervisor.max_tokens == DEFAULT_MAX_TOKENS

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_custom_initialization(self, mock_chat):
        """커스텀 파라미터 초기화 테스트"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(max_steps=5, max_tokens=2048)

        assert supervisor.max_steps == 5
        assert supervisor.max_tokens == 2048

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_temperature_is_0_7(self, mock_chat):
        """temperature가 0.7인지 확인"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        Supervisor()

        # ChatOpenAI 호출 시 temperature=0.7 확인
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7


class TestSupervisorShouldContinue:
    """_should_continue 메서드 테스트"""

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_continue_when_tool_calls_exist(self, mock_chat):
        """tool_calls가 있으면 continue 반환"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor()

        mock_message = MagicMock()
        mock_message.tool_calls = [{"name": "think", "args": {}}]
        state = {"messages": [mock_message]}

        result = supervisor._should_continue(state)
        assert result == "continue"

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_end_when_no_tool_calls(self, mock_chat):
        """tool_calls가 없으면 end 반환"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor()

        mock_message = MagicMock()
        mock_message.tool_calls = []
        state = {"messages": [mock_message]}

        result = supervisor._should_continue(state)
        assert result == "end"


class TestSupervisorExtractSources:
    """_extract_sources 메서드 테스트"""

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_extracts_tool_names(self, mock_chat):
        """도구 이름들을 추출하는지 확인"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor()

        messages = [
            AIMessage(content="", tool_calls=[{"name": "think", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[{"name": "aweb_search", "args": {}, "id": "2"}]),
        ]

        sources = supervisor._extract_sources(messages)

        assert "think" in sources
        assert "aweb_search" in sources

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_returns_unique_sources(self, mock_chat):
        """중복 없이 반환하는지 확인"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor()

        messages = [
            AIMessage(content="", tool_calls=[{"name": "think", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[{"name": "think", "args": {}, "id": "2"}]),
        ]

        sources = supervisor._extract_sources(messages)

        assert sources.count("think") == 1


class TestSupervisorProcessStream:
    """process_stream 메서드 테스트"""

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_stream_yields_events(self, mock_chat):
        """스트리밍이 이벤트를 yield하는지 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        # Mock graph의 astream_events
        async def mock_stream_events(*args, **kwargs):
            # 토큰 스트리밍 이벤트
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Hello")}
            }
            # think 도구 호출 이벤트
            yield {
                "event": "on_tool_start",
                "name": "think",
                "data": {"input": {"thought": "분석 중..."}}
            }
            # 검색 도구 호출 이벤트
            yield {
                "event": "on_tool_start",
                "name": "aweb_search",
                "data": {"input": {"query": "test query"}}
            }
            # 도구 결과 이벤트
            yield {
                "event": "on_tool_end",
                "name": "aweb_search",
                "data": {"output": "검색 결과..."}
            }

        supervisor.graph = MagicMock()
        supervisor.graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("테스트 질문"):
            events.append(event)

        # 이벤트 타입 확인
        event_types = [e["type"] for e in events]
        assert StreamEventType.TOKEN in event_types
        assert StreamEventType.THINK in event_types
        assert StreamEventType.ACT in event_types
        assert StreamEventType.OBSERVE in event_types

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_stream_token_event_format(self, mock_chat):
        """토큰 이벤트 포맷 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="테스트")}
            }

        supervisor.graph = MagicMock()
        supervisor.graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.TOKEN
        assert events[0]["content"] == "테스트"

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_stream_think_event_format(self, mock_chat):
        """think 이벤트 포맷 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_start",
                "name": "think",
                "data": {"input": {"thought": "생각 내용"}}
            }

        supervisor.graph = MagicMock()
        supervisor.graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.THINK
        assert events[0]["content"] == "생각 내용"

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_stream_act_event_format(self, mock_chat):
        """act 이벤트 포맷 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_start",
                "name": "aweb_search",
                "data": {"input": {"query": "검색어"}}
            }

        supervisor.graph = MagicMock()
        supervisor.graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.ACT
        assert events[0]["tool"] == "aweb_search"
        assert events[0]["args"] == {"query": "검색어"}

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_stream_observe_event_format(self, mock_chat):
        """observe 이벤트 포맷 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_end",
                "name": "arag_search",
                "data": {"output": "RAG 결과"}
            }

        supervisor.graph = MagicMock()
        supervisor.graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.OBSERVE
        assert "RAG 결과" in events[0]["content"]

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_stream_ignores_non_search_tool_end(self, mock_chat):
        """검색 도구가 아닌 도구의 on_tool_end는 무시"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_end",
                "name": "think",  # think는 SEARCH_TOOLS에 없음
                "data": {"output": "생각 결과"}
            }

        supervisor.graph = MagicMock()
        supervisor.graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        # think의 on_tool_end는 무시되어야 함
        assert len(events) == 0

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_stream_saves_to_history(self, mock_chat):
        """스트리밍 완료 후 히스토리에 저장"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_stream_events(*args, **kwargs):
            yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hello ")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="World")}}

        supervisor.graph = MagicMock()
        supervisor.graph.astream_events = mock_stream_events

        # 스트리밍 실행
        async for _ in supervisor.process_stream("테스트", session_id="test-session"):
            pass

        # 히스토리 확인
        messages = supervisor.memory.get_messages("test-session")
        assert len(messages) == 2
        assert messages[0].content == "테스트"
        assert messages[1].content == "Hello World"


class TestSupervisorProcess:
    """process 메서드 테스트 (Non-streaming)"""

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_returns_supervisor_response(self, mock_chat):
        """process가 SupervisorResponse를 반환"""
        from src.schemas.models import SupervisorResponse

        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        # Mock graph의 ainvoke
        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [
                SystemMessage(content="system"),
                HumanMessage(content="질문"),
                AIMessage(content="답변입니다")
            ]}

        supervisor.graph = MagicMock()
        supervisor.graph.ainvoke = mock_ainvoke

        result = await supervisor.process("테스트 질문")

        assert isinstance(result, SupervisorResponse)
        assert result.answer == "답변입니다"

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_extracts_sources(self, mock_chat):
        """process가 사용된 도구를 sources에 포함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [
                AIMessage(content="", tool_calls=[{"name": "aweb_search", "args": {}, "id": "1"}]),
                AIMessage(content="최종 답변")
            ]}

        supervisor.graph = MagicMock()
        supervisor.graph.ainvoke = mock_ainvoke

        result = await supervisor.process("질문")

        assert "aweb_search" in result.sources

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_saves_to_history_with_session(self, mock_chat):
        """session_id가 있으면 히스토리에 저장"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [AIMessage(content="답변")]}

        supervisor.graph = MagicMock()
        supervisor.graph.ainvoke = mock_ainvoke

        await supervisor.process("질문", session_id="test-session")

        messages = supervisor.memory.get_messages("test-session")
        assert len(messages) == 2

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_process_no_history_without_session(self, mock_chat):
        """session_id가 없으면 히스토리 저장 안 함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [AIMessage(content="답변")]}

        supervisor.graph = MagicMock()
        supervisor.graph.ainvoke = mock_ainvoke

        await supervisor.process("질문")  # session_id 없음

        # 어떤 세션에도 저장되지 않음
        assert supervisor.memory.list_sessions() == []


class TestSupervisorParseExecutionLog:
    """_parse_execution_log 메서드 테스트"""

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_parse_ai_message_content(self, mock_chat):
        """AIMessage content를 로그에 포함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        messages = [AIMessage(content="긴 응답 내용입니다" * 20)]
        log = supervisor._parse_execution_log(messages)

        assert len(log) == 1
        assert "Response:" in log[0]
        assert "..." in log[0]  # 100자 초과 시 truncate

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_parse_tool_calls(self, mock_chat):
        """tool_calls를 로그에 포함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        messages = [
            AIMessage(content="", tool_calls=[
                {"name": "aweb_search", "args": {"query": "test"}, "id": "1"}
            ])
        ]
        log = supervisor._parse_execution_log(messages)

        assert any("Tool: aweb_search" in entry for entry in log)

    @patch("src.supervisor.supervisor.ChatOpenAI")
    def test_parse_tool_message(self, mock_chat):
        """ToolMessage를 로그에 포함"""
        from langchain_core.messages import ToolMessage

        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        messages = [ToolMessage(content="결과 데이터" * 100, tool_call_id="1")]
        log = supervisor._parse_execution_log(messages)

        assert len(log) == 1
        assert "Result:" in log[0]
        assert "chars" in log[0]


class TestSupervisorNode:
    """_supervisor_node 메서드 테스트"""

    @patch("src.supervisor.supervisor.ChatOpenAI")
    async def test_supervisor_node_calls_llm(self, mock_chat):
        """_supervisor_node가 LLM을 호출"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor()

        # Mock LLM response
        mock_response = AIMessage(content="응답")
        supervisor.llm_with_tools = MagicMock()
        supervisor.llm_with_tools.ainvoke = AsyncMock(return_value=mock_response)

        state = {"messages": [HumanMessage(content="질문")]}
        result = await supervisor._supervisor_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "응답"
