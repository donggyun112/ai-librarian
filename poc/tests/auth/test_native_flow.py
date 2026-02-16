import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from src.api.app import app

client = TestClient(app)


@pytest.fixture
def mock_supabase_on_app():
    """app.state.supabase를 mock으로 설정 (미들웨어가 사용)"""
    mock = AsyncMock()
    mock.auth = AsyncMock()
    original = getattr(app.state, "supabase", None)
    app.state.supabase = mock
    yield mock
    if original is not None:
        app.state.supabase = original


def test_get_me_without_token():
    """토큰 없으면 미들웨어에서 401"""
    response = client.get("/v1/auth/me")
    assert response.status_code == 401


def test_get_me_with_invalid_token(mock_supabase_on_app):
    """유효하지 않은 토큰이면 미들웨어에서 401"""
    mock_supabase_on_app.auth.get_user.side_effect = Exception("Invalid Token")

    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401


def test_get_me_success(mock_supabase_on_app):
    """유효한 토큰이면 미들웨어 통과 후 /me 응답"""
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.aud = "authenticated"
    mock_user.role = "authenticated"
    mock_user.email = "test@example.com"
    mock_user.email_confirmed_at = "2023-01-01T00:00:00Z"
    mock_user.phone = None
    mock_user.confirmed_at = "2023-01-01T00:00:00Z"
    mock_user.last_sign_in_at = "2023-01-01T00:00:00Z"
    mock_user.app_metadata = {"provider": "email"}
    mock_user.user_metadata = {}
    mock_user.identities = []
    mock_user.created_at = "2023-01-01T00:00:00Z"
    mock_user.updated_at = "2023-01-01T00:00:00Z"

    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_supabase_on_app.auth.get_user.return_value = mock_response

    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer valid_token"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user-123"
    assert data["email"] == "test@example.com"
