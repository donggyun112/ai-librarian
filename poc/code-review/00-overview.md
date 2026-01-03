# 00. 프로젝트 전체 개요

> AI Librarian v2.0 - LangGraph ReAct Agent 기반 질의응답 시스템

---

## 1. 프로젝트 목적

사용자 질문에 대해 **웹 검색**을 활용하여 최적의 답변을 제공하는 AI 에이전트 시스템입니다.

### 핵심 가치
- **ReAct 패턴**: 생각(Think) → 행동(Act) → 관찰(Observe) 사이클로 추론 과정 투명화
- **웹 검색**: DuckDuckGo 기반 실시간 웹 검색 + LLM 지식 활용
- **실시간 스트리밍**: SSE로 토큰 단위 응답, 사용자 경험 개선

---

## 2. 기술 스택

```
┌─────────────────────────────────────────────────────────────┐
│                        기술 스택                              │
├─────────────────────────────────────────────────────────────┤
│  Language        │ Python 3.12+                             │
│  AI Framework    │ LangChain 0.3.x, LangGraph 0.2.x         │
│  LLM             │ OpenAI GPT-4o, Google Gemini 2.0 Flash   │
│  Web Search      │ DuckDuckGo (ddgs)                        │
│  Web Framework   │ FastAPI 0.127+                           │
│  Package Manager │ uv                                       │
│  Deployment      │ Docker, Google Cloud Run                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 디렉토리 구조

```
poc/
├── src/                          # 소스 코드
│   ├── adapters/                 # LLM 프로바이더 추상화 (Adapter 패턴)
│   │   ├── __init__.py          # 레지스트리 및 팩토리
│   │   ├── base.py              # BaseLLMAdapter 추상 클래스
│   │   ├── openai.py            # OpenAI 어댑터
│   │   └── gemini.py            # Gemini 어댑터
│   │
│   ├── api/                      # FastAPI 레이어
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI 앱 설정, CORS, 라우팅
│   │   ├── routes.py            # API 엔드포인트 정의
│   │   └── schemas.py           # 요청/응답 Pydantic 모델
│   │
│   ├── memory/                   # 대화 히스토리 저장소 (Strategy 패턴)
│   │   ├── __init__.py
│   │   ├── base.py              # ChatMemory 추상 인터페이스
│   │   └── in_memory.py         # In-Memory 구현체
│   │
│   ├── schemas/                  # 공용 데이터 모델
│   │   ├── __init__.py
│   │   └── models.py            # WorkerResult, SupervisorResponse 등
│   │
│   ├── supervisor/               # LangGraph 에이전트 (핵심)
│   │   ├── __init__.py
│   │   ├── supervisor.py        # Supervisor 클래스 (ReAct Agent)
│   │   ├── prompts.py           # 시스템 프롬프트 템플릿
│   │   └── tools.py             # LangChain Tool 정의
│   │
│   └── workers/                  # 검색 워커 (Strategy 패턴)
│       ├── __init__.py
│       ├── base.py              # BaseWorker 추상 클래스
│       ├── factory.py           # 워커 팩토리
│       └── web_worker.py        # 웹 검색
│
├── tests/                        # 테스트 코드
│   ├── test_supervisor.py       # Supervisor 통합 테스트
│   ├── test_tools.py            # 도구 단위 테스트
│   ├── test_memory.py           # 메모리 테스트
│   ├── test_prompts.py          # 프롬프트 테스트
│   └── test_eval.py             # 평가 테스트
│
├── static/                       # 프론트엔드
│   └── index.html               # SPA 웹 UI
│
├── config.py                     # 환경 변수 설정
├── main.py                       # 서버 엔트리포인트
├── pyproject.toml               # 프로젝트 설정
├── Dockerfile                   # 컨테이너 빌드
└── deploy.sh                    # GCP 배포 스크립트
```

---

## 4. 시스템 아키텍처

### 4.1 전체 흐름도

```
┌──────────────────────────────────────────────────────────────────────┐
│                              Client                                   │
│                         (Browser / curl)                             │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP POST /api/chat/stream
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                           FastAPI Server                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                        routes.py                                │  │
│  │   • /api/health         → 헬스 체크                            │  │
│  │   • /api/chat           → 비스트리밍 채팅                       │  │
│  │   • /api/chat/stream    → SSE 스트리밍 채팅                     │  │
│  │   • /api/sessions       → 세션 관리                            │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ supervisor.process_stream()
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Supervisor (LangGraph)                        │
│                                                                       │
│   ┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐    │
│   │   Adapter   │◄──►│   StateGraph    │◄──►│    ToolNode      │    │
│   │ (OpenAI/    │    │                 │    │                  │    │
│   │  Gemini)    │    │  supervisor ────┼───►│  • think         │    │
│   │             │    │      │          │    │  • arag_search   │    │
│   │  create_llm │    │      ▼          │    │  • aweb_search   │    │
│   │  normalize  │    │   tools ◄───────┼────│                  │    │
│   └─────────────┘    │      │          │    └──────────────────┘    │
│                      │      ▼          │              │              │
│   ┌─────────────┐    │    END          │              │              │
│   │   Memory    │◄───┤                 │              │              │
│   │ (In-Memory) │    └─────────────────┘              │              │
│   └─────────────┘                                     │              │
└───────────────────────────────────────────────────────┼──────────────┘
                                                        │
                              ┌─────────────────────────┴─────────────────────────┐
                              │                                                     │
                              ▼                                                     ▼
                    ┌──────────────────┐                              ┌──────────────────┐
                    │      think       │                              │   WebWorker      │
                    │                  │                              │                  │
                    │ 생각 과정 기록    │                              │ • DuckDuckGo     │
                    │ (추론 투명화)     │                              │ • 웹 검색        │
                    └──────────────────┘                              └──────────────────┘
                                                                                │
                                                                                ▼
                                                                    ┌──────────────────┐
                                                                    │   DuckDuckGo     │
                                                                    │      API         │
                                                                    └──────────────────┘
```

### 4.2 LangGraph 워크플로우

```
┌───────┐
│ START │
└───┬───┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│                        supervisor 노드                         │
│                                                                │
│   messages = state["messages"]                                 │
│   response = await llm_with_tools.ainvoke(messages)           │
│   return {"messages": [response]}                             │
└───────────────────────────────────────────────────────────────┘
    │
    │ _should_continue()
    │
    ▼
┌─────────────────────┐
│   tool_calls 있음?   │
└─────────────────────┘
    │           │
    │ Yes       │ No
    ▼           ▼
┌────────┐  ┌───────┐
│ tools  │  │  END  │
└────┬───┘  └───────┘
     │
     │ ToolNode 실행
     │ (think / arag_search / aweb_search)
     │
     └──────────────────┐
                        │
                        ▼
              supervisor 노드로 복귀
              (반복)
```

---

## 5. 핵심 데이터 흐름

### 5.1 비스트리밍 요청 흐름

```
1. Client → POST /api/chat {"message": "LangGraph란?", "session_id": "abc123"}
       │
2.     └→ routes.py: chat()
              │
3.            └→ supervisor.process(question, session_id)
                     │
4.                   ├→ _build_messages(): 시스템 프롬프트 + 히스토리 + 질문
                     │
5.                   └→ graph.ainvoke(): LangGraph 실행
                            │
6.                          ├→ supervisor 노드: LLM 호출
                            │     │
7.                          │     └→ tool_calls 발생 (think, aweb_search 등)
                            │
8.                          └→ tools 노드: 도구 실행
                                  │
9.                                └→ 반복... → 최종 AIMessage
                                        │
10.                                     └→ adapter.normalize_chunk(): 응답 정규화
                                              │
11.                                           └→ memory.save_conversation(): 히스토리 저장
                                                    │
12.                                                 └→ SupervisorResponse 반환
                                                          │
13. Client ← {"answer": "...", "sources": [...], "session_id": "abc123"}
```

### 5.2 스트리밍 요청 흐름

```
1. Client → POST /api/chat/stream {"message": "최신 AI 트렌드"}
       │
2.     └→ routes.py: chat_stream()
              │
3.            └→ EventSourceResponse(event_generator())
                     │
4.                   └→ supervisor.process_stream()
                            │
5.                          └→ graph.astream_events()
                                  │
    ┌─────────────────────────────┴─────────────────────────────┐
    │                                                            │
    ▼                                                            ▼
┌─────────────────────┐                              ┌─────────────────────┐
│ on_chat_model_stream│                              │    on_tool_start    │
│                     │                              │                     │
│ → TOKEN 이벤트      │                              │ think → THINK 이벤트│
│ → 토큰 수집         │                              │ search→ ACT 이벤트  │
└─────────────────────┘                              └─────────────────────┘
                                                              │
                                                              ▼
                                                     ┌─────────────────────┐
                                                     │    on_tool_end      │
                                                     │                     │
                                                     │ → OBSERVE 이벤트    │
                                                     └─────────────────────┘
    │
    └→ 스트림 완료 후:
         • collected_answer 합치기
         • memory.save_conversation()
         • done 이벤트 전송

6. Client ← SSE 이벤트들:
     event: think
     data: {"content": "최신 정보가 필요하므로 웹 검색..."}

     event: act
     data: {"tool": "aweb_search", "args": {"query": "2024 AI trends"}}

     event: observe
     data: {"content": "[웹 검색 결과]..."}

     event: token
     data: {"content": "최근"}

     event: token
     data: {"content": " AI"}

     event: token
     data: {"content": " 트렌드"}
     ...

     event: done
     data: {"session_id": "abc123"}
```

---

## 6. 설계 패턴

### 6.1 사용된 패턴 요약

| 패턴 | 위치 | 목적 |
|------|------|------|
| **Adapter** | `src/adapters/` | LLM 프로바이더 차이 캡슐화 |
| **Strategy** | `src/workers/` | 검색 방식 교체 가능 |
| **Factory** | `src/adapters/__init__.py` | 어댑터 인스턴스 생성 |
| **Template Method** | `src/supervisor/prompts.py` | 동적 프롬프트 생성 |
| **Repository** | `src/memory/` | 데이터 저장소 추상화 |
| **Dependency Injection** | `Supervisor.__init__` | 메모리 백엔드 교체 |

### 6.2 패턴 적용 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Adapter Pattern                              │
│                                                                      │
│   ┌──────────────────┐                                              │
│   │ BaseLLMAdapter   │◄────────────────────────────────┐            │
│   │ (Abstract)       │                                  │            │
│   │                  │                                  │            │
│   │ + create_llm()   │                                  │            │
│   │ + normalize()    │                                  │            │
│   └────────┬─────────┘                                  │            │
│            │                                            │            │
│   ┌────────┴────────┬───────────────────┐              │            │
│   ▼                 ▼                   ▼              │            │
│ ┌────────────┐ ┌────────────┐    ┌────────────┐       │            │
│ │OpenAIAdapter│ │GeminiAdapter│   │ (Future)  │       │            │
│ │            │ │            │    │Anthropic  │       │            │
│ │chunk: str  │ │chunk: list │    │           │       │            │
│ └────────────┘ └────────────┘    └────────────┘       │            │
│                                                        │            │
│                        ┌─────────────┐                 │            │
│                        │  Supervisor │─────────────────┘            │
│                        │             │                               │
│                        │ adapter ────┤ (의존성 주입)                  │
│                        └─────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        Strategy Pattern                              │
│                                                                      │
│   ┌──────────────────┐                                              │
│   │   BaseWorker     │◄────────────────────────────────┐            │
│   │   (Abstract)     │                                  │            │
│   │                  │                                  │            │
│   │ + execute()      │                                  │            │
│   │ + worker_type    │                                  │            │
│   └────────┬─────────┘                                  │            │
│            │                                            │            │
│   ┌────────┴────────┬───────────────────┐              │            │
│   ▼                 ▼                   ▼              │            │
│ ┌────────────┐ ┌────────────┐    ┌────────────┐       │            │
│ │WebWorker   │ │ (Future)   │    │ (Future)   │       │            │
│ │            │ │ RAGWorker  │    │ SQLWorker  │       │            │
│ │ DuckDuckGo │ │            │    │            │       │            │
│ └────────────┘ └────────────┘    └────────────┘       │            │
│                                                        │            │
│                        ┌─────────────┐                 │            │
│                        │   tools.py  │─────────────────┘            │
│                        │             │                               │
│                        │ aweb_search │                               │
│                        └─────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. 의존성 그래프

```
                              ┌─────────────┐
                              │   main.py   │
                              └──────┬──────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │  src/api/   │
                              │   app.py    │
                              └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
             ┌───────────┐    ┌───────────┐    ┌───────────┐
             │ routes.py │    │ schemas.py│    │ static/   │
             └─────┬─────┘    └───────────┘    └───────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
┌─────────────┐ ┌──────┐ ┌────────────┐
│ supervisor/ │ │memory│ │  config.py │
│ supervisor  │ │      │ └────────────┘
└──────┬──────┘ └──────┘
       │
       ├─────────────────────────────┐
       │                             │
       ▼                             ▼
┌─────────────┐               ┌─────────────┐
│  adapters/  │               │   tools.py  │
│  get_adapter│               │             │
└──────┬──────┘               └──────┬──────┘
       │                             │
       │                             ▼
       │                      ┌─────────────┐
       │                      │  workers/   │
       │                      │ rag_worker  │
       │                      │ web_worker  │
       │                      └──────┬──────┘
       │                             │
       ▼                             ▼
┌─────────────────────────────────────────────┐
│              External Services               │
│                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │
│  │ OpenAI  │  │ Gemini  │  │ Milvus/DDG  │  │
│  │  API    │  │   API   │  │             │  │
│  └─────────┘  └─────────┘  └─────────────┘  │
└─────────────────────────────────────────────┘
```

---

## 8. 핵심 클래스 관계도

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              Class Diagram                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           Supervisor                                 │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ - model: str                                                        │   │
│  │ - max_steps: int                                                    │   │
│  │ - max_tokens: int                                                   │   │
│  │ - memory: ChatMemory                   ◄──── DI (Strategy)          │   │
│  │ - adapter: BaseLLMAdapter              ◄──── DI (Adapter)           │   │
│  │ - tool_node: ToolNode                                               │   │
│  │ - _cached_graph: StateGraph                                         │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ + process(question, session_id) → SupervisorResponse                │   │
│  │ + process_stream(question, session_id) → AsyncIterator              │   │
│  │ - _build_graph() → StateGraph                                       │   │
│  │ - _should_continue(state) → "continue" | "end"                      │   │
│  │ - _build_messages(session_id, question) → List[BaseMessage]         │   │
│  │ - _save_to_history(session_id, question, answer)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                          │                    │                             │
│                          │ uses               │ uses                        │
│                          ▼                    ▼                             │
│  ┌──────────────────────────────┐  ┌──────────────────────────────────┐   │
│  │      BaseLLMAdapter          │  │        ChatMemory                 │   │
│  │         (ABC)                │  │          (ABC)                    │   │
│  ├──────────────────────────────┤  ├──────────────────────────────────┤   │
│  │ + create_llm() → BaseChatModel│  │ + get_messages() → List[Message] │   │
│  │ + normalize_chunk() → Norm... │  │ + add_user_message()             │   │
│  │ + provider_name: str          │  │ + add_ai_message()               │   │
│  └──────────────────────────────┘  │ + clear()                         │   │
│         △            △             │ + save_conversation()             │   │
│         │            │             └──────────────────────────────────┘   │
│         │            │                           △                         │
│  ┌──────┴───┐ ┌──────┴───┐              ┌───────┴────────┐                │
│  │OpenAI    │ │Gemini    │              │InMemoryChatMem │                │
│  │Adapter   │ │Adapter   │              │                │                │
│  └──────────┘ └──────────┘              │ _store: dict   │                │
│                                          └────────────────┘                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         BaseWorker (ABC)                             │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ + worker_type: WorkerType (property, abstract)                      │   │
│  │ + execute(query) → WorkerResult (async, abstract)                   │   │
│  │ # _create_result() → WorkerResult (helper)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                          △                    △                             │
│                          │                    │                             │
│               ┌──────────┴─────┐   ┌──────────┴─────┐                      │
│               │   RAGWorker    │   │  WebSearchWorker│                      │
│               ├────────────────┤   ├─────────────────┤                      │
│               │ embeddings     │   │ ddgs            │                      │
│               │ client (Milvus)│   │ max_results     │                      │
│               │ top_k          │   │                 │                      │
│               │ score_threshold│   │                 │                      │
│               └────────────────┘   └─────────────────┘                      │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. 데이터 모델

### 9.1 핵심 Enum/Model

```python
# src/schemas/models.py

class WorkerType(str, Enum):
    """워커 타입"""
    RAG = "rag"
    WEB_SEARCH = "web_search"

class StreamEventType(str, Enum):
    """스트리밍 이벤트 타입"""
    TOKEN = "token"      # LLM 토큰 출력
    THINK = "think"      # think 도구 호출
    ACT = "act"          # 검색 도구 호출
    OBSERVE = "observe"  # 도구 결과 반환

class WorkerResult(BaseModel):
    """워커 실행 결과"""
    worker: WorkerType
    query: str
    content: str
    confidence: float  # 0.0 ~ 1.0
    sources: List[str]
    success: bool
    error: Optional[str]

class SupervisorResponse(BaseModel):
    """최종 응답"""
    answer: str
    sources: List[str]
    execution_log: List[str]
    total_confidence: float
```

### 9.2 API 스키마

```python
# src/api/schemas.py

class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str        # 필수, 최소 1자
    session_id: Optional[str]

class ChatResponse(BaseModel):
    """채팅 응답"""
    answer: str
    sources: List[str]
    session_id: Optional[str]

class SessionInfo(BaseModel):
    """세션 정보"""
    session_id: str
    message_count: int

class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str  # "ok"
    provider: str  # "openai" | "gemini"
```

---

## 10. 환경 설정

### 10.1 config.py 구조

```python
class Config:
    # LLM 프로바이더 선택
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Google Gemini
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Milvus/Zilliz
    MILVUS_HOST = os.getenv("ZILLIZ_HOST")
    MILVUS_TOKEN = os.getenv("ZILLIZ_TOKEN")
    MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "documents")

    # Supervisor 설정
    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.7

    # 프롬프트 설정
    RESPONSE_LANGUAGE = os.getenv("RESPONSE_LANGUAGE", "Korean")
    AGENT_PERSONA = os.getenv("AGENT_PERSONA", "AI Librarian")
    AGENT_DESCRIPTION = os.getenv("AGENT_DESCRIPTION", "...")
```

### 10.2 필수 환경 변수

```bash
# .env 예시

# 필수 (OpenAI 사용 시)
OPENAI_API_KEY=sk-...

# 필수 (RAG 사용 시)
ZILLIZ_HOST=https://xxx.zillizcloud.com
ZILLIZ_TOKEN=...

# 선택
LLM_PROVIDER=openai
OPENAI_CHAT_MODEL=gpt-4o
MILVUS_COLLECTION=documents
RESPONSE_LANGUAGE=Korean
```

---

## 11. 리뷰 문서 구성

다음 문서들에서 각 모듈을 심층 분석합니다:

| 문서 | 내용 |
|------|------|
| [01-supervisor.md](./01-supervisor.md) | Supervisor 클래스 심층 분석 |
| [02-adapters.md](./02-adapters.md) | Adapter 패턴 및 LLM 추상화 |
| [03-workers.md](./03-workers.md) | 검색 워커 (RAG, Web) |
| [04-memory.md](./04-memory.md) | 메모리 시스템 |
| [05-api.md](./05-api.md) | FastAPI 레이어 |
| [06-prompts.md](./06-prompts.md) | 프롬프트 엔지니어링 |
| [07-frontend.md](./07-frontend.md) | 프론트엔드 (index.html) |
| [08-issues.md](./08-issues.md) | 이슈 및 개선사항 종합 |

---

*다음: [01-supervisor.md](./01-supervisor.md) - Supervisor 클래스 심층 분석*
