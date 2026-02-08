"""실제 Supabase 연결 통합 테스트

이 테스트는 실제 Supabase 데이터베이스에 연결하여 테스트합니다.
실행하려면 Supabase URL과 KEY가 환경 변수에 설정되어 있어야 합니다.

사용법:
    RUN_REAL_SUPABASE_TESTS=true SUPABASE_URL=<your-url> SUPABASE_SERVICE_ROLE_KEY=<your-key> pytest tests/test_real_supabase_integration.py -v

주의:
    - 테스트 데이터베이스를 사용하세요 (프로덕션 DB 아님!)
    - 테스트 후 데이터가 자동으로 정리됩니다
"""
import pytest
import pytest_asyncio
import os
import uuid
from typing import AsyncGenerator
from langchain_core.messages import HumanMessage, AIMessage

from src.memory.supabase_memory import SupabaseChatMemory
from supabase import create_async_client, AsyncClient


# 명시적으로 RUN_REAL_SUPABASE_TESTS=true 를 설정해야만 실행됩니다.
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_REAL_SUPABASE_TESTS"),
    reason="Set RUN_REAL_SUPABASE_TESTS=true (along with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY) to run these tests."
)

_URL = os.getenv("SUPABASE_URL", "")
_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


@pytest_asyncio.fixture(scope="module")
async def setup_users() -> AsyncGenerator[tuple[str, str], None]:
    """Create two test users for the entire module, clean up after."""
    client = await create_async_client(_URL, _KEY)

    email1 = f"test-{uuid.uuid4().hex[:8]}@integration-test.local"
    email2 = f"test-{uuid.uuid4().hex[:8]}@integration-test.local"

    resp1 = await client.auth.admin.create_user({
        "email": email1,
        "password": "test-password-12345",
        "email_confirm": True
    })
    resp2 = await client.auth.admin.create_user({
        "email": email2,
        "password": "test-password-12345",
        "email_confirm": True
    })

    uid1 = resp1.user.id
    uid2 = resp2.user.id

    yield uid1, uid2

    # Cleanup
    try:
        await client.auth.admin.delete_user(uid1)
    except Exception:
        pass
    try:
        await client.auth.admin.delete_user(uid2)
    except Exception:
        pass


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Fresh async client per test to avoid stale HTTP/2 connections."""
    client = await create_async_client(_URL, _KEY)
    yield client


@pytest.fixture
def memory() -> SupabaseChatMemory:
    """실제 Supabase 연결"""
    return SupabaseChatMemory(url=_URL, key=_KEY)


@pytest.fixture
def test_session_id() -> str:
    """테스트용 고유 세션 ID 생성"""
    return str(uuid.uuid4())


class TestRealSupabaseIntegration:
    """실제 Supabase 데이터베이스 통합 테스트"""

    @pytest.mark.asyncio
    async def test_session_creation_and_message_storage(
        self, memory, test_session_id, setup_users, async_client
    ):
        """세션 생성 및 메시지 저장 테스트"""
        test_user_id = setup_users[0]
        try:
            await memory.save_conversation_async(
                test_session_id,
                "테스트 질문",
                "테스트 답변",
                user_id=test_user_id,
                client=async_client,
            )

            sessions = await memory.list_sessions_async(user_id=test_user_id, client=async_client)
            assert test_session_id in sessions

            count = await memory.get_message_count_async(test_session_id, user_id=test_user_id, client=async_client)
            assert count == 2

            messages = await memory.get_messages_async(test_session_id, user_id=test_user_id, client=async_client)
            assert len(messages) == 2
            assert messages[0].content == "테스트 질문"
            assert messages[1].content == "테스트 답변"
            assert isinstance(messages[0], HumanMessage)
            assert isinstance(messages[1], AIMessage)

        finally:
            await memory.delete_session_async(test_session_id, user_id=test_user_id, client=async_client)

    @pytest.mark.asyncio
    async def test_multiple_conversations_history(
        self, memory, test_session_id, setup_users, async_client
    ):
        """여러 대화의 히스토리 보존 테스트"""
        test_user_id = setup_users[0]
        try:
            conversations = [
                ("질문 1", "답변 1"),
                ("질문 2", "답변 2"),
                ("질문 3", "답변 3"),
            ]

            for q, a in conversations:
                await memory.save_conversation_async(
                    test_session_id, q, a,
                    user_id=test_user_id,
                    client=async_client,
                )

            messages = await memory.get_messages_async(test_session_id, user_id=test_user_id, client=async_client)
            assert len(messages) == 6

            for i, (q, a) in enumerate(conversations):
                assert messages[i*2].content == q
                assert messages[i*2+1].content == a

        finally:
            await memory.delete_session_async(test_session_id, user_id=test_user_id, client=async_client)

    @pytest.mark.asyncio
    async def test_user_isolation(self, memory, setup_users, async_client):
        """사용자 간 데이터 격리 테스트"""
        user1_id, user2_id = setup_users
        session1_id = str(uuid.uuid4())
        session2_id = str(uuid.uuid4())

        try:
            await memory.add_user_message_async(session1_id, "User 1 질문", user_id=user1_id, client=async_client)
            await memory.add_ai_message_async(session1_id, "User 1 답변", user_id=user1_id, client=async_client)

            await memory.add_user_message_async(session2_id, "User 2 질문", user_id=user2_id, client=async_client)
            await memory.add_ai_message_async(session2_id, "User 2 답변", user_id=user2_id, client=async_client)

            # User 1은 User 2의 세션을 볼 수 없음
            user1_sessions = await memory.list_sessions_async(user_id=user1_id, client=async_client)
            user2_sessions = await memory.list_sessions_async(user_id=user2_id, client=async_client)

            assert session1_id in user1_sessions
            assert session2_id not in user1_sessions
            assert session2_id in user2_sessions
            assert session1_id not in user2_sessions

        finally:
            await memory.delete_session_async(session1_id, user_id=user1_id, client=async_client)
            await memory.delete_session_async(session2_id, user_id=user2_id, client=async_client)

    @pytest.mark.asyncio
    async def test_session_clear(self, memory, test_session_id, setup_users, async_client):
        """세션 메시지 정리 테스트"""
        test_user_id = setup_users[0]
        try:
            await memory.add_user_message_async(test_session_id, "질문", user_id=test_user_id, client=async_client)
            await memory.add_ai_message_async(test_session_id, "답변", user_id=test_user_id, client=async_client)

            count = await memory.get_message_count_async(test_session_id, user_id=test_user_id, client=async_client)
            assert count == 2

            await memory.clear_async(test_session_id, user_id=test_user_id, client=async_client)

            count = await memory.get_message_count_async(test_session_id, user_id=test_user_id, client=async_client)
            assert count == 0

        finally:
            await memory.delete_session_async(test_session_id, user_id=test_user_id, client=async_client)

    @pytest.mark.asyncio
    async def test_metadata_preservation(self, memory, test_session_id, setup_users, async_client):
        """메타데이터 보존 테스트"""
        test_user_id = setup_users[0]
        try:
            await memory.save_conversation_async(
                test_session_id,
                "질문",
                "답변",
                user_id=test_user_id,
                custom_field="custom_value",
                timestamp="2024-01-01",
                client=async_client,
            )

            messages = await memory.get_messages_async(test_session_id, user_id=test_user_id, client=async_client)
            assert len(messages) == 2

        finally:
            await memory.delete_session_async(test_session_id, user_id=test_user_id, client=async_client)


class TestSupabaseConnectionHealth:
    """Supabase 연결 상태 테스트"""

    @pytest.mark.asyncio
    async def test_connection_works(self, memory, async_client):
        """기본 연결 테스트"""
        sessions = await memory.list_sessions_async(client=async_client)
        assert isinstance(sessions, list)

    @pytest.mark.asyncio
    async def test_table_schema(self, memory, test_session_id, setup_users, async_client):
        """테이블 스키마가 올바르게 설정되었는지 테스트"""
        test_user_id = setup_users[0]
        try:
            await memory.add_user_message_async(test_session_id, "테스트", user_id=test_user_id, client=async_client)

            messages = await memory.get_messages_async(test_session_id, user_id=test_user_id, client=async_client)
            assert len(messages) == 1

        finally:
            await memory.delete_session_async(test_session_id, user_id=test_user_id, client=async_client)
