"""
Question model for user queries and question analysis.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Question type classification for routing decisions."""
    
    FACTUAL = "factual"              # 사실적 질문 (PDF 검색 우선)
    GENERAL = "general"              # 일반적 질문 (LLM 직접 답변 우선)
    CURRENT_EVENTS = "current_events" # 최신 정보 (웹 검색 우선)
    COMPLEX = "complex"              # 복합적 질문 (다중 소스 결합)
    UNKNOWN = "unknown"              # 분류 불가


class Question(BaseModel):
    """
    User question model with metadata and analysis results.
    """
    
    # 기본 정보
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="고유 질문 ID")
    content: str = Field(..., description="사용자 질문 내용", min_length=1)
    user_id: Optional[str] = Field(None, description="사용자 ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="질문 시간")
    
    # 질문 분석 결과
    question_type: QuestionType = Field(QuestionType.UNKNOWN, description="질문 유형")
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    intent: Optional[str] = Field(None, description="질문 의도")
    confidence: float = Field(0.0, description="분류 신뢰도", ge=0.0, le=1.0)
    
    # 라우팅 정보
    preferred_sources: List[str] = Field(
        default_factory=list, 
        description="우선 답변 소스 ['vector_db', 'llm_direct', 'web_search']"
    )
    context_needed: bool = Field(False, description="문맥 정보 필요 여부")
    
    # 추가 메타데이터
    language: str = Field("ko", description="질문 언어")
    complexity_score: float = Field(0.0, description="질문 복잡도", ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    def add_keyword(self, keyword: str) -> None:
        """키워드 추가."""
        if keyword and keyword not in self.keywords:
            self.keywords.append(keyword)
            
    def set_preferred_source(self, source: str) -> None:
        """우선 답변 소스 설정."""
        valid_sources = ["vector_db", "llm_direct", "web_search"]
        if source in valid_sources and source not in self.preferred_sources:
            self.preferred_sources.append(source)
            
    def is_complex_question(self) -> bool:
        """복합적 질문 여부 판단."""
        return (
            self.question_type == QuestionType.COMPLEX or
            self.complexity_score > 0.7 or
            len(self.keywords) > 5
        )
        
    def requires_real_time_info(self) -> bool:
        """실시간 정보 필요 여부 판단."""
        real_time_keywords = ["최신", "현재", "오늘", "지금", "최근", "today", "now", "current"]
        return (
            self.question_type == QuestionType.CURRENT_EVENTS or
            any(keyword in self.content.lower() for keyword in real_time_keywords)
        )