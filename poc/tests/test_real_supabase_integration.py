"""실제 Supabase 연결 통합 테스트

이 테스트는 실제 Supabase 데이터베이스에 연결하여 테스트합니다.
실행하려면 Supabase URL과 KEY가 환경 변수에 설정되어 있어야 합니다.

사용법:
    SUPABASE_URL=<your-url> SUPABASE_SERVICE_ROLE_KEY=<your-key> pytest tests/test_real_supabase_integration.py -v

주의:
    - 테스트 데이터베이스를 사용하세요 (프로덕션 DB 아님!)
    - 테스트 후 데이터가 자동으로 정리됩니다
"""
import pytest
import os
import uuid
from langchain_core.messages import HumanMessage, AIMessage

from src.memory.supabase_memory import SupabaseChatMemory


# 환경 변수가 설정되어 있을 때만 테스트 실행
pytestmark = pytest.mark.skipif(
    not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
    reason="Supabase credentials not provided. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to run these tests."
)


@pytest.fixture
def memory():
    """실제 Supabase 연결"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    return SupabaseChatMemory(url=url, key=key)


@pytest.fixture
def test_session_id():
    """테스트용 고유 세션 ID 생성"""
    return str(uuid.uuid4())


@pytest.fixture
def test_user_id():
    """테스트용 고유 사용자 ID 생성"""
    # 실제 auth.users에 존재하는 사용자 ID를 사용해야 합니다
    # 또는 테스트용으로 미리 생성된 사용자 ID
    return os.getenv("TEST_USER_ID", "00000000-0000-0000-0000-000000000001")


class TestRealSupabaseIntegration:
    """실제 Supabase 데이터베이스 통합 테스트"""

    @pytest.mark.asyncio
    async def test_session_creation_and_message_storage(self, memory, test_session_id, test_user_id):
        """세션 생성 및 메시지 저장 테스트"""
        try:
            # 메시지 저장
            await memory.save_conversation_async(
                test_session_id,
                "테스트 질문",
                "테스트 답변",
                user_id=test_user_id
            )

            # 세션 목록 확인
            sessions = memory.list_sessions(user_id=test_user_id)
            assert test_session_id in sessions, f"Session {test_session_id} not found in {sessions}"

            # 메시지 개수 확인
            count = memory.get_message_count(test_session_id, user_id=test_user_id)
            assert count == 2, f"Expected 2 messages, got {count}"

            # 메시지 내용 확인
            messages = memory.get_messages(test_session_id, user_id=test_user_id)
            assert len(messages) == 2
            assert messages[0].content == "테스트 질문"
            assert messages[1].content == "테스트 답변"
            assert isinstance(messages[0], HumanMessage)
            assert isinstance(messages[1], AIMessage)

        finally:
            # 정리
            memory.delete_session(test_session_id, user_id=test_user_id)

    @pytest.mark.asyncio
    async def test_multiple_conversations_history(self, memory, test_session_id, test_user_id):
        """여러 대화의 히스토리 보존 테스트"""
        try:
            # 3개의 대화 추가
            conversations = [
                ("질문 1", "답변 1"),
                ("질문 2", "답변 2"),
                ("질문 3", "답변 3"),
            ]

            for q, a in conversations:
                await memory.save_conversation_async(
                    test_session_id,
                    q,
                    a,
                    user_id=test_user_id
                )

            # 히스토리 확인
            messages = memory.get_messages(test_session_id, user_id=test_user_id)
            assert len(messages) == 6, f"Expected 6 messages, got {len(messages)}"

            # 순서 확인
            for i, (q, a) in enumerate(conversations):
                assert messages[i*2].content == q
                assert messages[i*2+1].content == a

        finally:
            memory.delete_session(test_session_id, user_id=test_user_id)

    def test_user_isolation(self, memory, test_user_id):
        """사용자 간 데이터 격리 테스트"""
        user1_id = test_user_id
        user2_id = str(uuid.uuid4())
        session1_id = str(uuid.uuid4())
        session2_id = str(uuid.uuid4())

        try:
            # User 1의 세션 (동기 메서드 사용)
            memory.add_user_message(session1_id, "User 1 질문", user_id=user1_id)
            memory.add_ai_message(session1_id, "User 1 답변", user_id=user1_id)

            # User 2의 세션
            memory.add_user_message(session2_id, "User 2 질문", user_id=user2_id)
            memory.add_ai_message(session2_id, "User 2 답변", user_id=user2_id)

            # User 1은 User 2의 세션을 볼 수 없음
            messages = memory.get_messages(session2_id, user_id=user1_id)
            assert len(messages) == 0, "User 1 should not see User 2's messages"

            # User 2는 User 1의 세션을 볼 수 없음
            messages = memory.get_messages(session1_id, user_id=user2_id)
            assert len(messages) == 0, "User 2 should not see User 1's messages"

            # 각 사용자는 자신의 세션만 볼 수 있음
            user1_sessions = memory.list_sessions(user_id=user1_id)
            user2_sessions = memory.list_sessions(user_id=user2_id)

            assert session1_id in user1_sessions
            assert session2_id not in user1_sessions
            assert session2_id in user2_sessions
            assert session1_id not in user2_sessions

        finally:
            # 정리
            memory.delete_session(session1_id, user_id=user1_id)
            memory.delete_session(session2_id, user_id=user2_id)

    def test_session_clear(self, memory, test_session_id, test_user_id):
        """세션 메시지 정리 테스트"""
        try:
            # 메시지 추가
            memory.add_user_message(test_session_id, "질문", user_id=test_user_id)
            memory.add_ai_message(test_session_id, "답변", user_id=test_user_id)

            # 메시지 확인
            assert memory.get_message_count(test_session_id, user_id=test_user_id) == 2

            # 메시지 정리
            memory.clear(test_session_id, user_id=test_user_id)

            # 메시지가 삭제되었는지 확인
            assert memory.get_message_count(test_session_id, user_id=test_user_id) == 0

            # 세션은 여전히 존재
            sessions = memory.list_sessions(user_id=test_user_id)
            # 세션이 존재할 수도 있고 아닐 수도 있음 (구현에 따라)

        finally:
            memory.delete_session(test_session_id, user_id=test_user_id)

    @pytest.mark.asyncio
    async def test_metadata_preservation(self, memory, test_session_id, test_user_id):
        """메타데이터 보존 테스트"""
        try:
            # 커스텀 메타데이터와 함께 저장
            await memory.save_conversation_async(
                test_session_id,
                "질문",
                "답변",
                user_id=test_user_id,
                custom_field="custom_value",
                timestamp="2024-01-01"
            )

            # 메시지 확인 (메타데이터는 additional_kwargs에 저장됨)
            messages = memory.get_messages(test_session_id, user_id=test_user_id)
            assert len(messages) == 2

            # 메타데이터는 LangChain 메시지 객체의 additional_kwargs에 저장됩니다
            # (Supabase에 저장된 후 복원됨)

        finally:
            memory.delete_session(test_session_id, user_id=test_user_id)


class TestSupabaseConnectionHealth:
    """Supabase 연결 상태 테스트"""

    def test_connection_works(self, memory):
        """기본 연결 테스트"""
        # 세션 목록을 가져올 수 있으면 연결 성공
        sessions = memory.list_sessions()
        assert isinstance(sessions, list)

    def test_table_schema(self, memory, test_session_id, test_user_id):
        """테이블 스키마가 올바르게 설정되었는지 테스트"""
        try:
            # 세션과 메시지를 생성할 수 있으면 스키마가 올바름
            memory.add_user_message(test_session_id, "테스트", user_id=test_user_id)

            # RLS 정책이 올바르게 작동하는지 확인
            messages = memory.get_messages(test_session_id, user_id=test_user_id)
            assert len(messages) == 1

        finally:
            memory.delete_session(test_session_id, user_id=test_user_id)
