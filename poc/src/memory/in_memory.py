"""In-Memory 대화 히스토리 저장소

개발/테스트용. 서버 재시작 시 데이터 소실됩니다.
프로덕션에서는 SupabaseChatMemory를 사용하세요.
"""
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .base import ChatMemory


class InMemoryChatMemory(ChatMemory):
    """In-Memory 기반 대화 히스토리 저장소

    특징:
        - 빠른 읽기/쓰기
        - 서버 재시작 시 데이터 소실
        - 개발/테스트 환경에 적합
        - 스레드 안전 (Lock 사용)
        - async/sync 양쪽 모두 지원
    """

    def __init__(self) -> None:
        self._store: dict[str, List[BaseMessage]] = defaultdict(list)
        self._lock = threading.Lock()

    # ==============================================================
    # Sync interface
    # ==============================================================

    def get_messages(self, session_id: str, **kwargs) -> List[BaseMessage]:
        with self._lock:
            return self._store[session_id].copy()

    def add_user_message(self, session_id: str, content: str, **kwargs) -> None:
        with self._lock:
            msg = HumanMessage(content=content)
            metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
            if 'timestamp' not in metadata:
                metadata['timestamp'] = datetime.now(timezone.utc).isoformat()
            msg.additional_kwargs.update(metadata)
            self._store[session_id].append(msg)

    def add_ai_message(self, session_id: str, content: str, **kwargs) -> None:
        with self._lock:
            msg = AIMessage(content=content)
            metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
            if 'timestamp' not in metadata:
                metadata['timestamp'] = datetime.now(timezone.utc).isoformat()
            msg.additional_kwargs.update(metadata)
            self._store[session_id].append(msg)

    def clear(self, session_id: str, **kwargs) -> None:
        with self._lock:
            if session_id in self._store:
                self._store[session_id].clear()

    def delete_session(self, session_id: str, **kwargs) -> None:
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]

    def list_sessions(self, **kwargs) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def get_message_count(self, session_id: str, **kwargs) -> int:
        with self._lock:
            return len(self._store[session_id])

    def init_session(self, session_id: str, **kwargs) -> None:
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = []

    # ==============================================================
    # Async interface (sync 위임)
    # ==============================================================

    async def get_messages_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> List[BaseMessage]:
        return self.get_messages(session_id)

    async def save_conversation_async(
        self, session_id: str, user_message: str, ai_message: str, **kwargs
    ) -> None:
        self.save_conversation(session_id, user_message, ai_message, **kwargs)

    async def list_sessions_async(
        self, user_id: Optional[str] = None, **kwargs
    ) -> List[str]:
        return self.list_sessions()

    async def get_message_count_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> int:
        return self.get_message_count(session_id)

    async def delete_session_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> None:
        self.delete_session(session_id)

    async def clear_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> None:
        self.clear(session_id)

    async def init_session_async(
        self, session_id: str, user_id: Optional[str] = None, **kwargs
    ) -> bool:
        self.init_session(session_id)
        return True
