# Phase 3: 워커 에이전트 구현

## 목표
슈퍼바이저의 지시를 받아 실제 작업을 수행하는 3개의 워커를 구현합니다.

---

## Task 3.1: 워커 베이스 클래스

### 작업 내용: `poc/src/workers/base.py`

```python
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

### 완료 조건
- 추상 베이스 클래스 정의
- 결과 생성 헬퍼 메서드 포함

---

## Task 3.2: RAG 워커 (벡터 검색)

### 작업 내용: `poc/src/workers/rag_worker.py`

```python
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
        self.embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL,
            api_key=config.OPENAI_API_KEY
        )
        self.client = MilvusClient(
            uri=config.MILVUS_HOST,
            token=config.MILVUS_TOKEN
        )
        self.collection_name = config.MILVUS_COLLECTION
        self.top_k = 5
        self.score_threshold = 0.7

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

            if not results or not results[0]:
                return self._create_result(
                    query=query,
                    content="관련 문서를 찾지 못했습니다.",
                    confidence=0.0,
                    sources=[]
                )

            # 3. 결과 정리
            documents = []
            sources = []
            total_score = 0.0

            for hit in results[0]:
                score = hit.get("distance", 0)
                if score >= self.score_threshold:
                    text = hit.get("entity", {}).get("text", "")
                    source = hit.get("entity", {}).get("source", "unknown")
                    documents.append(f"- {text}")
                    sources.append(source)
                    total_score += score

            if not documents:
                return self._create_result(
                    query=query,
                    content="신뢰도 높은 문서를 찾지 못했습니다.",
                    confidence=0.3,
                    sources=[]
                )

            avg_score = total_score / len(documents)
            content = "\n".join(documents)

            return self._create_result(
                query=query,
                content=content,
                confidence=min(avg_score, 1.0),
                sources=list(set(sources))
            )

        except Exception as e:
            return self._create_result(
                query=query,
                content="",
                success=False,
                error=f"RAG 검색 실패: {str(e)}"
            )
```

### 완료 조건
- Milvus 연동 완료
- 임베딩 생성 및 검색 구현
- 신뢰도 계산 로직 포함

---

## Task 3.3: 웹 서치 워커

### 작업 내용: `poc/src/workers/web_worker.py`

```python
"""웹 서치 워커 - Tavily API 사용"""
from tavily import TavilyClient

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker
from config import config


class WebSearchWorker(BaseWorker):
    """웹 검색을 수행하는 워커"""

    def __init__(self):
        self.client = TavilyClient(api_key=config.TAVILY_API_KEY)
        self.max_results = 5

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.WEB_SEARCH

    async def execute(self, query: str) -> WorkerResult:
        """웹 검색 실행"""
        try:
            # Tavily 검색 실행
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=self.max_results,
                include_answer=True
            )

            # 결과 정리
            answer = response.get("answer", "")
            results = response.get("results", [])

            if not results and not answer:
                return self._create_result(
                    query=query,
                    content="검색 결과가 없습니다.",
                    confidence=0.0,
                    sources=[]
                )

            # 검색 결과 컨텐츠 조합
            content_parts = []
            sources = []

            if answer:
                content_parts.append(f"[요약]\n{answer}")

            for result in results[:3]:  # 상위 3개만
                title = result.get("title", "")
                snippet = result.get("content", "")
                url = result.get("url", "")

                content_parts.append(f"\n[{title}]\n{snippet}")
                sources.append(url)

            content = "\n".join(content_parts)

            # Tavily 점수 기반 신뢰도
            avg_score = sum(r.get("score", 0.5) for r in results) / max(len(results), 1)

            return self._create_result(
                query=query,
                content=content,
                confidence=avg_score,
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

### 완료 조건
- Tavily API 연동
- 검색 결과 및 요약 반환
- 출처 URL 포함

---

## Task 3.4: LLM Direct 워커

### 작업 내용: `poc/src/workers/llm_worker.py`

```python
"""LLM Direct 워커 - 직접 LLM 질의"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker
from config import config


class LLMDirectWorker(BaseWorker):
    """LLM에 직접 질의하는 워커"""

    SYSTEM_PROMPT = """당신은 지식이 풍부한 AI 어시스턴트입니다.
사용자의 질문에 정확하고 도움이 되는 답변을 제공하세요.

지침:
- 정확한 정보만 제공하세요
- 불확실한 경우 솔직히 말하세요
- 한국어로 답변하세요
- 간결하지만 충분한 설명을 하세요"""

    def __init__(self, model: str = None, temperature: float = 0.7):
        self.llm = ChatOpenAI(
            model=model or config.OPENAI_MODEL,
            temperature=temperature,
            api_key=config.OPENAI_API_KEY
        )

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.LLM_DIRECT

    async def execute(self, query: str) -> WorkerResult:
        """LLM 직접 질의 실행"""
        try:
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=query)
            ]

            response = await self.llm.ainvoke(messages)
            content = response.content

            # LLM 응답은 기본 신뢰도 0.7
            # 길이가 너무 짧으면 신뢰도 하락
            confidence = 0.7
            if len(content) < 50:
                confidence = 0.5
            elif len(content) > 500:
                confidence = 0.8

            return self._create_result(
                query=query,
                content=content,
                confidence=confidence,
                sources=["LLM Knowledge"]
            )

        except Exception as e:
            return self._create_result(
                query=query,
                content="",
                success=False,
                error=f"LLM 질의 실패: {str(e)}"
            )
```

### 완료 조건
- ChatOpenAI 연동
- 시스템 프롬프트 설정
- 응답 길이 기반 신뢰도 계산

---

## Task 3.5: 워커 __init__.py

### 작업 내용: `poc/src/workers/__init__.py`

```python
from .base import BaseWorker
from .rag_worker import RAGWorker
from .web_worker import WebSearchWorker
from .llm_worker import LLMDirectWorker

__all__ = ["BaseWorker", "RAGWorker", "WebSearchWorker", "LLMDirectWorker"]
```

### 완료 조건
- 모든 워커 export

---

## Task 3.6: 워커 팩토리 함수

### 작업 내용: `poc/src/workers/factory.py`

```python
"""워커 팩토리"""
from typing import Dict
from src.schemas.models import WorkerType
from src.workers.base import BaseWorker
from src.workers.rag_worker import RAGWorker
from src.workers.web_worker import WebSearchWorker
from src.workers.llm_worker import LLMDirectWorker


def create_all_workers() -> Dict[WorkerType, BaseWorker]:
    """모든 워커 인스턴스 생성"""
    return {
        WorkerType.RAG: RAGWorker(),
        WorkerType.WEB_SEARCH: WebSearchWorker(),
        WorkerType.LLM_DIRECT: LLMDirectWorker()
    }


def create_worker(worker_type: WorkerType) -> BaseWorker:
    """특정 워커 인스턴스 생성"""
    workers = {
        WorkerType.RAG: RAGWorker,
        WorkerType.WEB_SEARCH: WebSearchWorker,
        WorkerType.LLM_DIRECT: LLMDirectWorker
    }
    return workers[worker_type]()
```

### 완료 조건
- 워커 생성 팩토리 함수 구현

---

## Phase 3 완료 체크리스트

- [ ] base.py - 워커 베이스 클래스
- [ ] rag_worker.py - RAG 워커 (Milvus 연동)
- [ ] web_worker.py - 웹 서치 워커 (Tavily 연동)
- [ ] llm_worker.py - LLM Direct 워커
- [ ] factory.py - 워커 팩토리
- [ ] __init__.py - export 정의

---

## 다음 단계
Phase 3 완료 후 [PHASE-4.md](./PHASE-4.md)로 진행합니다.
