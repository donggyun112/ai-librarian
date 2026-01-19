"""API 라우트 정의"""
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, Dict, List, Union

from langchain_core.messages import BaseMessage

from fastapi import APIRouter, HTTPException, Depends, Header

from sse_starlette.sse import EventSourceResponse
from loguru import logger

from src.supervisor import Supervisor
from src.memory import InMemoryChatMemory, SupabaseChatMemory
from config import config
from .schemas import (
    MessageRequest,
    ChatResponse,
    SessionCreateResponse,
    SessionDetailResponse,
    SessionInfo,
    SessionListResponse,
    SessionHistoryResponse,
    MessageInfo,
    HealthResponse,
)


async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Authorization 헤더에서 user_id 추출

    TODO: 실제 JWT 검증 로직 구현 필요
    현재는 Bearer 토큰을 user_id로 직접 사용 (개발용)

    Args:
        authorization: Authorization 헤더 (Bearer <token>)

    Returns:
        user_id 또는 None (InMemory 모드)

    Raises:
        HTTPException: Supabase 모드에서 토큰 없을 때
    """
    if not authorization:
        return None

    # Bearer 토큰 파싱
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )

    token = parts[1]

    # TODO: JWT 검증 및 user_id 추출
    # 현재는 토큰을 그대로 user_id로 사용 (개발용)
    # 실제 구현 시:
    # decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    # return decoded["sub"]  # or decoded["user_id"]

    return token


def require_user_id(user_id: Optional[str], mem: Union[InMemoryChatMemory, SupabaseChatMemory, None] = None) -> Optional[str]:
    """Supabase 모드에서 user_id 필수 검증

    Args:
        user_id: 사용자 ID (Authorization 헤더에서 추출)
        mem: 메모리 인스턴스 (테스트용, 기본값은 전역 memory 사용)

    Returns:
        user_id (Supabase 모드) 또는 None (InMemory 모드)

    Raises:
        HTTPException: Supabase 모드에서 user_id 없을 때
    """
    mem = mem or memory
    if isinstance(mem, SupabaseChatMemory) and not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required. Use: Bearer <token>"
        )
    return user_id


def _extract_timestamps(messages: List[BaseMessage]) -> tuple[Optional[str], Optional[str]]:
    """메시지 목록에서 생성 시간과 마지막 활동 시간 추출

    Args:
        messages: BaseMessage 목록

    Returns:
        (created_at, last_activity) 튜플
    """
    if not messages:
        return None, None

    first_msg = messages[0]
    created_at = first_msg.additional_kwargs.get("timestamp")
    last_msg = messages[-1]
    last_activity = last_msg.additional_kwargs.get("timestamp")

    return created_at, last_activity

router = APIRouter()

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
async def health_check() -> HealthResponse:
    """헬스 체크"""
    return HealthResponse(
        status="ok",
        provider=supervisor.adapter.provider_name
    )


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    user_id: Optional[str] = Depends(get_current_user)
) -> SessionCreateResponse:
    """새 세션 생성

    Headers:
        Authorization: Bearer <token> (Supabase 사용 시 필수)

    Returns:
        SessionCreateResponse: 생성된 세션 정보
    """
    require_user_id(user_id)

    session_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # 세션 저장소에 실제로 세션 생성
    if isinstance(memory, SupabaseChatMemory):
        success = await memory.init_session_async(session_id, user_id)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to create session"
            )
    else:
        # InMemoryChatMemory
        memory.init_session(session_id)

    logger.info(f"Created new session: {session_id} for user: {user_id or 'anonymous'}")

    return SessionCreateResponse(
        session_id=session_id,
        created_at=created_at
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    user_id: Optional[str] = Depends(get_current_user)
) -> SessionDetailResponse:
    """세션 상세 정보 조회

    Args:
        session_id: 세션 ID

    Headers:
        Authorization: Bearer <token> (Supabase 사용 시 필수)

    Returns:
        SessionDetailResponse: 세션 상세 정보
    """
    require_user_id(user_id)

    if isinstance(memory, SupabaseChatMemory):
        # 세션 존재 및 소유권 검증
        user_sessions = await memory.list_sessions_async(user_id=user_id)
        if session_id not in user_sessions:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )

        message_count = await memory.get_message_count_async(session_id, user_id=user_id)
        messages = await memory.get_messages_async(session_id, user_id=user_id)
    else:
        # InMemoryChatMemory
        if session_id not in memory.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")

        message_count = memory.get_message_count(session_id)
        messages = memory.get_messages(session_id)

    created_at, last_activity = _extract_timestamps(messages)

    return SessionDetailResponse(
        session_id=session_id,
        message_count=message_count,
        created_at=created_at,
        last_activity=last_activity
    )


@router.post("/sessions/{session_id}/messages", response_model=None)
async def send_message(
    session_id: str,
    body: MessageRequest,
    user_id: Optional[str] = Depends(get_current_user)
):
    """메시지 전송 (body.stream으로 스트리밍/JSON 구분)

    Args:
        session_id: 세션 ID
        body: 메시지 요청 본문 (message, stream)

    Headers:
        Authorization: Bearer <token> (Supabase 사용 시 필수)

    Returns:
        - stream: true → SSE 스트리밍 응답
        - stream: false → JSON 응답

    Events (SSE):
        - token: LLM 토큰 출력
        - think: 생각 과정
        - act: 도구 호출
        - observe: 도구 결과
        - done: 스트림 완료
        - error: 에러 발생
    """
    require_user_id(user_id)

    # 스트리밍 응답
    if body.stream:
        async def event_generator() -> AsyncGenerator[dict, None]:
            try:
                kwargs = {}
                if user_id:
                    kwargs["user_id"] = user_id

                async for event in supervisor.process_stream(
                    question=body.message,
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

            except ValueError as e:
                logger.error(f"Validation error: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }

            except Exception as e:
                logger.exception("Stream processing failed")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "스트리밍 처리 중 오류가 발생했습니다."})
                }

        return EventSourceResponse(event_generator())

    # JSON 응답
    else:
        try:
            kwargs = {}
            if user_id:
                kwargs["user_id"] = user_id

            result = await supervisor.process(
                question=body.message,
                session_id=session_id,
                **kwargs
            )
            return ChatResponse(
                answer=result.answer,
                sources=result.sources,
                session_id=session_id
            )
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except Exception as e:
            logger.exception("Chat processing failed")
            raise HTTPException(
                status_code=500,
                detail="요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user_id: Optional[str] = Depends(get_current_user)
) -> SessionListResponse:
    """세션 목록 조회

    Headers:
        Authorization: Bearer <token> (Supabase 사용 시 필수)
    """
    require_user_id(user_id)

    if isinstance(memory, SupabaseChatMemory):
        session_ids = await memory.list_sessions_async(user_id=user_id)
        sessions = [
            SessionInfo(
                session_id=sid,
                message_count=await memory.get_message_count_async(sid, user_id=user_id)
            )
            for sid in session_ids
        ]
    else:
        # InMemoryChatMemory는 user_id 무시
        session_ids = memory.list_sessions()
        sessions = [
            SessionInfo(
                session_id=sid,
                message_count=memory.get_message_count(sid)
            )
            for sid in session_ids
        ]

    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_messages(
    session_id: str,
    user_id: Optional[str] = Depends(get_current_user)
) -> SessionHistoryResponse:
    """세션의 대화 히스토리 조회

    Args:
        session_id: 세션 ID

    Headers:
        Authorization: Bearer <token> (Supabase 사용 시 필수)
    """
    require_user_id(user_id)

    if isinstance(memory, SupabaseChatMemory):
        messages = await memory.get_messages_async(session_id, user_id=user_id)
    else:
        # InMemoryChatMemory는 user_id 무시
        messages = memory.get_messages(session_id)

    # Convert BaseMessage objects to MessageInfo
    message_list = []
    for msg in messages:
        message_list.append(MessageInfo(
            role=msg.type,
            content=msg.content,
            timestamp=msg.additional_kwargs.get("timestamp")
        ))

    return SessionHistoryResponse(
        session_id=session_id,
        messages=message_list
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: Optional[str] = Depends(get_current_user)
) -> Dict[str, str]:
    """세션 삭제

    Args:
        session_id: 세션 ID

    Headers:
        Authorization: Bearer <token> (Supabase 사용 시 필수)
    """
    require_user_id(user_id)

    if isinstance(memory, SupabaseChatMemory):
        # 소유권 검증
        user_sessions = await memory.list_sessions_async(user_id=user_id)
        if session_id not in user_sessions:
            raise HTTPException(status_code=404, detail="Session not found or access denied")
        await memory.delete_session_async(session_id, user_id=user_id)
    else:
        # InMemoryChatMemory는 user_id 무시
        if session_id not in memory.list_sessions():
            raise HTTPException(status_code=404, detail="Session not found")
        memory.delete_session(session_id)

    return {"message": "Session deleted", "session_id": session_id}
