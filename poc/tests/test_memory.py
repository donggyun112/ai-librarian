"""Memory 모듈 테스트"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

from src.memory import ChatMemory, InMemoryChatMemory
from src.memory.base import ChatMemory as ChatMemoryBase
from src.memory.supabase_memory import SupabaseChatMemory, SessionAccessDenied


class TestChatMemoryInterface:
    """ChatMemory 인터페이스 테스트"""

    def test_is_abstract_class(self):
        """ChatMemory는 추상 클래스"""
        with pytest.raises(TypeError):
            ChatMemoryBase()

    def test_inmemory_implements_interface(self):
        """InMemoryChatMemory는 ChatMemory 구현체"""
        memory = InMemoryChatMemory()
        assert isinstance(memory, ChatMemory)


class TestInMemoryChatMemory:
    """InMemoryChatMemory 테스트"""

    def test_empty_session_returns_empty_list(self):
        """존재하지 않는 세션은 빈 리스트 반환"""
        memory = InMemoryChatMemory()
        messages = memory.get_messages("nonexistent")
        assert messages == []

    def test_add_user_message(self):
        """사용자 메시지 추가"""
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "안녕하세요")

        messages = memory.get_messages("session-1")
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "안녕하세요"

    def test_add_ai_message(self):
        """AI 메시지 추가"""
        memory = InMemoryChatMemory()
        memory.add_ai_message("session-1", "안녕하세요!")

        messages = memory.get_messages("session-1")
        assert len(messages) == 1
        assert isinstance(messages[0], AIMessage)
        assert messages[0].content == "안녕하세요!"

    def test_save_conversation(self):
        """대화 쌍 저장"""
        memory = InMemoryChatMemory()
        memory.save_conversation("session-1", "질문입니다", "답변입니다")

        messages = memory.get_messages("session-1")
        assert len(messages) == 2
        assert isinstance(messages[0], HumanMessage)
        assert isinstance(messages[1], AIMessage)
        assert messages[0].content == "질문입니다"
        assert messages[1].content == "답변입니다"

    def test_clear_session(self):
        """세션 히스토리 초기화"""
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "메시지")
        memory.clear("session-1")

        messages = memory.get_messages("session-1")
        assert messages == []

    def test_clear_nonexistent_session_no_error(self):
        """존재하지 않는 세션 초기화해도 에러 없음"""
        memory = InMemoryChatMemory()
        memory.clear("nonexistent")  # 에러 발생하지 않아야 함

    def test_session_isolation(self):
        """세션 간 격리"""
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "세션1 메시지")
        memory.add_user_message("session-2", "세션2 메시지")

        messages_1 = memory.get_messages("session-1")
        messages_2 = memory.get_messages("session-2")

        assert len(messages_1) == 1
        assert len(messages_2) == 1
        assert messages_1[0].content == "세션1 메시지"
        assert messages_2[0].content == "세션2 메시지"

    def test_get_messages_returns_copy(self):
        """get_messages는 복사본 반환 (원본 보호)"""
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "메시지")

        messages = memory.get_messages("session-1")
        messages.clear()  # 반환된 리스트 수정

        # 원본은 영향받지 않아야 함
        original = memory.get_messages("session-1")
        assert len(original) == 1

    def test_delete_session(self):
        """세션 완전 삭제"""
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "메시지")
        memory.delete_session("session-1")

        assert "session-1" not in memory.list_sessions()

    def test_list_sessions(self):
        """모든 세션 조회"""
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "메시지1")
        memory.add_user_message("session-2", "메시지2")

        sessions = memory.list_sessions()
        assert "session-1" in sessions
        assert "session-2" in sessions

    def test_get_message_count(self):
        """메시지 개수 조회"""
        memory = InMemoryChatMemory()
        assert memory.get_message_count("session-1") == 0

        memory.save_conversation("session-1", "질문", "답변")
        assert memory.get_message_count("session-1") == 2

    def test_user_id_not_in_additional_kwargs(self):
        """user_id는 additional_kwargs에 포함되지 않음 (LLM API 호환성)"""
        memory = InMemoryChatMemory()

        # user_id와 함께 메시지 추가
        memory.add_user_message("session-1", "테스트 메시지", user_id="user-123")
        memory.add_ai_message("session-1", "AI 응답", user_id="user-123")

        messages = memory.get_messages("session-1")

        # user_id가 additional_kwargs에 없어야 함
        assert "user_id" not in messages[0].additional_kwargs
        assert "user_id" not in messages[1].additional_kwargs

    def test_other_metadata_preserved_without_user_id(self):
        """user_id 제외한 다른 메타데이터는 보존"""
        memory = InMemoryChatMemory()

        memory.add_user_message(
            "session-1",
            "테스트",
            user_id="user-123",  # 필터링됨
            timestamp="2024-01-01",  # 보존됨
            custom_field="value"  # 보존됨
        )

        messages = memory.get_messages("session-1")

        # user_id만 제외되고 나머지는 보존
        assert "user_id" not in messages[0].additional_kwargs
        assert messages[0].additional_kwargs["timestamp"] == "2024-01-01"
        assert messages[0].additional_kwargs["custom_field"] == "value"


class TestSupervisorWithMemory:
    """Supervisor 메모리 주입 테스트"""

    def test_supervisor_uses_injected_memory(self):
        """Supervisor에 주입된 메모리 사용"""
        from src.supervisor import Supervisor

        memory = InMemoryChatMemory()
        supervisor = Supervisor(memory=memory)

        assert supervisor.memory is memory

    def test_supervisor_default_memory(self):
        """메모리 미지정 시 기본 InMemoryChatMemory 사용"""
        from src.supervisor import Supervisor

        supervisor = Supervisor()
        assert isinstance(supervisor.memory, InMemoryChatMemory)

    @pytest.mark.asyncio
    async def test_build_messages_includes_history(self):
        """_build_messages가 히스토리를 포함하는지 확인"""
        from src.supervisor import Supervisor
        from langchain_core.messages import SystemMessage

        memory = InMemoryChatMemory()
        memory.save_conversation("session-1", "이전 질문", "이전 답변")

        supervisor = Supervisor(memory=memory)
        messages = await supervisor._build_messages("session-1", "새 질문")

        # SystemMessage + 이전 대화 2개 + 새 질문 = 4개
        assert len(messages) == 4
        assert isinstance(messages[0], SystemMessage)
        assert messages[1].content == "이전 질문"
        assert messages[2].content == "이전 답변"
        assert messages[3].content == "새 질문"

    @pytest.mark.asyncio
    async def test_build_messages_passes_client_to_memory(self):
        """_build_messages가 user-scoped client를 메모리에 전달하는지 확인"""
        from src.supervisor import Supervisor

        class DummyAsyncMemory:
            def __init__(self):
                self.captured_client = None

            async def get_messages_async(self, session_id: str, user_id=None, client=None):
                self.captured_client = client
                return []

        memory = DummyAsyncMemory()
        supervisor = Supervisor(memory=memory)

        client = object()
        await supervisor._build_messages("session-1", "새 질문", user_id="user-1", client=client)

        assert memory.captured_client is client


class TestSupabaseMemoryGuard:
    """SupabaseChatMemory의 user-scoped client 강제 확인"""

    @pytest.mark.asyncio
    async def test_requires_user_scoped_client_when_enabled(self):
        from src.memory.supabase_memory import SupabaseChatMemory

        memory = SupabaseChatMemory(
            url="http://localhost",
            key="test-key",
            require_user_scoped_client=True,
        )

        with pytest.raises(ValueError):
            await memory.get_messages_async("session-1", user_id="user-1", client=None)

    @pytest.mark.asyncio
    async def test_save_to_history_async_adds_to_memory(self):
        """_save_to_history_async가 메모리에 저장하는지 확인"""
        from src.supervisor import Supervisor

        memory = InMemoryChatMemory()
        supervisor = Supervisor(memory=memory)

        await supervisor._save_to_history_async("session-1", "질문", "답변")

        messages = memory.get_messages("session-1")
        assert len(messages) == 2
        assert messages[0].content == "질문"
        assert messages[1].content == "답변"

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self):
        """여러 세션이 서로 격리되는지 확인"""
        from src.supervisor import Supervisor

        memory = InMemoryChatMemory()
        supervisor = Supervisor(memory=memory)

        await supervisor._save_to_history_async("session-1", "질문1", "답변1")
        await supervisor._save_to_history_async("session-2", "질문2", "답변2")

        messages_1 = await supervisor._build_messages("session-1", "새질문")
        messages_2 = await supervisor._build_messages("session-2", "새질문")

        # session-1: System + 질문1 + 답변1 + 새질문 = 4
        # session-2: System + 질문2 + 답변2 + 새질문 = 4
        assert len(messages_1) == 4
        assert len(messages_2) == 4
        assert messages_1[1].content == "질문1"
        assert messages_2[1].content == "질문2"

    @pytest.mark.asyncio
    async def test_build_messages_without_session_no_history(self):
        """session_id 없이 호출 시 히스토리 없음 (process 메서드 동작)"""
        from src.supervisor import Supervisor
        from langchain_core.messages import SystemMessage, HumanMessage

        memory = InMemoryChatMemory()
        memory.save_conversation("session-1", "저장된 질문", "저장된 답변")

        supervisor = Supervisor(memory=memory)

        # session_id 없이 빌드하면 다른 세션으로 취급
        messages = await supervisor._build_messages("new-session", "새 질문")

        # new-session에는 히스토리가 없음: System + 새 질문 = 2
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)


class TestSupabaseChatMemory:
    """SupabaseChatMemory 테스트 (async 전용)"""

    @pytest.fixture
    def mock_async_client(self):
        """Mock Supabase AsyncClient"""
        return MagicMock()

    @pytest.fixture
    def memory(self, mock_async_client):
        """SupabaseChatMemory 인스턴스"""
        return SupabaseChatMemory(
            url="http://test",
            key="test-key",
            async_client=mock_async_client,
        )

    def test_implements_interface(self, memory):
        """SupabaseChatMemory는 ChatMemory 구현체"""
        assert isinstance(memory, ChatMemory)

    @pytest.mark.asyncio
    async def test_get_messages_async_filters_by_ownership(self, memory, mock_async_client):
        """user_id가 제공되면 세션 소유권 검증"""
        session_check = MagicMock()
        session_check.data = [{"id": "session-1", "user_id": "user-1"}]
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        messages_response = MagicMock()
        messages_response.data = []
        mock_async_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
            return_value=messages_response
        )

        messages = await memory.get_messages_async("session-1", user_id="user-1")

        assert mock_async_client.table.called
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_messages_async_denies_wrong_user(self, memory, mock_async_client):
        """잘못된 user_id로는 SessionAccessDenied 발생"""
        session_check = MagicMock()
        session_check.data = []
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        with pytest.raises(SessionAccessDenied):
            await memory.get_messages_async("session-1", user_id="wrong-user")

    @pytest.mark.asyncio
    async def test_list_sessions_async_filters_by_user_id(self, memory, mock_async_client):
        """user_id가 제공되면 해당 사용자의 세션만 조회"""
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "session-1", "title": None, "last_message_at": None},
            {"id": "session-2", "title": None, "last_message_at": None},
        ]

        mock_table = mock_async_client.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_order = mock_eq.order.return_value
        mock_order.execute = AsyncMock(return_value=mock_response)

        sessions = await memory.list_sessions_async(user_id="user-1")

        mock_select.eq.assert_called_once_with("user_id", "user-1")
        assert len(sessions) == 2
        assert sessions[0]["id"] == "session-1"
        assert sessions[1]["id"] == "session-2"

    @pytest.mark.asyncio
    async def test_delete_session_async_with_ownership(self, memory, mock_async_client):
        """user_id가 제공되면 소유권 검증 후 삭제"""
        session_check = MagicMock()
        session_check.data = [{"id": "session-1", "user_id": "user-1"}]
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        mock_async_client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock()
        )

        await memory.delete_session_async("session-1", user_id="user-1")

        assert mock_async_client.table.return_value.delete.called

    @pytest.mark.asyncio
    async def test_clear_async_verifies_ownership(self, memory, mock_async_client):
        """user_id가 제공되면 세션 소유권 검증 후 메시지 삭제"""
        session_check = MagicMock()
        session_check.data = [{"id": "session-1", "user_id": "user-1"}]
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        mock_async_client.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock()
        )

        await memory.clear_async("session-1", user_id="user-1")

        assert mock_async_client.table.return_value.select.called

    @pytest.mark.asyncio
    async def test_clear_async_denies_wrong_user(self, memory, mock_async_client):
        """잘못된 user_id로는 clear 시 SessionAccessDenied 발생"""
        session_check = MagicMock()
        session_check.data = []
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        with pytest.raises(SessionAccessDenied):
            await memory.clear_async("session-1", user_id="wrong-user")

    @pytest.mark.asyncio
    async def test_save_conversation_async_preserves_metadata(self, memory, mock_async_client):
        """비동기 save_conversation이 메타데이터를 보존"""
        session_check = MagicMock()
        session_check.data = [{"id": "session-1", "user_id": "user-1"}]

        mock_async_client.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        insert_mock = mock_async_client.table.return_value.insert.return_value
        insert_mock.on_conflict.return_value = insert_mock
        insert_mock.execute = AsyncMock(return_value=MagicMock())
        mock_async_client.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock()
        )

        await memory.save_conversation_async(
            "session-1",
            "질문",
            "답변",
            user_id="user-1",
            custom_metadata="test"
        )

        assert mock_async_client.table.return_value.insert.call_count >= 2

    @pytest.mark.asyncio
    async def test_get_message_count_async_verifies_ownership(self, memory, mock_async_client):
        """user_id가 제공되면 세션 소유권 검증 후 개수 조회"""
        session_check = MagicMock()
        session_check.data = [{"id": "session-1", "user_id": "user-1"}]
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        count_response = MagicMock()
        count_response.count = 5
        mock_async_client.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
            return_value=count_response
        )

        count = await memory.get_message_count_async("session-1", user_id="user-1")

        assert count == 5

    @pytest.mark.asyncio
    async def test_get_message_count_async_raises_for_wrong_user(self, memory, mock_async_client):
        """잘못된 user_id로는 SessionAccessDenied 발생"""
        session_check = MagicMock()
        session_check.data = []
        mock_async_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=session_check
        )

        with pytest.raises(SessionAccessDenied):
            await memory.get_message_count_async("session-1", user_id="wrong-user")
