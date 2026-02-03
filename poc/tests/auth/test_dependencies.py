"""
Unit tests for Auth dependencies
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from src.auth.dependencies import verify_current_user, get_supabase_client
from src.auth.schemas import User

@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.app.state.supabase = AsyncMock()
    return request

@pytest.fixture
def mock_supabase_client():
    client = AsyncMock()
    # Mock auth.get_user
    client.auth.get_user = AsyncMock()
    return client

@pytest.mark.asyncio
async def test_get_supabase_client(mock_request):
    """Test retrieving the global Supabase client"""
    client = get_supabase_client(mock_request)
    assert client == mock_request.app.state.supabase

@pytest.mark.asyncio
async def test_get_supabase_client_uninitialized():
    """Test retrieving client when not initialized raises 500"""
    request = MagicMock(spec=Request)
    # Simulate missing supabase in state
    del request.app.state.supabase 
    # Or just ensure it doesn't have it by default on a fresh mock, 
    # but MagicMock might auto-create attributes.
    # Properly:
    request = MagicMock(spec=Request)
    # request.app.state is a MagicMock, so it has .supabase access.
    # We need to force it to NOT have it. 
    # But get_supabase_client uses `hasattr(request.app.state, "supabase")`.
    # MagicMock usually returns True for hasattr unless spec is restricted or explicitly deleted.
    
    # Let's use a simpler object for state
    class State:
        pass
    request.app.state = State()
    
    with pytest.raises(HTTPException) as exc:
        get_supabase_client(request)
    
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "not initialized" in exc.value.detail

@pytest.mark.asyncio
async def test_verify_current_user_valid(mock_supabase_client):
    """Test successful token verification"""
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid_token")
    
    # Mock successful Supabase response
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.aud = "authenticated"
    mock_user.role = "authenticated"
    mock_user.email = "test@example.com"
    mock_user.email_confirmed_at = "2024-01-01T00:00:00Z"
    mock_user.created_at = "2024-01-01T00:00:00Z"
    mock_user.updated_at = "2024-01-01T00:00:00Z"
    # Optional fields
    mock_user.phone = None
    mock_user.confirmed_at = None
    mock_user.last_sign_in_at = None
    mock_user.app_metadata = {}
    mock_user.user_metadata = {}
    mock_user.identities = []

    mock_response = MagicMock()
    mock_response.user = mock_user
    
    mock_supabase_client.auth.get_user.return_value = mock_response

    user = await verify_current_user(token, mock_supabase_client)

    assert isinstance(user, User)
    assert user.id == "user-123"
    assert user.email == "test@example.com"
    
    mock_supabase_client.auth.get_user.assert_called_once_with("valid_token")

@pytest.mark.asyncio
async def test_verify_current_user_invalid(mock_supabase_client):
    """Test handling of invalid token"""
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_token")
    
    # Mock Supabase returning None/empty
    mock_supabase_client.auth.get_user.return_value = MagicMock(user=None)

    with pytest.raises(HTTPException) as exc:
        await verify_current_user(token, mock_supabase_client)
    
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_verify_current_user_exception(mock_supabase_client):
    """Test handling of Supabase errors"""
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="error_token")
    
    # Mock Supabase raising exception
    mock_supabase_client.auth.get_user.side_effect = Exception("Supabase Error")

    with pytest.raises(HTTPException) as exc:
        await verify_current_user(token, mock_supabase_client)
    
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
