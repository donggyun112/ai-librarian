import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from src.api.app import app
from src.auth.dependencies import get_supabase_client

client = TestClient(app)

@pytest.fixture
def mock_supabase_client():
    mock = AsyncMock()
    # auth.get_user returning a Response-like object
    mock.auth = AsyncMock()
    return mock

def test_get_me_without_token():
    response = client.get("/v1/auth/me")
    assert response.status_code == 401  # HTTPBearer auto_error returns 401 for missing credentials

def test_get_me_with_invalid_token(mock_supabase_client):
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client
    
    # Setup mock to raise error or return invalid
    mock_supabase_client.auth.get_user.side_effect = Exception("Invalid Token")
    
    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    
    app.dependency_overrides = {}

def test_get_me_success(mock_supabase_client):
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    # Setup mock user with actual attributes (not model_dump)
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
    mock_supabase_client.auth.get_user.return_value = mock_response

    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer valid_token"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user-123"
    assert data["email"] == "test@example.com"

    app.dependency_overrides = {}
