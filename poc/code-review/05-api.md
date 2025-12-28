# 05. FastAPI 심층 분석

> REST API 및 SSE 스트리밍 엔드포인트

---

## 1. 파일 정보

| 파일 | 라인 수 | 역할 |
|------|---------|------|
| `src/api/app.py` | 38줄 | FastAPI 앱 설정 |
| `src/api/routes.py` | 146줄 | API 엔드포인트 |
| `src/api/schemas.py` | 34줄 | 요청/응답 모델 |

---

## 2. 아키텍처 개요

### 2.1 API 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FastAPI 구조                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         app.py                                   │   │
│   │                                                                  │   │
│   │   app = FastAPI(title="AI Librarian", version="2.0.0")          │   │
│   │                                                                  │   │
│   │   ┌─────────────────────────────────────────────────────────┐   │   │
│   │   │ Middleware: CORS                                        │   │   │
│   │   │ allow_origins=["*"], allow_methods=["*"]                │   │   │
│   │   └─────────────────────────────────────────────────────────┘   │   │
│   │                                                                  │   │
│   │   app.include_router(router, prefix="/api")                     │   │
│   │                                                                  │   │
│   │   ┌─────────────────────────────────────────────────────────┐   │   │
│   │   │ Static Files: /static → static/                         │   │   │
│   │   │ Root: / → static/index.html                             │   │   │
│   │   └─────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                      │                                   │
│                                      ▼                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                        routes.py                                 │   │
│   │                                                                  │   │
│   │   GET  /api/health              → 헬스 체크                     │   │
│   │   POST /api/chat                → 비스트리밍 채팅                │   │
│   │   POST /api/chat/stream         → SSE 스트리밍 채팅             │   │
│   │   GET  /api/sessions            → 세션 목록                     │   │
│   │   DELETE /api/sessions/{id}     → 세션 삭제                     │   │
│   │   DELETE /api/sessions/{id}/msg → 메시지 초기화                 │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                      │                                   │
│                                      ▼                                   │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                       schemas.py                                 │   │
│   │                                                                  │   │
│   │   ChatRequest, ChatResponse, SessionInfo, HealthResponse        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 요청 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          요청 처리 흐름                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Client (Browser)                                                       │
│        │                                                                 │
│        │ POST /api/chat/stream                                          │
│        │ Content-Type: application/json                                 │
│        │ {"message": "LangGraph란?", "session_id": "abc"}               │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ FastAPI                                                          │   │
│   │                                                                  │   │
│   │ 1. CORS Middleware → Origin 검사                                │   │
│   │ 2. Request Validation → ChatRequest 파싱                        │   │
│   │ 3. Route Handler → chat_stream()                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ chat_stream() Handler                                            │   │
│   │                                                                  │   │
│   │ session_id = request.session_id or str(uuid.uuid4())            │   │
│   │                                                                  │   │
│   │ async def event_generator():                                    │   │
│   │     async for event in supervisor.process_stream(...):          │   │
│   │         yield {"event": event_type, "data": json.dumps(data)}  │   │
│   │                                                                  │   │
│   │ return EventSourceResponse(event_generator())                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        │ SSE (Server-Sent Events)                                       │
│        ▼                                                                 │
│   Client                                                                 │
│        │                                                                 │
│        │ event: think                                                   │
│        │ data: {"content": "웹 검색 필요..."}                           │
│        │                                                                 │
│        │ event: token                                                   │
│        │ data: {"content": "Lang"}                                      │
│        │                                                                 │
│        │ event: token                                                   │
│        │ data: {"content": "Graph"}                                     │
│        │                                                                 │
│        │ event: done                                                    │
│        │ data: {"session_id": "abc"}                                    │
│        │                                                                 │
│        ▼                                                                 │
│   연결 종료                                                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 코드 분석

### 3.1 app.py - FastAPI 앱 설정

```python
# src/api/app.py

"""FastAPI 애플리케이션"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .routes import router

# 앱 생성
app = FastAPI(
    title="AI Librarian",
    description="AI 기반 문서 검색 및 질의응답 서비스",
    version="2.0.0",
)

# CORS 설정 ⚠️ 보안 이슈!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 모든 오리진 허용
    allow_credentials=True,         # 쿠키/인증 허용
    allow_methods=["*"],            # 모든 HTTP 메서드 허용
    allow_headers=["*"],            # 모든 헤더 허용
)

# API 라우트 등록
app.include_router(router, prefix="/api")

# Static 파일 서빙 (UI)
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_ui():
        """메인 UI 페이지"""
        return FileResponse(static_dir / "index.html")
```

### CORS 보안 이슈

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CORS 설정 분석                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   현재 설정:                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ allow_origins=["*"]       → 모든 도메인에서 접근 가능            │   │
│   │ allow_credentials=True    → 쿠키/인증 정보 포함 가능             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ⚠️ 보안 문제:                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ allow_origins=["*"] + allow_credentials=True 조합은             │   │
│   │ CORS 스펙에서 허용하지 않음!                                     │   │
│   │                                                                  │   │
│   │ 브라우저에 따라:                                                 │   │
│   │ - 요청 자체가 거부될 수 있음                                    │   │
│   │ - 또는 credentials가 무시될 수 있음                             │   │
│   │                                                                  │   │
│   │ 악의적인 사이트에서 사용자 세션 탈취 가능                        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   개선안:                                                                │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ import os                                                        │   │
│   │                                                                  │   │
│   │ ALLOWED_ORIGINS = os.getenv(                                    │   │
│   │     "ALLOWED_ORIGINS",                                          │   │
│   │     "http://localhost:3000,http://localhost:8000"               │   │
│   │ ).split(",")                                                    │   │
│   │                                                                  │   │
│   │ app.add_middleware(                                             │   │
│   │     CORSMiddleware,                                             │   │
│   │     allow_origins=ALLOWED_ORIGINS,  # 명시적 허용               │   │
│   │     allow_credentials=True,                                     │   │
│   │     allow_methods=["GET", "POST", "DELETE"],                    │   │
│   │     allow_headers=["Content-Type", "Authorization"],            │   │
│   │ )                                                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 3.2 schemas.py - 요청/응답 모델

```python
# src/api/schemas.py

"""API 스키마 정의"""
from typing import Optional, List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str = Field(..., min_length=1, description="사용자 메시지")
    session_id: Optional[str] = Field(None, description="세션 ID")


class ChatResponse(BaseModel):
    """채팅 응답 (Non-streaming)"""
    answer: str = Field(..., description="AI 응답")
    sources: List[str] = Field(default_factory=list, description="사용된 도구 목록")
    session_id: Optional[str] = Field(None, description="세션 ID")


class SessionInfo(BaseModel):
    """세션 정보"""
    session_id: str
    message_count: int


class SessionListResponse(BaseModel):
    """세션 목록 응답"""
    sessions: List[SessionInfo]


class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str = "ok"
    provider: str
```

### 스키마 검증 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Pydantic 검증 흐름                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   입력 JSON:                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ {"message": "LangGraph란?", "session_id": "abc123"}             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ ChatRequest 검증                                                 │   │
│   │                                                                  │   │
│   │ message: str = Field(..., min_length=1)                         │   │
│   │   ├─ 필수 (...)                                                 │   │
│   │   ├─ 최소 1자 (min_length=1)                                   │   │
│   │   └─ "LangGraph란?" → ✅ 통과                                   │   │
│   │                                                                  │   │
│   │ session_id: Optional[str] = Field(None)                         │   │
│   │   ├─ 선택 (Optional)                                            │   │
│   │   └─ "abc123" → ✅ 통과                                         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ChatRequest(message="LangGraph란?", session_id="abc123")              │
│                                                                          │
│   ─────────────────────────────────────────────────────────────────     │
│                                                                          │
│   잘못된 입력:                                                           │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ {"message": ""}  ← 빈 문자열                                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ ValidationError                                                  │   │
│   │                                                                  │   │
│   │ {                                                                │   │
│   │   "detail": [                                                   │   │
│   │     {                                                           │   │
│   │       "loc": ["body", "message"],                               │   │
│   │       "msg": "String should have at least 1 character",         │   │
│   │       "type": "string_too_short"                                │   │
│   │     }                                                           │   │
│   │   ]                                                             │   │
│   │ }                                                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   HTTP 422 Unprocessable Entity                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 3.3 routes.py - API 엔드포인트

```python
# src/api/routes.py

"""API 라우트 정의"""
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from src.supervisor import Supervisor
from src.memory import InMemoryChatMemory
from config import config
from .schemas import (
    ChatRequest, ChatResponse, SessionInfo,
    SessionListResponse, HealthResponse,
)

router = APIRouter()

# 전역 인스턴스 (애플리케이션 수명 동안 유지) ⚠️
memory = InMemoryChatMemory()
supervisor = Supervisor(memory=memory)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스 체크"""
    return HealthResponse(
        status="ok",
        provider=supervisor.adapter.provider_name
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """채팅 (Non-streaming)"""
    session_id = request.session_id or str(uuid.uuid4())

    try:
        result = await supervisor.process(
            question=request.message,
            session_id=session_id
        )
        return ChatResponse(
            answer=result.answer,
            sources=result.sources,
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # ⚠️ 에러 노출


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """채팅 (SSE Streaming)"""
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for event in supervisor.process_stream(
                question=request.message,
                session_id=session_id
            ):
                event_type = event.get("type", "token")

                if event_type == "token":
                    yield {
                        "event": "token",
                        "data": json.dumps({"content": event.get("content", "")})
                    }
                elif event_type == "think":
                    yield {
                        "event": "think",
                        "data": json.dumps({"content": event.get("content", "")})
                    }
                elif event_type == "act":
                    yield {
                        "event": "act",
                        "data": json.dumps({
                            "tool": event.get("tool", ""),
                            "args": event.get("args", {})
                        })
                    }
                elif event_type == "observe":
                    yield {
                        "event": "observe",
                        "data": json.dumps({"content": event.get("content", "")})
                    }

            # 완료 이벤트
            yield {
                "event": "done",
                "data": json.dumps({"session_id": session_id})
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())


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
    """세션 메시지 초기화"""
    memory.clear(session_id)
    return {"message": "Session cleared", "session_id": session_id}
```

---

## 4. 엔드포인트별 상세 분석

### 4.1 GET /api/health

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GET /api/health                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   요청:                                                                  │
│   GET /api/health                                                       │
│                                                                          │
│   응답:                                                                  │
│   {                                                                      │
│       "status": "ok",                                                   │
│       "provider": "openai"   // 또는 "gemini"                           │
│   }                                                                      │
│                                                                          │
│   용도:                                                                  │
│   - 서버 상태 확인                                                       │
│   - 현재 LLM 프로바이더 확인                                             │
│   - 로드밸런서/헬스체크 용도                                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 POST /api/chat

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        POST /api/chat                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   요청:                                                                  │
│   POST /api/chat                                                        │
│   Content-Type: application/json                                        │
│                                                                          │
│   {                                                                      │
│       "message": "LangGraph란 무엇인가요?",                             │
│       "session_id": "abc123"   // 선택, 없으면 자동 생성                │
│   }                                                                      │
│                                                                          │
│   처리 흐름:                                                             │
│   1. session_id 확인 (없으면 UUID 생성)                                 │
│   2. supervisor.process() 호출                                          │
│   3. 결과를 ChatResponse로 반환                                         │
│                                                                          │
│   응답 (성공):                                                           │
│   {                                                                      │
│       "answer": "LangGraph는 LangChain의 상태 기반 워크플로우...",      │
│       "sources": ["think", "arag_search"],                              │
│       "session_id": "abc123"                                            │
│   }                                                                      │
│                                                                          │
│   응답 (실패):                                                           │
│   HTTP 500                                                               │
│   {                                                                      │
│       "detail": "에러 메시지..."   ⚠️ 내부 에러 노출                    │
│   }                                                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 POST /api/chat/stream (SSE)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     POST /api/chat/stream (SSE)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   요청:                                                                  │
│   POST /api/chat/stream                                                 │
│   Content-Type: application/json                                        │
│   Accept: text/event-stream                                             │
│                                                                          │
│   {                                                                      │
│       "message": "최신 AI 트렌드",                                      │
│       "session_id": "abc123"                                            │
│   }                                                                      │
│                                                                          │
│   응답 (SSE 스트림):                                                     │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ Content-Type: text/event-stream                                 │   │
│   │                                                                  │   │
│   │ event: think                                                    │   │
│   │ data: {"content": "최신 정보가 필요하므로 웹 검색..."}           │   │
│   │                                                                  │   │
│   │ event: act                                                      │   │
│   │ data: {"tool": "aweb_search", "args": {"query": "2024 AI"}}     │   │
│   │                                                                  │   │
│   │ event: observe                                                  │   │
│   │ data: {"content": "[웹 검색 결과]..."}                          │   │
│   │                                                                  │   │
│   │ event: token                                                    │   │
│   │ data: {"content": "최"}                                         │   │
│   │                                                                  │   │
│   │ event: token                                                    │   │
│   │ data: {"content": "근"}                                         │   │
│   │                                                                  │   │
│   │ event: token                                                    │   │
│   │ data: {"content": " AI"}                                        │   │
│   │                                                                  │   │
│   │ ... (토큰 계속)                                                 │   │
│   │                                                                  │   │
│   │ event: done                                                     │   │
│   │ data: {"session_id": "abc123"}                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   이벤트 타입:                                                           │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ think   → 생각 과정 (ReAct의 Reasoning)                         │   │
│   │ act     → 도구 호출 (ReAct의 Action)                            │   │
│   │ observe → 도구 결과 (ReAct의 Observation)                       │   │
│   │ token   → LLM 출력 토큰                                         │   │
│   │ done    → 스트림 완료                                           │   │
│   │ error   → 에러 발생                                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.4 세션 관리 API

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        세션 관리 API                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   GET /api/sessions                                                      │
│   ─────────────────                                                      │
│   응답:                                                                  │
│   {                                                                      │
│       "sessions": [                                                     │
│           {"session_id": "abc123", "message_count": 10},                │
│           {"session_id": "xyz789", "message_count": 5}                  │
│       ]                                                                  │
│   }                                                                      │
│                                                                          │
│   ─────────────────────────────────────────────────────────────────     │
│                                                                          │
│   DELETE /api/sessions/{session_id}                                      │
│   ─────────────────────────────────                                      │
│   세션 완전 삭제 (메시지 + 세션 정보)                                    │
│                                                                          │
│   응답 (성공):                                                           │
│   {"message": "Session deleted", "session_id": "abc123"}                │
│                                                                          │
│   응답 (404):                                                            │
│   {"detail": "Session not found"}                                       │
│                                                                          │
│   ─────────────────────────────────────────────────────────────────     │
│                                                                          │
│   DELETE /api/sessions/{session_id}/messages                             │
│   ──────────────────────────────────────────                             │
│   메시지만 삭제 (세션은 유지)                                            │
│                                                                          │
│   응답:                                                                  │
│   {"message": "Session cleared", "session_id": "abc123"}                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 주요 이슈 및 개선점

### 5.1 Critical Issues

#### Issue 1: CORS 설정 (app.py:18-24)

```python
# 현재 - 보안 취약
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 모든 오리진
    allow_credentials=True,      # + 인증 정보
    allow_methods=["*"],
    allow_headers=["*"],
)

# 수정
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
```

#### Issue 2: 에러 메시지 노출 (routes.py:52-53)

```python
# 현재 - 내부 에러 스택트레이스 노출
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

# 수정
import logging
logger = logging.getLogger(__name__)

except Exception as e:
    logger.exception("Chat processing failed")
    raise HTTPException(
        status_code=500,
        detail="An error occurred while processing your request"
    )
```

### 5.2 High Issues

#### Issue 3: 전역 싱글톤 (routes.py:24-25)

```python
# 현재 - 전역 인스턴스
memory = InMemoryChatMemory()
supervisor = Supervisor(memory=memory)

# 문제:
# 1. 멀티 워커 환경(Gunicorn)에서 메모리 공유 안 됨
# 2. 테스트 격리 어려움

# 개선안 - FastAPI lifespan 사용
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    app.state.memory = InMemoryChatMemory()
    app.state.supervisor = Supervisor(memory=app.state.memory)
    yield
    # 종료 시
    pass

app = FastAPI(lifespan=lifespan)

# routes.py에서
@router.post("/chat")
async def chat(request: ChatRequest, request_obj: Request):
    supervisor = request_obj.app.state.supervisor
    ...
```

### 5.3 Medium Issues

#### Issue 4: 입력 길이 제한 없음 (schemas.py:8)

```python
# 현재
message: str = Field(..., min_length=1)

# 개선 - max_length 추가 (DoS 방지)
message: str = Field(..., min_length=1, max_length=10000)
```

#### Issue 5: 에러 이벤트 후 return 없음 (routes.py:108-112)

```python
# 현재
except Exception as e:
    yield {
        "event": "error",
        "data": json.dumps({"error": str(e)})
    }
# 이후 done 이벤트 전송될 수 있음

# 수정
except Exception as e:
    yield {
        "event": "error",
        "data": json.dumps({"error": str(e)})
    }
    return  # 명시적 종료
```

### 5.4 Low Issues

#### Issue 6: Rate Limiting 없음

```python
# 개선안 - slowapi 사용
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    ...
```

---

## 6. 테스트 포인트

```python
# tests/test_api.py

1. 헬스 체크
   - GET /api/health → 200, provider 확인

2. 비스트리밍 채팅
   - POST /api/chat → 200, 응답 구조 확인
   - 빈 메시지 → 422
   - 서버 에러 → 500

3. 스트리밍 채팅
   - POST /api/chat/stream → SSE 이벤트 순서 확인
   - think, act, observe, token, done 이벤트

4. 세션 관리
   - GET /api/sessions
   - DELETE /api/sessions/{id}
   - DELETE /api/sessions/{id}/messages
   - 존재하지 않는 세션 삭제 → 404

5. 보안 테스트
   - CORS 헤더 확인
   - 에러 메시지 노출 확인
```

---

## 7. 요약

| 항목 | 내용 |
|------|------|
| **책임** | HTTP API, SSE 스트리밍, 세션 관리 |
| **프레임워크** | FastAPI + sse-starlette |
| **핵심 엔드포인트** | `/api/chat`, `/api/chat/stream` |
| **주요 이슈** | CORS 설정, 에러 노출, 전역 싱글톤 |
| **개선 필요** | Rate Limiting, 입력 검증 강화 |

---

*다음: [06-prompts.md](./06-prompts.md) - 프롬프트 엔지니어링 심층 분석*
