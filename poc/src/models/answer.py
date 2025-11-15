"""
Answer model for system responses and metadata.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class AnswerSource(str, Enum):
    """Answer source type."""
    
    VECTOR_DB = "vector_db"          # 벡터 DB 시멘틱 서치
    LLM_DIRECT = "llm_direct"        # LLM 직접 답변
    WEB_SEARCH = "web_search"        # 웹 검색 결과
    HYBRID = "hybrid"                # 다중 소스 결합
    UNKNOWN = "unknown"              # 알 수 없음


class AnswerConfidenceLevel(str, Enum):
    """Answer confidence level."""
    
    HIGH = "high"        # 높음 (0.8+)
    MEDIUM = "medium"    # 보통 (0.5-0.8)
    LOW = "low"          # 낮음 (0.0-0.5)


class AnswerConfidence(BaseModel):
    """Answer confidence metrics."""
    
    relevance: float = Field(0.0, description="관련성 점수", ge=0.0, le=1.0)
    completeness: float = Field(0.0, description="완성도 점수", ge=0.0, le=1.0)
    accuracy: float = Field(0.0, description="정확도 점수", ge=0.0, le=1.0)
    reliability: float = Field(0.0, description="신뢰도 점수", ge=0.0, le=1.0)
    
    def overall_score(self) -> float:
        """전체 신뢰도 점수 계산."""
        return (self.relevance + self.completeness + self.accuracy + self.reliability) / 4
    
    def confidence_level(self) -> AnswerConfidenceLevel:
        """신뢰도 수준 반환."""
        score = self.overall_score()
        if score >= 0.8:
            return AnswerConfidenceLevel.HIGH
        elif score >= 0.5:
            return AnswerConfidenceLevel.MEDIUM
        else:
            return AnswerConfidenceLevel.LOW


class SourceReference(BaseModel):
    """Source reference information."""
    
    source_type: AnswerSource = Field(..., description="소스 유형")
    reference_id: Optional[str] = Field(None, description="참조 ID")
    title: Optional[str] = Field(None, description="소스 제목")
    url: Optional[str] = Field(None, description="소스 URL")
    snippet: Optional[str] = Field(None, description="관련 내용 스니펫")
    relevance_score: float = Field(0.0, description="관련성 점수", ge=0.0, le=1.0)


class Answer(BaseModel):
    """
    System answer model with source information and confidence.
    """
    
    # 기본 정보
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="고유 답변 ID")
    question_id: str = Field(..., description="관련 질문 ID")
    content: str = Field(..., description="답변 내용", min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now, description="답변 생성 시간")
    
    # 소스 정보
    primary_source: AnswerSource = Field(..., description="주요 답변 소스")
    sources: List[SourceReference] = Field(default_factory=list, description="참조 소스 목록")
    
    # 신뢰도 정보
    confidence: AnswerConfidence = Field(default_factory=AnswerConfidence, description="신뢰도 메트릭")
    confidence_level: AnswerConfidenceLevel = Field(AnswerConfidenceLevel.MEDIUM, description="신뢰도 수준")
    
    # 처리 정보
    processing_time_ms: int = Field(0, description="처리 시간 (밀리초)")
    tokens_used: int = Field(0, description="사용된 토큰 수")
    model_used: Optional[str] = Field(None, description="사용된 모델명")
    
    # 품질 지표
    relevance_score: float = Field(0.0, description="관련성 점수", ge=0.0, le=1.0)
    completeness_score: float = Field(0.0, description="완성도 점수", ge=0.0, le=1.0)
    accuracy_score: float = Field(0.0, description="정확도 점수", ge=0.0, le=1.0)
    
    # 추가 메타데이터
    language: str = Field("ko", description="답변 언어")
    tags: List[str] = Field(default_factory=list, description="답변 태그")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    
    # 사용자 피드백
    user_rating: Optional[int] = Field(None, description="사용자 평점 (1-5)", ge=1, le=5)
    user_feedback: Optional[str] = Field(None, description="사용자 피드백")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    def add_source(self, source: SourceReference) -> None:
        """소스 참조 추가."""
        self.sources.append(source)
        
    def add_tag(self, tag: str) -> None:
        """태그 추가."""
        if tag and tag not in self.tags:
            self.tags.append(tag)
            
    def update_confidence_level(self) -> None:
        """신뢰도 수준 업데이트."""
        overall_score = self.confidence.overall_score()
        if overall_score >= 0.8:
            self.confidence_level = AnswerConfidenceLevel.HIGH
        elif overall_score >= 0.5:
            self.confidence_level = AnswerConfidenceLevel.MEDIUM
        else:
            self.confidence_level = AnswerConfidenceLevel.LOW
            
    def calculate_overall_score(self) -> float:
        """전체 품질 점수 계산."""
        return (
            self.relevance_score * 0.4 +
            self.completeness_score * 0.3 +
            self.accuracy_score * 0.2 +
            self.confidence.overall_score() * 0.1
        )
        
    def is_high_quality(self) -> bool:
        """고품질 답변 여부 판단."""
        return (
            self.confidence_level == AnswerConfidenceLevel.HIGH and
            self.calculate_overall_score() >= 0.7 and
            len(self.sources) > 0
        )
        
    def get_source_summary(self) -> str:
        """소스 요약 정보 반환."""
        if not self.sources:
            return f"소스: {self.primary_source.value}"
            
        source_types = [source.source_type.value for source in self.sources]
        unique_types = list(set(source_types))
        
        if len(unique_types) == 1:
            return f"소스: {unique_types[0]} ({len(self.sources)}개 참조)"
        else:
            return f"소스: {', '.join(unique_types)} (총 {len(self.sources)}개 참조)"