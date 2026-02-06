"""ChatMemory 추상 인터페이스

SQL, Redis 등으로 교체 시 이 인터페이스를 구현하면 됩니다.

사용 예시:
    from src.memory.supabase_memory import SupabaseChatMemory

    memory = SupabaseChatMemory(url="...", key="...")
    supervisor = Supervisor(memory=memory)

Note:
    비동기 메서드(get_messages_async, save_conversation_async 등)가
    primary interface입니다. 동기 메서드는 InMemoryChatMemory 등
    테스트/개발용 구현체를 위한 optional interface입니다.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from langchain_core.messages import BaseMessage


class ChatMemory(ABC):
    """대화 히스토리 저장소 인터페이스

    세션별로 대화 기록을 저장하고 조회합니다.

    Primary interface: async 메서드 (get_messages_async, save_conversation_async 등)
    Optional interface: sync 메서드 (InMemoryChatMemory 등 동기 구현체용)
    """

    # ==============================================================
    # Async interface (primary - 프로덕션 코드에서 사용)
    # ==============================================================

    @abstractmethod
    async def get_messages_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회 (비동기)"""
        ...

    @abstractmethod
    async def save_conversation_async(
        self, session_id: str, user_message: str, ai_message: str, **kwargs
    ) -> None:
        """대화 쌍(사용자 + AI) 저장 (비동기)"""
        ...

    @abstractmethod
    async def list_sessions_async(
        self, user_id: Optional[str] = None, **kwargs
    ) -> List[str]:
        """모든 세션 ID 조회 (비동기)"""
        ...

    @abstractmethod
    async def get_message_count_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> int:
        """세션의 메시지 개수 (비동기)"""
        ...

    @abstractmethod
    async def delete_session_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> None:
        """세션 및 관련 메시지 완전 삭제 (비동기)"""
        ...

    @abstractmethod
    async def clear_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> None:
        """세션 히스토리 메시지 삭제 (비동기)"""
        ...

    @abstractmethod
    async def init_session_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> bool:
        """빈 세션 초기화 (비동기)"""
        ...

    # ==============================================================
    # Sync interface (optional - InMemory 등 동기 구현체용)
    # ==============================================================

    def get_messages(self, session_id: str, **kwargs) -> List[BaseMessage]:
        raise NotImplementedError

    def add_user_message(self, session_id: str, content: str, **kwargs) -> None:
        raise NotImplementedError

    def add_ai_message(self, session_id: str, content: str, **kwargs) -> None:
        raise NotImplementedError

    def clear(self, session_id: str, **kwargs) -> None:
        raise NotImplementedError

    def init_session(self, session_id: str, **kwargs) -> None:
        raise NotImplementedError

    def save_conversation(self, session_id: str, user_message: str, ai_message: str, **kwargs) -> None:
        self.add_user_message(session_id, user_message, **kwargs)
        self.add_ai_message(session_id, ai_message, **kwargs)
