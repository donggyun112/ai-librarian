"""API Routes 테스트"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock

from src.api.routes import router
from src.memory.supabase_memory import SupabaseChatMemory
from src.memory import InMemoryChatMemory
from fastapi import FastAPI
from langchain_core.messages import HumanMessage, AIMessage


@pytest.fixture
def app():
    """FastAPI 앱 인스턴스"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """테스트 클라이언트"""
    return TestClient(app)


class TestSessionEndpointsWithUserID:
    """세션 엔드포인트 user_id 필터링 테스트"""

    @pytest.fixture
    def mock_supabase_memory(self):
        """Mock SupabaseChatMemory"""
        with patch('src.api.routes.memory') as mock_memory:
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

            mock_memory.clear_async = AsyncMock()
            mock_memory.clear_async.__code__ = MagicMock()
            mock_memory.clear_async.__code__.co_varnames = ['self', 'session_id', 'user_id']

            mock_memory.get_messages_async = AsyncMock(return_value=[])
            mock_memory.get_messages_async.__code__ = MagicMock()
            mock_memory.get_messages_async.__code__.co_varnames = ['self', 'session_id', 'user_id']

            yield mock_memory

    def test_list_sessions_with_user_id(self, client, mock_supabase_memory):
        """user_id를 포함하여 세션 목록 조회"""
        mock_supabase_memory.list_sessions_async.return_value = ["session-1", "session-2"]

        response = client.get("/sessions?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2

        # user_id로 필터링이 호출되었는지 확인
        mock_supabase_memory.list_sessions_async.assert_called_once_with(user_id="user-1")

    def test_list_sessions_without_user_id_fails(self, client, mock_supabase_memory):
        """user_id 없이 세션 목록 조회 시도 (Supabase 백엔드는 거부해야 함)"""
        response = client.get("/sessions")

        # Supabase 백엔드는 user_id 필수
        assert response.status_code == 400
        data = response.json()
        assert "user_id is required" in data["detail"]

    def test_delete_session_with_user_id(self, client, mock_supabase_memory):
        """user_id를 포함하여 세션 삭제"""
        mock_supabase_memory.list_sessions_async.return_value = ["session-1"]

        response = client.delete("/sessions/session-1?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Session deleted"
        assert data["session_id"] == "session-1"

        # user_id로 삭제가 호출되었는지 확인
        mock_supabase_memory.delete_session_async.assert_called_once_with("session-1", user_id="user-1")

    def test_delete_session_without_user_id_fails(self, client, mock_supabase_memory):
        """user_id 없이 세션 삭제 시도 (Supabase 백엔드는 거부해야 함)"""
        response = client.delete("/sessions/session-1")

        # Supabase 백엔드는 user_id 필수
        assert response.status_code == 400
        data = response.json()
        assert "user_id is required" in data["detail"]

    def test_delete_session_denies_access_for_wrong_user(self, client, mock_supabase_memory):
        """잘못된 user_id로는 세션 삭제 불가"""
        # user-1의 세션만 반환
        mock_supabase_memory.list_sessions_async.return_value = []

        response = client.delete("/sessions/session-1?user_id=wrong-user")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "denied" in data["detail"].lower()

    def test_clear_session_with_user_id(self, client, mock_supabase_memory):
        """user_id를 포함하여 세션 메시지 초기화"""
        mock_supabase_memory.list_sessions_async.return_value = ["session-1"]

        response = client.delete("/sessions/session-1/messages?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Session cleared"
        assert data["session_id"] == "session-1"

        # user_id로 clear가 호출되었는지 확인
        mock_supabase_memory.clear_async.assert_called_once_with("session-1", user_id="user-1")

    def test_clear_session_without_user_id_fails(self, client, mock_supabase_memory):
        """user_id 없이 세션 메시지 초기화 시도 (Supabase 백엔드는 거부해야 함)"""
        response = client.delete("/sessions/session-1/messages")

        # Supabase 백엔드는 user_id 필수
        assert response.status_code == 400
        data = response.json()
        assert "user_id is required" in data["detail"]

    def test_get_session_messages_with_user_id(self, client, mock_supabase_memory):
        """user_id를 포함하여 세션 메시지 조회"""
        # Mock messages
        mock_messages = [
            HumanMessage(content="Hello", additional_kwargs={"timestamp": "2024-01-01T00:00:00Z"}),
            AIMessage(content="Hi there!", additional_kwargs={"timestamp": "2024-01-01T00:00:01Z"})
        ]
        mock_supabase_memory.get_messages_async.return_value = mock_messages

        response = client.get("/sessions/session-1/messages?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-1"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "human"
        assert data["messages"][0]["content"] == "Hello"
        assert data["messages"][1]["role"] == "ai"
        assert data["messages"][1]["content"] == "Hi there!"

        # user_id로 메시지 조회가 호출되었는지 확인
        mock_supabase_memory.get_messages_async.assert_called_once_with("session-1", user_id="user-1")

    def test_get_session_messages_without_user_id_fails(self, client, mock_supabase_memory):
        """user_id 없이 세션 메시지 조회 시도 (Supabase 백엔드는 거부해야 함)"""
        response = client.get("/sessions/session-1/messages")

        # Supabase 백엔드는 user_id 필수
        assert response.status_code == 400
        data = response.json()
        assert "user_id is required" in data["detail"]


class TestSessionEndpointsWithInMemory:
    """InMemoryChatMemory를 사용한 세션 엔드포인트 테스트"""

    @pytest.fixture
    def mock_inmemory(self):
        """Mock InMemoryChatMemory"""
        with patch('src.api.routes.memory') as mock_memory:
            # Create a proper MagicMock that will pass isinstance() check for InMemoryChatMemory
            mock_memory.__class__ = InMemoryChatMemory
            mock_memory.spec = InMemoryChatMemory

            # Configure methods
            mock_memory.list_sessions = MagicMock(return_value=["session-1"])
            mock_memory.list_sessions.__code__ = MagicMock()
            mock_memory.list_sessions.__code__.co_varnames = ['self']  # user_id 파라미터 없음

            mock_memory.get_message_count = MagicMock(return_value=3)
            mock_memory.get_message_count.__code__ = MagicMock()
            mock_memory.get_message_count.__code__.co_varnames = ['self', 'session_id']  # user_id 파라미터 없음

            mock_memory.delete_session = MagicMock()
            mock_memory.delete_session.__code__ = MagicMock()
            mock_memory.delete_session.__code__.co_varnames = ['self', 'session_id']

            mock_memory.clear = MagicMock()
            mock_memory.clear.__code__ = MagicMock()
            mock_memory.clear.__code__.co_varnames = ['self', 'session_id']

            yield mock_memory

    def test_list_sessions_ignores_user_id_for_inmemory(self, client, mock_inmemory):
        """InMemoryChatMemory는 user_id를 무시"""
        response = client.get("/sessions?user_id=user-1")

        assert response.status_code == 200

        # user_id 없이 호출되었는지 확인 (InMemoryChatMemory는 user_id 파라미터가 없음)
        mock_inmemory.list_sessions.assert_called_once_with()

    def test_delete_session_works_without_user_id_for_inmemory(self, client, mock_inmemory):
        """InMemoryChatMemory는 user_id 없이 삭제"""
        response = client.delete("/sessions/session-1?user_id=user-1")

        assert response.status_code == 200

        # user_id 없이 호출되었는지 확인
        mock_inmemory.delete_session.assert_called_once_with("session-1")

    def test_get_session_messages_ignores_user_id_for_inmemory(self, client, mock_inmemory):
        """InMemoryChatMemory는 user_id를 무시하고 메시지 조회"""
        # Mock messages
        mock_messages = [
            HumanMessage(content="Test message"),
            AIMessage(content="Test response")
        ]
        mock_inmemory.get_messages = MagicMock(return_value=mock_messages)

        response = client.get("/sessions/session-1/messages?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-1"
        assert len(data["messages"]) == 2

        # user_id 없이 호출되었는지 확인 (InMemory는 user_id 무시)
        mock_inmemory.get_messages.assert_called_once_with("session-1")


class TestChatEndpoints:
    """채팅 엔드포인트 테스트"""

    @pytest.fixture
    def mock_supervisor(self):
        """Mock Supervisor"""
        with patch('src.api.routes.supervisor') as mock_sup:
            yield mock_sup

    def test_chat_requires_user_id_with_supabase(self, client, mock_supervisor):
        """POST /chat without user_id returns 400 with Supabase backend"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory

            response = client.post("/chat", json={"message": "hello"})

            assert response.status_code == 400
            data = response.json()
            assert "user_id" in data["detail"].lower()

    def test_chat_works_with_user_id_and_supabase(self, client, mock_supervisor):
        """POST /chat with user_id succeeds with Supabase backend"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory

            # Mock supervisor response
            from src.schemas.models import SupervisorResponse
            mock_supervisor.process = AsyncMock(return_value=SupervisorResponse(
                answer="Test response",
                sources=["aweb_search"],
                execution_log=[],
                total_confidence=1.0
            ))

            response = client.post("/chat", json={
                "message": "hello",
                "user_id": "user-1"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["answer"] == "Test response"
            assert "session_id" in data

            # Verify supervisor was called with user_id
            mock_supervisor.process.assert_called_once()
            call_kwargs = mock_supervisor.process.call_args.kwargs
            assert call_kwargs["user_id"] == "user-1"

    def test_chat_works_without_user_id_for_inmemory(self, client, mock_supervisor):
        """POST /chat without user_id succeeds with InMemory backend"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = InMemoryChatMemory

            # Mock supervisor response
            from src.schemas.models import SupervisorResponse
            mock_supervisor.process = AsyncMock(return_value=SupervisorResponse(
                answer="Test response",
                sources=[],
                execution_log=[],
                total_confidence=1.0
            ))

            response = client.post("/chat", json={"message": "hello"})

            assert response.status_code == 200
            data = response.json()
            assert data["answer"] == "Test response"

    def test_chat_handles_supervisor_value_error(self, client, mock_supervisor):
        """POST /chat returns 400 when Supervisor raises ValueError"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory

            # Mock supervisor to raise ValueError
            mock_supervisor.process = AsyncMock(side_effect=ValueError("user_id is required"))

            response = client.post("/chat", json={
                "message": "hello",
                "user_id": "user-1"
            })

            assert response.status_code == 400
            data = response.json()
            assert "user_id is required" in data["detail"]
