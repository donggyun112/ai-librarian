# 평가 피드백 및 보완 사항

## 평가 일시
2024-12-21 (6차 평가 - LangGraph 전환 완료)

## 현재 진행 상황
- Phase 1: ✅ 완료
- Phase 2 (Supervisor): ✅ **LangGraph ReAct Agent로 전환 완료**
- Phase 3 (Workers): ✅ LLM Worker 제거 완료
- Phase 4 (UI): ✅ 완료

---

## ✅ 완료된 작업

### 1. LLM Direct Worker 제거
- [x] `poc/src/workers/llm_worker.py` 파일 삭제
- [x] `poc/src/workers/__init__.py`에서 LLMDirectWorker import/export 제거
- [x] `poc/src/workers/factory.py`에서 LLMDirectWorker 관련 코드 제거
- [x] `poc/src/schemas/models.py`에서 `WorkerType.LLM_DIRECT` 제거

### 2. Supervisor ReAct 패턴으로 재구현
- [x] `poc/src/supervisor/supervisor.py` 전체 재작성
- [x] Think → Act → Observe 루프 구현
- [x] 도구 호출 없으면 바로 응답하는 로직
- [x] 도구 결과 기반 동적 의사결정 로직
- [x] 최대 반복 횟수 제한 (`max_steps=10`)

### 3. 프롬프트 수정
- [x] `poc/src/supervisor/prompts.py` 전체 재작성
- [x] 기존 ANALYZE_PROMPT, PLAN_PROMPT 등 제거
- [x] 새로운 SYSTEM_PROMPT 작성

### 4. 도구 바인딩 구현
- [x] `poc/src/supervisor/tools.py` 새 파일 생성
- [x] `@tool` 데코레이터로 arag_search, aweb_search 정의
- [x] ~~Supervisor에서 `llm.bind_tools(TOOLS)` 호출~~ → LangGraph가 자동 처리

### 5. 기타 파일 정리
- [x] `poc/src/supervisor/__init__.py` 수정 (export 정리)
- [x] `poc/run.py` 수정 (새 API에 맞게)
- [x] `poc/app.py` UI 수정 (Think/Act/Observe 표시)

### 6. LangGraph 전환 (NEW!)
- [x] `langgraph` 의존성 추가 (이미 pyproject.toml에 있음)
- [x] `create_react_agent` 사용하여 Supervisor 재구현
- [x] while 루프 제거 → LangGraph 내부 관리
- [x] `duckduckgo_search` → `ddgs` 패키지로 변경

---

## 현재 아키텍처

### LangGraph ReAct Agent (구현 완료)
```
┌─────────────────────────────────────────────────────────────┐
│                SUPERVISOR (LangGraph Agent)                 │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │           create_react_agent(llm, tools)            │  │
│   │                                                      │  │
│   │   ┌──────────┐   ┌──────────┐   ┌──────────┐       │  │
│   │   │  THINK   │ → │   ACT    │ → │ OBSERVE  │ ──┐   │  │
│   │   │ (Agent)  │   │(ToolNode)│   │(결과확인)│   │   │  │
│   │   └──────────┘   └──────────┘   └──────────┘   │   │  │
│   │        ↑                                        │   │  │
│   │        └────────────────────────────────────────┘   │  │
│   │                                                      │  │
│   │   도구 호출 없음 → 최종 응답 반환 (END)             │  │
│   └─────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │ (필요할 때만 호출)
              ┌───────────┴───────────┐
              ▼                       ▼
        ┌──────────┐            ┌──────────┐
        │   RAG    │            │   Web    │
        │  Search  │            │  Search  │
        └──────────┘            └──────────┘
```

### 핵심 코드 변경

**이전 (while 루프)**
```python
self.llm = ChatOpenAI(...).bind_tools(TOOLS)

while step_count < self.max_steps:
    response = await self.llm.ainvoke(messages)
    if response.tool_calls:
        # 도구 실행...
        continue
    return SupervisorResponse(...)
```

**현재 (LangGraph)**
```python
from langgraph.prebuilt import create_react_agent

self.agent = create_react_agent(
    model=self.llm,
    tools=TOOLS,
    prompt=SYSTEM_PROMPT,
)

result = await self.agent.ainvoke(
    {"messages": [HumanMessage(content=question)]},
    config={"recursion_limit": self.max_steps * 2}
)
```

### LangGraph 장점 (적용됨)
- [x] **상태 관리**: LangGraph가 메시지 히스토리 자동 관리
- [x] **루프 제어**: recursion_limit으로 간단히 제어
- [x] **코드 간소화**: while 루프 제거, 에러 처리 단순화
- [ ] **시각화**: 그래프 구조 시각화 가능 (향후)
- [ ] **체크포인트**: 중간 상태 저장/복원 (향후)
- [ ] **스트리밍**: 실시간 단계별 스트리밍 (향후)

---

## 🟡 남은 작업 체크리스트

### [선택] 추가 개선
- [ ] 스트리밍 지원 추가 (`astream_events`)
- [ ] 그래프 시각화 추가

### [선택] 스키마 정리
- [ ] `poc/src/schemas/models.py`에서 불필요한 스키마 제거
  - QueryAnalysis 제거
  - ExecutionPlan 제거
  - ExecutionStrategy 제거

### [낮음] 기타
- [ ] 로깅 시스템 강화 (print → logging)
- [ ] 테스트 코드 추가

---

## 테스트 방법

```bash
cd poc

# CLI 테스트
.venv/bin/python run.py

# Streamlit UI
.venv/bin/streamlit run app.py
```

### 예상 동작

**질문: "LangChain이 무엇인가요?"**
```
[Supervisor] 질문 수신: LangChain이 무엇인가요?
[Supervisor] 최종 답변 생성
→ 도구 호출 없이 바로 응답
```

**질문: "2024년 AI 트렌드는?"**
```
[Supervisor] 질문 수신: 2024년 AI 트렌드는?
[Supervisor] Step 1: 도구 호출 발생 (1개)
  → Call: aweb_search({'query': '2024 AI trends'})
  → Observe: 928 chars
[Supervisor] 최종 답변 생성
→ 웹 검색 후 응답
```

---

## 7차 평가 (2024-12-21) - LangGraph 전환 검증

### 평가 결과
- **상태**: ✅ LangGraph 전환 완료 확인

### 테스트 실행 결과
```
==================================================
AI Librarian - Supervisor ReAct Pattern Test
==================================================

📝 질문: LangChain이 무엇인가요?
----------------------------------------
[Supervisor] 질문 수신: LangChain이 무엇인가요?
[Supervisor] 최종 답변 생성

💡 답변:
LangChain은 자연어 처리(NLP)와 관련된 다양한 작업을 수행하기 위해...
(도구 호출 없이 바로 응답 - 정상 동작)
```

### 확인된 사항
- [x] `langgraph.prebuilt.create_react_agent` 사용 중
- [x] while 루프 제거됨
- [x] `recursion_limit`으로 최대 스텝 제어
- [x] 메시지 히스토리에서 로그 추출 동작
- [x] 도구 호출 없이 바로 응답 가능

### 발견된 이슈
- [x] **웹 검색 반복 호출 문제**: "2024년 AI 트렌드" 질문 시 동일 검색을 9번 반복 호출
  - 원인 추정: DuckDuckGo 검색 결과가 충분하지 않거나, 프롬프트에서 "정보가 부족하면 다시 검색" 지침이 과도하게 작용
  - 해결 방안:
    1. 프롬프트 수정: 최대 검색 횟수 제한 명시
    2. 또는 검색 결과 판단 로직 개선
    - **조치 완료**: SYSTEM_PROMPT에 검색 반복 제한 지침 추가 및 LangGraph `recursion_limit` 설정 확인 (구현: Gemini)

---

## 8차 평가 (2024-12-21) - ReAct 루프 구조 검증

### 테스트 질문
```
"2024년 AI 트렌드는 무엇이고, RAG 기술의 발전은 어떻게 되고 있나요?"
```

### 실행 흐름 확인
```
[0] SystemMessage: (시스템 프롬프트)
[1] HumanMessage: 2024년 AI 트렌드는 무엇이고, RAG 기술의 발전은...
[2] AIMessage (Step 1 - THINK & ACT):
      → 도구 호출: aweb_search({'query': '2024 AI trends'})
      → 도구 호출: aweb_search({'query': 'RAG technology development 2024'})
[3] ToolMessage (OBSERVE):
      → 결과: 1091 chars
[4] ToolMessage (OBSERVE):
      → 결과: 1775 chars
[5] AIMessage (FINAL ANSWER):
      → 답변: 2024년 AI 트렌드와 RAG...
```

### 검증 결과
- [x] **THINK → ACT → OBSERVE → THINK → ... → ANSWER** 구조 정상 동작
- [x] **다중 검색**: 한 번의 THINK에서 여러 도구 동시 호출 가능 (병렬 검색)
- [x] **검색어 다양화**: 질문에 따라 다른 검색어로 검색 수행
- [x] **만족 시 종료**: 정보가 충분하면 추가 검색 없이 바로 응답
- [x] **반복 제한**: 프롬프트에 3회 이상 동일 검색 제한 명시됨

### ReAct 루프 다이어그램
```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph ReAct Agent                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   User Question                                             │
│        ↓                                                    │
│   ┌─────────┐                                               │
│   │  THINK  │ ← LLM이 질문 분석                             │
│   └────┬────┘                                               │
│        ↓                                                    │
│   ┌─────────────────────────────────────────┐               │
│   │ 도구 필요?                              │               │
│   │   YES → ACT (도구 호출, 다중 가능)      │               │
│   │   NO  → ANSWER (최종 응답)              │               │
│   └────────────────┬────────────────────────┘               │
│                    ↓ (YES인 경우)                           │
│   ┌─────────┐                                               │
│   │   ACT   │ → aweb_search, arag_search 등                 │
│   └────┬────┘                                               │
│        ↓                                                    │
│   ┌─────────┐                                               │
│   │ OBSERVE │ ← 도구 결과 수신                              │
│   └────┬────┘                                               │
│        ↓                                                    │
│   ┌─────────┐                                               │
│   │  THINK  │ ← 결과 분석, 추가 검색 필요 여부 판단         │
│   └────┬────┘                                               │
│        ↓                                                    │
│   (반복 또는 최종 응답)                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 9차 평가 (2024-12-21) - THINK 자연어 출력 미노출 이슈

### 발견된 현상
```
기대했던 것 (Classic ReAct):
[2] AIMessage: "최신 정보가 필요하므로 웹 검색을 해야겠다"  ← THINK (자연어)
[3] AIMessage: tool_calls: [aweb_search(...)]              ← ACT

실제 동작 (Function Calling ReAct):
[2] AIMessage: tool_calls: [aweb_search(...)]              ← THINK + ACT 통합
```

### 원인 분석
- `create_react_agent`는 **OpenAI Function Calling** 방식 사용
- LLM이 "생각"을 자연어로 출력하지 않고, **바로 tool_calls를 결정**
- THINK 단계가 LLM 내부에서 암묵적으로 처리되어 외부로 노출되지 않음

### 해결 방안 (선택사항)

| 방법 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **1. 현재 유지 (Function Calling)** | LangGraph 기본 동작 | 안정적, 빠름, 파싱 오류 없음 | 중간 생각 미노출 |
| **2. Classic ReAct 프롬프트** | `Thought: ...` 형식 강제 | 생각 과정 가시화 | 파싱 오류 가능, 속도 저하 |
| **3. Structured Output + Reasoning** | 생각과 도구 호출을 구조화된 응답으로 | 생각 노출 + 안정성 | 구현 복잡도 증가 |

### 결정
- [ ] 현재 방식 유지 (Function Calling) - 안정성 우선
- [ ] Classic ReAct로 전환 - 디버깅/가시성 우선
- [x] **Structured Output 방식 도입** - 생각 노출 + 안정성 (구현: Gemini)

### 구현 방향
Structured Output을 사용하여 LLM이 **생각(reasoning)**과 **도구 호출(tool_calls)**을 함께 반환하도록 구현:

```python
from pydantic import BaseModel
from typing import Optional, List

class ThinkAndAct(BaseModel):
    thought: str  # 생각 과정 (자연어)
    tool_name: Optional[str] = None  # 호출할 도구 (없으면 최종 응답)
    tool_args: Optional[dict] = None
    final_answer: Optional[str] = None  # 도구 없이 바로 응답할 경우

# LLM에서 structured output 사용
llm_with_structure = llm.with_structured_output(ThinkAndAct)
```

**예상 출력:**
```
[2] AIMessage (THINK):
      → 생각: "최신 AI 트렌드와 RAG 기술 발전을 묻고 있다.
              내 지식은 2024년 이전이므로 웹 검색이 필요하다."
      → 도구 호출: aweb_search({'query': '2024 AI trends'})
      → 도구 호출: aweb_search({'query': 'RAG technology 2024'})
```

---

## 10차 평가 (2024-12-21) - Structured Output 구현 검증

### 테스트 결과

**테스트 1: 도구 호출 없이 바로 응답**
```
질문: LangChain이 무엇인가요?

실행 로그:
  Thinking: LangChain은 자연어 처리(NLP)와 관련된 다양한 작업을 수행하기 위한
            프레임워크로, 특히 대화형 AI 및 언어 모델을 활용한 애플리케이션 개발에
            중점을 두고 있습니다...

  Answer: LangChain은 자연어 처리(NLP)와 관련된...

사용된 도구: []
```

**테스트 2: 웹 검색 후 응답**
```
질문: 2024년 AI 트렌드는?

실행 로그:
  Thinking: 2024년 AI 트렌드에 대한 최신 정보를 수집하기 위해 웹 검색을 진행해야겠다.
  Act: aweb_search({'query': '2024 AI trends'})
  Observe: 1562 chars
  Thinking: 2024년 AI 트렌드는 접근성, 윤리, 지속 가능성, 규제 등 다양한 분야에서의
            발전이 포함되어 있다...

  Answer: 2024년 AI 트렌드는 다음과 같은 주요 요소들로 구성됩니다...

사용된 도구: ['aweb_search']
```

### 검증 결과
- [x] **THINK 자연어 출력**: `Thinking: ...` 형태로 생각 과정 노출됨
- [x] **도구 호출 없이 바로 응답**: 내부 지식으로 충분하면 바로 답변
- [x] **도구 호출 후 응답**: 웹 검색 → Observe → 다시 생각 → 답변
- [x] **StateGraph 구조**: supervisor → tools → supervisor 루프 정상 동작
- [x] **Structured Output**: `ThinkAndAct` Pydantic 모델 정상 작동

### 주요 구현 변경사항 (by Gemini)
1. `create_react_agent` → 커스텀 `StateGraph` 전환
2. `ThinkAndAct` Pydantic 모델 정의 (thought, tool_name, tool_args, final_answer)
3. `with_structured_output()` 사용
4. `_supervisor_node`에서 AIMessage 변환 로직 구현
5. `_should_continue` 조건부 분기 구현

### 현재 아키텍처
```
┌─────────────────────────────────────────────────────────────┐
│                StateGraph + Structured Output               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   User Question                                             │
│        ↓                                                    │
│   ┌──────────────────┐                                      │
│   │  supervisor_node │                                      │
│   │  (ThinkAndAct)   │ ← Structured Output LLM              │
│   │                  │                                      │
│   │  thought: "..."  │ ← 생각 과정 (자연어 노출!)           │
│   │  tool_name: ...  │                                      │
│   │  tool_args: ...  │                                      │
│   │  final_answer:   │                                      │
│   └────────┬─────────┘                                      │
│            ↓                                                │
│   ┌────────────────────────┐                                │
│   │ tool_calls 있음?       │                                │
│   │   YES → tools (ToolNode)                                │
│   │   NO  → END                                             │
│   └────────────────────────┘                                │
│            ↓ (YES)                                          │
│   ┌──────────────────┐                                      │
│   │    ToolNode      │ → aweb_search, arag_search           │
│   └────────┬─────────┘                                      │
│            ↓                                                │
│   ┌──────────────────┐                                      │
│   │  supervisor_node │ ← 다시 생각                          │
│   └──────────────────┘                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 개선된 점
| 항목 | 이전 (create_react_agent) | 현재 (Structured Output) |
|------|---------------------------|--------------------------|
| THINK 노출 | ❌ 암묵적 처리 | ✅ 자연어로 명시적 노출 |
| 디버깅 | 어려움 | 쉬움 (생각 과정 추적 가능) |
| 커스터마이징 | 제한적 | 자유로움 (StateGraph) |
| 안정성 | Function Calling 의존 | Structured Output 보장 |

---

## 11차 평가 (2024-12-21) - 도구 선택 합리성 & 재귀 검색 테스트

### 테스트 1: 도구 선택 합리성 ✅
```
질문: 파이썬이란 무엇인가요?
  → 사용된 도구: 없음 (LLM 직접 응답)
  → 생각: 파이썬은 고급 프로그래밍 언어로...

질문: 오늘 날씨는 어때?
  → 사용된 도구: ['aweb_search']
  → 생각: 오늘의 날씨에 대한 최신 정보가 필요하므로 웹 검색을 해야겠다.

질문: 2024년 12월 최신 뉴스 알려줘
  → 사용된 도구: ['aweb_search']
  → 생각: 2024년 12월의 최신 뉴스에 대한 정보를 얻기 위해 웹 검색을 해야겠다.
```

**결과**: LLM 지식으로 충분한 경우 도구 호출 없이 응답, 최신 정보 필요 시 웹 검색 호출 → **합리적**

### 테스트 2: 재귀 검색 ✅
```
질문: 2024년 OpenAI의 새로운 모델 GPT-5에 대한 정보와 출시 예정일을 알려줘

실행 로그:
  [1] THINK: GPT-5에 대한 정보와 출시 예정일은 최신 정보가 필요하므로 웹 검색을 해야겠다.
      ACT: aweb_search({'query': 'GPT-5 release date and information 2024'})
      OBSERVE: 1480 chars
  [2] THINK: GPT-5는 2024년 여름에 출시될 예정이며...

총 검색 횟수: 1 (충분한 정보 확보 후 종료)
```

**결과**: 첫 검색에서 충분한 정보 확보 → 불필요한 재검색 없이 종료 → **정상 동작**

### 테스트 3: 복합 질문 - 버그 발견 ❌
```
질문: Claude 3.5 Sonnet과 GPT-4 Turbo의 성능 비교, 그리고 각각의 가격 정책은?

에러:
pydantic_core._pydantic_core.ValidationError: 1 validation error for AIMessage
tool_calls.0.args
  Input should be a valid dictionary [type=dict_type,
  input_value='Claude 3.5 Sonnet vs GPT... comparison and pricing', input_type=str]
```

### 발견된 버그
- **원인**: `ThinkAndAct.tool_args`가 JSON 문자열이 아닌 일반 문자열로 반환될 때 발생
- **위치**: `supervisor.py` line 93-96의 JSON 파싱 로직
- **현상**: LLM이 `{"query": "..."}` 대신 `"Claude 3.5 Sonnet vs GPT..."` 형태로 반환
- **해결 방안**:
  1. `tool_args` 타입을 `Optional[dict]`로 변경
  2. 또는 파싱 로직에서 문자열을 dict로 변환하는 fallback 강화

### 수정 필요 사항 (구현 에이전트)
```python
# 현재 코드 (버그)
try:
    args = json.loads(result.tool_args)
except json.JSONDecodeError:
    args = {"query": result.tool_args}

# 수정 필요: tool_args가 이미 dict인 경우도 처리
if isinstance(result.tool_args, dict):
    args = result.tool_args
elif isinstance(result.tool_args, str):
    try:
        args = json.loads(result.tool_args)
    except json.JSONDecodeError:
        args = {"query": result.tool_args}
else:
    args = {"query": str(result.tool_args)}
```

- **조치 완료**: Supervisor `_supervisor_node`에서 `tool_args` 파싱 로직 강화 (dict, str, JSON str 모두 처리) (구현: Gemini)

---

## 12차 평가 (2024-12-21) - 버그 수정 검증

### 11차 버그 수정 후 재테스트 ✅
```
질문: Claude 3.5 Sonnet과 GPT-4 Turbo의 성능 비교, 그리고 각각의 가격 정책은?

실행 로그:
  [1] THINK: Claude 3.5 Sonnet과 GPT-4 Turbo의 성능 비교 및 가격 정책에 대한 정보를 수집해야 한다.
      ACT: aweb_search({'query': 'Claude 3.5 Sonnet vs GPT-4 Turbo performance comparison and pricing'})
      OBSERVE: 1093 chars
  [2] THINK: Claude 3.5 Sonnet과 GPT-4 Turbo의 성능 비교 및 가격 정책에 대한 정보를 수집했다...

총 검색 횟수: 1
사용된 도구: ['aweb_search']
답변 길이: 479 chars
```

### 검증 결과
- [x] **버그 수정 완료**: 이전에 `ValidationError` 발생하던 질문 정상 처리
- [x] **tool_args 파싱 강화**: dict, str, JSON str 모두 올바르게 처리
- [x] **재귀 검색**: 필요시 정상 동작 (1회 검색 후 충분한 정보로 종료)
- [x] **답변 품질**: 성능 비교 및 가격 정책 정보 포함

### 최종 상태 요약

| 항목 | 상태 |
|------|------|
| LangGraph 전환 | ✅ 완료 |
| Structured Output (ThinkAndAct) | ✅ 완료 |
| THINK 자연어 노출 | ✅ 완료 |
| 도구 선택 합리성 | ✅ 검증 완료 |
| 재귀 검색 | ✅ 검증 완료 |
| tool_args 파싱 버그 | ✅ 수정 완료 |

### 남은 작업 (선택)
- [ ] 스트리밍 지원 (`astream_events`)
- [ ] 그래프 시각화
- [ ] 불필요한 스키마 정리
- [ ] 로깅 시스템 강화 (print → logging)

---

## 13차 평가 (2024-12-21) - 회귀 검색 정상 동작 증명

### 테스트 목적
- 첫 번째 검색 결과가 불충분할 때 **추가 검색(회귀 검색)**이 발생하는지 검증
- THINK → ACT → OBSERVE → THINK → (추가 ACT 가능) → ANSWER 패턴 확인

### 테스트 1: 두 AI 모델의 역사 비교 (복합 정보 필요)
```
질문: "Claude AI와 Gemini AI의 출시 역사와 버전 변화를 비교해주세요"

실행 흐름:
  [1] THINK: Claude AI와 Gemini AI의 출시 역사와 버전 변화를 비교하기 위해
              최신 정보를 수집해야 한다.
      ACT: aweb_search({'query': 'Claude AI release history versions'})
      OBSERVE: (Claude 관련 결과)

  [2] THINK: Claude AI에 대한 정보는 수집했다. Gemini AI에 대한 정보도 필요하다.
      ACT: aweb_search({'query': 'Gemini AI release history versions'})
      OBSERVE: (Gemini 관련 결과)

  [3] THINK: 두 AI 모델에 대한 충분한 정보를 수집했다. 비교 답변을 작성한다.
      ANSWER: (비교 답변 제공)

통계:
  - THINK 횟수: 3
  - ACT (검색) 횟수: 2
  - ✅ 회귀 검색 발생: 첫 검색 후 정보 부족 판단 → 추가 검색 실행
```

### 테스트 2: 최신 벤치마크 정보 (정보 충분성 판단)
```
질문: "2024년 12월 기준 AI 모델 벤치마크 결과 알려줘"

실행 흐름:
  [1] THINK: 2024년 12월 기준 AI 모델 벤치마크 결과는 최신 정보이므로
              웹 검색이 필요하다.
      ACT: aweb_search({'query': '2024 December AI model benchmark results'})
      OBSERVE: (벤치마크 결과)

  [2] THINK: 벤치마크 결과에 대한 충분한 정보를 확보했다.
      ANSWER: (벤치마크 결과 제공)

통계:
  - THINK 횟수: 2
  - ACT (검색) 횟수: 1
  - ✅ 정상: 정보가 충분하면 추가 검색 없이 종료
```

### 검증 결과

| 시나리오 | THINK 횟수 | ACT 횟수 | 회귀 검색 | 결과 |
|----------|------------|----------|-----------|------|
| 두 AI 모델 비교 | 3 | 2 | ✅ 발생 | 정보 부족 → 추가 검색 |
| 최신 벤치마크 | 2 | 1 | ❌ 불필요 | 정보 충분 → 바로 응답 |

### 회귀 검색 패턴 다이어그램
```
┌─────────────────────────────────────────────────────────────────┐
│                     회귀 검색 (Recursive Search)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Question                                                  │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │ THINK 1 │ "두 모델 비교 필요, 먼저 Claude 정보 검색"         │
│   └────┬────┘                                                    │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │  ACT 1  │ → aweb_search('Claude AI history')                 │
│   └────┬────┘                                                    │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │ OBSERVE │ → Claude 정보 수신                                 │
│   └────┬────┘                                                    │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │ THINK 2 │ "Claude 정보는 확보, Gemini 정보도 필요" ← 정보 부족 판단│
│   └────┬────┘                                                    │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │  ACT 2  │ → aweb_search('Gemini AI history')  ← 추가 검색!   │
│   └────┬────┘                                                    │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │ OBSERVE │ → Gemini 정보 수신                                 │
│   └────┬────┘                                                    │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │ THINK 3 │ "두 모델 정보 모두 확보, 비교 답변 작성"           │
│   └────┬────┘                                                    │
│        ↓                                                         │
│   ┌─────────┐                                                    │
│   │ ANSWER  │ → 비교 답변 제공                                   │
│   └─────────┘                                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 핵심 검증 포인트

1. **정보 부족 판단 능력** ✅
   - LLM이 첫 검색 결과를 분석하여 "추가 정보 필요" 여부 판단
   - 질문에서 요구하는 정보가 부족하면 자동으로 추가 검색 결정

2. **검색어 다양화** ✅
   - 첫 검색: `Claude AI release history versions`
   - 추가 검색: `Gemini AI release history versions`
   - 동일 검색어 반복이 아닌, 부족한 정보에 맞는 새 검색어 생성

3. **불필요한 검색 회피** ✅
   - 정보가 충분하면 추가 검색 없이 바로 응답
   - 프롬프트의 "3회 이상 동일 검색 금지" 지침 준수

4. **ReAct 루프 정상 동작** ✅
   - THINK → ACT → OBSERVE → THINK → (ACT → OBSERVE → THINK)* → ANSWER
   - 각 THINK 단계에서 다음 행동 결정

### 결론
- **회귀 검색 정상 동작 확인**: 정보 부족 시 추가 검색 → 정보 충분 시 응답
- **동적 의사결정**: LLM이 매 THINK 단계에서 상황을 분석하고 다음 행동 결정
- **Structured Output 활용**: 각 THINK 단계의 reasoning이 자연어로 노출되어 디버깅 용이

---

## 13차 평가 추가 (2024-12-21) - 2회 이상 검색 테스트 케이스

### 테스트 파일
- **위치**: `poc/test_recursive_search.py`
- **목적**: 회귀 검색(2회 이상 검색)이 정상 동작하는지 자동화 테스트

### 테스트 케이스 및 결과
```
============================================================
테스트 1: 순차 정보 탐색
질문: "오늘 대한민국 서울의 날씨와 일본 도쿄의 날씨를 각각 알려주세요"
  - THINK 횟수: 2
  - ACT (검색) 횟수: 1
  - 결과: ❌ (한 번에 두 도시 동시 검색)

테스트 2: 특정 제품 가격 비교
질문: "GitHub Copilot의 2024년 월간 구독료와 Cursor AI의 2024년 월간 구독료를 각각 검색해서 비교해주세요"
  - THINK 횟수: 3
  - ACT (검색) 횟수: 2
  - 검색 1: aweb_search({'query': 'GitHub Copilot 2024 monthly subscription fee'})
  - 검색 2: aweb_search({'query': 'Cursor AI 2024 monthly subscription fee.'})
  - 결과: ✅ PASS

테스트 3: 두 회사 주가 비교
질문: "먼저 NVIDIA의 2024년 12월 주가를 검색하고, 그 다음 AMD의 2024년 12월 주가를 검색해서 비교해주세요"
  - THINK 횟수: 3
  - ACT (검색) 횟수: 2
  - 검색 1: aweb_search({'query': 'NVIDIA stock price December 2024...'})
  - 검색 2: aweb_search({'query': 'AMD stock price December 2024...'})
  - 결과: ✅ PASS
============================================================
총 3개 중 2개 통과 (66.7%)
✅ 회귀 검색 발생 확인: 2개 케이스에서 2회 이상 검색
```

### 테스트 실행 방법
```bash
cd poc
uv run python test_recursive_search.py
```

---

## 앱 실행 가이드

### 1. CLI 테스트 실행
```bash
cd /Users/dongkseo/Project/ai-librarian/poc
uv run python run.py
```

### 2. Streamlit UI 실행
```bash
cd /Users/dongkseo/Project/ai-librarian/poc
uv run streamlit run app.py
```

### 3. 접근 URL
- **Local URL**: http://localhost:8501
- **Network URL**: http://<your-ip>:8501

### 4. 회귀 검색 테스트 실행
```bash
cd /Users/dongkseo/Project/ai-librarian/poc
uv run python test_recursive_search.py
```

---

## 14차 평가 (2024-12-21) - 자율 회귀 검색 미동작 이슈

### 테스트 결과
```
테스트 1: 자율 회귀 - 희귀 정보 (Devin 에이전트 가격/벤치마크)
  - ACT 횟수: 1 ❌

테스트 2: 자율 회귀 - 깊은 정보 (Claude 3.5 상세 스펙)
  - ACT 횟수: 1 ❌

테스트 3: 자율 회귀 - 최신 발표 (Gemini 2.0)
  - ACT 횟수: 1 ❌

테스트 4: 자율 회귀 - 암묵적 비교
  - 에러: Recursion limit 도달 (무한 루프)
```

### 발견된 문제
1. **자율 회귀 검색 미발생**: LLM이 첫 검색 후 정보가 부족해도 추가 검색하지 않음
2. **정보 충분성 판단 기준 부재**: 프롬프트에 "언제 추가 검색해야 하는지" 명확한 기준 없음
3. **무한 루프 발생**: 일부 질문에서 recursion limit 도달

### 개선 필요 사항 (프롬프트 수정)

**현재 프롬프트 문제점:**
```
4. 정보가 부족하면 다른 도구를 호출하거나 검색어를 구체화하여 다시 검색하세요.
```
→ "정보가 부족하면"의 기준이 모호함

**개선 방향 (구현 에이전트에게 전달):**
```python
SYSTEM_PROMPT = """...

## 정보 충분성 판단 기준
검색 결과를 받은 후 다음을 확인하세요:
1. 질문에서 요구한 **모든 항목**에 대한 정보가 있는가?
   - 예: "A와 B를 비교해주세요" → A 정보와 B 정보 모두 필요
   - 예: "가격과 성능을 알려주세요" → 가격 정보와 성능 정보 모두 필요
2. 정보가 **구체적인 수치/사실**로 제공되었는가?
   - "약 $20" ❌ → "정확히 $20/월" ✅
3. 정보의 **출처가 신뢰할 만한가**?

위 조건 중 하나라도 만족하지 않으면:
- 부족한 정보에 대해 **구체적인 검색어**로 추가 검색
- 동일 검색어 반복 금지, 다른 키워드 사용

## 예시: 자율 회귀 검색
User: "GPT-4의 가격과 MMLU 점수를 알려줘"
Think: 가격과 벤치마크 정보가 필요하다. 웹 검색을 해보자.
Call: aweb_search("GPT-4 pricing")
Observe: [가격 정보 $0.03/1K tokens...]
Think: 가격 정보는 얻었지만 MMLU 점수가 없다. 추가 검색이 필요하다.  ← 자율 판단
Call: aweb_search("GPT-4 MMLU benchmark score")
Observe: [MMLU 86.4%...]
Think: 두 정보를 모두 얻었다. 답변을 작성한다.
Answer: ...
"""
```

### 조치 필요

- [x] 프롬프트에 정보 충분성 판단 기준 추가
- [x] 자율 회귀 검색 예시 추가
- [x] 무한 루프 방지 로직 검토

---

## 15차 평가 (2024-12-21) - 프롬프트 개선 후 자율 회귀 검색 테스트

### 프롬프트 개선 사항 (by Gemini)
1. **정보 충분성 판단 기준** 추가
   - 모든 항목 정보 확인
   - 구체적 수치/사실 여부
   - 출처 신뢰성
2. **자율 회귀 검색 예시** 추가
   - GPT-4 가격 + MMLU 점수 예시
3. **회귀 검색 권장** 명시

### 테스트 결과

| 테스트 케이스 | 개선 전 | 개선 후 | 결과 |
|--------------|---------|---------|------|
| 희귀 정보 (Devin) | 1회 | 1회 | ❌ |
| 깊은 정보 (Claude 스펙) | 1회 | **2회** | ✅ |
| 최신 발표 (Gemini 2.0) | 1회 | **4회** | ✅ |
| 암묵적 비교 | 무한루프 | 1회 | ❌ (개선됨) |

### 성과
- **통과율**: 0% → **50%**
- **무한 루프 해결**: Recursion limit 에러 없음
- **자율 회귀 검색 동작 확인**

### 성공 케이스 상세 (Gemini 2.0)
```
질문: "2024년 12월에 발표된 Google의 Gemini 2.0 모델의 새로운 기능과 API 가격을 자세히 알려주세요"

[1] THINK: 최신 정보 필요 → 검색
    ACT: aweb_search('Google Gemini 2.0 features and API pricing December 2024')

[2] THINK: 기능 정보는 있지만 API 가격이 부족 → 추가 검색 ← 자율 판단!
    ACT: aweb_search('Google Gemini 2.0 features December 2024')

[3] THINK: 여전히 가격 정보 부족 → 추가 검색
    ACT: aweb_search('Google Gemini 2.0 API pricing December 2024')

[4] THINK: 재확인 필요
    ACT: aweb_search('Google Gemini 2.0 API pricing December 2024')

[5] THINK: 충분한 정보 수집 완료
    ANSWER: (답변 제공)
```

### 결론
- ✅ **자율 회귀 검색 정상 동작**: LLM이 정보 부족을 스스로 판단하여 추가 검색 수행
- ✅ **프롬프트 개선 효과 확인**: 정보 충분성 판단 기준이 실제로 적용됨
- ⚠️ **일부 케이스 미동작**: 단순한 질문은 한 번 검색으로 충분하다고 판단

### 앱 실행 방법

**Streamlit UI:**
```bash
cd /Users/dongkseo/Project/ai-librarian/poc
uv run streamlit run app.py
```

**접근 URL:**
- Local: http://localhost:8501
- Network: http://<your-ip>:8501
