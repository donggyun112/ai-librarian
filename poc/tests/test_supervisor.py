"""supervisor.py 테스트"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.supervisor.supervisor import (
    Supervisor,
    SEARCH_TOOLS,
    THINK_TOOL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MAX_STEPS,
)
from src.schemas.models import StreamEventType

# pytest-asyncio STRICT mode에서 async 테스트 마킹
pytest_plugins = ('pytest_asyncio',)


class TestSupervisorConstants:
    """상수 테스트"""

    def test_search_tools(self):
        """검색 도구 목록 확인"""
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

    @patch("src.adapters.openai.ChatOpenAI")
    def test_default_initialization(self, mock_chat):
        """기본 초기화 테스트"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(provider="openai")

        assert supervisor.max_steps == DEFAULT_MAX_STEPS
        assert supervisor.max_tokens == DEFAULT_MAX_TOKENS
        assert supervisor.adapter.provider_name == "openai"

    @patch("src.adapters.openai.ChatOpenAI")
    def test_custom_initialization(self, mock_chat):
        """커스텀 파라미터 초기화 테스트"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(max_steps=5, max_tokens=2048, provider="openai")

        assert supervisor.max_steps == 5
        assert supervisor.max_tokens == 2048

    @patch("src.adapters.openai.ChatOpenAI")
    def test_openai_adapter_selected(self, mock_chat):
        """provider=openai일 때 OpenAI Adapter 선택"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(provider="openai")
        assert supervisor.adapter.provider_name == "openai"

    @patch("src.adapters.gemini.ChatGoogleGenerativeAI")
    def test_gemini_adapter_selected(self, mock_chat):
        """provider=gemini일 때 Gemini Adapter 선택"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(provider="gemini")
        assert supervisor.adapter.provider_name == "gemini"


class TestSupervisorShouldContinue:
    """_should_continue 메서드 테스트"""

    @patch("src.adapters.openai.ChatOpenAI")
    def test_continue_when_tool_calls_exist(self, mock_chat):
        """tool_calls가 있으면 continue 반환"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(provider="openai")

        mock_message = MagicMock()
        mock_message.tool_calls = [{"name": "think", "args": {}}]
        state = {"messages": [mock_message]}

        result = supervisor._should_continue(state)
        assert result == "continue"

    @patch("src.adapters.openai.ChatOpenAI")
    def test_end_when_no_tool_calls(self, mock_chat):
        """tool_calls가 없으면 end 반환"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(provider="openai")

        mock_message = MagicMock()
        mock_message.tool_calls = []
        state = {"messages": [mock_message]}

        result = supervisor._should_continue(state)
        assert result == "end"


class TestSupervisorExtractSources:
    """_extract_sources 메서드 테스트"""

    @patch("src.adapters.openai.ChatOpenAI")
    def test_extracts_tool_names(self, mock_chat):
        """도구 이름들을 추출하는지 확인"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(provider="openai")

        messages = [
            AIMessage(content="", tool_calls=[{"name": "think", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[{"name": "aweb_search", "args": {}, "id": "2"}]),
        ]

        sources = supervisor._extract_sources(messages)

        assert "think" in sources
        assert "aweb_search" in sources

    @patch("src.adapters.openai.ChatOpenAI")
    def test_returns_unique_sources(self, mock_chat):
        """중복 없이 반환하는지 확인"""
        mock_chat.return_value = MagicMock()
        mock_chat.return_value.bind_tools = MagicMock(return_value=MagicMock())

        supervisor = Supervisor(provider="openai")

        messages = [
            AIMessage(content="", tool_calls=[{"name": "think", "args": {}, "id": "1"}]),
            AIMessage(content="", tool_calls=[{"name": "think", "args": {}, "id": "2"}]),
        ]

        sources = supervisor._extract_sources(messages)

        assert sources.count("think") == 1


class TestSupervisorProcessStream:
    """process_stream 메서드 테스트"""

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_stream_yields_events(self, mock_chat):
        """스트리밍이 이벤트를 yield하는지 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        # Mock graph의 astream_events
        async def mock_stream_events(*args, **kwargs):
            # 토큰 스트리밍 이벤트
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Hello")}
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

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("테스트 질문"):
            events.append(event)

        # 이벤트 타입 확인 (Native Thinking은 OpenAI에서 지원하지 않음)
        event_types = [e["type"] for e in events]
        assert StreamEventType.TOKEN in event_types
        assert StreamEventType.ACT in event_types
        assert StreamEventType.OBSERVE in event_types

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_stream_passes_client_to_build_messages(self, mock_chat):
        """process_stream이 client를 _build_messages로 전달하는지 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")
        supervisor._build_messages = AsyncMock(return_value=[])

        async def mock_stream_events(*args, **kwargs):
            if False:
                yield {}

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

        client = object()
        async for _ in supervisor.process_stream("질문", session_id="session-1", user_id="user-1", client=client):
            pass

        supervisor._build_messages.assert_called_once_with(
            "session-1", "질문", user_id="user-1", client=client
        )

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_stream_token_event_format(self, mock_chat):
        """토큰 이벤트 포맷 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="테스트")}
            }

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.TOKEN
        assert events[0]["content"] == "테스트"

    @pytest.mark.asyncio
    @patch("src.adapters.gemini.ChatGoogleGenerativeAI")
    async def test_process_stream_think_event_format(self, mock_chat):
        """native thinking 이벤트 포맷 확인 (Gemini)"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="gemini")

        async def mock_stream_events(*args, **kwargs):
            # Gemini Native Thinking 형식: content가 list with thinking type
            chunk = MagicMock()
            chunk.content = [{"type": "thinking", "thinking": "생각 내용"}]
            chunk.additional_kwargs = {}
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk}
            }

        # Gemini는 매번 새로 생성하므로 _build_graph를 mock
        mock_graph = MagicMock()
        mock_graph.astream_events = mock_stream_events
        supervisor._build_graph = MagicMock(return_value=mock_graph)

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.THINK
        assert events[0]["content"] == "생각 내용"

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_stream_act_event_format(self, mock_chat):
        """act 이벤트 포맷 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_start",
                "name": "aweb_search",
                "data": {"input": {"query": "검색어"}}
            }

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.ACT
        assert events[0]["tool"] == "aweb_search"
        assert events[0]["args"] == {"query": "검색어"}

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_stream_observe_event_format(self, mock_chat):
        """observe 이벤트 포맷 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_end",
                "name": "aweb_search",
                "data": {"output": "Web search 결과"}
            }

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == StreamEventType.OBSERVE
        assert "Web search 결과" in events[0]["content"]

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_stream_ignores_non_search_tool_end(self, mock_chat):
        """검색 도구가 아닌 도구의 on_tool_end는 무시"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_end",
                "name": "think",  # think는 SEARCH_TOOLS에 없음
                "data": {"output": "생각 결과"}
            }

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        # think의 on_tool_end는 무시되어야 함
        assert len(events) == 0

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_stream_saves_to_history(self, mock_chat):
        """스트리밍 완료 후 히스토리에 저장"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_stream_events(*args, **kwargs):
            yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hello ")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="World")}}

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

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

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_returns_supervisor_response(self, mock_chat):
        """process가 SupervisorResponse를 반환"""
        from src.schemas.models import SupervisorResponse

        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        # Mock graph의 ainvoke
        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [
                SystemMessage(content="system"),
                HumanMessage(content="질문"),
                AIMessage(content="답변입니다")
            ]}

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.ainvoke = mock_ainvoke

        result = await supervisor.process("테스트 질문")

        assert isinstance(result, SupervisorResponse)
        assert result.answer == "답변입니다"

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_passes_client_to_build_messages(self, mock_chat):
        """process가 client를 _build_messages로 전달하는지 확인"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")
        supervisor._build_messages = AsyncMock(return_value=[])

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="ok")]})

        client = object()
        await supervisor.process("질문", session_id="session-1", user_id="user-1", client=client)

        supervisor._build_messages.assert_called_once_with(
            "session-1", "질문", user_id="user-1", client=client
        )

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_extracts_sources(self, mock_chat):
        """process가 사용된 도구를 sources에 포함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [
                AIMessage(content="", tool_calls=[{"name": "aweb_search", "args": {}, "id": "1"}]),
                AIMessage(content="최종 답변")
            ]}

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.ainvoke = mock_ainvoke

        result = await supervisor.process("질문")

        assert "aweb_search" in result.sources

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_saves_to_history_with_session(self, mock_chat):
        """session_id가 있으면 히스토리에 저장"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [AIMessage(content="답변")]}

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.ainvoke = mock_ainvoke

        await supervisor.process("질문", session_id="test-session")

        messages = supervisor.memory.get_messages("test-session")
        assert len(messages) == 2

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_process_no_history_without_session(self, mock_chat):
        """session_id가 없으면 히스토리 저장 안 함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_ainvoke(*args, **kwargs):
            return {"messages": [AIMessage(content="답변")]}

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.ainvoke = mock_ainvoke

        await supervisor.process("질문")  # session_id 없음

        # 어떤 세션에도 저장되지 않음
        assert supervisor.memory.list_sessions() == []


class TestSupervisorParseExecutionLog:
    """_parse_execution_log 메서드 테스트"""

    @patch("src.adapters.openai.ChatOpenAI")
    def test_parse_ai_message_content(self, mock_chat):
        """AIMessage content를 로그에 포함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        messages = [AIMessage(content="긴 응답 내용입니다" * 20)]
        log = supervisor._parse_execution_log(messages)

        assert len(log) == 1
        assert "Response:" in log[0]
        assert "..." in log[0]  # 100자 초과 시 truncate

    @patch("src.adapters.openai.ChatOpenAI")
    def test_parse_tool_calls(self, mock_chat):
        """tool_calls를 로그에 포함"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        messages = [
            AIMessage(content="", tool_calls=[
                {"name": "aweb_search", "args": {"query": "test"}, "id": "1"}
            ])
        ]
        log = supervisor._parse_execution_log(messages)

        assert any("Tool: aweb_search" in entry for entry in log)

    @patch("src.adapters.openai.ChatOpenAI")
    def test_parse_tool_message(self, mock_chat):
        """ToolMessage를 로그에 포함"""
        from langchain_core.messages import ToolMessage

        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        messages = [ToolMessage(content="결과 데이터" * 100, tool_call_id="1")]
        log = supervisor._parse_execution_log(messages)

        assert len(log) == 1
        assert "Result:" in log[0]
        assert "chars" in log[0]


class TestChunkNormalization:
    """청크 정규화 테스트 (Adapter 통합)"""

    @pytest.mark.asyncio
    @patch("src.adapters.openai.ChatOpenAI")
    async def test_openai_chunk_normalized(self, mock_chat):
        """OpenAI 청크가 정규화되어 스트리밍됨"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="openai")

        async def mock_stream_events(*args, **kwargs):
            # OpenAI 형식: chunk.content = str
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="안녕하세요")}
            }

        supervisor._cached_graph = MagicMock()
        supervisor._cached_graph.astream_events = mock_stream_events

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        assert events[0]["content"] == "안녕하세요"

    @pytest.mark.asyncio
    @patch("src.adapters.gemini.ChatGoogleGenerativeAI")
    async def test_gemini_chunk_normalized(self, mock_chat):
        """Gemini 청크가 정규화되어 스트리밍됨"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        supervisor = Supervisor(provider="gemini")

        async def mock_stream_events(*args, **kwargs):
            # Gemini 형식: chunk.content = list[dict]
            chunk = MagicMock()
            chunk.content = [{"type": "text", "text": "안녕"}, {"type": "text", "text": "하세요"}]
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk}
            }

        # Gemini는 매번 새로 생성하므로 _build_graph를 mock
        mock_graph = MagicMock()
        mock_graph.astream_events = mock_stream_events
        supervisor._build_graph = MagicMock(return_value=mock_graph)

        events = []
        async for event in supervisor.process_stream("질문"):
            events.append(event)

        # Gemini list 형식이 str로 정규화됨
        assert events[0]["content"] == "안녕하세요"
