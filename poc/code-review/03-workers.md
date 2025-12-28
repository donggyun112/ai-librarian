# 03. Workers 심층 분석

> 검색 전략의 캡슐화 - RAG와 웹 검색을 통일된 인터페이스로

---

## 1. 파일 정보

| 파일 | 라인 수 | 역할 |
|------|---------|------|
| `src/workers/base.py` | 47줄 | 추상 베이스 클래스 |
| `src/workers/rag_worker.py` | 92줄 | 벡터 DB 검색 |
| `src/workers/web_worker.py` | 62줄 | 웹 검색 (DuckDuckGo) |
| `src/workers/factory.py` | ~30줄 | 워커 팩토리 |

---

## 2. 아키텍처 개요

### 2.1 Strategy 패턴 적용

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Workers Strategy Pattern                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                          ┌─────────────────────┐                        │
│                          │     BaseWorker      │                        │
│                          │     (Abstract)      │                        │
│                          │                     │                        │
│                          │ + worker_type       │                        │
│                          │ + execute(query)    │                        │
│                          │ # _create_result()  │                        │
│                          └──────────┬──────────┘                        │
│                                     │                                    │
│                     ┌───────────────┴───────────────┐                   │
│                     │                               │                    │
│                     ▼                               ▼                    │
│         ┌─────────────────────┐       ┌─────────────────────┐          │
│         │     RAGWorker       │       │   WebSearchWorker   │          │
│         │                     │       │                     │          │
│         │ • Milvus/Zilliz     │       │ • DuckDuckGo API    │          │
│         │ • OpenAI Embeddings │       │ • 무료 검색         │          │
│         │ • top_k=5           │       │ • max_results=10    │          │
│         │ • threshold=0.7     │       │ • confidence=0.7    │          │
│         └─────────────────────┘       └─────────────────────┘          │
│                     │                               │                    │
│                     │                               │                    │
│                     ▼                               ▼                    │
│         ┌─────────────────────┐       ┌─────────────────────┐          │
│         │   WorkerResult      │       │   WorkerResult      │          │
│         │   (통일된 출력)      │       │   (통일된 출력)      │          │
│         └─────────────────────┘       └─────────────────────┘          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 도구(Tool)과의 관계

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Tools ↔ Workers 관계                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   tools.py (LangChain Tool)              workers/ (검색 로직)           │
│   ┌─────────────────────────┐            ┌─────────────────────────┐    │
│   │                         │            │                         │    │
│   │  @tool                  │            │   class RAGWorker:      │    │
│   │  async def arag_search  │───────────▶│     async def execute   │    │
│   │      worker.execute()   │            │                         │    │
│   │                         │            └─────────────────────────┘    │
│   │                         │                                           │
│   │  @tool                  │            ┌─────────────────────────┐    │
│   │  async def aweb_search  │───────────▶│   class WebSearchWorker │    │
│   │      worker.execute()   │            │     async def execute   │    │
│   │                         │            │                         │    │
│   └─────────────────────────┘            └─────────────────────────┘    │
│                                                                          │
│   Tool = LLM이 호출하는 인터페이스                                       │
│   Worker = 실제 검색 로직 구현                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 코드 분석

### 3.1 base.py - 추상 베이스 클래스

```python
# src/workers/base.py

"""워커 베이스 클래스"""
from abc import ABC, abstractmethod
from src.schemas.models import WorkerResult, WorkerType


class BaseWorker(ABC):
    """모든 워커의 베이스 클래스"""

    @property
    @abstractmethod
    def worker_type(self) -> WorkerType:
        """워커 타입 반환"""
        pass

    @abstractmethod
    async def execute(self, query: str) -> WorkerResult:
        """
        쿼리를 실행하고 결과를 반환합니다.

        Args:
            query: 실행할 쿼리

        Returns:
            WorkerResult: 실행 결과
        """
        pass

    def _create_result(
        self,
        query: str,
        content: str,
        confidence: float = 0.0,
        sources: list = None,
        success: bool = True,
        error: str = None
    ) -> WorkerResult:
        """결과 객체 생성 헬퍼"""
        return WorkerResult(
            worker=self.worker_type,
            query=query,
            content=content,
            confidence=confidence,
            sources=sources or [],
            success=success,
            error=error
        )
```

### WorkerResult 모델

```python
# src/schemas/models.py

class WorkerType(str, Enum):
    """워커 타입"""
    RAG = "rag"
    WEB_SEARCH = "web_search"


class WorkerResult(BaseModel):
    """워커 실행 결과"""
    worker: WorkerType           # 어떤 워커가 실행했는지
    query: str                   # 실행한 쿼리
    content: str                 # 검색 결과 내용
    confidence: float            # 신뢰도 (0.0 ~ 1.0)
    sources: List[str]           # 출처 목록
    success: bool                # 성공 여부
    error: Optional[str]         # 에러 메시지 (실패 시)
```

### 인터페이스 설계

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      BaseWorker 인터페이스                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ worker_type: WorkerType (property, abstract)                    │   │
│   │                                                                  │   │
│   │ 책임: 워커 식별                                                  │   │
│   │ 용도: 결과에서 어떤 워커가 실행했는지 표시                        │   │
│   │                                                                  │   │
│   │ RAGWorker: WorkerType.RAG                                       │   │
│   │ WebSearchWorker: WorkerType.WEB_SEARCH                          │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ execute(query: str) → WorkerResult (async, abstract)            │   │
│   │                                                                  │   │
│   │ 책임: 검색 실행                                                  │   │
│   │ 입력: 검색 쿼리                                                  │   │
│   │ 출력: 통일된 WorkerResult                                       │   │
│   │                                                                  │   │
│   │ RAGWorker: 벡터 DB 검색                                         │   │
│   │ WebSearchWorker: 웹 검색                                        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ _create_result(...) → WorkerResult (helper)                     │   │
│   │                                                                  │   │
│   │ 책임: 결과 객체 생성 간소화                                      │   │
│   │ 이점: 보일러플레이트 코드 감소                                   │   │
│   │       worker_type 자동 주입                                     │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 3.2 rag_worker.py - 벡터 DB 검색

```python
# src/workers/rag_worker.py

"""RAG 워커 - 벡터 검색 기반"""
from typing import List
from langchain_openai import OpenAIEmbeddings
from pymilvus import MilvusClient

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker
from config import config


class RAGWorker(BaseWorker):
    """벡터 DB 검색을 수행하는 워커"""

    def __init__(self):
        # OpenAI 임베딩 클라이언트
        self.embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL,       # text-embedding-3-small
            api_key=config.OPENAI_API_KEY
        )

        # Milvus/Zilliz 클라이언트
        self.client = MilvusClient(
            uri=config.MILVUS_HOST,             # Zilliz Cloud URL
            token=config.MILVUS_TOKEN
        )

        self.collection_name = config.MILVUS_COLLECTION  # "documents"
        self.top_k = 5                          # 검색 결과 개수
        self.score_threshold = 0.7              # 최소 신뢰도

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.RAG

    async def execute(self, query: str) -> WorkerResult:
        """벡터 검색 실행"""
        try:
            # 1. 쿼리 임베딩 생성
            query_embedding = await self.embeddings.aembed_query(query)

            # 2. Milvus 검색
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=self.top_k,
                output_fields=["text", "source", "metadata"]
            )

            # 3. 결과 없음 처리
            if not results or not results[0]:
                return self._create_result(
                    query=query,
                    content="관련 문서를 찾지 못했습니다.",
                    confidence=0.0,
                    sources=[]
                )

            # 4. 결과 정리
            documents = []
            sources = []
            total_score = 0.0

            for hit in results[0]:
                score = hit.get("distance", 0)
                if score >= self.score_threshold:  # ⚠️ 주의: 메트릭 타입 확인 필요
                    text = hit.get("entity", {}).get("text", "")
                    source = hit.get("entity", {}).get("source", "unknown")
                    documents.append(f"- {text}")
                    sources.append(source)
                    total_score += score

            # 5. 임계값 미달 처리
            if not documents:
                return self._create_result(
                    query=query,
                    content="신뢰도 높은 문서를 찾지 못했습니다.",
                    confidence=0.3,
                    sources=[]
                )

            # 6. 성공 결과 반환
            avg_score = total_score / len(documents)
            content = "\n".join(documents)

            return self._create_result(
                query=query,
                content=content,
                confidence=min(avg_score, 1.0),
                sources=list(set(sources))  # 중복 제거
            )

        except Exception as e:
            return self._create_result(
                query=query,
                content="",
                success=False,
                error=f"RAG 검색 실패: {str(e)}"
            )
```

### RAG 검색 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RAGWorker.execute() 흐름                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   execute("LangGraph 사용법")                                           │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 1. 쿼리 임베딩 생성                                              │   │
│   │                                                                  │   │
│   │    await self.embeddings.aembed_query(query)                    │   │
│   │                                                                  │   │
│   │    "LangGraph 사용법" → [0.123, -0.456, 0.789, ...]            │   │
│   │                         (1536차원 벡터)                         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 2. Milvus 벡터 검색                                              │   │
│   │                                                                  │   │
│   │    self.client.search(                                          │   │
│   │        collection_name="documents",                             │   │
│   │        data=[query_embedding],                                  │   │
│   │        limit=5,  # top_k                                        │   │
│   │        output_fields=["text", "source", "metadata"]             │   │
│   │    )                                                            │   │
│   │                                                                  │   │
│   │    → 유사도 높은 상위 5개 문서 반환                               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 3. 결과 필터링 (score >= 0.7)                                    │   │
│   │                                                                  │   │
│   │    results = [                                                  │   │
│   │        {"distance": 0.95, "entity": {"text": "...", ...}},     │   │
│   │        {"distance": 0.82, "entity": {"text": "...", ...}},     │   │
│   │        {"distance": 0.71, "entity": {"text": "...", ...}},     │   │
│   │        {"distance": 0.45, ...},  ← 필터링 됨 (< 0.7)           │   │
│   │        {"distance": 0.32, ...},  ← 필터링 됨                   │   │
│   │    ]                                                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 4. WorkerResult 생성                                             │   │
│   │                                                                  │   │
│   │    WorkerResult(                                                │   │
│   │        worker=WorkerType.RAG,                                   │   │
│   │        query="LangGraph 사용법",                                │   │
│   │        content="- 문서1 내용\n- 문서2 내용\n- 문서3 내용",      │   │
│   │        confidence=0.826,  # 평균 점수                           │   │
│   │        sources=["docs/langgraph.md", "tutorial.md"],           │   │
│   │        success=True,                                            │   │
│   │        error=None                                               │   │
│   │    )                                                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### ⚠️ 주의: distance vs similarity

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Milvus 메트릭 타입 주의                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   현재 코드:                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ score = hit.get("distance", 0)                                  │   │
│   │ if score >= self.score_threshold:  # 0.7 이상이면 포함          │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   문제: 메트릭 타입에 따라 의미가 다름!                                   │
│                                                                          │
│   ┌─────────────────────────┐    ┌─────────────────────────────────┐    │
│   │   L2 (Euclidean)        │    │   IP (Inner Product) / Cosine   │    │
│   ├─────────────────────────┤    ├─────────────────────────────────┤    │
│   │                         │    │                                 │    │
│   │ distance가 작을수록     │    │ distance가 클수록               │    │
│   │ 더 유사함               │    │ 더 유사함                       │    │
│   │                         │    │                                 │    │
│   │ 0.0 = 완전 동일         │    │ 1.0 = 완전 동일 (코사인)        │    │
│   │ 큰값 = 다름             │    │ 0.0 = 무관                      │    │
│   │                         │    │                                 │    │
│   │ ❌ score >= 0.7 틀림    │    │ ✅ score >= 0.7 맞음            │    │
│   └─────────────────────────┘    └─────────────────────────────────┘    │
│                                                                          │
│   확인 필요:                                                             │
│   1. Milvus 컬렉션 생성 시 어떤 metric_type 사용했는지                   │
│   2. L2라면 로직 수정 필요: if score <= threshold (작을수록 좋음)        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 3.3 web_worker.py - 웹 검색

```python
# src/workers/web_worker.py

"""웹 서치 워커 - DuckDuckGo 사용"""
from ddgs import DDGS

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker


class WebSearchWorker(BaseWorker):
    """웹 검색을 수행하는 워커 (DuckDuckGo)"""

    def __init__(self, max_results: int = 10):
        self.ddgs = DDGS()                  # DuckDuckGo 클라이언트
        self.max_results = max_results      # 최대 검색 결과 수

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.WEB_SEARCH

    async def execute(self, query: str) -> WorkerResult:
        """웹 검색 실행"""
        try:
            # ⚠️ 동기 함수를 async 메서드에서 직접 호출 (블로킹!)
            results = list(self.ddgs.text(query, max_results=self.max_results))

            # 결과 없음 처리
            if not results:
                return self._create_result(
                    query=query,
                    content="검색 결과가 없습니다.",
                    confidence=0.0,
                    sources=[]
                )

            # 결과 포맷팅
            content_parts = []
            sources = []

            for i, result in enumerate(results, 1):
                title = result.get("title", "")
                body = result.get("body", "")
                url = result.get("href", "")

                content_parts.append(f"[{i}] {title}\n{body}\n출처: {url}")
                sources.append(url)

            content = "\n\n".join(content_parts)

            return self._create_result(
                query=query,
                content=content,
                confidence=0.7,  # DuckDuckGo는 점수 없음, 고정값 사용
                sources=sources
            )

        except Exception as e:
            return self._create_result(
                query=query,
                content="",
                success=False,
                error=f"웹 검색 실패: {str(e)}"
            )
```

### 웹 검색 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     WebSearchWorker.execute() 흐름                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   execute("2024 AI 트렌드")                                             │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 1. DuckDuckGo 검색                                               │   │
│   │                                                                  │   │
│   │    self.ddgs.text(query, max_results=10)                        │   │
│   │                                                                  │   │
│   │    → DuckDuckGo API 호출 (무료)                                 │   │
│   │    → ⚠️ 동기 함수 (이벤트 루프 블로킹!)                         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 2. 결과 파싱                                                     │   │
│   │                                                                  │   │
│   │    results = [                                                  │   │
│   │        {                                                        │   │
│   │            "title": "2024 AI Trends...",                       │   │
│   │            "body": "The latest AI developments...",            │   │
│   │            "href": "https://example.com/ai-2024"               │   │
│   │        },                                                       │   │
│   │        {...},                                                   │   │
│   │        {...},                                                   │   │
│   │    ]                                                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 3. 콘텐츠 포맷팅                                                 │   │
│   │                                                                  │   │
│   │    content = """                                                │   │
│   │    [1] 2024 AI Trends...                                       │   │
│   │    The latest AI developments...                               │   │
│   │    출처: https://example.com/ai-2024                           │   │
│   │                                                                  │   │
│   │    [2] Another Article Title                                   │   │
│   │    Article content...                                          │   │
│   │    출처: https://other.com/article                             │   │
│   │    ...                                                          │   │
│   │    """                                                          │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ 4. WorkerResult 생성                                             │   │
│   │                                                                  │   │
│   │    WorkerResult(                                                │   │
│   │        worker=WorkerType.WEB_SEARCH,                            │   │
│   │        query="2024 AI 트렌드",                                  │   │
│   │        content="[1] 2024 AI Trends...\n\n[2] ...",             │   │
│   │        confidence=0.7,  # 고정값                                │   │
│   │        sources=["https://...", "https://...", ...],            │   │
│   │        success=True,                                            │   │
│   │        error=None                                               │   │
│   │    )                                                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Tools와의 연결

### 4.1 tools.py 분석

```python
# src/supervisor/tools.py

"""슈퍼바이저 도구 정의"""
import asyncio
from typing import Optional
from langchain_core.tools import tool
from src.workers import RAGWorker, WebSearchWorker


# 전역 워커 인스턴스 (lazy initialization)
_rag_worker: Optional[RAGWorker] = None
_web_worker: Optional[WebSearchWorker] = None


def _get_rag_worker() -> RAGWorker:
    """RAGWorker 싱글톤"""
    global _rag_worker
    if _rag_worker is None:
        _rag_worker = RAGWorker()
    return _rag_worker


def _get_web_worker() -> WebSearchWorker:
    """WebSearchWorker 싱글톤"""
    global _web_worker
    if _web_worker is None:
        _web_worker = WebSearchWorker()
    return _web_worker


@tool
async def think(thought: str) -> str:
    """
    생각을 기록합니다. 도구를 호출하거나 답변하기 전에 반드시 이 도구로 생각을 먼저 말하세요.

    Args:
        thought: 현재 상황 분석, 다음 행동 계획, 또는 판단 근거

    예시:
        - "최신 정보가 필요하므로 웹 검색을 해야겠다"
        - "검색 결과에서 A 정보는 얻었지만 B 정보가 부족하다. 추가 검색이 필요하다"
        - "충분한 정보를 얻었다. 이제 답변을 작성하자"
    """
    return thought


@tool
async def arag_search(query: str) -> str:
    """내부 문서에서 정보를 검색합니다 (비동기)."""
    worker = _get_rag_worker()
    result = await worker.execute(query)
    return f"[RAG 검색 결과]\n{result.content}"


@tool
async def aweb_search(query: str) -> str:
    """웹에서 최신 정보를 검색합니다 (비동기)."""
    worker = _get_web_worker()
    result = await worker.execute(query)
    return f"[웹 검색 결과]\n{result.content}"


# Supervisor에서 사용할 도구 목록
TOOLS = [think, arag_search, aweb_search]
```

### 4.2 Tool → Worker 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      LLM Tool Call → Worker 실행                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   LLM이 도구 호출 결정                                                   │
│        │                                                                 │
│        │ AIMessage(tool_calls=[                                         │
│        │     {"name": "arag_search", "args": {"query": "LangGraph"}}    │
│        │ ])                                                             │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ LangGraph ToolNode                                               │   │
│   │                                                                  │   │
│   │ → tool_calls 파싱                                               │   │
│   │ → 해당 도구 함수 호출                                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ @tool arag_search(query: str)                                   │   │
│   │                                                                  │   │
│   │ async def arag_search(query: str) -> str:                       │   │
│   │     worker = _get_rag_worker()   # 싱글톤 획득                   │   │
│   │     result = await worker.execute(query)                        │   │
│   │     return f"[RAG 검색 결과]\n{result.content}"                 │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ RAGWorker.execute(query)                                        │   │
│   │                                                                  │   │
│   │ → 임베딩 생성                                                    │   │
│   │ → Milvus 검색                                                   │   │
│   │ → WorkerResult 반환                                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ ToolMessage로 변환                                               │   │
│   │                                                                  │   │
│   │ ToolMessage(                                                    │   │
│   │     content="[RAG 검색 결과]\n- 문서1\n- 문서2...",             │   │
│   │     tool_call_id="call_abc123"                                  │   │
│   │ )                                                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        │ messages에 추가되어 다음 LLM 호출에 포함                       │
│        ▼                                                                 │
│   supervisor 노드로 복귀                                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 주요 이슈 및 개선점

### 5.1 Critical Issues

#### Issue 1: Milvus 거리/유사도 로직 오류 (rag_worker.py:59)

```python
# 현재 - 메트릭 타입에 따라 틀릴 수 있음
score = hit.get("distance", 0)
if score >= self.score_threshold:  # L2면 반대!

# 개선안 - 메트릭 타입 확인 후 처리
# Option 1: 컬렉션이 IP/Cosine 메트릭 사용 확인
# Option 2: 로직 수정
if metric_type == "L2":
    if score <= (1 - self.score_threshold):  # 작을수록 좋음
        ...
else:  # IP, Cosine
    if score >= self.score_threshold:  # 클수록 좋음
        ...
```

### 5.2 High Issues

#### Issue 2: 동기 함수 블로킹 (web_worker.py:25)

```python
# 현재 - 이벤트 루프 블로킹
async def execute(self, query: str) -> WorkerResult:
    results = list(self.ddgs.text(query, max_results=self.max_results))  # 동기!

# 수정 - asyncio.to_thread 사용
import asyncio

async def execute(self, query: str) -> WorkerResult:
    try:
        # 동기 함수를 별도 스레드에서 실행
        results = await asyncio.to_thread(
            lambda: list(self.ddgs.text(query, max_results=self.max_results))
        )
        ...
```

#### Issue 3: Milvus 연결 실패 미처리 (rag_worker.py:19-22)

```python
# 현재 - 연결 실패 시 앱 크래시
self.client = MilvusClient(
    uri=config.MILVUS_HOST,
    token=config.MILVUS_TOKEN
)

# 개선안 - lazy initialization + 에러 처리
def __init__(self):
    self.embeddings = OpenAIEmbeddings(...)
    self._client = None

@property
def client(self):
    if self._client is None:
        try:
            self._client = MilvusClient(
                uri=config.MILVUS_HOST,
                token=config.MILVUS_TOKEN
            )
        except Exception as e:
            raise RuntimeError(f"Milvus 연결 실패: {e}")
    return self._client
```

### 5.3 Medium Issues

#### Issue 4: 전역 워커 인스턴스 (tools.py:9-10)

```python
# 현재 - 전역 상태
_rag_worker: Optional[RAGWorker] = None
_web_worker: Optional[WebSearchWorker] = None

# 문제:
# 1. 테스트 시 모킹 어려움
# 2. 스레드 안전성 미보장

# 개선안 1 - 스레드 안전 싱글톤
import threading

_lock = threading.Lock()
_rag_worker: Optional[RAGWorker] = None

def _get_rag_worker() -> RAGWorker:
    global _rag_worker
    if _rag_worker is None:
        with _lock:
            if _rag_worker is None:  # Double-check locking
                _rag_worker = RAGWorker()
    return _rag_worker

# 개선안 2 - 의존성 주입 컨테이너
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    rag_worker = providers.Singleton(RAGWorker)
    web_worker = providers.Singleton(WebSearchWorker)
```

### 5.4 Low Issues

#### Issue 5: 매직넘버 (rag_worker.py:24-25)

```python
# 현재
self.top_k = 5
self.score_threshold = 0.7

# 개선안 - config로 이동
# config.py
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.7"))

# rag_worker.py
self.top_k = config.RAG_TOP_K
self.score_threshold = config.RAG_SCORE_THRESHOLD
```

---

## 6. 확장 가이드

### 6.1 새 워커 추가하기

```python
# 1. src/workers/sql_worker.py 생성

"""SQL 워커 - 데이터베이스 검색"""
from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker


class SQLWorker(BaseWorker):
    """SQL 데이터베이스 검색을 수행하는 워커"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        # 연결 설정...

    @property
    def worker_type(self) -> WorkerType:
        # WorkerType Enum에 SQL 추가 필요
        return WorkerType.SQL

    async def execute(self, query: str) -> WorkerResult:
        try:
            # SQL 검색 로직
            results = await self._search_database(query)

            return self._create_result(
                query=query,
                content=self._format_results(results),
                confidence=0.8,
                sources=["database"]
            )
        except Exception as e:
            return self._create_result(
                query=query,
                content="",
                success=False,
                error=f"SQL 검색 실패: {str(e)}"
            )
```

```python
# 2. src/schemas/models.py 수정

class WorkerType(str, Enum):
    RAG = "rag"
    WEB_SEARCH = "web_search"
    SQL = "sql"  # 추가
```

```python
# 3. src/supervisor/tools.py에 도구 추가

from src.workers import SQLWorker

_sql_worker: Optional[SQLWorker] = None

def _get_sql_worker() -> SQLWorker:
    global _sql_worker
    if _sql_worker is None:
        _sql_worker = SQLWorker(config.DATABASE_URL)
    return _sql_worker

@tool
async def asql_search(query: str) -> str:
    """데이터베이스에서 정보를 검색합니다."""
    worker = _get_sql_worker()
    result = await worker.execute(query)
    return f"[SQL 검색 결과]\n{result.content}"

TOOLS = [think, arag_search, aweb_search, asql_search]  # 추가
```

---

## 7. 테스트 포인트

```python
# tests/test_workers.py

1. RAGWorker 테스트
   - 정상 검색 결과 반환
   - 결과 없음 처리
   - 임계값 미달 처리
   - Milvus 연결 실패 처리

2. WebSearchWorker 테스트
   - 정상 검색 결과 반환
   - 결과 없음 처리
   - DuckDuckGo API 실패 처리

3. 통합 테스트
   - tools.py의 arag_search 호출
   - tools.py의 aweb_search 호출
   - Supervisor에서 워커 호출

4. 모킹 테스트
   - Milvus 클라이언트 모킹
   - DDGS 클라이언트 모킹
   - OpenAI 임베딩 모킹
```

---

## 8. 요약

| 항목 | 내용 |
|------|------|
| **책임** | 검색 로직 캡슐화 (RAG, 웹) |
| **패턴** | Strategy, Singleton (lazy) |
| **핵심 인터페이스** | `execute(query) → WorkerResult` |
| **지원 워커** | RAGWorker, WebSearchWorker |
| **확장성** | 새 워커 추가 시 Tool만 추가하면 됨 |
| **주요 이슈** | 거리/유사도 로직, 동기 블로킹, 연결 실패 |

---

*다음: [04-memory.md](./04-memory.md) - Memory System 심층 분석*
