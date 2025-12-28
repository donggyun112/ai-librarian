# 04. Memory System 심층 분석

> 대화 히스토리 저장소 - 세션 기반 대화 관리

---

## 1. 파일 정보

| 파일 | 라인 수 | 역할 |
|------|---------|------|
| `src/memory/base.py` | 76줄 | 추상 인터페이스 |
| `src/memory/in_memory.py` | 63줄 | In-Memory 구현체 |

---

## 2. 아키텍처 개요

### 2.1 Repository 패턴 적용

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Memory Repository Pattern                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                       ┌─────────────────────┐                           │
│                       │     ChatMemory      │                           │
│                       │     (Abstract)      │                           │
│                       │                     │                           │
│                       │ + get_messages()    │                           │
│                       │ + add_user_message()│                           │
│                       │ + add_ai_message()  │                           │
│                       │ + clear()           │                           │
│                       │ + save_conversation()│                          │
│                       └──────────┬──────────┘                           │
│                                  │                                       │
│              ┌───────────────────┼───────────────────┐                  │
│              │                   │                   │                   │
│              ▼                   ▼                   ▼                   │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│   │InMemoryChatMemory│ │  SQLChatMemory  │ │ RedisChatMemory │          │
│   │    (구현됨)      │ │   (미구현)      │ │   (미구현)      │          │
│   │                 │ │                 │ │                 │          │
│   │ dict 기반       │ │ PostgreSQL 등   │ │ Redis 기반      │          │
│   │ 서버 재시작 시  │ │ 영구 저장       │ │ 분산 캐시       │          │
│   │ 데이터 소실     │ │ 트랜잭션 지원   │ │ TTL 지원        │          │
│   └─────────────────┘ └─────────────────┘ └─────────────────┘          │
│                                                                          │
│   ✅ Supervisor는 ChatMemory 인터페이스만 알면 됨                        │
│   ✅ 저장소 교체 시 Supervisor 코드 수정 불필요                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Supervisor와의 관계

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Supervisor ↔ Memory 관계                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         Supervisor                               │   │
│   │                                                                  │   │
│   │   def __init__(self, memory: ChatMemory = None):                │   │
│   │       self.memory = memory or InMemoryChatMemory()              │   │
│   │                    ▲                                             │   │
│   │                    │ 의존성 주입                                 │   │
│   │                    │                                             │   │
│   │   def _build_messages(session_id, question):                    │   │
│   │       messages = [SystemMessage(...)]                           │   │
│   │       messages.extend(self.memory.get_messages(session_id))     │   │
│   │       messages.append(HumanMessage(question))                   │   │
│   │       return messages                                           │   │
│   │                                                                  │   │
│   │   def _save_to_history(session_id, question, answer):           │   │
│   │       self.memory.save_conversation(session_id, question, answer)│   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   사용 예시:                                                             │
│                                                                          │
│   # 기본 (InMemory)                                                     │
│   supervisor = Supervisor()                                             │
│                                                                          │
│   # SQL로 교체                                                          │
│   from src.memory.sql import SQLChatMemory                              │
│   memory = SQLChatMemory(connection_string="postgresql://...")          │
│   supervisor = Supervisor(memory=memory)                                │
│                                                                          │
│   # Redis로 교체                                                        │
│   from src.memory.redis import RedisChatMemory                          │
│   memory = RedisChatMemory(url="redis://...")                           │
│   supervisor = Supervisor(memory=memory)                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 코드 분석

### 3.1 base.py - 추상 인터페이스

```python
# src/memory/base.py

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
```

### 인터페이스 설계

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ChatMemory 인터페이스                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ get_messages(session_id) → List[BaseMessage]                    │   │
│   │                                                                  │   │
│   │ 책임: 세션의 전체 대화 히스토리 조회                             │   │
│   │ 입력: session_id (세션 식별자)                                   │   │
│   │ 출력: [HumanMessage, AIMessage, ...] 시간순                     │   │
│   │                                                                  │   │
│   │ 용도: Supervisor._build_messages()에서 히스토리 로드            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ add_user_message(session_id, content) → None                    │   │
│   │ add_ai_message(session_id, content) → None                      │   │
│   │                                                                  │   │
│   │ 책임: 개별 메시지 저장                                           │   │
│   │ 입력: session_id, content (메시지 내용)                         │   │
│   │                                                                  │   │
│   │ 내부적으로 HumanMessage/AIMessage 생성                          │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ clear(session_id) → None                                        │   │
│   │                                                                  │   │
│   │ 책임: 세션 히스토리 초기화 (메시지만 삭제)                       │   │
│   │ 용도: API /sessions/{id}/messages DELETE                        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ save_conversation(session_id, user_message, ai_message) → None  │   │
│   │                                                                  │   │
│   │ 책임: 대화 쌍 저장 (편의 메서드, 구현됨)                         │   │
│   │ 구현: add_user_message() + add_ai_message() 순차 호출           │   │
│   │                                                                  │   │
│   │ 용도: Supervisor._save_to_history()에서 사용                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 3.2 in_memory.py - In-Memory 구현체

```python
# src/memory/in_memory.py

"""In-Memory 대화 히스토리 저장소

개발/테스트용. 서버 재시작 시 데이터 소실됩니다.
프로덕션에서는 SQLChatMemory나 RedisChatMemory를 사용하세요.
"""
from collections import defaultdict
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .base import ChatMemory


class InMemoryChatMemory(ChatMemory):
    """In-Memory 기반 대화 히스토리 저장소

    특징:
        - 빠른 읽기/쓰기
        - 서버 재시작 시 데이터 소실
        - 개발/테스트 환경에 적합

    사용 예시:
        memory = InMemoryChatMemory()
        memory.add_user_message("session-1", "안녕하세요")
        memory.add_ai_message("session-1", "안녕하세요! 무엇을 도와드릴까요?")

        messages = memory.get_messages("session-1")
        # [HumanMessage(...), AIMessage(...)]
    """

    def __init__(self):
        # session_id → List[BaseMessage] 매핑
        # defaultdict로 존재하지 않는 키 접근 시 빈 리스트 자동 생성
        self._store: dict[str, List[BaseMessage]] = defaultdict(list)

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회"""
        # 방어적 복사: 외부에서 리스트 수정해도 내부 상태 보호
        return self._store[session_id].copy()

    def add_user_message(self, session_id: str, content: str) -> None:
        """사용자 메시지 추가"""
        self._store[session_id].append(HumanMessage(content=content))

    def add_ai_message(self, session_id: str, content: str) -> None:
        """AI 메시지 추가"""
        self._store[session_id].append(AIMessage(content=content))

    def clear(self, session_id: str) -> None:
        """세션 히스토리 초기화"""
        if session_id in self._store:
            self._store[session_id].clear()

    # 추가 메서드 (base에는 없음)

    def delete_session(self, session_id: str) -> None:
        """세션 완전 삭제"""
        if session_id in self._store:
            del self._store[session_id]

    def list_sessions(self) -> List[str]:
        """모든 세션 ID 조회"""
        return list(self._store.keys())

    def get_message_count(self, session_id: str) -> int:
        """세션의 메시지 개수"""
        return len(self._store[session_id])
```

### 내부 저장 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    InMemoryChatMemory 저장 구조                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   self._store = defaultdict(list)                                       │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ "session-abc123": [                                             │   │
│   │     HumanMessage(content="안녕하세요"),                         │   │
│   │     AIMessage(content="안녕하세요! 무엇을 도와드릴까요?"),       │   │
│   │     HumanMessage(content="LangGraph란 뭐야?"),                  │   │
│   │     AIMessage(content="LangGraph는 LangChain의..."),           │   │
│   │ ]                                                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ "session-xyz789": [                                             │   │
│   │     HumanMessage(content="파이썬 문법 알려줘"),                 │   │
│   │     AIMessage(content="파이썬의 기본 문법은..."),               │   │
│   │ ]                                                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ "session-new": []   ← defaultdict로 자동 생성                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 동작 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      대화 저장 및 조회 흐름                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   1. 첫 번째 대화                                                        │
│   ─────────────────                                                      │
│                                                                          │
│   supervisor.process("안녕", session_id="sess-1")                       │
│        │                                                                 │
│        ├─► _build_messages("sess-1", "안녕")                            │
│        │       │                                                         │
│        │       ├─► memory.get_messages("sess-1")                        │
│        │       │       └─► []  (빈 리스트, 새 세션)                      │
│        │       │                                                         │
│        │       └─► [SystemMessage, HumanMessage("안녕")]                │
│        │                                                                 │
│        ├─► (LangGraph 실행, AI 응답 생성)                                │
│        │                                                                 │
│        └─► _save_to_history("sess-1", "안녕", "안녕하세요!")             │
│                │                                                         │
│                └─► memory.save_conversation(...)                        │
│                        │                                                 │
│                        ├─► add_user_message("sess-1", "안녕")           │
│                        │       └─► _store["sess-1"].append(HumanMessage)│
│                        │                                                 │
│                        └─► add_ai_message("sess-1", "안녕하세요!")      │
│                                └─► _store["sess-1"].append(AIMessage)   │
│                                                                          │
│   _store["sess-1"] = [HumanMessage("안녕"), AIMessage("안녕하세요!")]   │
│                                                                          │
│   ─────────────────────────────────────────────────────────────────     │
│                                                                          │
│   2. 두 번째 대화 (같은 세션)                                            │
│   ───────────────────────────                                            │
│                                                                          │
│   supervisor.process("LangGraph 뭐야?", session_id="sess-1")            │
│        │                                                                 │
│        ├─► _build_messages("sess-1", "LangGraph 뭐야?")                 │
│        │       │                                                         │
│        │       ├─► memory.get_messages("sess-1")                        │
│        │       │       └─► [HumanMessage("안녕"), AIMessage("안녕!")]   │
│        │       │                                                         │
│        │       └─► [SystemMessage,                                      │
│        │            HumanMessage("안녕"),    ← 이전 대화                 │
│        │            AIMessage("안녕!"),      ← 이전 대화                 │
│        │            HumanMessage("LangGraph 뭐야?")]  ← 현재 질문        │
│        │                                                                 │
│        └─► (LLM이 이전 맥락을 보고 응답)                                 │
│                                                                          │
│   ✅ 대화 맥락 유지!                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. API에서의 사용

### 4.1 routes.py

```python
# src/api/routes.py

# 전역 인스턴스 (애플리케이션 수명 동안 유지)
memory = InMemoryChatMemory()
supervisor = Supervisor(memory=memory)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """세션 목록 조회"""
    session_ids = memory.list_sessions()
    sessions = [
        SessionInfo(
            session_id=sid,
            message_count=memory.get_message_count(sid)
        )
        for sid in session_ids
    ]
    return SessionListResponse(sessions=sessions)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """세션 삭제"""
    if session_id not in memory.list_sessions():
        raise HTTPException(status_code=404, detail="Session not found")

    memory.delete_session(session_id)
    return {"message": "Session deleted", "session_id": session_id}


@router.delete("/sessions/{session_id}/messages")
async def clear_session(session_id: str):
    """세션 메시지 초기화 (세션은 유지)"""
    memory.clear(session_id)
    return {"message": "Session cleared", "session_id": session_id}
```

---

## 5. 주요 이슈 및 개선점

### 5.1 Medium Issues

#### Issue 1: 스레드 안전성 미보장 (in_memory.py:32)

```python
# 현재 - 레이스 컨디션 가능
self._store: dict[str, List[BaseMessage]] = defaultdict(list)

# 문제 상황:
# Thread 1: _store["sess-1"].append(msg1)
# Thread 2: _store["sess-1"].append(msg2)
# → 메시지 순서 뒤바뀜 또는 데이터 손상 가능

# 개선안 - Lock 사용
import threading

class InMemoryChatMemory(ChatMemory):
    def __init__(self):
        self._store: dict[str, List[BaseMessage]] = defaultdict(list)
        self._lock = threading.Lock()

    def add_user_message(self, session_id: str, content: str) -> None:
        with self._lock:
            self._store[session_id].append(HumanMessage(content=content))

    def add_ai_message(self, session_id: str, content: str) -> None:
        with self._lock:
            self._store[session_id].append(AIMessage(content=content))

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        with self._lock:
            return self._store[session_id].copy()
```

#### Issue 2: 추가 메서드가 base에 없음 (in_memory.py:51-62)

```python
# 현재 - InMemoryChatMemory에만 있는 메서드
def delete_session(self, session_id: str) -> None: ...
def list_sessions(self) -> List[str]: ...
def get_message_count(self, session_id: str) -> int: ...

# 문제: LSP(Liskov Substitution Principle) 위반 가능
# routes.py에서 이 메서드들을 사용하면 다른 구현체로 교체 시 에러

# 개선안 - base.py에 추상 메서드 추가
class ChatMemory(ABC):
    ...

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """세션 완전 삭제"""
        pass

    @abstractmethod
    def list_sessions(self) -> List[str]:
        """모든 세션 ID 조회"""
        pass

    @abstractmethod
    def get_message_count(self, session_id: str) -> int:
        """세션의 메시지 개수"""
        pass
```

### 5.2 Low Issues

#### Issue 3: 메모리 제한 없음

```python
# 현재 - 무한 성장 가능
self._store: dict[str, List[BaseMessage]] = defaultdict(list)

# 문제: 세션이 많아지면 메모리 부족

# 개선안 1 - 세션당 최대 메시지 수 제한
MAX_MESSAGES_PER_SESSION = 100

def add_user_message(self, session_id: str, content: str) -> None:
    with self._lock:
        if len(self._store[session_id]) >= MAX_MESSAGES_PER_SESSION:
            # 오래된 메시지 삭제 (FIFO)
            self._store[session_id] = self._store[session_id][-MAX_MESSAGES_PER_SESSION+2:]
        self._store[session_id].append(HumanMessage(content=content))

# 개선안 2 - LRU 캐시 적용
from functools import lru_cache

# 개선안 3 - TTL 적용 (Redis 사용 시 자연스러움)
```

#### Issue 4: save_conversation 트랜잭션 미보장

```python
# 현재 - 원자성 없음
def save_conversation(self, session_id: str, user_message: str, ai_message: str) -> None:
    self.add_user_message(session_id, user_message)   # 성공
    self.add_ai_message(session_id, ai_message)       # 실패하면?

# InMemory에서는 문제 없지만 SQL 구현 시 주의
# 개선안 - SQL 구현체에서 트랜잭션 사용
class SQLChatMemory(ChatMemory):
    def save_conversation(self, session_id: str, user_message: str, ai_message: str) -> None:
        with self.db.transaction():
            self.add_user_message(session_id, user_message)
            self.add_ai_message(session_id, ai_message)
```

---

## 6. 확장 가이드

### 6.1 Redis 구현체 예시

```python
# src/memory/redis.py

"""Redis 기반 대화 히스토리 저장소

분산 환경, 서버 재시작에도 데이터 유지.
TTL 설정으로 자동 만료 가능.
"""
import json
from typing import List
import redis

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from .base import ChatMemory


class RedisChatMemory(ChatMemory):
    """Redis 기반 대화 히스토리 저장소

    특징:
        - 분산 환경 지원 (여러 서버에서 공유)
        - 서버 재시작에도 데이터 유지
        - TTL로 자동 세션 만료
    """

    def __init__(self, url: str = "redis://localhost:6379", ttl: int = 3600):
        self.client = redis.from_url(url)
        self.ttl = ttl  # 세션 만료 시간 (초)
        self.prefix = "chat:session:"

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        key = self._key(session_id)
        data = self.client.lrange(key, 0, -1)

        messages = []
        for item in data:
            msg_dict = json.loads(item)
            if msg_dict["type"] == "human":
                messages.append(HumanMessage(content=msg_dict["content"]))
            elif msg_dict["type"] == "ai":
                messages.append(AIMessage(content=msg_dict["content"]))

        return messages

    def add_user_message(self, session_id: str, content: str) -> None:
        key = self._key(session_id)
        msg = json.dumps({"type": "human", "content": content})
        self.client.rpush(key, msg)
        self.client.expire(key, self.ttl)

    def add_ai_message(self, session_id: str, content: str) -> None:
        key = self._key(session_id)
        msg = json.dumps({"type": "ai", "content": content})
        self.client.rpush(key, msg)
        self.client.expire(key, self.ttl)

    def clear(self, session_id: str) -> None:
        key = self._key(session_id)
        self.client.delete(key)

    def delete_session(self, session_id: str) -> None:
        self.clear(session_id)

    def list_sessions(self) -> List[str]:
        pattern = f"{self.prefix}*"
        keys = self.client.keys(pattern)
        return [k.decode().replace(self.prefix, "") for k in keys]

    def get_message_count(self, session_id: str) -> int:
        key = self._key(session_id)
        return self.client.llen(key)
```

### 6.2 SQL 구현체 예시 (개략)

```python
# src/memory/sql.py

"""SQL 기반 대화 히스토리 저장소"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

Base = declarative_base()


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), index=True)
    role = Column(String(10))  # "human" or "ai"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SQLChatMemory(ChatMemory):
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        with self.Session() as session:
            rows = session.query(Message)\
                .filter(Message.session_id == session_id)\
                .order_by(Message.created_at)\
                .all()

            messages = []
            for row in rows:
                if row.role == "human":
                    messages.append(HumanMessage(content=row.content))
                else:
                    messages.append(AIMessage(content=row.content))
            return messages

    # ... 나머지 메서드 구현
```

---

## 7. 테스트 포인트

```python
# tests/test_memory.py

1. 기본 CRUD 테스트
   - add_user_message → get_messages
   - add_ai_message → get_messages
   - save_conversation → get_messages
   - clear → get_messages (빈 리스트)

2. 세션 관리 테스트
   - list_sessions
   - get_message_count
   - delete_session

3. 격리 테스트
   - 서로 다른 session_id는 독립적
   - 방어적 복사 확인 (외부 수정 시 내부 불변)

4. 스레드 안전성 테스트 (개선 후)
   - 동시 쓰기 테스트
   - 동시 읽기/쓰기 테스트

5. 경계 조건 테스트
   - 빈 세션 조회
   - 존재하지 않는 세션 삭제
   - 빈 메시지 저장
```

---

## 8. 요약

| 항목 | 내용 |
|------|------|
| **책임** | 세션별 대화 히스토리 저장/조회 |
| **패턴** | Repository, Dependency Injection |
| **핵심 인터페이스** | `get_messages()`, `save_conversation()` |
| **현재 구현체** | InMemoryChatMemory |
| **확장 가능** | SQLChatMemory, RedisChatMemory |
| **주요 이슈** | 스레드 안전성, LSP 위반, 메모리 제한 |

---

*다음: [05-api.md](./05-api.md) - FastAPI 심층 분석*
