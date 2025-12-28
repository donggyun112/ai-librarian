# 01. Supervisor 심층 분석

> LangGraph ReAct Agent의 핵심 - 모든 질의응답 처리의 중심

---

## 1. 파일 정보

- **경로**: `src/supervisor/supervisor.py`
- **라인 수**: 334줄
- **의존성**: LangGraph, LangChain, Adapters, Memory, Tools

---

## 2. 모듈 개요

Supervisor는 이 프로젝트의 **핵심 클래스**입니다. LangGraph를 사용하여 ReAct(Reasoning + Acting) 패턴을 구현하며, 사용자 질문을 받아 도구를 호출하고 최종 답변을 생성합니다.

### 핵심 책임
1. LangGraph 워크플로우 구성 및 실행
2. LLM과 도구 간의 상호작용 관리
3. 스트리밍/비스트리밍 응답 처리
4. 세션 기반 대화 히스토리 관리

---

## 3. 코드 구조

### 3.1 임포트 및 상수

```python
# 라인 1-49

# 타입 힌트
from typing import List, Literal, TypedDict, Annotated, AsyncIterator, Optional

# LangChain 메시지 타입
from langchain_core.messages import (
    HumanMessage,      # 사용자 메시지
    SystemMessage,     # 시스템 프롬프트
    ToolMessage,       # 도구 결과
    AIMessage,         # AI 응답
    BaseMessage        # 베이스 타입
)

# LangGraph 핵심
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages  # 메시지 리듀서
from langgraph.prebuilt import ToolNode           # 도구 실행 노드

# 내부 모듈
from src.schemas.models import SupervisorResponse, StreamEventType, LangGraphEventName
from src.memory import ChatMemory, InMemoryChatMemory
from src.adapters import get_adapter, BaseLLMAdapter
from .prompts import get_system_prompt
from .tools import TOOLS
from config import config
```

### 3.2 상수 정의

```python
# 라인 37-48

# 도구 이름 상수
SEARCH_TOOLS = ["arag_search", "aweb_search"]  # 검색 도구들
THINK_TOOL = "think"                            # 생각 도구

# 기본값
DEFAULT_MAX_TOKENS = 4096  # LLM 최대 출력 토큰
DEFAULT_MAX_STEPS = 10     # LangGraph 최대 반복 횟수

# LangGraph 이벤트 타입 (타입 안전)
EVENT_CHAT_MODEL_STREAM: LangGraphEventName = "on_chat_model_stream"
EVENT_TOOL_START: LangGraphEventName = "on_tool_start"
EVENT_TOOL_END: LangGraphEventName = "on_tool_end"
```

**설계 의도:**
- 매직 스트링 방지를 위해 상수로 추출
- `LangGraphEventName` Literal 타입으로 IDE 자동완성 지원

---

## 4. AgentState 정의

```python
# 라인 54-56

class AgentState(TypedDict):
    """LangGraph Agent 상태"""
    messages: Annotated[List[BaseMessage], add_messages]
```

### 동작 원리

1. **TypedDict**: LangGraph 상태는 딕셔너리 형태
2. **Annotated**: 메타데이터 추가 (리듀서 지정)
3. **add_messages**: 메시지 병합 리듀서

```python
# add_messages 리듀서 동작 예시
state1 = {"messages": [HumanMessage("안녕")]}
state2 = {"messages": [AIMessage("안녕하세요!")]}

# 리듀서가 자동으로 병합
merged = {"messages": [HumanMessage("안녕"), AIMessage("안녕하세요!")]}
```

---

## 5. Supervisor 클래스

### 5.1 생성자

```python
# 라인 62-106

class Supervisor:
    def __init__(
        self,
        model: str = None,           # LLM 모델명 (None이면 config 사용)
        max_steps: int = DEFAULT_MAX_STEPS,      # 최대 반복 횟수
        max_tokens: int = DEFAULT_MAX_TOKENS,    # 최대 출력 토큰
        memory: ChatMemory = None,   # 메모리 백엔드 (DI)
        provider: str = None         # LLM 프로바이더 (None이면 config 사용)
    ):
        self.model = model
        self.max_steps = max_steps
        self.max_tokens = max_tokens

        # 메모리: 주입되지 않으면 기본 InMemory 사용
        self.memory = memory or InMemoryChatMemory()

        # Adapter 초기화: 프로바이더 이름으로 팩토리에서 생성
        provider_name = provider or config.LLM_PROVIDER
        self.adapter: BaseLLMAdapter = get_adapter(provider_name)

        # ToolNode: 모든 프로바이더가 공유
        self.tool_node = ToolNode(TOOLS)

        # Graph 캐시: 첫 호출 시 생성
        self._cached_graph = None
```

### 의존성 주입 포인트

```
┌─────────────────────────────────────────────────────────────┐
│                    Supervisor 생성자                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   memory ─────────────► ChatMemory (인터페이스)              │
│                              │                               │
│                              ├─ InMemoryChatMemory (기본)    │
│                              ├─ SQLChatMemory (확장 가능)    │
│                              └─ RedisChatMemory (확장 가능)  │
│                                                              │
│   provider ─────────────► get_adapter(provider)             │
│                              │                               │
│                              ├─ OpenAIAdapter                │
│                              └─ GeminiAdapter                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 5.2 _build_graph() - 워크플로우 구성

```python
# 라인 107-142

def _build_graph(self) -> StateGraph:
    """
    Graph 구조:
        START → supervisor → (tool_calls?) → tools → supervisor
                        └── (no tools) → END
    """

    # 1. LLM 생성 (Adapter 통해)
    llm = self.adapter.create_llm(
        model=self.model,
        temperature=0.7,
        max_tokens=self.max_tokens
    )

    # 2. 도구 바인딩
    llm_with_tools = llm.bind_tools(TOOLS)

    # 3. supervisor 노드 정의
    async def supervisor_node(state: AgentState) -> dict:
        """Supervisor 노드: LLM 호출"""
        messages = state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # 4. 워크플로우 구성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("tools", self.tool_node)

    # 엣지 연결
    workflow.add_edge(START, "supervisor")      # 시작 → supervisor
    workflow.add_conditional_edges(              # supervisor → 분기
        "supervisor",
        self._should_continue,
        {"continue": "tools", "end": END}
    )
    workflow.add_edge("tools", "supervisor")    # tools → supervisor

    return workflow.compile()
```

### 그래프 시각화

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LangGraph Workflow                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│         ┌───────┐                                                   │
│         │ START │                                                   │
│         └───┬───┘                                                   │
│             │                                                        │
│             │ add_edge(START, "supervisor")                         │
│             ▼                                                        │
│    ┌────────────────────────────────────────────────────────────┐   │
│    │                    supervisor 노드                          │   │
│    │                                                             │   │
│    │   async def supervisor_node(state):                        │   │
│    │       messages = state["messages"]                         │   │
│    │       response = await llm_with_tools.ainvoke(messages)    │   │
│    │       return {"messages": [response]}                      │   │
│    │                                                             │   │
│    │   → LLM이 메시지를 분석하고 응답 생성                       │   │
│    │   → tool_calls가 있으면 도구 호출 정보 포함                 │   │
│    └────────────────────────────────────────────────────────────┘   │
│             │                                                        │
│             │ add_conditional_edges("supervisor", _should_continue) │
│             ▼                                                        │
│    ┌────────────────────┐                                           │
│    │  _should_continue  │                                           │
│    │                    │                                           │
│    │  tool_calls 있음?  │                                           │
│    └────────────────────┘                                           │
│         │           │                                                │
│    Yes  │           │ No                                            │
│         ▼           ▼                                                │
│    ┌─────────┐  ┌───────┐                                           │
│    │  tools  │  │  END  │                                           │
│    │         │  └───────┘                                           │
│    │ToolNode │                                                       │
│    │ 실행    │                                                       │
│    └────┬────┘                                                       │
│         │                                                            │
│         │ add_edge("tools", "supervisor")                           │
│         │                                                            │
│         └──────────────────────────┐                                │
│                                    │                                 │
│                     supervisor로 복귀 (반복)                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 5.3 _should_continue() - 분기 로직

```python
# 라인 150-155

def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
    """도구 호출 여부에 따라 분기"""
    last_message = state["messages"][-1]

    # AIMessage에 tool_calls가 있으면 도구 실행으로
    if last_message.tool_calls:
        return "continue"

    # 없으면 종료
    return "end"
```

### tool_calls 구조 예시

```python
# LLM이 도구를 호출하려 할 때 AIMessage 구조
AIMessage(
    content="",  # 보통 빈 문자열
    tool_calls=[
        {
            "id": "call_abc123",
            "name": "think",
            "args": {"thought": "최신 정보가 필요하므로 웹 검색을 해야겠다"}
        },
        {
            "id": "call_def456",
            "name": "aweb_search",
            "args": {"query": "2024 AI trends"}
        }
    ]
)
```

---

### 5.4 _build_messages() - 메시지 구성

```python
# 라인 160-166

def _build_messages(self, session_id: str, question: str) -> List[BaseMessage]:
    """시스템 프롬프트 + 히스토리 + 새 질문으로 메시지 구성"""

    # 1. 시스템 프롬프트 (도구 정보 동적 주입)
    messages = [SystemMessage(content=get_system_prompt(tools=TOOLS))]

    # 2. 이전 대화 히스토리
    messages.extend(self.memory.get_messages(session_id))

    # 3. 현재 질문
    messages.append(HumanMessage(content=question))

    return messages
```

### 메시지 구성 예시

```python
# session_id="user-123"에 이미 대화가 있을 때

messages = [
    # 1. 시스템 프롬프트
    SystemMessage(content="""
        You are AI Librarian...
        Available tools:
        - think: Record your reasoning process
        - arag_search: Search internal documents
        - aweb_search: Search the web
        ...
    """),

    # 2. 이전 대화 (memory에서 로드)
    HumanMessage(content="LangChain이 뭐야?"),
    AIMessage(content="LangChain은 LLM 애플리케이션 개발 프레임워크입니다..."),

    # 3. 현재 질문
    HumanMessage(content="LangGraph는 뭐가 다른데?")
]
```

---

### 5.5 process() - 비스트리밍 처리

```python
# 라인 179-223

async def process(
    self,
    question: str,
    session_id: Optional[str] = None
) -> SupervisorResponse:
    """질문 처리 (Non-streaming)"""

    # 1. 메시지 구성
    if session_id:
        messages = self._build_messages(session_id, question)
    else:
        # 세션 없으면 히스토리 없이 처리
        messages = [
            SystemMessage(content=get_system_prompt(tools=TOOLS)),
            HumanMessage(content=question)
        ]

    # 2. 그래프 실행
    final_state = await self._get_graph().ainvoke(
        {"messages": messages},
        config={"recursion_limit": self.max_steps * 2}  # 안전 마진
    )

    # 3. 결과 추출
    result_messages = final_state["messages"]
    last_message = result_messages[-1]

    # 4. 응답 정규화 (Adapter 통해)
    if isinstance(last_message, AIMessage):
        normalized = self.adapter.normalize_chunk(last_message)
        answer = normalized.text
    else:
        answer = ""

    # 5. 히스토리에 저장
    if session_id:
        self._save_to_history(session_id, question, answer)

    # 6. 응답 반환
    return SupervisorResponse(
        answer=answer,
        sources=self._extract_sources(result_messages),
        execution_log=self._parse_execution_log(result_messages),
        total_confidence=1.0  # TODO: 실제 신뢰도 계산
    )
```

### 실행 흐름 다이어그램

```
process("LangGraph란?", "session-123")
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. _build_messages()                                        │
│    → [SystemMessage, HumanMessage("이전질문"),              │
│       AIMessage("이전답변"), HumanMessage("LangGraph란?")]  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. graph.ainvoke()                                          │
│                                                             │
│    Round 1:                                                 │
│    ├─ supervisor: LLM 호출                                  │
│    │   → AIMessage(tool_calls=[think, arag_search])        │
│    └─ tools: think 실행, arag_search 실행                   │
│                                                             │
│    Round 2:                                                 │
│    ├─ supervisor: LLM 호출 (검색 결과 포함)                 │
│    │   → AIMessage(content="LangGraph는...")               │
│    └─ _should_continue → "end" (tool_calls 없음)           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 결과 처리                                                 │
│    ├─ adapter.normalize_chunk() → 응답 텍스트 추출          │
│    ├─ _extract_sources() → ["think", "arag_search"]        │
│    └─ _parse_execution_log() → 실행 로그                    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. memory.save_conversation()                               │
│    → 질문과 답변을 히스토리에 저장                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
SupervisorResponse(
    answer="LangGraph는 LangChain의 상태 기반 워크플로우...",
    sources=["think", "arag_search"],
    execution_log=[...],
    total_confidence=1.0
)
```

---

### 5.6 process_stream() - 스트리밍 처리

```python
# 라인 228-306

async def process_stream(
    self,
    question: str,
    session_id: Optional[str] = None
) -> AsyncIterator[dict]:
    """스트리밍 처리 - 토큰 단위 실시간 출력"""

    # 메시지 구성 (process와 동일)
    if session_id:
        messages = self._build_messages(session_id, question)
    else:
        messages = [
            SystemMessage(content=get_system_prompt(tools=TOOLS)),
            HumanMessage(content=question)
        ]

    # 답변 수집용 (히스토리 저장을 위해)
    collected_answer = []

    # astream_events로 이벤트 스트리밍
    async for event in self._get_graph().astream_events(
        {"messages": messages},
        config={"recursion_limit": self.max_steps * 2},
        version="v2"  # 최신 이벤트 형식
    ):
        event_type = event["event"]
        data = event.get("data", {})

        # 1. LLM 토큰 스트리밍 (최종 답변)
        if event_type == EVENT_CHAT_MODEL_STREAM:
            chunk = data.get("chunk")
            if chunk and chunk.content:
                # Adapter로 청크 정규화 (OpenAI: str, Gemini: list)
                normalized = self.adapter.normalize_chunk(chunk)
                if normalized.text:
                    collected_answer.append(normalized.text)
                    yield {"type": StreamEventType.TOKEN, "content": normalized.text}

        # 2. 도구 호출 시작
        elif event_type == EVENT_TOOL_START:
            tool_name = event.get("name", "")
            tool_input = data.get("input", {})

            # think 도구 → 생각 표시
            if tool_name == THINK_TOOL:
                thought = tool_input.get("thought", "")
                yield {"type": StreamEventType.THINK, "content": thought}

            # 검색 도구 → 액션 표시
            elif tool_name in SEARCH_TOOLS:
                yield {
                    "type": StreamEventType.ACT,
                    "tool": tool_name,
                    "args": tool_input
                }

        # 3. 도구 결과 반환 (검색 도구만)
        elif event_type == EVENT_TOOL_END:
            tool_name = event.get("name", "")
            if tool_name in SEARCH_TOOLS:
                yield {
                    "type": StreamEventType.OBSERVE,
                    "content": str(data.get("output", ""))
                }

    # 스트리밍 완료 후 히스토리에 저장
    if session_id and collected_answer:
        full_answer = "".join(collected_answer)
        self._save_to_history(session_id, question, full_answer)
```

### 스트리밍 이벤트 흐름

```
process_stream("최신 AI 트렌드", "session-123")
    │
    ├──▶ astream_events() 시작
    │
    │    ┌─────────────────────────────────────────────────────┐
    │    │ Event: on_tool_start                                │
    │    │ name: "think"                                       │
    │    │ input: {"thought": "최신 정보 필요, 웹 검색 수행"}   │
    │    └─────────────────────────────────────────────────────┘
    │         │
    │         └──▶ yield {"type": "think", "content": "..."}
    │
    │    ┌─────────────────────────────────────────────────────┐
    │    │ Event: on_tool_start                                │
    │    │ name: "aweb_search"                                 │
    │    │ input: {"query": "2024 AI trends"}                  │
    │    └─────────────────────────────────────────────────────┘
    │         │
    │         └──▶ yield {"type": "act", "tool": "aweb_search", "args": {...}}
    │
    │    ┌─────────────────────────────────────────────────────┐
    │    │ Event: on_tool_end                                  │
    │    │ name: "aweb_search"                                 │
    │    │ output: "[웹 검색 결과]..."                          │
    │    └─────────────────────────────────────────────────────┘
    │         │
    │         └──▶ yield {"type": "observe", "content": "[웹 검색 결과]..."}
    │
    │    ┌─────────────────────────────────────────────────────┐
    │    │ Event: on_chat_model_stream                         │
    │    │ chunk: AIMessageChunk(content="최")                 │
    │    └─────────────────────────────────────────────────────┘
    │         │
    │         └──▶ yield {"type": "token", "content": "최"}
    │
    │    ┌─────────────────────────────────────────────────────┐
    │    │ Event: on_chat_model_stream                         │
    │    │ chunk: AIMessageChunk(content="근")                 │
    │    └─────────────────────────────────────────────────────┘
    │         │
    │         └──▶ yield {"type": "token", "content": "근"}
    │
    │    ... (토큰 계속)
    │
    └──▶ 스트림 완료
         │
         └──▶ memory.save_conversation("session-123", question, full_answer)
```

---

### 5.7 유틸리티 메서드

```python
# 라인 310-333

def _extract_sources(self, messages: List[BaseMessage]) -> List[str]:
    """사용된 도구 목록 추출"""
    sources = set()
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tool_call in msg.tool_calls:
                sources.add(tool_call['name'])
    return list(sources)

def _parse_execution_log(self, messages: List[BaseMessage]) -> List[str]:
    """실행 로그 추출"""
    log = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            if msg.content:
                # Adapter로 정규화하여 로그 추출
                normalized = self.adapter.normalize_chunk(msg)
                log.append(f"Response: {normalized.text[:100]}...")
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    log.append(f"Tool: {tc['name']}({tc['args']})")
        elif isinstance(msg, ToolMessage):
            log.append(f"Result: {len(str(msg.content))} chars")
    return log
```

---

## 6. 주요 이슈 및 개선점

### 6.1 Critical Issues

#### Issue 1: 타입 힌트 불일치 (라인 86)
```python
# 현재
model: str = None

# 수정
model: Optional[str] = None
```

#### Issue 2: 빈 메시지 리스트 처리 (라인 152)
```python
# 현재 - IndexError 가능
last_message = state["messages"][-1]

# 수정
def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
    messages = state.get("messages", [])
    if not messages:
        return "end"
    last_message = messages[-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue"
    return "end"
```

### 6.2 Medium Issues

#### Issue 3: 예외 처리 없음 (라인 121-125)
```python
# 현재
async def supervisor_node(state: AgentState) -> dict:
    messages = state["messages"]
    response = await llm_with_tools.ainvoke(messages)  # 예외 발생 가능
    return {"messages": [response]}

# 수정
async def supervisor_node(state: AgentState) -> dict:
    messages = state["messages"]
    try:
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        # 에러 메시지를 AIMessage로 반환
        error_msg = AIMessage(content=f"처리 중 오류가 발생했습니다: {str(e)}")
        return {"messages": [error_msg]}
```

#### Issue 4: 고정된 신뢰도 값 (라인 222)
```python
# 현재
total_confidence=1.0

# 개선: 워커 결과에서 신뢰도 계산
def _calculate_confidence(self, messages: List[BaseMessage]) -> float:
    confidences = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            # ToolMessage에서 신뢰도 추출 (파싱 필요)
            pass
    return sum(confidences) / len(confidences) if confidences else 0.5
```

### 6.3 Low Issues

#### Issue 5: 매직 넘버 (라인 327)
```python
# 현재
log.append(f"Response: {normalized.text[:100]}...")

# 수정
LOG_TRUNCATE_LENGTH = 100
log.append(f"Response: {normalized.text[:LOG_TRUNCATE_LENGTH]}...")
```

---

## 7. 테스트 포인트

```python
# tests/test_supervisor.py에서 확인해야 할 케이스

1. 기본 질문 처리
   - process() 정상 동작
   - 도구 없이 직접 답변하는 경우

2. 도구 호출 시나리오
   - think + arag_search 조합
   - think + aweb_search 조합
   - 다중 도구 호출

3. 세션 관리
   - session_id 있을 때 히스토리 로드
   - session_id 없을 때 히스토리 없이 처리
   - 대화 저장 확인

4. 스트리밍
   - process_stream() 이벤트 순서
   - 토큰 수집 및 저장

5. 에러 케이스
   - LLM 호출 실패
   - 도구 실행 실패
   - 빈 메시지 리스트

6. Adapter 교체
   - OpenAI Adapter로 동작
   - Gemini Adapter로 동작
```

---

## 8. 요약

| 항목 | 내용 |
|------|------|
| **책임** | LangGraph ReAct Agent 실행, 도구 호출 관리, 응답 생성 |
| **패턴** | Dependency Injection (memory, adapter) |
| **핵심 메서드** | `process()`, `process_stream()`, `_build_graph()` |
| **주요 이슈** | 타입 힌트, 빈 리스트 처리, 예외 처리 |
| **테스트 커버리지** | 통합 테스트 필요 |

---

*다음: [02-adapters.md](./02-adapters.md) - Adapter 패턴 심층 분석*
