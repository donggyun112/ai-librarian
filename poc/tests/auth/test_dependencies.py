"""
Unit tests for Auth dependencies
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request, status

from src.auth.dependencies import verify_current_user, get_supabase_client
from src.auth.schemas import User


@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.app.state.supabase = AsyncMock()
    return request


@pytest.fixture
def mock_supabase_user():
    """미들웨어가 request.state.user에 저장하는 Supabase user 객체"""
    mock_user = MagicMock()
    mock_user.id = "user-123"
    mock_user.aud = "authenticated"
    mock_user.role = "authenticated"
    mock_user.email = "test@example.com"
    mock_user.email_confirmed_at = "2024-01-01T00:00:00Z"
    mock_user.created_at = "2024-01-01T00:00:00Z"
    mock_user.updated_at = "2024-01-01T00:00:00Z"
    mock_user.phone = None
    mock_user.confirmed_at = None
    mock_user.last_sign_in_at = None
    mock_user.app_metadata = {}
    mock_user.user_metadata = {}
    mock_user.identities = []
    return mock_user


@pytest.mark.asyncio
async def test_get_supabase_client(mock_request):
    """Test retrieving the global Supabase client"""
    client = get_supabase_client(mock_request)
    assert client == mock_request.app.state.supabase


@pytest.mark.asyncio
async def test_get_supabase_client_uninitialized():
    """Test retrieving client when not initialized raises 500"""
    request = MagicMock(spec=Request)
    class State:
        pass
    request.app.state = State()

    with pytest.raises(HTTPException) as exc:
        get_supabase_client(request)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "not initialized" in exc.value.detail


@pytest.mark.asyncio
async def test_verify_current_user_valid(mock_supabase_user):
    """미들웨어가 request.state.user를 설정한 경우 User 반환"""
    request = MagicMock(spec=Request)
    request.state.user = mock_supabase_user

    user = await verify_current_user(request)

    assert isinstance(user, User)
    assert user.id == "user-123"
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_verify_current_user_invalid():
    """request.state.user가 None이면 401"""
    request = MagicMock(spec=Request)
    request.state.user = None

    with pytest.raises(HTTPException) as exc:
        await verify_current_user(request)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_verify_current_user_no_state():
    """request.state에 user 속성이 없으면 401"""
    from types import SimpleNamespace
    request = MagicMock(spec=Request)
    # user 속성이 없는 state
    request.state = SimpleNamespace()

    with pytest.raises(HTTPException) as exc:
        await verify_current_user(request)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
