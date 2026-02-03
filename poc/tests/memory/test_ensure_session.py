"""Tests for SupabaseChatMemory._ensure_session() RLS race condition handling"""
from unittest.mock import AsyncMock, MagicMock
import pytest

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


@pytest.mark.asyncio
async def test_ensure_session_rls_hidden_duplicate_raises_access_denied(memory: SupabaseChatMemory):
    """Test that existing session hidden by RLS raises SessionAccessDenied"""
    mock_client = MagicMock()
    session_id = "test-session-123"
    user_id = "user-456"

    # Mock INSERT with on_conflict do-nothing
    insert_mock = MagicMock()
    insert_mock.on_conflict.return_value = insert_mock

    async def mock_insert_execute():
        result = MagicMock()
        result.data = []
        return result

    insert_mock.execute = mock_insert_execute

    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    mock_client.table.return_value = table_mock

    memory._check_session_ownership_async = AsyncMock(
        side_effect=SessionAccessDenied("not accessible")
    )

    with pytest.raises(SessionAccessDenied, match="not accessible"):
        await memory._ensure_session(session_id, user_id, client=mock_client)


@pytest.mark.asyncio
async def test_ensure_session_insert_success(memory: SupabaseChatMemory):
    """Test successful session creation when session does not exist"""
    mock_client = MagicMock()
    session_id = "test-session-789"
    user_id = "user-101"

    # Mock INSERT succeeds with on_conflict do-nothing
    insert_mock = MagicMock()
    insert_mock.on_conflict.return_value = insert_mock

    async def mock_insert_execute():
        result = MagicMock()
        result.data = [{"id": session_id}]
        return result

    insert_mock.execute = mock_insert_execute

    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    mock_client.table.return_value = table_mock
    memory._check_session_ownership_async = AsyncMock()

    result = await memory._ensure_session(session_id, user_id, client=mock_client)

    assert result is True
    memory._check_session_ownership_async.assert_called_once_with(session_id, user_id, mock_client)


@pytest.mark.asyncio
async def test_ensure_session_on_conflict_same_user_succeeds(memory: SupabaseChatMemory):
    """Test that on_conflict no-op still succeeds for same user after ownership check"""
    mock_client = MagicMock()
    session_id = "test-session-duplicate"
    user_id = "user-222"

    insert_mock = MagicMock()
    insert_mock.on_conflict.return_value = insert_mock

    async def mock_insert_execute():
        result = MagicMock()
        result.data = []
        return result

    insert_mock.execute = mock_insert_execute

    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    mock_client.table.return_value = table_mock

    memory._check_session_ownership_async = AsyncMock()

    result = await memory._ensure_session(session_id, user_id, client=mock_client)

    assert result is True
    memory._check_session_ownership_async.assert_called_once_with(session_id, user_id, mock_client)


@pytest.mark.asyncio
async def test_ensure_session_other_db_error_raises_operation_error(memory: SupabaseChatMemory):
    """Test that insert exceptions raise SupabaseOperationError"""
    mock_client = MagicMock()
    session_id = "test-session-999"
    user_id = "user-202"

    # Mock INSERT raises error
    insert_mock = MagicMock()
    insert_mock.on_conflict.return_value = insert_mock

    async def mock_insert_execute():
        raise RuntimeError("relation does not exist")

    insert_mock.execute = mock_insert_execute

    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    mock_client.table.return_value = table_mock

    with pytest.raises(SupabaseOperationError, match="Failed to create session"):
        await memory._ensure_session(session_id, user_id, client=mock_client)


@pytest.mark.asyncio
async def test_ensure_session_existing_session_checks_ownership(memory: SupabaseChatMemory):
    """Test that session creation path checks ownership when user_id provided"""
    mock_client = MagicMock()
    session_id = "test-session-existing"
    user_id = "user-303"

    # Mock INSERT with on_conflict do-nothing
    insert_mock = MagicMock()
    insert_mock.on_conflict.return_value = insert_mock

    async def mock_insert_execute():
        result = MagicMock()
        result.data = []
        return result

    insert_mock.execute = mock_insert_execute

    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    mock_client.table.return_value = table_mock

    # Mock _check_session_ownership_async to verify it's called
    memory._check_session_ownership_async = AsyncMock()

    result = await memory._ensure_session(session_id, user_id, client=mock_client)

    assert result is True
    memory._check_session_ownership_async.assert_called_once_with(session_id, user_id, mock_client)


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
