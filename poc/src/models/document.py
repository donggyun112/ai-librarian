"""
Document model for PDF documents and text chunks.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Document processing status."""
    
    PENDING = "pending"              # 처리 대기
    PROCESSING = "processing"        # 처리 중
    COMPLETED = "completed"          # 처리 완료
    FAILED = "failed"                # 처리 실패
    ARCHIVED = "archived"            # 보관됨


class ChunkType(str, Enum):
    """Text chunk type."""
    
    PARAGRAPH = "paragraph"          # 단락
    SECTION = "section"              # 섹션
    TABLE = "table"                  # 표
    LIST = "list"                    # 목록
    HEADER = "header"                # 헤더
    FOOTER = "footer"                # 푸터
    OTHER = "other"                  # 기타


class DocumentChunk(BaseModel):
    """
    Text chunk from document with embedding information.
    """
    
    # 기본 정보
    id: str = Field(..., description="고유 청크 ID")
    document_id: str = Field(..., description="소속 문서 ID")
    content: str = Field(..., description="청크 텍스트 내용", min_length=1)
    
    # 위치 정보
    page_number: Optional[int] = Field(None, description="페이지 번호")
    chunk_index: int = Field(..., description="문서 내 청크 순서")
    start_char: Optional[int] = Field(None, description="시작 문자 위치")
    end_char: Optional[int] = Field(None, description="종료 문자 위치")
    
    # 청크 속성
    chunk_type: ChunkType = Field(ChunkType.PARAGRAPH, description="청크 유형")
    word_count: int = Field(0, description="단어 수")
    char_count: int = Field(0, description="문자 수")
    
    # 임베딩 정보
    embedding_vector: Optional[List[float]] = Field(None, description="임베딩 벡터")
    embedding_model: Optional[str] = Field(None, description="사용된 임베딩 모델")
    
    # 메타데이터
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    summary: Optional[str] = Field(None, description="청크 요약")
    language: str = Field("ko", description="언어")
    
    # 품질 지표
    readability_score: float = Field(0.0, description="가독성 점수", ge=0.0, le=1.0)
    importance_score: float = Field(0.0, description="중요도 점수", ge=0.0, le=1.0)
    
    # 시간 정보
    created_at: datetime = Field(default_factory=datetime.now, description="생성 시간")
    updated_at: datetime = Field(default_factory=datetime.now, description="수정 시간")
    
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
            
    def update_counts(self) -> None:
        """단어 수와 문자 수 업데이트."""
        self.char_count = len(self.content)
        self.word_count = len(self.content.split())
        
    def get_preview(self, max_length: int = 100) -> str:
        """청크 미리보기 반환."""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."


class Document(BaseModel):
    """
    PDF document model with processing information.
    """
    
    # 기본 정보
    id: str = Field(..., description="고유 문서 ID")
    filename: str = Field(..., description="파일명")
    title: Optional[str] = Field(None, description="문서 제목")
    author: Optional[str] = Field(None, description="문서 저자")
    
    # 파일 정보
    file_path: str = Field(..., description="파일 경로")
    file_size: int = Field(0, description="파일 크기 (바이트)")
    file_hash: Optional[str] = Field(None, description="파일 해시")
    
    # 문서 속성
    page_count: int = Field(0, description="총 페이지 수")
    total_chunks: int = Field(0, description="총 청크 수")
    language: str = Field("ko", description="문서 언어")
    
    # 처리 상태
    status: DocumentStatus = Field(DocumentStatus.PENDING, description="처리 상태")
    processing_started_at: Optional[datetime] = Field(None, description="처리 시작 시간")
    processing_completed_at: Optional[datetime] = Field(None, description="처리 완료 시간")
    error_message: Optional[str] = Field(None, description="에러 메시지")
    
    # 임베딩 정보
    embedding_model: Optional[str] = Field(None, description="사용된 임베딩 모델")
    vector_store_collection: Optional[str] = Field(None, description="벡터 저장소 컬렉션명")
    
    # 메타데이터
    keywords: List[str] = Field(default_factory=list, description="문서 키워드")
    summary: Optional[str] = Field(None, description="문서 요약")
    categories: List[str] = Field(default_factory=list, description="문서 카테고리")
    tags: List[str] = Field(default_factory=list, description="문서 태그")
    
    # 품질 지표
    extraction_quality: float = Field(0.0, description="텍스트 추출 품질", ge=0.0, le=1.0)
    content_richness: float = Field(0.0, description="콘텐츠 풍부도", ge=0.0, le=1.0)
    
    # 시간 정보
    created_at: datetime = Field(default_factory=datetime.now, description="생성 시간")
    updated_at: datetime = Field(default_factory=datetime.now, description="수정 시간")
    
    # 추가 메타데이터
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
            
    def add_category(self, category: str) -> None:
        """카테고리 추가."""
        if category and category not in self.categories:
            self.categories.append(category)
            
    def add_tag(self, tag: str) -> None:
        """태그 추가."""
        if tag and tag not in self.tags:
            self.tags.append(tag)
            
    def update_status(self, status: DocumentStatus, error_message: Optional[str] = None) -> None:
        """처리 상태 업데이트."""
        self.status = status
        self.updated_at = datetime.now()
        
        if status == DocumentStatus.PROCESSING and not self.processing_started_at:
            self.processing_started_at = datetime.now()
        elif status == DocumentStatus.COMPLETED:
            self.processing_completed_at = datetime.now()
            self.error_message = None
        elif status == DocumentStatus.FAILED:
            self.error_message = error_message
            
    def get_processing_duration(self) -> Optional[float]:
        """처리 소요 시간 반환 (초)."""
        if not self.processing_started_at:
            return None
            
        end_time = self.processing_completed_at or datetime.now()
        duration = end_time - self.processing_started_at
        return duration.total_seconds()
        
    def is_ready_for_search(self) -> bool:
        """검색 가능 상태 여부."""
        return (
            self.status == DocumentStatus.COMPLETED and
            self.total_chunks > 0 and
            self.vector_store_collection is not None
        )
        
    def get_file_info(self) -> Dict[str, Any]:
        """파일 정보 요약."""
        return {
            "filename": self.filename,
            "size_mb": round(self.file_size / (1024 * 1024), 2),
            "pages": self.page_count,
            "chunks": self.total_chunks,
            "language": self.language,
            "status": self.status.value
        }