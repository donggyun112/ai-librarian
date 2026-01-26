"""API 스키마 정의"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    """메시지 전송 요청 (session_id는 path parameter, user_id는 Authorization header)"""
    message: str = Field(..., min_length=1, description="사용자 메시지")
    stream: bool = Field(default=False, description="스트리밍 응답 여부")


class ChatResponse(BaseModel):
    """채팅 응답 (Non-streaming)"""
    answer: str = Field(..., description="AI 응답")
    sources: List[str] = Field(default_factory=list, description="사용된 도구 목록")
    session_id: Optional[str] = Field(None, description="세션 ID")


class SessionCreateResponse(BaseModel):
    """세션 생성 응답"""
    session_id: str = Field(..., description="생성된 세션 ID")
    created_at: str = Field(..., description="세션 생성 시간 (ISO 8601)")


class SessionInfo(BaseModel):
    """세션 정보"""
    session_id: str
    message_count: int


class SessionDetailResponse(BaseModel):
    """세션 상세 정보"""
    session_id: str = Field(..., description="세션 ID")
    message_count: int = Field(..., description="메시지 개수")
    created_at: Optional[str] = Field(None, description="세션 생성 시간")
    last_activity: Optional[str] = Field(None, description="마지막 활동 시간")


class SessionListResponse(BaseModel):
    """세션 목록 응답"""
    sessions: List[SessionInfo]


class MessageInfo(BaseModel):
    """메시지 정보"""
    role: str = Field(..., description="메시지 역할 (human, ai, system, tool)")
    content: str = Field(..., description="메시지 내용")
    timestamp: Optional[str] = Field(None, description="메시지 생성 시간")


class SessionHistoryResponse(BaseModel):
    """세션 히스토리 응답"""
    session_id: str
    messages: List[MessageInfo]


class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str = "ok"
    provider: str


# ─────────────────────────────────────────────────────────────
# Ingestion Schemas
# ─────────────────────────────────────────────────────────────


class IngestFileRequest(BaseModel):
    """파일 임베딩 요청 (경로 기반)"""
    file_path: str = Field(..., description="서버 내 파일 경로 (PDF, MD)")
    force_ocr: bool = Field(False, description="OCR 강제 적용")


class IngestResponse(BaseModel):
    """임베딩 결과 응답"""
    document_id: str = Field(..., description="생성된 문서 ID")
    source_path: str = Field(..., description="원본 파일 경로")
    fragments_count: int = Field(..., description="생성된 Fragment 수")
    embeddings_count: int = Field(..., description="저장된 Embedding 수")
    elapsed_seconds: float = Field(..., description="소요 시간 (초)")
    status: str = Field(..., description="상태 (success/failed)")
    errors: List[str] = Field(default_factory=list, description="에러 메시지")


class IngestDirectoryRequest(BaseModel):
    """디렉토리 일괄 임베딩 요청"""
    dir_path: str = Field(..., description="디렉토리 경로")
    pattern: str = Field("*.pdf", description="파일 패턴 (glob)")
    force_ocr: bool = Field(False, description="OCR 강제 적용")
    recursive: bool = Field(True, description="하위 디렉토리 포함")


class BatchIngestResponse(BaseModel):
    """일괄 임베딩 결과 응답"""
    total_files: int = Field(..., description="처리 대상 파일 수")
    successful_files: int = Field(..., description="성공한 파일 수")
    failed_files: int = Field(..., description="실패한 파일 수")
    total_fragments: int = Field(..., description="총 Fragment 수")
    total_embeddings: int = Field(..., description="총 Embedding 수")
    elapsed_seconds: float = Field(..., description="총 소요 시간 (초)")
    results: List[IngestResponse] = Field(default_factory=list, description="개별 결과")

