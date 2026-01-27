import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from src.api.app import app
from src.auth.dependencies import get_user_scoped_client

client = TestClient(app)

@pytest.fixture
def mock_supabase_dependency():
    """Mock the get_user_scoped_client dependency logic directly or components"""
    # Since we want to test the DEPENDENCY logic itself (creation + cleanup),
    # we should patch the 'create_async_client' used INSIDE dependencies.py.
    with patch("src.auth.dependencies.create_async_client", new_callable=AsyncMock) as mock_create:
        mock_client = AsyncMock()
        mock_client.postgrest = MagicMock()
        mock_client.table = MagicMock()
        
        # Setup table().select().execute() chain
        mock_query = AsyncMock()
        mock_query.execute.return_value = MagicMock(data=[
            {"id": "book-1", "user_id": "user-123", "title": "Test Book", "created_at": "2023-01-01"}
        ])
        mock_client.table.return_value.select.return_value = mock_query
        
        mock_create.return_value = mock_client
        yield mock_create, mock_client

@pytest.fixture
def override_auth_verification():
    """Bypass verify_current_user for books tests"""
    from src.auth.dependencies import verify_current_user
    from src.auth.schemas import User
    
    mock_user = User(
        id="user-123",
        aud="authenticated",
        role="authenticated",
        email="test@example.com",
        created_at="2023-01-01",
        updated_at="2023-01-01"
    )
    
    app.dependency_overrides[verify_current_user] = lambda: mock_user
    yield
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_books_lifecycle(mock_supabase_dependency, override_auth_verification):
    mock_create, mock_client = mock_supabase_dependency
    
    # We need to make a request that triggers the dependency
    # Note: TestClient runs sync, but FastAPI handles async dependencies.
    # To test 'aclose', we rely on FastAPI's dependency teardown.
    
    response = client.get("/v1/books", headers={"Authorization": "Bearer test-jwt"})
    
    # 1. Verify Response
    assert response.status_code == 200
    assert response.json()["total"] == 1
    
    # 2. Verify Dependency Logic
    # Check if create_async_client was called
    mock_create.assert_called_once()
    
    # Check if auth header was set
    mock_client.postgrest.auth.assert_called_with("test-jwt")
    
    # Check if aclose was called (Critical for resource cleanup fix)
    mock_client.aclose.assert_called_once()
