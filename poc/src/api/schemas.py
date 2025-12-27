"""API 스키마 정의"""
from typing import Optional, List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str = Field(..., min_length=1, description="사용자 메시지")
    session_id: Optional[str] = Field(None, description="세션 ID (없으면 히스토리 없이 처리)")


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
