"""API 라우트 정의"""
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional, Union

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

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
    ChatPromptRequest,
    SessionCreateResponse,
    SessionDetailResponse,
    SessionInfo,
    SessionListResponse,
    SessionHistoryResponse,
    ChatMessage,
    TextContentItem,
    ToolUseContentItem,
    ToolResultContentItem,
    HealthResponse,
    SessionUpdateRequest,
)


# ──────────────────────────────────────────────
# 히스토리 그룹핑 헬퍼
# ──────────────────────────────────────────────

_TOOL_DISPLAY_MESSAGES: dict[str, str] = {
    "aweb_search": "Searching the web",
    "rag_retrieval": "Searching knowledge base",
}


def _tool_display_message(name: str) -> str:
    return _TOOL_DISPLAY_MESSAGES.get(name, f"Running {name}")


def _extract_text_and_reasoning(msg: BaseMessage) -> tuple[str, Optional[str]]:
    """BaseMessage에서 텍스트와 reasoning 분리.

    Gemini: content = [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]
    DeepSeek: additional_kwargs.reasoning_content
    Others: content = str
    """
    text = ""
    reasoning: Optional[str] = None

    if isinstance(msg.content, str):
        text = msg.content
    elif isinstance(msg.content, list):
        texts: list[str] = []
        thinkings: list[str] = []
        for item in msg.content:
            if isinstance(item, dict):
                if item.get("type") == "thinking":
                    thinkings.append(item.get("thinking", ""))
                else:
                    texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)
        text = "".join(texts)
        if thinkings:
            reasoning = "".join(thinkings)
    else:
        text = str(msg.content) if msg.content else ""

    # DeepSeek: additional_kwargs.reasoning_content
    if not reasoning and isinstance(msg, AIMessage):
        reasoning = msg.additional_kwargs.get("reasoning_content")

    return text, reasoning


def _group_to_chat_messages(messages: list[BaseMessage]) -> list[ChatMessage]:
    """LangGraph flat 메시지 목록 → Claude.ai 포맷 ChatMessage 리스트.

    AIMessage(tool_calls) + ToolMessage(s) + AIMessage(final) 를
    하나의 assistant ChatMessage로 묶는다.
    """
    result: list[ChatMessage] = []
    i = 0
    while i < len(messages):
        msg = messages[i]

        if isinstance(msg, HumanMessage):
            text, _ = _extract_text_and_reasoning(msg)
            result.append(ChatMessage(
                uuid=msg.id,
                sender="human",
                content=[TextContentItem(text=text)],
                created_at=msg.additional_kwargs.get("created_at"),
            ))
            i += 1

        elif isinstance(msg, AIMessage):
            content_items: list = []
            reasoning: Optional[str] = None

            text, reasoning = _extract_text_and_reasoning(msg)
            if text:
                content_items.append(TextContentItem(text=text))

            for tc in (msg.tool_calls or []):
                content_items.append(ToolUseContentItem(
                    id=tc["id"],
                    name=tc["name"],
                    input=tc.get("args", {}),
                    message=_tool_display_message(tc["name"]),
                ))

            # 연속된 ToolMessage 소비
            j = i + 1
            while j < len(messages) and messages[j].type == "tool":
                tm = messages[j]
                is_error = bool(tm.additional_kwargs.get("is_error", False))
                content_items.append(ToolResultContentItem(
                    tool_use_id=getattr(tm, "tool_call_id", "") or "",
                    name=getattr(tm, "name", "") or "",
                    content=str(tm.content),
                    is_error=is_error,
                ))
                j += 1

            # 다음이 tool_calls 없는 최종 AIMessage이면 같은 블록에 합산
            if (
                j < len(messages)
                and isinstance(messages[j], AIMessage)
                and not messages[j].tool_calls
            ):
                final = messages[j]
                final_text, final_reasoning = _extract_text_and_reasoning(final)
                if final_reasoning:
                    reasoning = (reasoning or "") + final_reasoning
                if final_text:
                    content_items.append(TextContentItem(text=final_text))
                j += 1

            if not content_items:
                content_items.append(TextContentItem(text=""))

            result.append(ChatMessage(
                uuid=msg.id,
                sender="assistant",
                content=content_items,
                reasoning=reasoning,
                created_at=msg.additional_kwargs.get("created_at"),
            ))
            i = j

        else:
            # ToolMessage가 AIMessage 없이 단독으로 오는 경우 (예외 처리)
            i += 1

    return result


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def _extract_timestamps(messages: List[BaseMessage]) -> tuple[Optional[str], Optional[str]]:
    """메시지 목록에서 생성 시간과 마지막 활동 시간 추출"""
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


# ──────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────

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
    """새 세션 생성"""
    user_id = current_user.id
    session_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    success = await memory.init_session_async(session_id, user_id, client=client)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create session")

    logger.info(f"Created new session: {session_id}")
    return SessionCreateResponse(session_id=session_id, created_at=created_at)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> SessionDetailResponse:
    """세션 상세 정보 조회"""
    user_id = current_user.id

    try:
        message_count = await memory.get_message_count_async(session_id, user_id=user_id, client=client)
        messages = await memory.get_messages_async(session_id, user_id=user_id, client=client)
    except SessionAccessDenied:
        raise HTTPException(status_code=404, detail="Session not found or access denied")

    created_at, last_activity = _extract_timestamps(messages)
    return SessionDetailResponse(
        session_id=session_id,
        message_count=message_count,
        created_at=created_at,
        last_activity=last_activity,
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

    Events (SSE):
        - token: LLM 토큰 출력
        - think: 생각 과정
        - act: 도구 호출 (tool_call_id, tool, args)
        - observe: 도구 결과 (tool_call_id, content, is_error)
        - done: 스트림 완료
        - error: 에러 발생
    """
    user_id = current_user.id

    if body.stream:
        async def event_generator() -> AsyncGenerator[dict, None]:
            try:
                kwargs: dict = {}
                if user_id:
                    kwargs["user_id"] = user_id

                async for event in supervisor.process_stream(
                    question=body.message,
                    session_id=session_id,
                    client=client,
                    **kwargs,
                ):
                    event_type = event.get("type", "token")

                    if event_type == "token":
                        yield {
                            "event": "token",
                            "data": json.dumps({"content": event.get("content", "")}),
                        }
                    elif event_type == "think":
                        yield {
                            "event": "think",
                            "data": json.dumps({"content": event.get("content", "")}),
                        }
                    elif event_type == "act":
                        yield {
                            "event": "act",
                            "data": json.dumps({
                                "tool": event.get("tool", ""),
                                "args": event.get("args", {}),
                                "tool_call_id": event.get("tool_call_id"),
                            }),
                        }
                    elif event_type == "observe":
                        yield {
                            "event": "observe",
                            "data": json.dumps({
                                "content": event.get("content", ""),
                                "tool_call_id": event.get("tool_call_id"),
                                "is_error": event.get("is_error", False),
                            }),
                        }

                yield {"event": "done", "data": json.dumps({"session_id": session_id})}

            except SessionAccessDenied:
                yield {"event": "error", "data": json.dumps({"error": "Session not found or access denied"})}
            except ValueError:
                logger.warning("Validation error in stream processing")
                yield {"event": "error", "data": json.dumps({"error": "잘못된 요청입니다."})}
            except Exception:
                logger.exception("Stream processing failed")
                yield {"event": "error", "data": json.dumps({"error": "스트리밍 처리 중 오류가 발생했습니다."})}

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
                **kwargs,
            )
            return ChatResponse(answer=result.answer, sources=result.sources, session_id=session_id)
        except SessionAccessDenied:
            raise HTTPException(status_code=404, detail="Session not found or access denied")
        except ValueError:
            logger.warning("Validation error in chat processing")
            raise HTTPException(status_code=400, detail="잘못된 요청입니다.")
        except Exception:
            logger.exception("Chat processing failed")
            raise HTTPException(status_code=500, detail="요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> SessionListResponse:
    """세션 목록 조회"""
    user_id = current_user.id
    session_rows = await memory.list_sessions_async(user_id=user_id, client=client)
    sessions = [
        SessionInfo(
            session_id=row["id"],
            title=row.get("title"),
            message_count=await memory.get_message_count_async(row["id"], user_id=user_id, client=client),
            last_message_at=row.get("last_message_at"),
        )
        for row in session_rows
    ]
    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
    supervisor: Supervisor = Depends(get_supervisor),
) -> SessionHistoryResponse:
    """세션 대화 히스토리 조회 (Claude.ai 포맷)

    응답 구조:
        messages[].sender: "human" | "assistant"
        messages[].content: ContentItem 배열
            - type "text": 텍스트
            - type "tool_use": 도구 호출 (id, name, input, message, is_error)
            - type "tool_result": 도구 결과 (tool_use_id, content, is_error)
    """
    user_id = current_user.id

    try:
        await memory._check_session_ownership_async(session_id, user_id, client)
    except SessionAccessDenied:
        raise HTTPException(status_code=404, detail="Session not found or access denied")

    raw_messages = await supervisor.get_session_messages(session_id)
    chat_messages = _group_to_chat_messages(raw_messages)
    return SessionHistoryResponse(session_id=session_id, messages=chat_messages)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    body: SessionUpdateRequest,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> Dict[str, str]:
    """세션 정보 업데이트"""
    user_id = current_user.id
    try:
        if body.title is not None:
            await memory.update_session_title_async(session_id, body.title, user_id=user_id, client=client)
    except SessionAccessDenied:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
    return {"message": "Session updated", "session_id": session_id}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    memory: ChatMemory = Depends(get_memory),
) -> Dict[str, str]:
    """세션 삭제"""
    user_id = current_user.id
    try:
        await memory.delete_session_async(session_id, user_id=user_id, client=client)
    except SessionAccessDenied:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
    return {"message": "Session deleted", "session_id": session_id}


@router.post("/chat")
async def ai_chat(
    body: ChatPromptRequest,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
    supervisor: Supervisor = Depends(get_supervisor),
    memory: ChatMemory = Depends(get_memory),
):
    """Claude 방식 채팅 엔드포인트

    Protocol: UI Message Stream (https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
    """
    user_text = body.prompt
    user_id = current_user.id
    session_id = body.session_id

    if session_id:
        await memory.init_session_async(session_id, user_id, client=client)

    async def ui_message_stream() -> AsyncGenerator[str, None]:
        """UI Message Stream v1 프로토콜 형식으로 스트리밍"""
        message_id = f"msg_{uuid.uuid4().hex}"
        text_id = f"text_{uuid.uuid4().hex}"
        reasoning_id = f"rsn_{uuid.uuid4().hex}"
        reasoning_started = False
        text_started = False
        # tool_call_id: supervisor에서 온 실제 ID 또는 로컬 생성 ID
        current_tool_call_id = ""

        try:
            yield f"data: {json.dumps({'type': 'start', 'messageId': message_id})}\n\n"

            kwargs: dict = {}
            if user_id:
                kwargs["user_id"] = user_id
            if client:
                kwargs["client"] = client

            async for event in supervisor.process_stream(
                question=user_text,
                session_id=session_id,
                **kwargs,
            ):
                event_type = event.get("type")
                content = event.get("content", "")

                if event_type == "think" and content:
                    if not reasoning_started:
                        yield f"data: {json.dumps({'type': 'reasoning-start', 'id': reasoning_id})}\n\n"
                        reasoning_started = True
                    yield f"data: {json.dumps({'type': 'reasoning-delta', 'id': reasoning_id, 'delta': content})}\n\n"

                elif event_type == "act":
                    if reasoning_started:
                        yield f"data: {json.dumps({'type': 'reasoning-end', 'id': reasoning_id})}\n\n"
                        reasoning_started = False
                    if text_started:
                        yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"
                        text_started = False
                        text_id = f"text_{uuid.uuid4().hex}"

                    tool_name = event.get("tool", "")
                    tool_args = event.get("args", {})
                    # supervisor가 실제 tool_call_id를 제공하면 사용, 아니면 로컬 생성
                    current_tool_call_id = event.get("tool_call_id") or f"call_{uuid.uuid4().hex}"
                    yield f"data: {json.dumps({'type': 'tool-input-start', 'toolCallId': current_tool_call_id, 'toolName': tool_name})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool-input-available', 'toolCallId': current_tool_call_id, 'toolName': tool_name, 'input': tool_args})}\n\n"

                elif event_type == "observe":
                    # supervisor가 tool_call_id를 제공하면 우선 사용
                    observe_tool_call_id = event.get("tool_call_id") or current_tool_call_id
                    is_error = event.get("is_error", False)
                    if observe_tool_call_id:
                        yield f"data: {json.dumps({'type': 'tool-output-available', 'toolCallId': observe_tool_call_id, 'output': content, 'isError': is_error})}\n\n"
                        current_tool_call_id = ""

                elif event_type == "token" and content:
                    if reasoning_started:
                        yield f"data: {json.dumps({'type': 'reasoning-end', 'id': reasoning_id})}\n\n"
                        reasoning_started = False
                    if not text_started:
                        yield f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"
                        text_started = True
                    yield f"data: {json.dumps({'type': 'text-delta', 'id': text_id, 'delta': content})}\n\n"

            if reasoning_started:
                yield f"data: {json.dumps({'type': 'reasoning-end', 'id': reasoning_id})}\n\n"
            if text_started:
                yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"

            yield f"data: {json.dumps({'type': 'finish'})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.exception("Chat stream failed")
            yield f"data: {json.dumps({'type': 'error', 'errorText': str(e)})}\n\n"

    return StreamingResponse(
        ui_message_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Vercel-AI-UI-Message-Stream": "v1",
        },
    )
