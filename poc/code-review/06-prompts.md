# 06. 프롬프트 엔지니어링 심층 분석

## 파일 위치
- `src/supervisor/prompts.py` (173 lines)

---

## 1. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                    프롬프트 시스템 구조                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │   Config    │───▶│ get_system   │───▶│ SYSTEM_PROMPT   │    │
│  │             │    │ _prompt()    │    │ _TEMPLATE       │    │
│  │ - LANGUAGE  │    │              │    │                 │    │
│  │ - PERSONA   │    │ Variables:   │    │ Placeholders:   │    │
│  │ - DESC      │    │ - date       │    │ {persona}       │    │
│  └─────────────┘    │ - year       │    │ {description}   │    │
│                     │ - tools      │    │ {language}      │    │
│  ┌─────────────┐    └──────────────┘    │ {tools_desc}    │    │
│  │   Tools     │           │            │ {current_date}  │    │
│  │ (LangChain) │───────────┘            │ {current_year}  │    │
│  └─────────────┘                        └─────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 핵심 컴포넌트 분석

### 2.1 ToolInfo 데이터클래스

```python
@dataclass
class ToolInfo:
    """도구 정보"""
    name: str
    description: str
    category: str = "general"  # "think", "search", "action" 등
```

**특징:**
- `category` 필드가 정의되어 있지만 **실제로 사용되지 않음**
- 향후 도구를 카테고리별로 그룹화할 때 활용 가능

---

### 2.2 get_tools_description() 함수

```python
def get_tools_description(tools: List) -> str:
    """도구 목록에서 설명 문자열 생성"""
    lines = []
    for tool in tools:
        name = tool.name
        desc = tool.description.split('\n')[0].strip()  # 첫 줄만 사용
        lines.append(f"- `{name}`: {desc}")
    return "\n".join(lines)
```

**동작 흐름:**
```
Input: [Tool(name="think", description="Record reasoning\nMore details..."), ...]
                    │
                    ▼
            description.split('\n')[0]
                    │
                    ▼
Output: "- `think`: Record reasoning"
```

**설계 의도:**
- 도구 설명의 **첫 줄만 추출** (간결성 유지)
- 마크다운 리스트 형식으로 포맷팅

---

### 2.3 get_system_prompt() 함수

```python
def get_system_prompt(
    tools: Optional[List] = None,
    language: Optional[str] = None,
    persona: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
```

**매개변수 우선순위:**

```
┌──────────────────────────────────────────────────────┐
│            매개변수 결정 로직                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│  language 파라미터 제공?                              │
│       │                                              │
│       ├── YES ──▶ 파라미터 값 사용                   │
│       │                                              │
│       └── NO ───▶ config.RESPONSE_LANGUAGE 사용     │
│                   (기본값: "Korean")                 │
│                                                      │
│  동일한 로직이 persona, description에도 적용         │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**코드 분석:**
```python
# 설정값 결정 (None-coalescing 패턴)
lang = language or config.RESPONSE_LANGUAGE
agent_persona = persona or config.AGENT_PERSONA
agent_desc = description or config.AGENT_DESCRIPTION

# 도구 설명 생성
if tools:
    tools_desc = get_tools_description(tools)
else:
    tools_desc = DEFAULT_TOOLS_DESCRIPTION

# 템플릿에 변수 주입
return SYSTEM_PROMPT_TEMPLATE.format(
    current_date=current_date,
    current_year=current_year,
    language=lang,
    persona=agent_persona,
    description=agent_desc,
    tools_description=tools_desc,
)
```

---

## 3. 시스템 프롬프트 템플릿 분석

### 3.1 전체 구조

```
SYSTEM_PROMPT_TEMPLATE
├── 페르소나 정의
├── <core_principles>       - 핵심 원칙
├── <available_tools>       - 사용 가능한 도구
├── <query_classification>  - 쿼리 분류 가이드
├── <workflow>              - 워크플로우 단계
├── <response_formatting>   - 응답 포맷팅
├── <default_to_action>     - 행동 우선 원칙
├── <investigate_before_answering> - 검증 우선 원칙
└── <important_reminders>   - 중요 리마인더
```

### 3.2 각 섹션 상세 분석

#### (1) 페르소나 정의
```
You are {persona}, {description}.
Current date: {current_date}
```
- 에이전트의 정체성 설정
- 현재 날짜 주입으로 시간 인식 제공

#### (2) Core Principles (핵심 원칙)
```xml
<core_principles>
Use the `think` tool before every action to record your reasoning.
Respond in {language}.
Balance warmth with intellectual honesty.
Provide clear, concise, authentic responses.
Subtly adapt your tone to the user's style.
</core_principles>
```

**핵심 지시사항:**
1. **think 도구 필수 사용** - ReAct 패턴의 Think 단계 강제
2. **언어 지정** - 다국어 지원
3. **톤 균형** - 따뜻함 + 지적 정직성
4. **사용자 스타일 적응** - 유연한 톤 매칭

#### (3) Query Classification (쿼리 분류)
```
| Type | Examples | Action |
|------|----------|--------|
| Static Knowledge | ... | NO SEARCH - answer directly |
| Time-sensitive | ... | Search required |
| Internal Document | ... | Use internal search |
| Exploratory | ... | Multiple searches if needed |
```

**쿼리 분류 의사결정 트리:**
```
                    사용자 쿼리
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    정적 지식?      시간 민감?     내부 문서?
          │             │             │
          ▼             ▼             ▼
    직접 답변      웹 검색       RAG 검색
          │             │             │
          └─────────────┴─────────────┘
                        │
                        ▼
                   최종 응답
```

**CRITICAL 지시:**
```
CRITICAL: Do NOT search for static, unchanging information like:
- Programming language syntax
- Mathematical formulas
- Well-established technical concepts
- Historical facts
```
- **불필요한 검색 방지** - 토큰 절약 및 응답 속도 향상
- LLM의 내장 지식 활용 극대화

#### (4) Workflow (워크플로우)
```
Step 1: Analyze (use `think`)
Step 2: Act (직접 답변 / 검색 / 내부 검색)
Step 3: Respond
```

**시각적 워크플로우:**
```
┌─────────────────────────────────────────────────────────────┐
│                     ReAct Workflow                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  THINK   │───▶│   ACT    │───▶│ RESPOND  │              │
│  │          │    │          │    │          │              │
│  │ think()  │    │ search() │    │ 최종답변  │              │
│  │ 호출     │    │ or 직접  │    │ 생성     │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                             │
│       "Does this require external information?"            │
│                        │                                   │
│           ┌───────────┴───────────┐                        │
│           ▼                       ▼                        │
│       YES: Search            NO: Direct                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### (5) Response Formatting
```
- Headings: Create clear hierarchy
- Bullet points: Break down information
- Tables: Organize and compare data
- Bold: Emphasize key phrases
- Blockquotes: Highlight important notes
```

**마크다운 활용 가이드:**
| 요소 | 용도 | 예시 |
|------|------|------|
| 헤딩 | 계층 구조 | `## 섹션 제목` |
| 불릿 | 정보 분해 | `- 항목 1` |
| 테이블 | 비교/정리 | `| A | B |` |
| 볼드 | 강조 | `**중요**` |
| 인용 | 노트 | `> 참고:` |

#### (6) Default to Action
```xml
<default_to_action>
When the user's intent suggests action, implement changes rather than just suggesting them.
Use tools to discover missing details rather than guessing.
If a tool call seems intended, proceed with it.
</default_to_action>
```

**의도:**
- 수동적 제안보다 **능동적 실행** 선호
- 추측보다 **도구를 통한 검증** 선호

#### (7) Investigate Before Answering
```xml
<investigate_before_answering>
Never guess about information you have not verified.
If the user references specific content, investigate it before responding.
Search thoroughly for key facts.
Provide grounded, hallucination-free answers.
If uncertain, acknowledge it and investigate further.
</investigate_before_answering>
```

**핵심 원칙:**
- **할루시네이션 방지**
- 불확실할 때 **인정 후 조사**
- 검증된 정보만 제공

---

## 4. 하위 호환성 처리

```python
# 기본 프롬프트 제공 (하위 호환성)
def get_default_system_prompt() -> str:
    """기본 설정으로 시스템 프롬프트 생성 (하위 호환성)"""
    return get_system_prompt()

# Deprecated: 정적 버전 (하위 호환성)
SYSTEM_PROMPT = get_default_system_prompt()
```

**마이그레이션 가이드:**
```python
# 레거시 코드 (Deprecated)
from prompts import SYSTEM_PROMPT

# 권장 코드
from prompts import get_system_prompt
prompt = get_system_prompt(tools=my_tools, language="Korean")
```

---

## 5. 프롬프트 엔지니어링 기법 분석

### 5.1 사용된 기법들

| 기법 | 설명 | 적용 위치 |
|------|------|----------|
| **Role Prompting** | 페르소나 정의 | `You are {persona}` |
| **XML Tags** | 섹션 구분 | `<core_principles>` 등 |
| **Chain of Thought** | 단계별 사고 | `think` 도구 강제 |
| **Few-shot (Table)** | 예시 제공 | Query Classification 테이블 |
| **Constraint Setting** | 제약 조건 | `CRITICAL: Do NOT search...` |
| **Dynamic Injection** | 변수 주입 | `{language}`, `{tools_description}` |

### 5.2 XML 태그 사용의 장점

```xml
<core_principles>
...
</core_principles>

<workflow>
...
</workflow>
```

**장점:**
1. **명확한 섹션 구분** - LLM이 구조를 쉽게 파악
2. **선택적 참조 가능** - 특정 섹션만 언급 가능
3. **파싱 용이성** - 프로그래밍적 추출 가능
4. **Claude 최적화** - Anthropic 권장 패턴

### 5.3 동적 프롬프트의 이점

```
Static Prompt (기존)          Dynamic Prompt (현재)
┌─────────────────┐          ┌─────────────────┐
│ 고정된 도구     │          │ 런타임 도구     │
│ 고정된 언어     │   ──▶    │ 환경변수 언어   │
│ 고정된 페르소나 │          │ 커스텀 페르소나 │
└─────────────────┘          └─────────────────┘
```

---

## 6. 발견된 이슈 및 개선점

### 6.1 [Low] 미사용 ToolInfo.category

**현황:**
```python
@dataclass
class ToolInfo:
    category: str = "general"  # 정의되어 있지만 사용 안 됨
```

**개선안:**
```python
def get_tools_description(tools: List) -> str:
    """카테고리별 도구 그룹화"""
    categorized = defaultdict(list)
    for tool in tools:
        category = getattr(tool, 'category', 'general')
        categorized[category].append(tool)

    lines = []
    for category, tools_in_cat in categorized.items():
        lines.append(f"\n### {category.title()} Tools")
        for tool in tools_in_cat:
            lines.append(f"- `{tool.name}`: {tool.description.split(chr(10))[0]}")
    return "\n".join(lines)
```

### 6.2 [Low] 타입 힌트 개선 필요

**현황:**
```python
def get_tools_description(tools: List) -> str:  # List[Any]
```

**개선안:**
```python
from langchain_core.tools import BaseTool

def get_tools_description(tools: List[BaseTool]) -> str:
```

### 6.3 [Medium] 프롬프트 길이 최적화

**현황:**
- 전체 프롬프트 약 2,000 토큰
- 모든 요청에 동일한 전체 프롬프트 전송

**개선안 - 상황별 프롬프트 압축:**
```python
def get_system_prompt(
    tools: Optional[List] = None,
    mode: str = "full"  # "full", "compact", "minimal"
) -> str:
    if mode == "minimal":
        return MINIMAL_PROMPT_TEMPLATE.format(...)
    elif mode == "compact":
        return COMPACT_PROMPT_TEMPLATE.format(...)
    return SYSTEM_PROMPT_TEMPLATE.format(...)
```

### 6.4 [Info] 다국어 프롬프트 지원

**현재:** 영어 프롬프트 + `{language}` 변수로 응답 언어만 지정

**고려사항:**
- 프롬프트 자체를 다국어로 제공하면 더 나은 결과 가능
- 단, 영어 프롬프트가 일반적으로 가장 안정적

---

## 7. Supervisor와의 통합

### 7.1 프롬프트 주입 흐름

```python
# supervisor.py에서의 사용
class Supervisor:
    def __init__(self, ...):
        self.system_prompt = get_system_prompt(
            tools=self.tools,
            language=config.RESPONSE_LANGUAGE
        )

    def _get_system_message(self) -> SystemMessage:
        return SystemMessage(content=self.system_prompt)
```

### 7.2 도구 → 프롬프트 연결

```
┌─────────────┐    ┌───────────────────┐    ┌─────────────────┐
│   tools.py  │───▶│ get_tools_desc()  │───▶│ System Prompt   │
│             │    │                   │    │                 │
│ - think     │    │ "- `think`: ..."  │    │ <available_     │
│ - arag      │    │ "- `arag`: ..."   │    │  tools>         │
│ - aweb      │    │ "- `aweb`: ..."   │    │ {tools_desc}    │
└─────────────┘    └───────────────────┘    └─────────────────┘
```

---

## 8. 테스트 전략

### 8.1 현재 테스트 커버리지

```python
# tests/test_prompts.py
def test_system_prompt_generation():
    """시스템 프롬프트 생성 테스트"""
    prompt = get_system_prompt()
    assert "AI Librarian" in prompt
    assert "Korean" in prompt

def test_tools_description():
    """도구 설명 포맷팅 테스트"""
    # Mock tool 생성
    # 설명 생성 검증
```

### 8.2 추가 테스트 권장

```python
def test_custom_persona():
    """커스텀 페르소나 테스트"""
    prompt = get_system_prompt(persona="Customer Support Bot")
    assert "Customer Support Bot" in prompt
    assert "AI Librarian" not in prompt

def test_dynamic_date():
    """동적 날짜 주입 테스트"""
    prompt = get_system_prompt()
    today = datetime.now().strftime("%Y-%m-%d")
    assert today in prompt

def test_empty_tools_list():
    """빈 도구 리스트 처리"""
    prompt = get_system_prompt(tools=[])
    assert DEFAULT_TOOLS_DESCRIPTION in prompt  # 또는 빈 문자열 처리
```

---

## 9. 환경변수 설정 가이드

### 9.1 지원 환경변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `RESPONSE_LANGUAGE` | `"Korean"` | 응답 언어 |
| `AGENT_PERSONA` | `"AI Librarian"` | 에이전트 이름 |
| `AGENT_DESCRIPTION` | `"an AI assistant..."` | 에이전트 설명 |

### 9.2 설정 예시

```bash
# .env 파일
RESPONSE_LANGUAGE=English
AGENT_PERSONA=Research Assistant
AGENT_DESCRIPTION=a specialized assistant for academic research and paper analysis
```

---

## 10. 프롬프트 확장 가이드

### 10.1 새 섹션 추가

```python
SYSTEM_PROMPT_TEMPLATE = """...

<new_capability>
Your additional capability description here.
Use when {condition}.
</new_capability>

..."""
```

### 10.2 도구 카테고리 활용

```python
# 도구 정의 시 카테고리 지정
tools = [
    ToolInfo(name="think", description="...", category="reasoning"),
    ToolInfo(name="arag_search", description="...", category="search"),
    ToolInfo(name="code_execute", description="...", category="action"),
]
```

---

## 11. 요약

### 강점
1. **동적 프롬프트 시스템** - 환경변수로 커스터마이징 가능
2. **XML 태그 구조화** - 명확한 섹션 구분
3. **쿼리 분류 가이드** - 불필요한 검색 방지
4. **ReAct 패턴 강제** - think 도구 필수 사용

### 개선 필요
1. **ToolInfo.category 활용** - 현재 미사용
2. **타입 힌트 강화** - List[Any] → List[BaseTool]
3. **프롬프트 압축 옵션** - 토큰 효율성

### 핵심 설계 원칙
- **검증 후 답변** (Investigate Before Answering)
- **행동 우선** (Default to Action)
- **할루시네이션 방지** (Grounded Responses)
