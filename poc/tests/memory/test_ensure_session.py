"""Tests for SupabaseChatMemory._ensure_session() RLS race condition handling"""
from unittest.mock import AsyncMock, MagicMock
import pytest
from postgrest.exceptions import APIError

from src.memory.supabase_memory import (
    SupabaseChatMemory,
    SessionAccessDenied,
    SupabaseOperationError,
)


@pytest.fixture
def memory() -> SupabaseChatMemory:
    """Create SupabaseChatMemory instance with require_user_scoped_client=False for testing"""
    return SupabaseChatMemory(
        url="http://test.supabase.co",
        key="test-key",
        require_user_scoped_client=False,
    )


def _make_select_chain(data: list) -> MagicMock:
    """Helper: build .select().eq().eq().execute() mock chain returning given data."""
    async def mock_execute():
        result = MagicMock()
        result.data = data
        return result

    eq2_mock = MagicMock()
    eq2_mock.execute = mock_execute

    eq1_mock = MagicMock()
    eq1_mock.eq.return_value = eq2_mock

    select_mock = MagicMock()
    select_mock.eq.return_value = eq1_mock

    return select_mock


def _make_insert_chain(*, raises: Exception | None = None, data: list | None = None) -> MagicMock:
    """Helper: build .insert().execute() mock chain."""
    async def mock_execute():
        if raises:
            raise raises
        result = MagicMock()
        result.data = data or []
        return result

    insert_mock = MagicMock()
    insert_mock.execute = mock_execute
    return insert_mock


@pytest.mark.asyncio
async def test_ensure_session_existing_session_returns_true(memory: SupabaseChatMemory):
    """Test that existing session owned by user returns True without INSERT"""
    mock_client = MagicMock()
    session_id = "test-session-existing"
    user_id = "user-123"

    # SELECT finds the session (user owns it)
    select_chain = _make_select_chain([{"id": session_id}])

    table_mock = MagicMock()
    table_mock.select.return_value = select_chain

    mock_client.table.return_value = table_mock

    result = await memory._ensure_session(session_id, user_id, client=mock_client)

    assert result is True
    # INSERT should never have been called
    table_mock.insert.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_session_insert_success(memory: SupabaseChatMemory):
    """Test successful session creation when session does not exist"""
    mock_client = MagicMock()
    session_id = "test-session-789"
    user_id = "user-101"

    # SELECT returns empty (session doesn't exist)
    select_chain = _make_select_chain([])
    # INSERT succeeds
    insert_chain = _make_insert_chain(data=[{"id": session_id}])

    table_mock = MagicMock()
    table_mock.select.return_value = select_chain
    table_mock.insert.return_value = insert_chain

    mock_client.table.return_value = table_mock

    result = await memory._ensure_session(session_id, user_id, client=mock_client)

    assert result is True


@pytest.mark.asyncio
async def test_ensure_session_rls_hidden_duplicate_raises_access_denied(memory: SupabaseChatMemory):
    """Test that session hidden by RLS (SELECT empty, INSERT 23505) raises SessionAccessDenied"""
    mock_client = MagicMock()
    session_id = "test-session-123"
    user_id = "user-456"

    # SELECT returns empty (RLS hides another user's session)
    select_chain = _make_select_chain([])
    # INSERT raises 23505 (session actually exists)
    insert_chain = _make_insert_chain(
        raises=APIError({"message": "duplicate key", "code": "23505", "details": None, "hint": None})
    )

    table_mock = MagicMock()
    table_mock.select.return_value = select_chain
    table_mock.insert.return_value = insert_chain

    mock_client.table.return_value = table_mock

    with pytest.raises(SessionAccessDenied, match="not accessible"):
        await memory._ensure_session(session_id, user_id, client=mock_client)


@pytest.mark.asyncio
async def test_ensure_session_other_db_error_raises_operation_error(memory: SupabaseChatMemory):
    """Test that non-APIError exceptions raise SupabaseOperationError"""
    mock_client = MagicMock()
    session_id = "test-session-999"
    user_id = "user-202"

    # SELECT returns empty
    select_chain = _make_select_chain([])
    # INSERT raises non-APIError
    insert_chain = _make_insert_chain(raises=RuntimeError("relation does not exist"))

    table_mock = MagicMock()
    table_mock.select.return_value = select_chain
    table_mock.insert.return_value = insert_chain

    mock_client.table.return_value = table_mock

    with pytest.raises(SupabaseOperationError, match="Failed to create session"):
        await memory._ensure_session(session_id, user_id, client=mock_client)


@pytest.mark.asyncio
async def test_ensure_session_non_23505_api_error_raises_operation_error(memory: SupabaseChatMemory):
    """Test that APIError with code other than 23505 raises SupabaseOperationError"""
    mock_client = MagicMock()
    session_id = "test-session-existing"
    user_id = "user-303"

    # SELECT returns empty
    select_chain = _make_select_chain([])
    # INSERT raises APIError with different code
    insert_chain = _make_insert_chain(
        raises=APIError({"message": "permission denied", "code": "42501", "details": None, "hint": None})
    )

    table_mock = MagicMock()
    table_mock.select.return_value = select_chain
    table_mock.insert.return_value = insert_chain

    mock_client.table.return_value = table_mock

    with pytest.raises(SupabaseOperationError, match="Failed to create session"):
        await memory._ensure_session(session_id, user_id, client=mock_client)


@pytest.mark.asyncio
async def test_get_messages_always_checks_ownership(memory: SupabaseChatMemory):
    """Test that get_messages_async always calls _check_session_ownership_async when user_id provided"""
    mock_client = MagicMock()
    session_id = "test-session-ownership"
    user_id = "user-404"

    # Mock _check_session_ownership_async
    memory._check_session_ownership_async = AsyncMock()

    # Mock the query chain for messages
    order_mock = MagicMock()

    async def mock_messages_execute():
        result = MagicMock()
        result.data = []
        return result

    order_mock.execute = mock_messages_execute

    eq_mock = MagicMock()
    eq_mock.order.return_value = order_mock

    select_mock = MagicMock()
    select_mock.eq.return_value = eq_mock

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    mock_client.table.return_value = table_mock

    await memory.get_messages_async(session_id, user_id=user_id, client=mock_client)

    # Verify ownership check was called
    memory._check_session_ownership_async.assert_called_once_with(session_id, user_id, mock_client)


@pytest.mark.asyncio
async def test_get_message_count_always_checks_ownership(memory: SupabaseChatMemory):
    """Test that get_message_count_async always calls _check_session_ownership_async when user_id provided"""
    mock_client = MagicMock()
    session_id = "test-session-count"
    user_id = "user-505"

    # Mock _check_session_ownership_async
    memory._check_session_ownership_async = AsyncMock()

    # Mock the query chain for count
    eq_mock = MagicMock()

    async def mock_count_execute():
        result = MagicMock()
        result.count = 5
        result.data = []
        return result

    eq_mock.execute = mock_count_execute

    select_mock = MagicMock()
    select_mock.eq.return_value = eq_mock

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    mock_client.table.return_value = table_mock

    count = await memory.get_message_count_async(session_id, user_id=user_id, client=mock_client)

    assert count == 5
    # Verify ownership check was called
    memory._check_session_ownership_async.assert_called_once_with(session_id, user_id, mock_client)
