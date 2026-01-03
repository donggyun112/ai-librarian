"""ChatMemory 추상 인터페이스

SQL, Redis 등으로 교체 시 이 인터페이스를 구현하면 됩니다.

사용 예시:
    # SQL 구현체로 교체
    from src.memory.sql import SQLChatMemory

    memory = SQLChatMemory(connection_string="postgresql://...")
    supervisor = Supervisor(memory=memory)
"""
from abc import ABC, abstractmethod
from typing import List

from langchain_core.messages import BaseMessage


class ChatMemory(ABC):
    """대화 히스토리 저장소 인터페이스

    세션별로 대화 기록을 저장하고 조회합니다.
    SQL, Redis, In-Memory 등 다양한 백엔드로 구현 가능합니다.
    """

    @abstractmethod
    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회

        Args:
            session_id: 세션 식별자

        Returns:
            대화 메시지 리스트 (시간순)
        """
        pass

    @abstractmethod
    def add_user_message(self, session_id: str, content: str) -> None:
        """사용자 메시지 추가

        Args:
            session_id: 세션 식별자
            content: 메시지 내용
        """
        pass

    @abstractmethod
    def add_ai_message(self, session_id: str, content: str) -> None:
        """AI 메시지 추가

        Args:
            session_id: 세션 식별자
            content: 메시지 내용
        """
        pass

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """세션 히스토리 초기화

        Args:
            session_id: 세션 식별자
        """
        pass

    def save_conversation(self, session_id: str, user_message: str, ai_message: str) -> None:
        """대화 쌍(사용자 + AI) 저장 - 편의 메서드

        Args:
            session_id: 세션 식별자
            user_message: 사용자 메시지
            ai_message: AI 응답
        """
        self.add_user_message(session_id, user_message)
        self.add_ai_message(session_id, ai_message)
