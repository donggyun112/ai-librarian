# Phase 1: 프로젝트 구조 및 기반 설정

## 목표
기존 복잡한 코드를 정리하고, 슈퍼바이저 패턴을 위한 깔끔한 프로젝트 구조를 구축합니다.

---

## Task 1.1: 기존 코드 정리

### 작업 내용
1. `poc/src/langchain/` 폴더 전체 삭제
2. `poc/src/models/` 폴더 삭제
3. `poc/src/services/` 폴더 삭제 (vector_store.py, embedding_service.py만 보존)
4. `poc/src/utils/` 폴더 삭제
5. 루트의 불필요한 파일 삭제:
   - `streamlit_app_backup.py`
   - `test_autonomous_routing.py`
   - `test_setup.py`
   - `quick_test.py`
   - `run_streamlit.py`
   - `main.py`
   - `llm.py`
   - `PROJECT_CONTEXT.md`
   - `AUTONOMOUS_ROUTING_IMPLEMENTATION.md`

### 완료 조건
- `poc/src/` 폴더가 비어있거나 services만 남아있음

---

## Task 1.2: 새 디렉토리 구조 생성

### 작업 내용
```bash
mkdir -p poc/src/supervisor
mkdir -p poc/src/workers
mkdir -p poc/src/services
mkdir -p poc/src/schemas

touch poc/src/__init__.py
touch poc/src/supervisor/__init__.py
touch poc/src/workers/__init__.py
touch poc/src/services/__init__.py
touch poc/src/schemas/__init__.py
```

### 완료 조건
- 위 디렉토리 구조가 생성됨

---

## Task 1.3: 설정 파일 작성

### 작업 내용: `poc/config.py`

```python
"""설정 관리"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Milvus/Zilliz
    MILVUS_HOST = os.getenv("ZILLIZ_HOST")
    MILVUS_TOKEN = os.getenv("ZILLIZ_TOKEN")
    MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "documents")

    # Web Search (Tavily 권장)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Supervisor 설정
    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.7

config = Config()
```

### 완료 조건
- `poc/config.py` 파일 생성됨
- `.env` 파일에 필요한 환경변수 목록 확인

---

## Task 1.4: pyproject.toml 정리

### 작업 내용
기존 의존성을 정리하고 필수 패키지만 유지합니다.

```toml
[tool.poetry]
name = "ai-librarian"
version = "2.0.0"
description = "Supervisor Pattern based RAG System"
authors = ["Your Name"]

[tool.poetry.dependencies]
python = "^3.11"

# Core
langchain = "^0.3.0"
langchain-openai = "^0.3.0"
langgraph = "^0.2.0"
openai = "^1.50.0"

# Vector DB
pymilvus = "^2.5.0"

# Web Search
tavily-python = "^0.5.0"

# Data
pydantic = "^2.0"

# UI
streamlit = "^1.40.0"

# Utils
python-dotenv = "^1.0.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### 완료 조건
- `pyproject.toml` 업데이트됨
- 불필요한 의존성 제거됨

---

## Task 1.5: 기본 스키마 정의

### 작업 내용: `poc/src/schemas/models.py`

```python
"""Pydantic 모델 정의"""
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class WorkerType(str, Enum):
    RAG = "rag"
    WEB_SEARCH = "web_search"
    LLM_DIRECT = "llm_direct"

class ExecutionStrategy(str, Enum):
    SINGLE = "single"           # 단일 워커
    SEQUENTIAL = "sequential"   # 순차 실행
    PARALLEL = "parallel"       # 병렬 실행

class QueryAnalysis(BaseModel):
    """슈퍼바이저의 질문 분석 결과"""
    original_query: str = Field(description="원본 질문")
    intent: str = Field(description="질문의 의도")
    requires_recent_info: bool = Field(default=False, description="최신 정보 필요 여부")
    complexity: str = Field(default="simple", description="simple 또는 complex")
    keywords: List[str] = Field(default_factory=list, description="핵심 키워드")

class ExecutionPlan(BaseModel):
    """슈퍼바이저의 실행 계획"""
    strategy: ExecutionStrategy = Field(description="실행 전략")
    workers: List[WorkerType] = Field(description="사용할 워커 목록")
    refined_queries: List[str] = Field(description="정제된 쿼리 목록")
    reasoning: str = Field(description="이 계획을 선택한 이유")

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
    workers_used: List[WorkerType] = Field(description="사용된 워커 목록")
    execution_log: List[str] = Field(default_factory=list, description="실행 로그")
    total_confidence: float = Field(default=0.0, description="전체 신뢰도")
```

### 완료 조건
- `poc/src/schemas/models.py` 파일 생성됨
- 모든 핵심 스키마가 정의됨

---

## Phase 1 완료 체크리스트

- [ ] 기존 복잡한 코드 삭제 완료
- [ ] 새 디렉토리 구조 생성 완료
- [ ] config.py 작성 완료
- [ ] pyproject.toml 정리 완료
- [ ] schemas/models.py 작성 완료
- [ ] 기존 vector_store.py, embedding_service.py를 새 services/ 폴더로 이동

---

## 다음 단계
Phase 1 완료 후 [PHASE-2.md](./PHASE-2.md)로 진행합니다.
