# AI Librarian - 슈퍼바이저 패턴 아키텍처 설계

## 개요

기존의 복잡한 다중 그래프 구조를 제거하고, 단일 슈퍼바이저가 모든 의사결정을 담당하는 단순하고 강력한 아키텍처로 재설계합니다.

## 핵심 원칙

1. **단일 책임**: 슈퍼바이저만 의사결정, 워커는 실행만
2. **단순함**: 최소한의 파일과 클래스로 구성
3. **확장성**: 새로운 워커 추가가 쉬워야 함
4. **투명성**: 슈퍼바이저의 모든 판단 과정이 로깅됨

---

## 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                      USER QUERY                             │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     SUPERVISOR                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. 질문 분석 (의도, 복잡도, 시의성)                    │   │
│  │ 2. 전략 수립 (단일/다중 쿼리, 워커 선택)               │   │
│  │ 3. 쿼리 정제 (검색 최적화된 쿼리 생성)                 │   │
│  │ 4. 워커 실행 지시                                     │   │
│  │ 5. 결과 평가 및 재시도 판단                           │   │
│  │ 6. 최종 답변 생성                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │   RAG    │    │   Web    │    │   LLM    │
    │  Worker  │    │  Search  │    │  Direct  │
    │          │    │  Worker  │    │  Worker  │
    └──────────┘    └──────────┘    └──────────┘
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Milvus  │    │  Tavily  │    │  OpenAI  │
    │ VectorDB │    │   API    │    │   API    │
    └──────────┘    └──────────┘    └──────────┘
```

---

## 슈퍼바이저 상세 플로우

```
┌────────────────────────────────────────────────────────────────┐
│                    SUPERVISOR FLOW                             │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  [ANALYZE] ─────────────────────────────────────────────────► │
│     │                                                          │
│     ├─ 질문 유형 파악 (사실/의견/최신정보/복합)                   │
│     ├─ 시의성 판단 (최근 정보 필요 여부)                         │
│     └─ 복잡도 평가 (단순/복합 질문)                              │
│                                                                │
│  [PLAN] ────────────────────────────────────────────────────► │
│     │                                                          │
│     ├─ 워커 선택 (RAG / WebSearch / LLM / 조합)                 │
│     ├─ 쿼리 정제 여부 결정                                      │
│     │    ├─ 다중 쿼리 필요시: 세부 쿼리 생성                     │
│     │    └─ 단일 쿼리: 검색 최적화                              │
│     └─ 실행 순서 결정 (순차 / 병렬)                              │
│                                                                │
│  [EXECUTE] ─────────────────────────────────────────────────► │
│     │                                                          │
│     └─ 선택된 워커에게 정제된 쿼리 전달                          │
│                                                                │
│  [EVALUATE] ────────────────────────────────────────────────► │
│     │                                                          │
│     ├─ 결과 품질 평가                                          │
│     ├─ 충분한가? ──► YES ──► [SYNTHESIZE]                      │
│     └─ 충분한가? ──► NO  ──► [PLAN] (다른 전략 시도)             │
│                                                                │
│  [SYNTHESIZE] ──────────────────────────────────────────────► │
│     │                                                          │
│     └─ 수집된 정보로 최종 답변 생성                              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 디렉토리 구조

```
poc/
├── src/
│   ├── supervisor/
│   │   ├── __init__.py
│   │   └── supervisor.py        # 슈퍼바이저 메인 로직
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── base.py              # Worker 베이스 클래스
│   │   ├── rag_worker.py        # RAG (벡터 검색) 워커
│   │   ├── web_worker.py        # 웹 서치 워커
│   │   └── llm_worker.py        # LLM 직접 질의 워커
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── vector_store.py      # Milvus 연동 (기존 유지)
│   │   └── embedding.py         # 임베딩 서비스 (기존 유지)
│   │
│   └── schemas/
│       ├── __init__.py
│       └── models.py            # Pydantic 모델 정의
│
├── app.py                       # Streamlit UI (단순화)
├── config.py                    # 설정 관리
├── pyproject.toml
└── .env
```

---

## 핵심 스키마

```python
# schemas/models.py

class QueryAnalysis(BaseModel):
    """슈퍼바이저의 질문 분석 결과"""
    intent: str                    # 질문 의도
    requires_recent_info: bool     # 최신 정보 필요 여부
    complexity: str                # simple / complex
    suggested_workers: List[str]   # 추천 워커 목록

class ExecutionPlan(BaseModel):
    """슈퍼바이저의 실행 계획"""
    strategy: str                  # single / multi_query / parallel
    workers: List[str]             # 실행할 워커
    refined_queries: List[str]     # 정제된 쿼리들
    reasoning: str                 # 판단 근거

class WorkerResult(BaseModel):
    """워커 실행 결과"""
    worker_name: str
    query: str
    result: str
    confidence: float
    sources: List[str]

class SupervisorResponse(BaseModel):
    """최종 응답"""
    answer: str
    sources: List[str]
    execution_log: List[str]       # 판단 과정 로그
    workers_used: List[str]
```

---

## 슈퍼바이저 핵심 로직

```python
class Supervisor:
    """모든 의사결정을 담당하는 슈퍼바이저"""

    def __init__(self, llm, workers: Dict[str, BaseWorker]):
        self.llm = llm
        self.workers = workers
        self.max_retries = 2

    async def process(self, question: str) -> SupervisorResponse:
        # 1. 질문 분석
        analysis = await self._analyze(question)

        # 2. 실행 계획 수립
        plan = await self._plan(question, analysis)

        # 3. 워커 실행 및 결과 수집
        results = await self._execute(plan)

        # 4. 결과 평가 (불충분시 재시도)
        for _ in range(self.max_retries):
            if self._is_sufficient(results):
                break
            plan = await self._replan(question, analysis, results)
            results = await self._execute(plan)

        # 5. 최종 답변 생성
        return await self._synthesize(question, results)
```

---

## 워커 인터페이스

```python
class BaseWorker(ABC):
    """모든 워커의 베이스 클래스"""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def execute(self, query: str) -> WorkerResult:
        pass
```

각 워커는 단순히 쿼리를 받아 결과를 반환하는 역할만 수행합니다.
모든 판단과 결정은 슈퍼바이저가 담당합니다.

---

## 다음 단계

상세 구현 계획은 다음 문서들을 참조하세요:

1. [PHASE-1.md](./PHASE-1.md) - 프로젝트 구조 및 기반 설정
2. [PHASE-2.md](./PHASE-2.md) - 슈퍼바이저 코어 구현
3. [PHASE-3.md](./PHASE-3.md) - 워커 에이전트 구현
4. [PHASE-4.md](./PHASE-4.md) - Streamlit UI 구현
