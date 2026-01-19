"""In-Memory 대화 히스토리 저장소

개발/테스트용. 서버 재시작 시 데이터 소실됩니다.
프로덕션에서는 SQLChatMemory나 RedisChatMemory를 사용하세요.
"""
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .base import ChatMemory


class InMemoryChatMemory(ChatMemory):
    """In-Memory 기반 대화 히스토리 저장소

    특징:
        - 빠른 읽기/쓰기
        - 서버 재시작 시 데이터 소실
        - 개발/테스트 환경에 적합
        - 스레드 안전 (Lock 사용)

    사용 예시:
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "안녕하세요")
        memory.add_ai_message("session-1", "안녕하세요! 무엇을 도와드릴까요?")

        messages = memory.get_messages("session-1")
        # [HumanMessage(...), AIMessage(...)]
    """

    def __init__(self):
        self._store: dict[str, List[BaseMessage]] = defaultdict(list)
        self._lock = threading.Lock()

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회"""
        with self._lock:
            return self._store[session_id].copy()

    def add_user_message(self, session_id: str, content: str, **kwargs) -> None:
        """사용자 메시지 추가"""
        with self._lock:
            msg = HumanMessage(content=content)
            # user_id는 메모리 계층 메타데이터이므로 LangChain 메시지에서 제외
            metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
            # 타임스탬프 자동 추가
            if 'timestamp' not in metadata:
                metadata['timestamp'] = datetime.now(timezone.utc).isoformat()
            msg.additional_kwargs.update(metadata)
            self._store[session_id].append(msg)

    def add_ai_message(self, session_id: str, content: str, **kwargs) -> None:
        """AI 메시지 추가"""
        with self._lock:
            msg = AIMessage(content=content)
            # user_id는 메모리 계층 메타데이터이므로 LangChain 메시지에서 제외
            metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
            # 타임스탬프 자동 추가
            if 'timestamp' not in metadata:
                metadata['timestamp'] = datetime.now(timezone.utc).isoformat()
            msg.additional_kwargs.update(metadata)
            self._store[session_id].append(msg)

    def clear(self, session_id: str) -> None:
        """세션 히스토리 초기화"""
        with self._lock:
            if session_id in self._store:
                self._store[session_id].clear()

    def delete_session(self, session_id: str) -> None:
        """세션 완전 삭제"""
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]

    def list_sessions(self) -> List[str]:
        """모든 세션 ID 조회"""
        with self._lock:
            return list(self._store.keys())

    def get_message_count(self, session_id: str) -> int:
        """세션의 메시지 개수"""
        with self._lock:
            return len(self._store[session_id])

    def init_session(self, session_id: str) -> None:
        """빈 세션 초기화 (세션 생성 시 호출)

        Args:
            session_id: 세션 식별자
        """
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = []
