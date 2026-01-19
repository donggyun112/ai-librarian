"""RESTful API 테스트 (세션 중심 설계)"""
import uuid

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from src.api.routes import router
from src.memory.supabase_memory import SupabaseChatMemory
from src.memory import InMemoryChatMemory
from src.schemas.models import SupervisorResponse
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


class TestSessionCreation:
    """POST /sessions - 세션 생성 테스트"""

    def test_create_session_returns_session_id_and_timestamp(self, client):
        """세션 생성 시 session_id와 created_at 반환"""
        response = client.post("/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "created_at" in data

        # UUID 형식 검증
        try:
            uuid.UUID(data["session_id"])
        except ValueError:
            pytest.fail("session_id is not a valid UUID")

        # ISO 8601 타임스탬프 검증
        try:
            datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("created_at is not a valid ISO 8601 timestamp")

    def test_create_session_calls_init_session_for_inmemory(self, client):
        """InMemory 백엔드: 세션 생성 시 init_session 호출 검증"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = InMemoryChatMemory
            mock_memory.spec = InMemoryChatMemory
            mock_memory.init_session = MagicMock()

            response = client.post("/sessions")

            assert response.status_code == 200
            data = response.json()

            # init_session이 생성된 session_id로 호출되었는지 검증
            mock_memory.init_session.assert_called_once()
            call_args = mock_memory.init_session.call_args
            assert call_args[0][0] == data["session_id"]

    def test_create_session_calls_init_session_async_for_supabase(self, client):
        """Supabase 백엔드: 세션 생성 시 init_session_async 호출 검증"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory
            mock_memory.spec = SupabaseChatMemory
            mock_memory.init_session_async = AsyncMock(return_value=True)

            response = client.post(
                "/sessions",
                headers={"Authorization": "Bearer user-1"}
            )

            assert response.status_code == 200
            data = response.json()

            # init_session_async가 session_id와 user_id로 호출되었는지 검증
            mock_memory.init_session_async.assert_called_once()
            call_args = mock_memory.init_session_async.call_args
            assert call_args[0][0] == data["session_id"]
            assert call_args[0][1] == "user-1"

    def test_create_session_fails_when_supabase_init_fails(self, client):
        """Supabase 백엔드: 세션 초기화 실패 시 500 에러"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory
            mock_memory.spec = SupabaseChatMemory
            mock_memory.init_session_async = AsyncMock(return_value=False)

            response = client.post(
                "/sessions",
                headers={"Authorization": "Bearer user-1"}
            )

            assert response.status_code == 500
            data = response.json()
            assert "Failed to create session" in data["detail"]


class TestSessionDetail:
    """GET /sessions/{session_id} - 세션 상세 조회 테스트"""

    @pytest.fixture
    def mock_supabase_memory(self):
        """Mock SupabaseChatMemory"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory
            mock_memory.spec = SupabaseChatMemory

            # Configure async methods
            mock_memory.list_sessions_async = AsyncMock()
            mock_memory.get_message_count_async = AsyncMock()
            mock_memory.get_messages_async = AsyncMock()

            yield mock_memory

    def test_get_session_detail_with_messages(self, client, mock_supabase_memory):
        """메시지가 있는 세션 상세 조회"""
        session_id = "test-session-123"

        # Mock 데이터 설정
        mock_supabase_memory.list_sessions_async.return_value = [session_id]
        mock_supabase_memory.get_message_count_async.return_value = 4

        # 타임스탬프가 있는 메시지 목록
        mock_messages = [
            HumanMessage(
                content="First message",
                additional_kwargs={"timestamp": "2024-01-01T10:00:00Z"}
            ),
            AIMessage(
                content="First response",
                additional_kwargs={"timestamp": "2024-01-01T10:00:05Z"}
            ),
            HumanMessage(
                content="Second message",
                additional_kwargs={"timestamp": "2024-01-01T10:01:00Z"}
            ),
            AIMessage(
                content="Second response",
                additional_kwargs={"timestamp": "2024-01-01T10:01:10Z"}
            ),
        ]
        mock_supabase_memory.get_messages_async.return_value = mock_messages

        response = client.get(
            f"/sessions/{session_id}",
            headers={"Authorization": "Bearer user-1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["message_count"] == 4
        assert data["created_at"] == "2024-01-01T10:00:00Z"
        assert data["last_activity"] == "2024-01-01T10:01:10Z"

    def test_get_session_detail_without_auth_fails_for_supabase(
        self, client, mock_supabase_memory
    ):
        """Supabase 백엔드에서 Authorization 헤더 없이 조회 시도"""
        session_id = "test-session-123"

        response = client.get(f"/sessions/{session_id}")

        assert response.status_code == 401
        data = response.json()
        assert "Authorization header required" in data["detail"]

    def test_get_session_detail_not_found(self, client, mock_supabase_memory):
        """존재하지 않는 세션 조회"""
        session_id = "nonexistent-session"

        mock_supabase_memory.list_sessions_async.return_value = []

        response = client.get(
            f"/sessions/{session_id}",
            headers={"Authorization": "Bearer user-1"}
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "denied" in data["detail"].lower()

    def test_get_session_detail_with_inmemory(self, client):
        """InMemory 백엔드로 세션 상세 조회"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = InMemoryChatMemory
            mock_memory.spec = InMemoryChatMemory

            session_id = "test-session"
            mock_memory.list_sessions.return_value = [session_id]
            mock_memory.get_message_count.return_value = 2
            mock_memory.get_messages.return_value = [
                HumanMessage(
                    content="Hi",
                    additional_kwargs={"timestamp": "2024-01-01T12:00:00Z"}
                ),
                AIMessage(
                    content="Hello",
                    additional_kwargs={"timestamp": "2024-01-01T12:00:05Z"}
                ),
            ]

            response = client.get(f"/sessions/{session_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == session_id
            assert data["message_count"] == 2
            assert data["created_at"] == "2024-01-01T12:00:00Z"
            assert data["last_activity"] == "2024-01-01T12:00:05Z"


class TestSendMessage:
    """POST /sessions/{session_id}/messages - stream 파라미터 기반 응답"""

    @pytest.fixture
    def mock_supervisor(self):
        """Mock Supervisor"""
        with patch('src.api.routes.supervisor') as mock_sup:
            yield mock_sup

    @pytest.fixture
    def mock_supabase_memory(self):
        """Mock SupabaseChatMemory"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = SupabaseChatMemory
            mock_memory.spec = SupabaseChatMemory
            yield mock_memory

    def test_send_message_json_response(self, client, mock_supervisor, mock_supabase_memory):
        """stream: false → JSON 응답"""
        session_id = "test-session"

        # Mock supervisor response
        mock_supervisor.process = AsyncMock(return_value=SupervisorResponse(
            answer="This is a JSON response",
            sources=["web_search"],
            execution_log=[],
            total_confidence=1.0
        ))

        response = client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Hello", "stream": False},
            headers={"Authorization": "Bearer user-1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "This is a JSON response"
        assert data["sources"] == ["web_search"]
        assert data["session_id"] == session_id

        # Verify supervisor was called
        mock_supervisor.process.assert_called_once()
        call_kwargs = mock_supervisor.process.call_args.kwargs
        assert call_kwargs["question"] == "Hello"
        assert call_kwargs["session_id"] == session_id
        assert call_kwargs["user_id"] == "user-1"

    def test_send_message_streaming_response(self, client, mock_supervisor, mock_supabase_memory):
        """stream: true → SSE 스트리밍"""
        session_id = "test-session"

        # Mock streaming response - return the generator function itself
        async def mock_stream(question, session_id, **kwargs):
            yield {"type": "token", "content": "Hello"}
            yield {"type": "token", "content": " World"}
            yield {"type": "think", "content": "Thinking..."}
            yield {"type": "act", "tool": "search", "args": {"query": "test"}}
            yield {"type": "observe", "content": "Search results"}

        mock_supervisor.process_stream = mock_stream

        response = client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Hello", "stream": True},
            headers={"Authorization": "Bearer user-1"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # SSE 응답 검증
        content = response.text
        assert "event: token" in content
        assert "event: think" in content
        assert "event: act" in content
        assert "event: observe" in content
        assert "event: done" in content

    def test_send_message_defaults_to_json(
        self, client, mock_supervisor, mock_supabase_memory
    ):
        """stream 미지정 시 JSON 응답 (기본값)"""
        session_id = "test-session"

        mock_supervisor.process = AsyncMock(return_value=SupervisorResponse(
            answer="Default JSON response",
            sources=[],
            execution_log=[],
            total_confidence=1.0
        ))

        # stream 파라미터 없이 요청
        response = client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Test"},
            headers={"Authorization": "Bearer user-1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Default JSON response"

    def test_send_message_requires_auth_for_supabase(self, client, mock_supabase_memory):
        """Supabase 백엔드에서 Authorization 헤더 필수"""
        session_id = "test-session"

        response = client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Hello"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "Authorization header required" in data["detail"]

    def test_send_message_works_without_auth_for_inmemory(self, client, mock_supervisor):
        """InMemory 백엔드는 Authorization 헤더 불필요"""
        with patch('src.api.routes.memory') as mock_memory:
            mock_memory.__class__ = InMemoryChatMemory
            mock_memory.spec = InMemoryChatMemory

            session_id = "test-session"

            mock_supervisor.process = AsyncMock(return_value=SupervisorResponse(
                answer="Response without auth",
                sources=[],
                execution_log=[],
                total_confidence=1.0
            ))

            response = client.post(
                f"/sessions/{session_id}/messages",
                json={"message": "Hello"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["answer"] == "Response without auth"

    def test_send_message_streaming_handles_error(self, client, mock_supervisor, mock_supabase_memory):
        """스트리밍 중 에러 발생 시 error 이벤트"""
        session_id = "test-session"

        # Mock error during streaming
        async def mock_error_stream(question, session_id, **kwargs):
            yield {"type": "token", "content": "Start"}
            raise ValueError("Test error")

        mock_supervisor.process_stream = mock_error_stream

        response = client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Hello", "stream": True},
            headers={"Authorization": "Bearer user-1"}
        )

        assert response.status_code == 200
        content = response.text
        assert "event: error" in content

    def test_send_message_json_handles_validation_error(
        self, client, mock_supervisor, mock_supabase_memory
    ):
        """JSON 모드에서 ValidationError 처리"""
        session_id = "test-session"

        mock_supervisor.process = AsyncMock(side_effect=ValueError("Validation failed"))

        response = client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Hello", "stream": False},
            headers={"Authorization": "Bearer user-1"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Validation failed" in data["detail"]


class TestAPIDocumentation:
    """OpenAPI 문서 자동 생성 확인"""

    def test_openapi_schema_includes_new_endpoints(self, client):
        """OpenAPI 스키마에 새 엔드포인트 포함"""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        paths = schema["paths"]

        # RESTful 엔드포인트 확인
        assert "/sessions" in paths
        assert "/sessions/{session_id}" in paths
        assert "/sessions/{session_id}/messages" in paths
        assert "/health" in paths

        # 기존 엔드포인트는 제거됨
        assert "/chat" not in paths
        assert "/chat/stream" not in paths
