"""API 라우트 정의"""
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException

from sse_starlette.sse import EventSourceResponse
from loguru import logger

from src.supervisor import Supervisor
from src.memory import InMemoryChatMemory, SupabaseChatMemory
from config import config
from .schemas import (
    ChatRequest,
    ChatResponse,
    SessionInfo,
    SessionListResponse,
    HealthResponse,
)

router = APIRouter()

# 전역 인스턴스 (애플리케이션 수명 동안 유지)
# 전역 인스턴스 (애플리케이션 수명 동안 유지)
if config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY:
    logger.info(f"Supabase Memory enabled: {config.SUPABASE_URL}")
    memory = SupabaseChatMemory(
        url=config.SUPABASE_URL,
        key=config.SUPABASE_SERVICE_ROLE_KEY
    )
else:
    logger.info("Using In-Memory storage (not persistent)")
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
        kwargs = {}
        if request.user_id:
            kwargs["user_id"] = request.user_id

        result = await supervisor.process(
            question=request.message,
            session_id=session_id,
            **kwargs
        )
        return ChatResponse(
            answer=result.answer,
            sources=result.sources,
            session_id=session_id
        )
    except Exception as e:
        logger.exception("Chat processing failed")
        raise HTTPException(
            status_code=500,
            detail="요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """채팅 (SSE Streaming)

    이벤트 타입:
    - token: LLM 토큰 출력
    - think: 생각 과정
    - act: 도구 호출
    - observe: 도구 결과
    - done: 스트림 완료
    - error: 에러 발생
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            kwargs = {}
            if request.user_id:
                kwargs["user_id"] = request.user_id

            async for event in supervisor.process_stream(
                question=request.message,
                session_id=session_id,
                **kwargs
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
            logger.exception("Stream processing failed")
            yield {
                "event": "error",
                "data": json.dumps({"error": "스트리밍 처리 중 오류가 발생했습니다."})
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
