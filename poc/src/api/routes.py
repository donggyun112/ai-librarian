"""API 라우트 정의"""
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional, Union

from langchain_core.messages import BaseMessage

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from sse_starlette.sse import EventSourceResponse
from loguru import logger

from src.supervisor import Supervisor
from src.memory.supabase_memory import SessionAccessDenied
from src.memory.base import ChatMemory
from supabase import AsyncClient
from src.auth.dependencies import verify_current_user, get_user_scoped_client
from src.auth.schemas import User
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
    AIChatRequest,
)


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

def get_memory(request: Request) -> ChatMemory:
    if not hasattr(request.app.state, "memory") or request.app.state.memory is None:
        raise HTTPException(
            status_code=500,
            detail="Memory storage not initialized",
        )
    return request.app.state.memory

def get_supervisor(request: Request) -> Supervisor:
    if not hasattr(request.app.state, "supervisor") or request.app.state.supervisor is None:
        raise HTTPException(
            status_code=500,
            detail="Supervisor not initialized",
        )
    return request.app.state.supervisor


@router.get("/health", response_model=HealthResponse)
async def health_check(
    supervisor: Supervisor = Depends(get_supervisor),
) -> HealthResponse:
    """헬스 체크"""
    return HealthResponse(
        status="ok",
        provider=supervisor.adapter.provider_name
    )


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> SessionCreateResponse:
    """새 세션 생성

    Headers:
        Authorization: Bearer <token> (JWT required)

    Returns:
        SessionCreateResponse: 생성된 세션 정보
    """
    user_id = current_user.id

    session_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    success = await memory.init_session_async(session_id, user_id, client=client)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to create session"
        )

    logger.info(f"Created new session: {session_id}")

    return SessionCreateResponse(
        session_id=session_id,
        created_at=created_at
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> SessionDetailResponse:
    """세션 상세 정보 조회

    Args:
        session_id: 세션 ID

    Headers:
        Authorization: Bearer <token> (JWT required)

    Returns:
        SessionDetailResponse: 세션 상세 정보
    """
    user_id = current_user.id

    try:
        message_count = await memory.get_message_count_async(session_id, user_id=user_id, client=client)
        messages = await memory.get_messages_async(
            session_id, user_id=user_id, client=client
        )
    except SessionAccessDenied:
        raise HTTPException(
            status_code=404,
            detail="Session not found or access denied"
        )

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
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    supervisor: Supervisor = Depends(get_supervisor),
) -> Union[EventSourceResponse, ChatResponse]:
    """메시지 전송 (body.stream으로 스트리밍/JSON 구분)

    Args:
        session_id: 세션 ID
        body: 메시지 요청 본문 (message, stream)

    Headers:
        Authorization: Bearer <token> (JWT required)

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
    user_id = current_user.id

    if body.stream:
        async def event_generator() -> AsyncGenerator[dict, None]:
            try:
                kwargs = {}
                if user_id:
                    kwargs["user_id"] = user_id

                async for event in supervisor.process_stream(
                    question=body.message,
                    session_id=session_id,
                    client=client,
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

                yield {
                    "event": "done",
                    "data": json.dumps({"session_id": session_id})
                }

            except SessionAccessDenied:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Session not found or access denied"})
                }

            except ValueError:
                logger.warning("Validation error in stream processing")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "잘못된 요청입니다."})
                }

            except Exception:
                logger.exception("Stream processing failed")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "스트리밍 처리 중 오류가 발생했습니다."})
                }

        return EventSourceResponse(event_generator())

    else:
        try:
            kwargs = {}
            if user_id:
                kwargs["user_id"] = user_id

            result = await supervisor.process(
                question=body.message,
                session_id=session_id,
                client=client,
                **kwargs
            )
            return ChatResponse(
                answer=result.answer,
                sources=result.sources,
                session_id=session_id
            )
        except SessionAccessDenied:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )
        except ValueError:
            logger.warning("Validation error in chat processing")
            raise HTTPException(
                status_code=400,
                detail="잘못된 요청입니다."
            )
        except Exception:
            logger.exception("Chat processing failed")
            raise HTTPException(
                status_code=500,
                detail="요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> SessionListResponse:
    """세션 목록 조회

    Headers:
        Authorization: Bearer <token> (JWT required)
    """
    user_id = current_user.id

    session_ids = await memory.list_sessions_async(user_id=user_id, client=client)
    sessions = [
        SessionInfo(
            session_id=sid,
            message_count=await memory.get_message_count_async(
                sid, user_id=user_id, client=client
            )
        )
        for sid in session_ids
    ]

    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> SessionHistoryResponse:
    """세션의 대화 히스토리 조회

    Args:
        session_id: 세션 ID

    Headers:
        Authorization: Bearer <token> (JWT required)
    """
    user_id = current_user.id

    try:
        messages = await memory.get_messages_async(session_id, user_id=user_id, client=client)
    except SessionAccessDenied:
        raise HTTPException(status_code=404, detail="Session not found or access denied")

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
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> Dict[str, str]:
    """세션 삭제

    Args:
        session_id: 세션 ID

    Headers:
        Authorization: Bearer <token> (JWT required)
    """
    user_id = current_user.id

    try:
        await memory.delete_session_async(session_id, user_id=user_id, client=client)
    except SessionAccessDenied:
        raise HTTPException(status_code=404, detail="Session not found or access denied")

    return {"message": "Session deleted", "session_id": session_id}


@router.post("/chat")
async def ai_chat(request: AIChatRequest):
    """AI SDK UI Message Stream 호환 채팅 엔드포인트

    Vercel AI SDK의 toUIMessageStreamResponse() 형식과 호환되는
    SSE 스트리밍 응답을 반환합니다.

    Protocol: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
    """
    # 마지막 user 메시지 추출
    user_text = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_text = msg.get_text()
            break

    if not user_text:
        raise HTTPException(status_code=400, detail="No user message")

    # 임시 세션 생성
    session_id = str(uuid.uuid4())
    if isinstance(memory, SupabaseChatMemory):
        await memory.init_session_async(session_id)
    else:
        memory.init_session(session_id)

    async def ui_message_stream() -> AsyncGenerator[str, None]:
        """UI Message Stream 프로토콜 형식으로 스트리밍"""
        message_id = f"msg_{uuid.uuid4().hex}"
        text_id = f"text_{uuid.uuid4().hex}"

        try:
            # 1. message-start
            yield f"data: {json.dumps({'type': 'start', 'messageId': message_id})}\n\n"

            # 2. text-start
            yield f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"

            # 3. LangGraph supervisor 호출 및 text-delta 스트리밍
            async for event in supervisor.process_stream(
                question=user_text,
                session_id=session_id,
            ):
                if event.get("type") == "token":
                    content = event.get("content", "")
                    if content:
                        yield f"data: {json.dumps({'type': 'text-delta', 'id': text_id, 'delta': content})}\n\n"

            # 4. text-end
            yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"

            # 5. finish
            yield f"data: {json.dumps({'type': 'finish'})}\n\n"

            # 6. stream termination
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.exception("Chat stream failed")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        ui_message_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Vercel-AI-UI-Message-Stream": "v1",
        }
    )
