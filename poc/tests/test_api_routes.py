"""API Routes 테스트"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

from src.api.routes import router
from src.auth.dependencies import get_user_scoped_client, verify_current_user
from src.auth.schemas import User
from src.memory.supabase_memory import SupabaseChatMemory, SessionAccessDenied
from src.memory import InMemoryChatMemory
from fastapi import FastAPI
from langchain_core.messages import HumanMessage, AIMessage


@pytest.fixture
def app():
    """FastAPI 앱 인스턴스"""
    app = FastAPI()
    app.include_router(router)
    app.state.memory = InMemoryChatMemory()
    return app


@pytest.fixture
def client(app):
    """테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
def auth_overrides(app):
    """인증/클라이언트 의존성 오버라이드"""
    mock_client = AsyncMock()
    mock_client.postgrest = MagicMock()

    app.dependency_overrides[verify_current_user] = lambda: User(
        id="user-1",
        aud="authenticated",
        role="authenticated",
        email="test@example.com",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    app.dependency_overrides[get_user_scoped_client] = lambda: mock_client
    yield mock_client
    app.dependency_overrides = {}


class TestSessionEndpointsWithUserID:
    """세션 엔드포인트 user_id 필터링 테스트"""

    @pytest.fixture
    def mock_supabase_memory(self):
        """Mock SupabaseChatMemory"""
        mock_memory = MagicMock()
        # Create a proper MagicMock that will pass isinstance() check
        mock_memory.__class__ = SupabaseChatMemory
        mock_memory.spec = SupabaseChatMemory

        # Configure async methods (need AsyncMock)
        mock_memory.list_sessions_async = AsyncMock()
        mock_memory.list_sessions_async.__code__ = MagicMock()
        mock_memory.list_sessions_async.__code__.co_varnames = ['self', 'user_id']

        mock_memory.get_message_count_async = AsyncMock(return_value=5)
        mock_memory.get_message_count_async.__code__ = MagicMock()
        mock_memory.get_message_count_async.__code__.co_varnames = ['self', 'session_id', 'user_id']

        mock_memory.delete_session_async = AsyncMock()
        mock_memory.delete_session_async.__code__ = MagicMock()
        mock_memory.delete_session_async.__code__.co_varnames = ['self', 'session_id', 'user_id']

        mock_memory.get_messages_async = AsyncMock(return_value=[])
        mock_memory.get_messages_async.__code__ = MagicMock()
        mock_memory.get_messages_async.__code__.co_varnames = ['self', 'session_id', 'user_id']

        yield mock_memory

    def test_list_sessions_with_user_id(self, client, mock_supabase_memory, auth_overrides, app):
        """Authorization 헤더로 세션 목록 조회"""
        app.state.memory = mock_supabase_memory
        mock_supabase_memory.list_sessions_async.return_value = ["session-1", "session-2"]

        response = client.get("/sessions", headers={"Authorization": "Bearer user-1"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2

        # user_id로 필터링이 호출되었는지 확인
        mock_supabase_memory.list_sessions_async.assert_called_once_with(
            user_id="user-1",
            client=auth_overrides,
        )

    def test_list_sessions_without_auth_fails(self, client, mock_supabase_memory, app):
        """Authorization 헤더 없이 세션 목록 조회 시도 (Supabase 백엔드는 거부해야 함)"""
        app.state.memory = mock_supabase_memory
        response = client.get("/sessions")

        # Supabase 백엔드는 Authorization 헤더 필수
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"

    def test_delete_session_with_auth(self, client, mock_supabase_memory, auth_overrides, app):
        """Authorization 헤더로 세션 삭제"""
        app.state.memory = mock_supabase_memory
        mock_supabase_memory.list_sessions_async.return_value = ["session-1"]

        response = client.delete("/sessions/session-1", headers={"Authorization": "Bearer user-1"})

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Session deleted"
        assert data["session_id"] == "session-1"

        # user_id로 삭제가 호출되었는지 확인
        mock_supabase_memory.delete_session_async.assert_called_once_with(
            "session-1", user_id="user-1", client=auth_overrides
        )

    def test_delete_session_without_auth_fails(self, client, mock_supabase_memory, app):
        """Authorization 헤더 없이 세션 삭제 시도 (Supabase 백엔드는 거부해야 함)"""
        app.state.memory = mock_supabase_memory
        response = client.delete("/sessions/session-1")

        # Supabase 백엔드는 Authorization 헤더 필수
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"

    def test_delete_session_denies_access_for_wrong_user(self, client, mock_supabase_memory, auth_overrides, app):
        """잘못된 user_id로는 세션 삭제 불가"""
        app.state.memory = mock_supabase_memory
        mock_supabase_memory.delete_session_async.side_effect = SessionAccessDenied("denied")

        response = client.delete("/sessions/session-1", headers={"Authorization": "Bearer wrong-user"})

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "denied" in data["detail"].lower()

    def test_get_session_messages_with_auth(self, client, mock_supabase_memory, auth_overrides, app):
        """Authorization 헤더로 세션 메시지 조회"""
        app.state.memory = mock_supabase_memory
        # Mock messages
        mock_messages = [
            HumanMessage(content="Hello", additional_kwargs={"timestamp": "2024-01-01T00:00:00Z"}),
            AIMessage(content="Hi there!", additional_kwargs={"timestamp": "2024-01-01T00:00:01Z"})
        ]
        mock_supabase_memory.get_messages_async.return_value = mock_messages

        response = client.get("/sessions/session-1/messages", headers={"Authorization": "Bearer user-1"})

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-1"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "human"
        assert data["messages"][0]["content"] == "Hello"
        assert data["messages"][1]["role"] == "ai"
        assert data["messages"][1]["content"] == "Hi there!"

        # user_id로 메시지 조회가 호출되었는지 확인
        mock_supabase_memory.get_messages_async.assert_called_once_with(
            "session-1", user_id="user-1", client=auth_overrides
        )

    def test_get_session_messages_denies_access_for_wrong_user(self, client, mock_supabase_memory, auth_overrides, app):
        """잘못된 user_id로는 세션 메시지 조회 불가"""
        app.state.memory = mock_supabase_memory
        mock_supabase_memory.get_messages_async.side_effect = SessionAccessDenied("denied")

        response = client.get("/sessions/session-1/messages", headers={"Authorization": "Bearer wrong-user"})

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "denied" in data["detail"].lower()

    def test_get_session_messages_without_auth_fails(self, client, mock_supabase_memory, app):
        """Authorization 헤더 없이 세션 메시지 조회 시도 (Supabase 백엔드는 거부해야 함)"""
        app.state.memory = mock_supabase_memory
        response = client.get("/sessions/session-1/messages")

        # Supabase 백엔드는 Authorization 헤더 필수
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"


class TestSessionEndpointsWithInMemory:
    """InMemoryChatMemory를 사용한 세션 엔드포인트 테스트

    routes.py가 항상 async 메서드를 user_id, client와 함께 호출하므로,
    InMemory는 이 파라미터들을 무시하고 정상 동작해야 한다.
    """

    @pytest.fixture
    def mock_inmemory(self):
        """Mock InMemoryChatMemory (async 메서드)"""
        mock_memory = MagicMock()
        mock_memory.list_sessions_async = AsyncMock(return_value=["session-1"])
        mock_memory.get_message_count_async = AsyncMock(return_value=3)
        mock_memory.delete_session_async = AsyncMock()
        mock_memory.get_messages_async = AsyncMock(return_value=[])
        yield mock_memory

    def test_list_sessions_with_inmemory(self, client, mock_inmemory, auth_overrides, app):
        """InMemory 백엔드로 세션 목록 조회"""
        app.state.memory = mock_inmemory
        response = client.get("/sessions", headers={"Authorization": "Bearer user-1"})

        assert response.status_code == 200
        mock_inmemory.list_sessions_async.assert_called_once()

    def test_delete_session_with_inmemory(self, client, mock_inmemory, auth_overrides, app):
        """InMemory 백엔드로 세션 삭제"""
        app.state.memory = mock_inmemory
        response = client.delete("/sessions/session-1", headers={"Authorization": "Bearer user-1"})

        assert response.status_code == 200
        mock_inmemory.delete_session_async.assert_called_once()

    def test_get_session_messages_with_inmemory(self, client, mock_inmemory, auth_overrides, app):
        """InMemory 백엔드로 메시지 조회"""
        app.state.memory = mock_inmemory
        mock_messages = [
            HumanMessage(content="Test message"),
            AIMessage(content="Test response")
        ]
        mock_inmemory.get_messages_async = AsyncMock(return_value=mock_messages)

        response = client.get("/sessions/session-1/messages", headers={"Authorization": "Bearer user-1"})

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-1"
        assert len(data["messages"]) == 2
        mock_inmemory.get_messages_async.assert_called_once()


class TestAIChatEndpoint:
    """AI SDK /chat 엔드포인트 테스트"""

    @pytest.fixture
    def mock_supervisor(self):
        """Mock Supervisor"""
        with patch('src.api.routes.supervisor') as mock_sup:
            # Mock process_stream to return async generator
            async def mock_stream(*args, **kwargs):
                yield {"type": "token", "content": "Hello"}
                yield {"type": "token", "content": " world"}
                yield {"type": "think", "content": "Thinking..."}
                yield {"type": "act", "tool": "search", "args": {"query": "test"}}
                yield {"type": "observe", "content": "Search results"}

            mock_sup.process_stream = AsyncMock(side_effect=mock_stream)
            yield mock_sup

    @pytest.fixture
    def mock_inmemory_for_chat(self):
        """Mock InMemoryChatMemory for /chat endpoint"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = InMemoryChatMemory
            mock_memory.spec = InMemoryChatMemory
            mock_memory.init_session = MagicMock()
            yield mock_memory

    @pytest.fixture
    def mock_supabase_for_chat(self):
        """Mock SupabaseChatMemory for /chat endpoint"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory
            mock_memory.spec = SupabaseChatMemory
            mock_memory.init_session_async = AsyncMock(return_value=True)
            yield mock_memory

    def test_ai_chat_with_user_messages(self, client, mock_supervisor, mock_inmemory_for_chat):
        """AI SDK 포맷으로 채팅 요청"""
        request_data = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"}
            ]
        }

        response = client.post("/chat", json=request_data)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Check that last user message was used
        mock_supervisor.process_stream.assert_called_once()
        call_kwargs = mock_supervisor.process_stream.call_args.kwargs
        assert call_kwargs["question"] == "How are you?"

    def test_ai_chat_with_no_user_messages(self, client, mock_supervisor, mock_inmemory_for_chat):
        """user 메시지가 없으면 400 에러"""
        request_data = {
            "messages": [
                {"role": "assistant", "content": "Hi there!"}
            ]
        }

        response = client.post("/chat", json=request_data)

        assert response.status_code == 400
        assert "No user message found" in response.json()["detail"]

    def test_ai_chat_with_supabase_requires_auth(self, client, mock_supervisor, mock_supabase_for_chat):
        """Supabase 사용 시 Authorization 필수"""
        request_data = {
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }

        # Authorization 헤더 없이 요청
        response = client.post("/chat", json=request_data)

        assert response.status_code == 401
        assert "Authorization header required" in response.json()["detail"]

    def test_ai_chat_creates_temp_session(self, client, mock_supervisor, mock_inmemory_for_chat):
        """임시 세션이 생성되는지 확인"""
        request_data = {
            "messages": [
                {"role": "user", "content": "Test"}
            ]
        }

        response = client.post("/chat", json=request_data)

        assert response.status_code == 200

        # init_session이 호출되었는지 확인
        mock_inmemory_for_chat.init_session.assert_called_once()

        # supervisor.process_stream이 session_id와 함께 호출되었는지 확인
        mock_supervisor.process_stream.assert_called_once()
        call_kwargs = mock_supervisor.process_stream.call_args.kwargs
        assert "session_id" in call_kwargs
        assert call_kwargs["session_id"] is not None

    def test_ai_chat_with_auth_header(self, client, mock_supervisor, mock_supabase_for_chat):
        """Authorization 헤더와 함께 요청"""
        request_data = {
            "messages": [
                {"role": "user", "content": "Test with auth"}
            ]
        }

        response = client.post(
            "/chat",
            json=request_data,
            headers={"Authorization": "Bearer user-123"}
        )

        assert response.status_code == 200

        # Supabase init_session_async가 user_id와 함께 호출되었는지 확인
        mock_supabase_for_chat.init_session_async.assert_called_once()
        # call_args는 (args, kwargs) 튜플
        call_args, call_kwargs = mock_supabase_for_chat.init_session_async.call_args
        # 첫 번째 인자는 session_id (UUID), 두 번째 인자가 user_id
        assert len(call_args) == 2
        assert call_args[1] == "user-123"  # user_id 파라미터

        # supervisor.process_stream이 user_id와 함께 호출되었는지 확인
        mock_supervisor.process_stream.assert_called_once()
        call_kwargs = mock_supervisor.process_stream.call_args.kwargs
        assert call_kwargs.get("user_id") == "user-123"
