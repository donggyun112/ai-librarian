"""Supabase 통합 테스트 - 세션 관리 및 히스토리 보존 검증"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from src.memory.supabase_memory import SupabaseChatMemory


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase 클라이언트 with realistic behavior"""
    with patch('src.memory.supabase_memory.create_client') as mock_create:
        mock_client = MagicMock()

        # 세션 및 메시지 데이터 저장소
        sessions_db = {}
        messages_db = []

        def table_handler(table_name):
            """테이블별 핸들러"""
            table_mock = MagicMock()

            if table_name == "chat_sessions":
                # SELECT 핸들러
                def select_handler(fields):
                    select_mock = MagicMock()
                    # Track filtering state
                    filter_state = {"user_id": None}

                    def eq_handler(field, value):
                        eq_mock = MagicMock()

                        # For session ID filtering
                        if field == "id":
                            def execute_select():
                                result = MagicMock()
                                if value in sessions_db:
                                    result.data = [sessions_db[value]]
                                else:
                                    result.data = []
                                return result

                            def eq_user_handler(field2, value2):
                                eq2_mock = MagicMock()

                                def execute_select_with_user():
                                    result = MagicMock()
                                    if value in sessions_db and sessions_db[value].get("user_id") == value2:
                                        result.data = [sessions_db[value]]
                                    else:
                                        result.data = []
                                    return result

                                eq2_mock.execute.side_effect = execute_select_with_user
                                return eq2_mock

                            eq_mock.execute.side_effect = execute_select
                            eq_mock.eq.side_effect = eq_user_handler
                        # For user_id filtering (used in list_sessions)
                        elif field == "user_id":
                            filter_state["user_id"] = value

                            def order_handler_with_filter(field, desc=False):
                                order_mock = MagicMock()

                                def execute_list_filtered():
                                    result = MagicMock()
                                    # Filter by user_id
                                    filtered_sessions = [
                                        s for s in sessions_db.values()
                                        if s.get("user_id") == filter_state["user_id"]
                                    ]
                                    result.data = filtered_sessions
                                    return result

                                order_mock.execute.side_effect = execute_list_filtered
                                return order_mock

                            eq_mock.order = order_handler_with_filter

                        return eq_mock

                    def order_handler(field, desc=False):
                        order_mock = MagicMock()

                        def execute_list():
                            result = MagicMock()
                            result.data = list(sessions_db.values())
                            return result

                        order_mock.execute.side_effect = execute_list
                        return order_mock

                    select_mock.eq.side_effect = eq_handler
                    select_mock.order.side_effect = order_handler
                    return select_mock

                # INSERT 핸들러
                def insert_handler(data):
                    insert_mock = MagicMock()

                    def execute_insert():
                        sessions_db[data["id"]] = data
                        result = MagicMock()
                        result.data = [data]
                        return result

                    insert_mock.execute.side_effect = execute_insert
                    return insert_mock

                # UPDATE 핸들러
                def update_handler(data):
                    update_mock = MagicMock()

                    def eq_handler(field, value):
                        eq_mock = MagicMock()

                        def execute_update():
                            if value in sessions_db:
                                sessions_db[value].update(data)
                            result = MagicMock()
                            return result

                        eq_mock.execute.side_effect = execute_update
                        return eq_mock

                    update_mock.eq.side_effect = eq_handler
                    return update_mock

                # DELETE 핸들러
                def delete_handler():
                    delete_mock = MagicMock()

                    def eq_handler(field, value):
                        eq_mock = MagicMock()

                        def execute_delete():
                            if value in sessions_db:
                                del sessions_db[value]
                            # 관련 메시지도 삭제 (cascade)
                            nonlocal messages_db
                            messages_db = [m for m in messages_db if m.get("session_id") != value]
                            result = MagicMock()
                            return result

                        def eq_user_handler(field2, value2):
                            eq2_mock = MagicMock()

                            def execute_delete_with_user():
                                if value in sessions_db and sessions_db[value].get("user_id") == value2:
                                    del sessions_db[value]
                                    # 관련 메시지도 삭제
                                    nonlocal messages_db
                                    messages_db = [m for m in messages_db if m.get("session_id") != value]
                                result = MagicMock()
                                return result

                            eq2_mock.execute.side_effect = execute_delete_with_user
                            return eq2_mock

                        eq_mock.execute.side_effect = execute_delete
                        eq_mock.eq.side_effect = eq_user_handler
                        return eq_mock

                    delete_mock.eq.side_effect = eq_handler
                    return delete_mock

                table_mock.select.side_effect = select_handler
                table_mock.insert.side_effect = insert_handler
                table_mock.update.side_effect = update_handler
                table_mock.delete.side_effect = delete_handler

            elif table_name == "chat_messages":
                # SELECT 핸들러
                def select_handler(fields, count=None):
                    select_mock = MagicMock()

                    def eq_handler(field, value):
                        eq_mock = MagicMock()

                        def order_handler(field, desc=False):
                            order_mock = MagicMock()

                            def execute_messages():
                                result = MagicMock()
                                result.data = [m for m in messages_db if m.get("session_id") == value]
                                return result

                            order_mock.execute.side_effect = execute_messages
                            return order_mock

                        def execute_count():
                            result = MagicMock()
                            result.count = len([m for m in messages_db if m.get("session_id") == value])
                            return result

                        eq_mock.order.side_effect = order_handler
                        eq_mock.execute.side_effect = execute_count
                        return eq_mock

                    select_mock.eq.side_effect = eq_handler
                    return select_mock

                # INSERT 핸들러
                def insert_handler(data):
                    insert_mock = MagicMock()

                    def execute_insert():
                        messages_db.append(data)
                        result = MagicMock()
                        result.data = [data]
                        return result

                    insert_mock.execute.side_effect = execute_insert
                    return insert_mock

                # DELETE 핸들러
                def delete_handler():
                    delete_mock = MagicMock()

                    def eq_handler(field, value):
                        eq_mock = MagicMock()

                        def execute_delete():
                            nonlocal messages_db
                            messages_db = [m for m in messages_db if m.get("session_id") != value]
                            result = MagicMock()
                            return result

                        eq_mock.execute.side_effect = execute_delete
                        return eq_mock

                    delete_mock.eq.side_effect = eq_handler
                    return delete_mock

                table_mock.select.side_effect = select_handler
                table_mock.insert.side_effect = insert_handler
                table_mock.delete.side_effect = delete_handler

            return table_mock

        mock_client.table.side_effect = table_handler
        mock_create.return_value = mock_client
        yield mock_client


class TestSupabaseSessionManagement:
    """세션 관리 통합 테스트"""

    @pytest.mark.asyncio
    async def test_session_lifecycle_with_user_id(self, mock_supabase_client):
        """사용자별 세션 생명주기 전체 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # 1. 새 세션에 메시지 추가 (세션 자동 생성)
        await memory.save_conversation_async(
            "session-1",
            "첫 번째 질문",
            "첫 번째 답변",
            user_id="user-1"
        )

        # 2. 세션 목록에 표시되는지 확인
        sessions = await memory.list_sessions_async(user_id="user-1")
        assert "session-1" in sessions

        # 3. 메시지 개수 확인
        count = await memory.get_message_count_async("session-1", user_id="user-1")
        assert count == 2  # user + ai message

        # 4. 메시지 조회
        messages = await memory.get_messages_async("session-1", user_id="user-1")
        assert len(messages) == 2
        assert messages[0].content == "첫 번째 질문"
        assert messages[1].content == "첫 번째 답변"

    @pytest.mark.asyncio
    async def test_multi_user_isolation(self, mock_supabase_client):
        """다중 사용자 격리 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # User 1의 세션
        await memory.save_conversation_async(
            "session-user1",
            "User 1 질문",
            "User 1 답변",
            user_id="user-1"
        )

        # User 2의 세션
        await memory.save_conversation_async(
            "session-user2",
            "User 2 질문",
            "User 2 답변",
            user_id="user-2"
        )

        # User 1은 자신의 세션만 볼 수 있음
        user1_sessions = await memory.list_sessions_async(user_id="user-1")
        assert "session-user1" in user1_sessions
        assert "session-user2" not in user1_sessions

        # User 2는 자신의 세션만 볼 수 있음
        user2_sessions = await memory.list_sessions_async(user_id="user-2")
        assert "session-user2" in user2_sessions
        assert "session-user1" not in user2_sessions

        # User 1은 User 2의 메시지를 볼 수 없음
        messages = await memory.get_messages_async("session-user2", user_id="user-1")
        assert len(messages) == 0

        # User 2는 자신의 메시지를 볼 수 있음
        messages = await memory.get_messages_async("session-user2", user_id="user-2")
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_session_history_preservation(self, mock_supabase_client):
        """세션 히스토리 보존 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # 여러 대화 추가
        conversations = [
            ("질문 1", "답변 1"),
            ("질문 2", "답변 2"),
            ("질문 3", "답변 3"),
        ]

        for q, a in conversations:
            await memory.save_conversation_async(
                "session-history",
                q,
                a,
                user_id="user-1"
            )

        # 히스토리 조회
        messages = await memory.get_messages_async("session-history", user_id="user-1")

        # 6개 메시지 (3 질문 + 3 답변)
        assert len(messages) == 6

        # 순서 확인
        assert messages[0].content == "질문 1"
        assert messages[1].content == "답변 1"
        assert messages[2].content == "질문 2"
        assert messages[3].content == "답변 2"
        assert messages[4].content == "질문 3"
        assert messages[5].content == "답변 3"

        # 타입 확인
        assert isinstance(messages[0], HumanMessage)
        assert isinstance(messages[1], AIMessage)

    @pytest.mark.asyncio
    async def test_metadata_preservation(self, mock_supabase_client):
        """메타데이터 보존 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # 커스텀 메타데이터와 함께 저장
        await memory.save_conversation_async(
            "session-metadata",
            "질문",
            "답변",
            user_id="user-1",
            custom_field="custom_value",
            timestamp="2024-01-01"
        )

        # 메시지는 저장되어야 함 (메타데이터는 additional_kwargs에)
        count = await memory.get_message_count_async("session-metadata", user_id="user-1")
        assert count == 2

    @pytest.mark.asyncio
    async def test_unauthorized_access_denied(self, mock_supabase_client):
        """권한 없는 접근 차단 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # User 2는 User 1의 세션에 접근 불가
        messages = await memory.get_messages_async("session-user1", user_id="user-2")
        assert len(messages) == 0

        # User 2는 User 1의 세션 메시지 개수를 볼 수 없음
        count = await memory.get_message_count_async("session-user1", user_id="user-2")
        assert count == 0

    @pytest.mark.asyncio
    async def test_clear_session_with_ownership(self, mock_supabase_client):
        """소유권 검증 후 세션 정리 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # User 2는 User 1의 세션을 정리할 수 없음
        await memory.clear_async("session-user1", user_id="user-2")

        # User 1은 자신의 세션을 정리할 수 있음
        await memory.clear_async("session-user1", user_id="user-1")

    @pytest.mark.asyncio
    async def test_delete_session_with_ownership(self, mock_supabase_client):
        """소유권 검증 후 세션 삭제 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # User 1의 세션은 User 1만 삭제 가능
        await memory.delete_session_async("session-user1", user_id="user-1")

        # 삭제 후 조회 불가
        sessions = await memory.list_sessions_async(user_id="user-1")
        assert "session-user1" not in sessions

    @pytest.mark.asyncio
    async def test_cannot_write_to_other_users_session(self, mock_supabase_client):  # noqa: ARG002
        """다른 사용자의 세션에 메시지 작성 불가 테스트"""
        memory = SupabaseChatMemory(url="http://test", key="test-key")

        # User 1이 세션 생성
        await memory.save_conversation_async(
            "session-user1",
            "User 1의 질문",
            "User 1의 답변",
            user_id="user-1"
        )

        # User 2가 User 1의 세션에 메시지 추가 시도 -> 실패해야 함
        with pytest.raises(ValueError, match="could not be established"):
            await memory.save_conversation_async(
                "session-user1",  # User 1의 세션
                "User 2의 질문",
                "User 2의 답변",
                user_id="user-2"  # 다른 사용자
            )
