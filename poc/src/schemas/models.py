"""Pydantic 모델 정의"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum

class WorkerType(str, Enum):
    RAG = "rag"
    WEB_SEARCH = "web_search"

class WorkerResult(BaseModel):
    """워커 실행 결과"""
    worker: WorkerType = Field(description="워커 타입")
    query: str = Field(description="실행된 쿼리")
    content: str = Field(description="결과 내용")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="신뢰도")
    sources: List[str] = Field(default_factory=list, description="출처 목록")
    success: bool = Field(default=True, description="실행 성공 여부")
    error: Optional[str] = Field(default=None, description="에러 메시지")

class SupervisorResponse(BaseModel):
    """최종 응답"""
    answer: str = Field(description="최종 답변")
    sources: List[str] = Field(default_factory=list, description="사용된 출처")
    execution_log: List[str] = Field(default_factory=list, description="실행 로그 (Think/Act/Observe)")
    total_confidence: float = Field(default=0.0, description="전체 신뢰도")
