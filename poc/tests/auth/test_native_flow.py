import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from src.api.app import app
from src.auth.dependencies import get_supabase_client
from src.auth.schemas import User

client = TestClient(app)

@pytest.fixture
def mock_supabase_client():
    mock = AsyncMock()
    # auth.get_user returning a Response-like object
    mock.auth = AsyncMock()
    return mock

def test_get_me_without_token():
    response = client.get("/v1/auth/me")
    assert response.status_code == 401  # HTTPBearer auto_error=True returns 401 or 403

def test_get_me_with_invalid_token(mock_supabase_client):
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client
    
    # Setup mock to raise error
    mock_supabase_client.auth.get_user.side_effect = Exception("Invalid Token")
    
    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    
    app.dependency_overrides = {}

def test_get_me_success(mock_supabase_client):
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client
    
    # Setup mock success
    mock_user = MagicMock()
    mock_user.model_dump.return_value = {
        "id": "user-123",
        "aud": "authenticated",
        "email": "test@example.com",
        "role": "authenticated",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "app_metadata": {},
        "user_metadata": {},
        "identities": []
    }
    
    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_supabase_client.auth.get_user.return_value = mock_response
    
    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer valid_token"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user-123"
    assert data["email"] == "test@example.com"
    
    app.dependency_overrides = {}
