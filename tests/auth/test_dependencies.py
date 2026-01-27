import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from src.auth.dependencies import verify_current_user
from src.auth.schemas import User
from fastapi.security import HTTPAuthorizationCredentials


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase AsyncClient"""
    mock = AsyncMock()
    mock.auth = AsyncMock()
    return mock


@pytest.fixture
def mock_token():
    """Mock HTTPAuthorizationCredentials"""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid_token")


@pytest.mark.asyncio
async def test_verify_current_user_success(mock_supabase_client, mock_token):
    """Test successful JWT verification"""
    # Setup mock user response
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

    # Execute
    result = await verify_current_user(mock_token, mock_supabase_client)

    # Assert
    assert isinstance(result, User)
    assert result.id == "user-123"
    assert result.email == "test@example.com"
    assert result.aud == "authenticated"
    mock_supabase_client.auth.get_user.assert_called_once_with("valid_token")


@pytest.mark.asyncio
async def test_verify_current_user_invalid_token(mock_supabase_client, mock_token):
    """Test JWT verification with invalid token"""
    # Setup mock to return None user
    mock_response = MagicMock()
    mock_response.user = None
    mock_supabase_client.auth.get_user.return_value = mock_response

    # Execute & Assert
    with pytest.raises(HTTPException) as exc_info:
        await verify_current_user(mock_token, mock_supabase_client)

    assert exc_info.value.status_code == 401
    assert "Invalid authentication credentials" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_current_user_exception(mock_supabase_client, mock_token):
    """Test JWT verification with exception"""
    # Setup mock to raise exception
    mock_supabase_client.auth.get_user.side_effect = Exception("Network error")

    # Execute & Assert
    with pytest.raises(HTTPException) as exc_info:
        await verify_current_user(mock_token, mock_supabase_client)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail
