"""API Routes 테스트"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.api.routes import router
from src.memory.supabase_memory import SupabaseChatMemory
from src.memory import InMemoryChatMemory
from fastapi import FastAPI


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
            # SupabaseChatMemory인 것처럼 동작하도록 설정
            mock_memory.list_sessions = MagicMock()
            mock_memory.list_sessions.__code__ = MagicMock()
            mock_memory.list_sessions.__code__.co_varnames = ['self', 'user_id']

            mock_memory.get_message_count = MagicMock(return_value=5)
            mock_memory.get_message_count.__code__ = MagicMock()
            mock_memory.get_message_count.__code__.co_varnames = ['self', 'session_id', 'user_id']

            mock_memory.delete_session = MagicMock()
            mock_memory.delete_session.__code__ = MagicMock()
            mock_memory.delete_session.__code__.co_varnames = ['self', 'session_id', 'user_id']

            mock_memory.clear = MagicMock()
            mock_memory.clear.__code__ = MagicMock()
            mock_memory.clear.__code__.co_varnames = ['self', 'session_id', 'user_id']

            yield mock_memory

    def test_list_sessions_with_user_id(self, client, mock_supabase_memory):
        """user_id를 포함하여 세션 목록 조회"""
        mock_supabase_memory.list_sessions.return_value = ["session-1", "session-2"]

        response = client.get("/sessions?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2

        # user_id로 필터링이 호출되었는지 확인
        mock_supabase_memory.list_sessions.assert_called_once_with(user_id="user-1")

    def test_list_sessions_without_user_id(self, client, mock_supabase_memory):
        """user_id 없이 세션 목록 조회 (모든 세션)"""
        mock_supabase_memory.list_sessions.return_value = ["session-1", "session-2", "session-3"]

        response = client.get("/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 3

        # user_id=None으로 호출되었는지 확인
        mock_supabase_memory.list_sessions.assert_called_once_with(user_id=None)

    def test_delete_session_with_user_id(self, client, mock_supabase_memory):
        """user_id를 포함하여 세션 삭제"""
        mock_supabase_memory.list_sessions.return_value = ["session-1"]

        response = client.delete("/sessions/session-1?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Session deleted"
        assert data["session_id"] == "session-1"

        # user_id로 삭제가 호출되었는지 확인
        mock_supabase_memory.delete_session.assert_called_once_with("session-1", user_id="user-1")

    def test_delete_session_denies_access_for_wrong_user(self, client, mock_supabase_memory):
        """잘못된 user_id로는 세션 삭제 불가"""
        # user-1의 세션만 반환
        mock_supabase_memory.list_sessions.return_value = []

        response = client.delete("/sessions/session-1?user_id=wrong-user")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "denied" in data["detail"].lower()

    def test_clear_session_with_user_id(self, client, mock_supabase_memory):
        """user_id를 포함하여 세션 메시지 초기화"""
        response = client.delete("/sessions/session-1/messages?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Session cleared"
        assert data["session_id"] == "session-1"

        # user_id로 clear가 호출되었는지 확인
        mock_supabase_memory.clear.assert_called_once_with("session-1", user_id="user-1")


class TestSessionEndpointsWithInMemory:
    """InMemoryChatMemory를 사용한 세션 엔드포인트 테스트"""

    @pytest.fixture
    def mock_inmemory(self):
        """Mock InMemoryChatMemory"""
        with patch('src.api.routes.memory') as mock_memory:
            # InMemoryChatMemory인 것처럼 동작하도록 설정
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
