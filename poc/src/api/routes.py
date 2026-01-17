"""API 라우트 정의"""
import json
import uuid
from typing import AsyncGenerator, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from src.supervisor import Supervisor
from src.memory import InMemoryChatMemory, SupabaseChatMemory
from src.rag.api.use_cases import SearchUseCase
from src.rag.embedding import EmbeddingProviderFactory
from src.rag.shared.config import load_config as load_rag_config
from src.rag.shared.exceptions import DatabaseNotConfiguredError
from config import config
from .schemas import (
    ChatRequest,
    ChatResponse,
    SessionInfo,
    SessionListResponse,
    SessionHistoryResponse,
    MessageInfo,
    HealthResponse,
)

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


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """채팅 (Non-streaming)"""
    session_id = request.session_id or str(uuid.uuid4())

    # SupabaseChatMemory인 경우 user_id 필수
    if isinstance(memory, SupabaseChatMemory):
        if not request.user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when using Supabase backend"
            )

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
    except ValueError as e:
        # Handle user_id validation errors from Supervisor._build_messages
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


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    """채팅 (SSE Streaming)

    이벤트 타입:
    - token: LLM 토큰 출력
    - think: 생각 과정
    - act: 도구 호출
    - observe: 도구 결과
    - done: 스트림 완료
    - error: 에러 발생
    """
    # SupabaseChatMemory인 경우 user_id 필수
    if isinstance(memory, SupabaseChatMemory):
        if not request.user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when using Supabase backend"
            )

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

        except ValueError as e:
            # Handle user_id validation errors from Supervisor._build_messages
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


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(user_id: Optional[str] = None) -> SessionListResponse:
    """세션 목록 조회

    Args:
        user_id: 사용자 ID (Supabase 사용 시 필수)
    """
    # SupabaseChatMemory인 경우 user_id 필수
    if isinstance(memory, SupabaseChatMemory):
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when using Supabase backend"
            )
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
async def get_session_messages(session_id: str, user_id: Optional[str] = None) -> SessionHistoryResponse:
    """세션의 대화 히스토리 조회

    Args:
        session_id: 세션 ID
        user_id: 사용자 ID (Supabase 사용 시 필수)
    """
    # SupabaseChatMemory인 경우 user_id 필수 및 소유권 검증
    if isinstance(memory, SupabaseChatMemory):
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when using Supabase backend"
            )
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
async def delete_session(session_id: str, user_id: Optional[str] = None) -> Dict[str, str]:
    """세션 삭제

    Args:
        session_id: 세션 ID
        user_id: 사용자 ID (Supabase 사용 시 필수)
    """
    # SupabaseChatMemory인 경우 user_id 필수 및 소유권 검증
    if isinstance(memory, SupabaseChatMemory):
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when using Supabase backend"
            )
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


@router.delete("/sessions/{session_id}/messages")
async def clear_session(session_id: str, user_id: Optional[str] = None) -> Dict[str, str]:
    """세션 메시지 초기화

    Args:
        session_id: 세션 ID
        user_id: 사용자 ID (Supabase 사용 시 필수)
    """
    # SupabaseChatMemory인 경우 user_id 필수 및 소유권 검증
    if isinstance(memory, SupabaseChatMemory):
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when using Supabase backend"
            )
        # 소유권 검증
        user_sessions = await memory.list_sessions_async(user_id=user_id)
        if session_id not in user_sessions:
            raise HTTPException(status_code=404, detail="Session not found or access denied")
        await memory.clear_async(session_id, user_id=user_id)
    else:
        # InMemoryChatMemory는 user_id 무시
        memory.clear(session_id)

    return {"message": "Session cleared", "session_id": session_id}


# ─────────────────────────────────────────────────────────────
# RAG Search Endpoints
# ─────────────────────────────────────────────────────────────

# Request/Response schemas for RAG endpoints
class SearchRequest(BaseModel):
    """검색 요청"""
    query: str = Field(..., min_length=1, max_length=1000, description="검색어")
    view: Optional[Literal["text", "code", "image", "table", "figure", "caption"]] = Field(
        None, description="뷰 필터 (text, code, image, table, figure, caption)"
    )
    language: Optional[str] = Field(None, description="언어 필터 (python, javascript 등)")
    top_k: int = Field(10, ge=1, le=100, description="결과 개수 (1-100)")
    expand_context: bool = Field(True, description="Parent context 포함 여부")


class SearchResultItem(BaseModel):
    """검색 결과 항목"""
    fragment_id: str
    parent_id: str
    view: str
    language: Optional[str]
    content: str
    similarity: float
    parent_content: Optional[str] = None


class SearchResultResponse(BaseModel):
    """검색 결과 응답"""
    query: str
    results: List[SearchResultItem]


@router.post(
    "/rag/ingest",
    response_model=None,
    status_code=501,
    deprecated=True,
    summary="문서 임베딩 (보안상 비활성화됨)",
    responses={
        501: {
            "description": "Not Implemented - 보안상 비활성화됨. CLI 사용: python -m src.rag.api.cli ingest <files>",
        }
    },
)
async def rag_ingest() -> None:
    """문서 임베딩 (보안상 비활성화됨)

    ⚠️ SECURITY: 이 엔드포인트는 Remote File Read 취약점으로 인해 비활성화되었습니다.
    현재는 CLI (python -m src.rag.api.cli ingest)를 통해서만 사용 가능합니다.
    """
    raise HTTPException(
        status_code=501,
        detail="Ingestion via REST API is disabled for security reasons. "
               "Use CLI instead: python -m src.rag.api.cli ingest <files>"
    )


@router.post("/rag/search", response_model=SearchResultResponse)
async def rag_search(request: SearchRequest) -> SearchResultResponse:
    """벡터 검색

    쿼리와 유사한 문서 Fragment를 검색합니다.

    Args:
        request: 검색어, 필터, 결과 개수

    Returns:
        검색 결과 목록
    """
    try:
        rag_config = load_rag_config()
        embeddings_client = EmbeddingProviderFactory.create(rag_config)
        use_case = SearchUseCase(embeddings_client, rag_config)

        results = await run_in_threadpool(
            use_case.execute,
            query=request.query,
            view=request.view,
            language=request.language,
            top_k=request.top_k,
            expand_context=request.expand_context,
        )

        items = [
            SearchResultItem(
                fragment_id=r.result.fragment_id,
                parent_id=r.result.parent_id,
                view=r.result.view.value,
                language=r.result.language,
                content=r.result.content,
                similarity=r.result.similarity,
                parent_content=r.parent_content if request.expand_context else None,
            )
            for r in results
        ]

        return SearchResultResponse(query=request.query, results=items)
    except DatabaseNotConfiguredError as e:
        # DB not configured - service unavailable
        logger.error(f"Search service unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail="검색 서비스가 현재 사용 불가합니다. 데이터베이스 설정을 확인해주세요."
        )
    except Exception as e:
        logger.exception("Search failed")
        # 내부 예외 메시지 숨김 (보안)
        raise HTTPException(
            status_code=500,
            detail="검색 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


