"""Memory 모듈 테스트"""
import pytest
from langchain_core.messages import HumanMessage, AIMessage

from src.memory import ChatMemory, InMemoryChatMemory
from src.memory.base import ChatMemory as ChatMemoryBase


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

    def test_build_messages_includes_history(self):
        """_build_messages가 히스토리를 포함하는지 확인"""
        from src.supervisor import Supervisor
        from langchain_core.messages import SystemMessage

        memory = InMemoryChatMemory()
        memory.save_conversation("session-1", "이전 질문", "이전 답변")

        supervisor = Supervisor(memory=memory)
        messages = supervisor._build_messages("session-1", "새 질문")

        # SystemMessage + 이전 대화 2개 + 새 질문 = 4개
        assert len(messages) == 4
        assert isinstance(messages[0], SystemMessage)
        assert messages[1].content == "이전 질문"
        assert messages[2].content == "이전 답변"
        assert messages[3].content == "새 질문"

    def test_save_to_history_adds_to_memory(self):
        """_save_to_history가 메모리에 저장하는지 확인"""
        from src.supervisor import Supervisor

        memory = InMemoryChatMemory()
        supervisor = Supervisor(memory=memory)

        supervisor._save_to_history("session-1", "질문", "답변")

        messages = memory.get_messages("session-1")
        assert len(messages) == 2
        assert messages[0].content == "질문"
        assert messages[1].content == "답변"

    def test_clear_history_clears_memory(self):
        """clear_history가 메모리를 초기화하는지 확인"""
        from src.supervisor import Supervisor

        memory = InMemoryChatMemory()
        memory.save_conversation("session-1", "질문", "답변")

        supervisor = Supervisor(memory=memory)
        supervisor.clear_history("session-1")

        messages = memory.get_messages("session-1")
        assert messages == []

    def test_multiple_sessions_isolated(self):
        """여러 세션이 서로 격리되는지 확인"""
        from src.supervisor import Supervisor

        memory = InMemoryChatMemory()
        supervisor = Supervisor(memory=memory)

        supervisor._save_to_history("session-1", "질문1", "답변1")
        supervisor._save_to_history("session-2", "질문2", "답변2")

        messages_1 = supervisor._build_messages("session-1", "새질문")
        messages_2 = supervisor._build_messages("session-2", "새질문")

        # session-1: System + 질문1 + 답변1 + 새질문 = 4
        # session-2: System + 질문2 + 답변2 + 새질문 = 4
        assert len(messages_1) == 4
        assert len(messages_2) == 4
        assert messages_1[1].content == "질문1"
        assert messages_2[1].content == "질문2"

    def test_build_messages_without_session_no_history(self):
        """session_id 없이 호출 시 히스토리 없음 (process 메서드 동작)"""
        from src.supervisor import Supervisor
        from langchain_core.messages import SystemMessage, HumanMessage

        memory = InMemoryChatMemory()
        memory.save_conversation("session-1", "저장된 질문", "저장된 답변")

        supervisor = Supervisor(memory=memory)

        # session_id 없이 빌드하면 다른 세션으로 취급
        messages = supervisor._build_messages("new-session", "새 질문")

        # new-session에는 히스토리가 없음: System + 새 질문 = 2
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
