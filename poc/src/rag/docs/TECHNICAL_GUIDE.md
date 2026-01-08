# OCR Vector DB 기술 해설서

> **대상 독자**: 프로젝트에 새로 합류하는 개발자
> **버전**: 1.0 (2026-01-01)
> **기반 아키텍처**: Layered DDD (Domain-Driven Design)

---

## 목차

1. [개요](#1-개요)
2. [임베딩 전략](#2-임베딩-전략)
   - 2.1 [핵심 원칙: "저장 ≠ 임베딩"](#21-핵심-원칙-저장--임베딩)
   - 2.2 [4단계 엔티티 계층](#22-4단계-엔티티-계층)
   - 2.3 [Semantic Unit 기반 그룹화](#23-semantic-unit-기반-그룹화)
   - 2.4 [임베딩 필터링 규칙](#24-임베딩-필터링-규칙)
   - 2.5 [결정적 doc_id](#25-결정적-doc_id)
3. [문서 임베딩 후 구조](#3-문서-임베딩-후-구조)
   - 3.1 [계층적 데이터 모델](#31-계층적-데이터-모델)
   - 3.2 [Multi-View 구조](#32-multi-view-구조)
   - 3.3 [Parent-Child 관계](#33-parent-child-관계)
   - 3.4 [저장 구조](#34-저장-구조-postgresql--pgvector)
4. [검색 시 맥락 유지가 효과적인 이유](#4-검색-시-맥락-유지가-효과적인-이유)
   - 4.1 [핵심 원칙: SEARCH-SEP](#41-핵심-원칙-search-sep)
   - 4.2 [검색 파이프라인](#42-검색-파이프라인)
   - 4.3 [ContextExpander의 동작](#43-contextexpander의-동작)
   - 4.4 [왜 효과적인가?](#44-왜-효과적인가)
5. [핵심 다이어그램](#5-핵심-다이어그램)
6. [도메인 규칙 참조](#6-도메인-규칙-참조)

---

## 1. 개요

OCR Vector DB는 PDF, Markdown, 텍스트 문서를 처리하여 벡터 데이터베이스에 저장하고, 의미 기반 검색(semantic search)을 제공하는 시스템입니다.

### 시스템의 핵심 가치

```
┌─────────────────────────────────────────────────────────────────────┐
│  "작은 조각으로 정밀하게 검색하고, 큰 맥락을 함께 제공한다"          │
│                                                                     │
│  Search Target: Fragment (정밀도 ↑)                                 │
│  Context Provider: Parent Concept (맥락 ↑)                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 아키텍처 개요

```
ocr_vector_db/
├── domain/          # 순수 도메인 엔티티 (인프라 의존성 없음)
├── shared/          # 공통 유틸리티, 설정, 예외
├── ingestion/       # 파일 파싱 및 의미적 세그멘테이션
├── embedding/       # 벡터 생성 및 검증
├── retrieval/       # 검색 파이프라인 및 맥락 확장
├── storage/         # 데이터베이스 접근 및 리포지토리
└── api/             # CLI 및 REST 인터페이스
```

**의존성 방향**:
```
api → ingestion, embedding, retrieval, storage → domain, shared
                            ↓
              domain → (의존성 없음)
```

---

## 2. 임베딩 전략

### 2.1 핵심 원칙: "저장 ≠ 임베딩"

> **모든 텍스트가 임베딩 대상이 아닙니다.**

전통적인 RAG 시스템은 문서를 고정 크기로 분할(chunking)하고 모든 조각을 임베딩합니다. 이 방식은 다음 문제를 야기합니다:

| 문제 | 설명 |
|------|------|
| 검색 오염 | 페이지 번호, 저작권 문구 등 비의미적 텍스트가 검색 결과에 노출 |
| 중복 임베딩 | 동일 콘텐츠가 여러 번 임베딩되어 스토리지 낭비 |
| 맥락 손실 | 고정 크기 분할로 의미적 연관성이 끊어짐 |

**본 시스템의 접근 방식**:

```
                  ┌─────────────────┐
                  │   모든 텍스트    │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  명시적 필터링   │  ← FRAG-LEN-001, EMBED-BAN-*
                  │  규칙 적용       │
                  └────────┬────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │  임베딩 대상 ✅   │      │   저장만 ❌      │
     │  (Fragment)      │      │   (메타데이터)   │
     └──────────────────┘      └──────────────────┘
```

**참조 파일**: `embedding/validators.py`

---

### 2.2 4단계 엔티티 계층

시스템의 모든 데이터는 4단계 계층 구조를 따릅니다:

```
Document → Concept → Fragment → Embedding
```

#### Document (문서)
- **정의**: 시스템에 입력되는 최상위 단위 (파일)
- **임베딩 여부**: ❌ **임베딩되지 않음**
- **역할**: 소스 파일의 메타데이터와 위치 정보 보유

```python
# domain/entities.py:17-35
@dataclass
class Document:
    """
    Top-level input unit representing a file.
    A Document is the source of truth for all downstream Concepts.
    """
    id: str
    source_path: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
```

#### Concept (개념/의미 단위)
- **정의**: 의미적으로 응집된 정보 단위 (Semantic Parent)
- **임베딩 여부**: ⚠️ **선택적** (MAY)
- **역할**: 관련된 Fragment들을 그룹화하고 맥락 제공
- **도메인 규칙**: HIER-002 (반드시 하나의 Document에 귀속)

```python
# domain/entities.py:38-66
@dataclass
class Concept:
    """
    Semantically cohesive information unit (Semantic Parent).
    A Concept groups related Fragments (text + code + image views of same topic).
    """
    id: str
    document_id: str  # HIER-002: 반드시 Document에 귀속
    order: int = 0
    content: Optional[str] = None  # Parent document content for context
    metadata: dict = field(default_factory=dict)
```

#### Fragment (조각)
- **정의**: Concept을 구성하는 개별 정보 조각 (Child)
- **임베딩 여부**: ✅ **주요 임베딩 대상** (최소 길이 조건 충족 시)
- **역할**: 검색 대상, 실제 콘텐츠 보유
- **도메인 규칙**: HIER-001, HIER-003, FRAG-LEN-001

```python
# domain/entities.py:69-136
@dataclass
class Fragment:
    """
    Individual information chunk within a Concept.
    Fragments are the primary search target and embedding unit.
    """
    id: str
    concept_id: str      # parent_id - HIER-003: 반드시 Concept에 귀속
    content: str
    view: View           # FRAG-VIEW-001: View는 속성
    language: Optional[str]
    order: int
    metadata: dict = field(default_factory=dict)

    def is_embeddable(self) -> bool:
        """FRAG-LEN-001: 최소 10자 이상이어야 임베딩 가능"""
        return len(self.content) >= 10
```

#### Embedding (임베딩)
- **정의**: Fragment의 벡터 표현
- **역할**: 유사도 검색의 기반
- **도메인 규칙**: EMBED-OWN-001, EMBED-ID-002

```python
# domain/entities.py:139-168
@dataclass
class Embedding:
    """Vector representation of a Fragment for similarity search."""
    doc_id: str       # 결정적 ID: hash(parent_id + view + lang + content)
    fragment_id: str  # EMBED-OWN-001: 반드시 Fragment에 귀속
    vector: List[float]
    metadata: dict = field(default_factory=dict)
```

#### 계층 구조 다이어그램

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Document                                      │
│                    (source: book.pdf)                                 │
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                      Concept 1                               │    │
│   │              "HTTP 요청과 응답 처리"                          │    │
│   │                                                              │    │
│   │   ┌───────────────┐ ┌───────────────┐ ┌───────────────┐     │    │
│   │   │  Fragment 1   │ │  Fragment 2   │ │  Fragment 3   │     │    │
│   │   │  view=text    │ │  view=code    │ │  view=image   │     │    │
│   │   │  "HTTP 요청은 │ │  lang=python  │ │  "Figure 1"   │     │    │
│   │   │   클라이언트  │ │  "import      │ │               │     │    │
│   │   │   가..."      │ │   requests"   │ │               │     │    │
│   │   └───────┬───────┘ └───────┬───────┘ └───────┬───────┘     │    │
│   │           │                 │                 │              │    │
│   │           ▼                 ▼                 ▼              │    │
│   │       Embedding         Embedding         Embedding          │    │
│   │       [0.1, 0.2,...]    [0.3, 0.1,...]    [0.5, 0.4,...]     │    │
│   └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                      Concept 2                               │    │
│   │                  "에러 핸들링"                                │    │
│   │                       ...                                    │    │
│   └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 2.3 Semantic Unit 기반 그룹화

> **"청크 우선(Chunk-First)"이 아닌 "의미 단위 우선(Semantic-Unit-First)"**

#### 기존 방식의 문제 (Chunk-First)

```
❌ 고정 크기 청킹 (예: 1000자)

원본:                             청킹 결과:
┌────────────────────────────┐   ┌────────────────────┐
│ 리스트 컴프리헨션은        │   │ 청크 1: "리스트    │ ← 설명만
│ 파이썬의 강력한 기능...    │   │ 컴프리헨션은..."   │
│                            │   ├────────────────────┤
│ ```python                  │   │ 청크 2: "...강력한 │ ← 코드 시작부분
│ result = [x*2 for x in     │   │ ...```python       │    잘림!
│           range(10)]       │   │ result = [x*2..."  │
│ ```                        │   ├────────────────────┤
│                            │   │ 청크 3: "...range  │ ← 코드 끝부분
│ 결과: [0, 2, 4, 6, ...]    │   │ (10)]```결과..."   │    + 결과 혼합
└────────────────────────────┘   └────────────────────┘

문제: 코드가 의미 없는 경계에서 분리됨
```

#### 본 시스템의 방식 (Semantic-Unit-First)

```
✅ 의미 단위 그룹화

원본:                             의미 단위 결과:
┌────────────────────────────┐   ┌────────────────────────────┐
│ 리스트 컴프리헨션은        │   │ Concept: "리스트 컴프리헨션" │
│ 파이썬의 강력한 기능...    │   │                             │
│                            │   │ ├── Fragment (pre_text)     │
│ ```python                  │   │ │   "리스트 컴프리헨션은..." │
│ result = [x*2 for x in     │   │ │                           │
│           range(10)]       │   │ ├── Fragment (python)       │
│ ```                        │   │ │   "result = [x*2...]"     │
│                            │   │ │                           │
│ 결과: [0, 2, 4, 6, ...]    │   │ └── Fragment (post_text)    │
└────────────────────────────┘   │     "결과: [0, 2, 4,...]"   │
                                 └────────────────────────────┘

이점: 설명 + 코드 + 결과가 같은 unit_id로 연결됨
```

#### SegmentUnitizer 동작 원리

**참조 파일**: `ingestion/segmentation.py:9-130`

```python
class SegmentUnitizer:
    """
    Group segments into semantic units that preserve Python/JS adjacency.
    A semantic unit groups related content together (e.g., explanatory text + code).
    """

    def __init__(
        self,
        attach_pre_text: bool = True,   # 코드 앞 설명 연결
        attach_post_text: bool = False,  # 코드 뒤 설명 연결
        bridge_text_max: int = 0,        # Python-JS 사이 텍스트 허용
        max_pre_text_chars: int = 4000,  # pre_text 최대 길이
    ):
        ...
```

**처리 흐름**:

```
입력: [text, text, code(python), text, code(javascript), text]

처리:
1. text 버퍼링
2. Python 코드 발견 → 새 unit_id 생성
3. 버퍼된 text를 pre_text로 연결
4. Python 코드 연속 수집
5. JavaScript 코드 발견 → 같은 unit_id로 연결
6. post_text 옵션에 따라 후속 텍스트 연결

출력:
[
  UnitizedSegment(unit_id="abc", role="pre_text", segment),
  UnitizedSegment(unit_id="abc", role="python", segment),
  UnitizedSegment(unit_id="abc", role="javascript", segment),
  UnitizedSegment(unit_id=None, role="other", segment),  # 연결 안 됨
]
```

---

### 2.4 임베딩 필터링 규칙

모든 Fragment가 임베딩되는 것은 아닙니다. `EmbeddingValidator`가 다음 규칙을 적용합니다:

**참조 파일**: `embedding/validators.py`

#### 규칙 1: 최소 길이 (FRAG-LEN-001)

```python
MIN_LENGTH = 10  # 10자 미만은 임베딩에서 제외

# 이유: 짧은 텍스트는 의미적 표현력이 부족
# 예: "참조", "OK", "그림 1" → 임베딩 ❌
```

#### 규칙 2: 보일러플레이트 제외 (EMBED-BAN-003)

```python
# 저작권 패턴 (한국어 + 영어)
COPYRIGHT_PATTERNS = [
    r"^(?i:copyright|COPYRIGHT|저작권)\s+©?\s*\d{4}",
    r"^(?i:all\s+rights\s+reserved|무단\s*전재)",
]

# 페이지 번호 패턴
PAGE_NUMBER_PATTERNS = [
    r"^\s*(?i:page|페이지|쪽)\s*\d+\s*$",
    r"^\s*\d+\s*$",  # 순수 숫자
]
```

#### 규칙 3: 순수 참조 텍스트 제외 (EMBED-BAN-006)

```python
# 영어: "See Figure 3", "Refer to Table 1"
# 한국어: "그림 3 참조", "표 1 참고"
REFERENCE_PATTERNS = [
    r"^(?i:see|refer\s+to|reference)\s+(?i:figure|table)...",
    r"(그림|표|도표|사진)\s*\d+\s*(참조|참고|보기|확인)",
]
```

#### 필터링 프로세스

```
                    ┌─────────────────┐
                    │    Fragment     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ len(content)    │
                    │    >= 10?       │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ NO                          │ YES
              ▼                             ▼
        ┌───────────┐              ┌────────────────┐
        │ SKIP ❌    │              │ 보일러플레이트? │
        │ FRAG-LEN  │              └────────┬───────┘
        └───────────┘                       │
                              ┌─────────────┴─────────────┐
                              │ YES                       │ NO
                              ▼                           ▼
                        ┌───────────┐            ┌────────────────┐
                        │ SKIP ❌    │            │ 순수 참조?     │
                        │ EMBED-BAN │            └────────┬───────┘
                        └───────────┘                     │
                                          ┌───────────────┴───────────────┐
                                          │ YES                           │ NO
                                          ▼                               ▼
                                    ┌───────────┐                 ┌───────────┐
                                    │ SKIP ❌    │                 │ EMBED ✅   │
                                    └───────────┘                 └───────────┘
```

#### 코드 예시

```python
# embedding/validators.py:84-106
def is_eligible(self, fragment: Fragment) -> bool:
    """Check if fragment meets all requirements for embedding."""
    # FRAG-LEN-001: Minimum length check
    if len(fragment.content) < self.MIN_LENGTH:
        return False

    # EMBED-BAN-003: Reject boilerplate
    if self._is_boilerplate(fragment.content):
        return False

    # EMBED-BAN-006: Reject pure reference text
    if self._is_pure_reference(fragment.content):
        return False

    return True
```

---

### 2.5 결정적 doc_id

> **동일 콘텐츠 = 동일 ID (멱등성 보장)**

#### 규칙: EMBED-ID-002

```
doc_id = hash(parent_id + view + lang + content)
```

#### 왜 결정적 ID가 필요한가?

| 문제 | 랜덤 ID 사용 시 | 결정적 ID 사용 시 |
|------|----------------|------------------|
| 중복 임베딩 | 같은 콘텐츠가 여러 번 저장됨 | 자동 중복 방지 |
| 재실행 | 매번 새 ID 생성 → 누적 | 동일 ID → upsert |
| 동기화 | 어떤 게 최신인지 불분명 | 콘텐츠 기반 판단 |

#### 구현

**참조 파일**: `domain/entities.py:121-136`

```python
# domain/entities.py
def compute_doc_id(self) -> str:
    """
    Generate deterministic doc_id for this fragment.
    Rule: EMBED-ID-002 - doc_id = hash(parent_id + view + lang + content)
    """
    content_hash = ContentHash.compute(
        parent_id=self.concept_id,
        view=self.view,
        lang=self.language,
        content=self.content,
    )
    return content_hash.to_doc_id()  # 형식: "doc:{sha256_prefix}"
```

#### 해시 구성 요소

```
┌─────────────────────────────────────────────────────────────────┐
│                         doc_id 생성                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  parent_id   +   view   +   lang   +   content                  │
│  ─────────       ────       ────       ───────                  │
│  "concept-1"     TEXT       None       "HTTP 요청은..."         │
│                                                                  │
│              ┌─────────────────────────────┐                    │
│              │        SHA-256 해시          │                    │
│              └──────────────┬──────────────┘                    │
│                             │                                    │
│                             ▼                                    │
│              doc:a1b2c3d4e5f6g7h8...                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 문서 임베딩 후 구조

### 3.1 계층적 데이터 모델

문서가 임베딩되면 다음과 같은 계층 구조가 형성됩니다:

```
원본 파일 (예: python_guide.md)
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ Document                                                           │
│ ├── id: "doc-550e8400-e29b-41d4-a716-446655440000"                │
│ ├── source_path: "/books/python_guide.md"                         │
│ └── metadata: {"filename": "python_guide.md", "pages": 150}       │
└───────────────────────────────────────────────────────────────────┘
    │
    ├── Concept 1: "파이썬 소개"
    │   │
    │   ├── Fragment 1
    │   │   ├── id: "frag-001"
    │   │   ├── concept_id: "concept-001"  ← parent_id
    │   │   ├── content: "파이썬은 1991년에 귀도 반 로섬이 개발한..."
    │   │   ├── view: TEXT
    │   │   └── language: null
    │   │
    │   └── Fragment 2
    │       ├── id: "frag-002"
    │       ├── concept_id: "concept-001"
    │       ├── content: "print('Hello, World!')"
    │       ├── view: CODE
    │       └── language: "python"
    │
    ├── Concept 2: "변수와 타입"
    │   │
    │   ├── Fragment 3 (view=TEXT)
    │   ├── Fragment 4 (view=CODE, lang=python)
    │   └── Fragment 5 (view=TABLE)
    │
    └── ... (더 많은 Concept)
```

### 3.2 Multi-View 구조

하나의 Concept 안에 여러 종류의 Fragment가 공존합니다:

#### View 종류

| View | 설명 | 예시 |
|------|------|------|
| `TEXT` | 일반 텍스트 | "HTTP 요청은 클라이언트가..." |
| `CODE` | 코드 블록 | `import requests` |
| `IMAGE` | 이미지 참조 | alt text, 이미지 URL |
| `TABLE` | 표 데이터 | 마크다운 테이블 |
| `FIGURE` | 다이어그램/차트 | 플로우차트 설명 |
| `CAPTION` | 캡션 텍스트 | "그림 1: 시스템 아키텍처" |

#### View는 속성이다 (FRAG-VIEW-001)

```
❌ 잘못된 이해:
   View를 독립 엔티티로 취급

   Document
   ├── TextContent
   ├── CodeContent
   └── ImageContent

✅ 올바른 이해:
   View는 Fragment의 속성

   Document
   └── Concept
       ├── Fragment (view=TEXT)
       ├── Fragment (view=CODE)
       └── Fragment (view=IMAGE)
```

#### 코드 정의

**참조 파일**: `domain/value_objects.py`

```python
from enum import Enum

class View(str, Enum):
    """Fragment view types."""
    TEXT = "text"
    CODE = "code"
    IMAGE = "image"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
```

---

### 3.3 Parent-Child 관계

#### 소유권 체인

```
Embedding ─belongs to→ Fragment ─belongs to→ Concept ─belongs to→ Document
     │                      │                     │                    │
     │                      │                     │                    │
     ▼                      ▼                     ▼                    ▼
 fragment_id           concept_id            document_id           source_path
 (parent_id)           (parent_id)           (parent_id)
```

#### parent_id 불변성 (FRAG-IMMUT-001~003)

```python
# Fragment 생성 시 concept_id 확정
fragment = Fragment(
    id="frag-001",
    concept_id="concept-001",  # ← 이 값은 이후 변경 불가
    content="...",
    view=View.TEXT,
    ...
)

# ❌ 금지: parent_id 변경
fragment.concept_id = "concept-002"  # FRAG-IMMUT-002 위반!

# ✅ 허용: 새 Fragment 생성
new_fragment = Fragment(
    id="frag-002",
    concept_id="concept-002",  # 새 parent
    content="...",
    ...
)
```

#### 연쇄 삭제 (CASCADE-001~004)

```
Document 삭제
    │
    ├─── CASCADE-001 ───▶ 모든 하위 Concept 삭제
    │                          │
    │                          ├─── CASCADE-002 ───▶ 모든 하위 Fragment 삭제
    │                          │                          │
    │                          │                          └─── CASCADE-003 ───▶ 모든 Embedding 삭제
    │                          │
    └─────────────────── 고아 엔티티 없음 (CASCADE-004) ◀───────┘
```

---

### 3.4 저장 구조 (PostgreSQL + pgvector)

#### 테이블 구조

```sql
-- Document 저장
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Concept 저장 (Parent 문서)
CREATE TABLE concepts (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    "order" INTEGER,
    content TEXT,
    metadata JSONB
);

-- Fragment 저장
CREATE TABLE fragments (
    id TEXT PRIMARY KEY,
    concept_id TEXT REFERENCES concepts(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    view TEXT NOT NULL,  -- 'text', 'code', 'image', etc.
    language TEXT,       -- 'python', 'javascript', etc.
    "order" INTEGER,
    metadata JSONB
);

-- LangChain PGVector 통합 테이블
CREATE TABLE langchain_pg_embedding (
    id UUID PRIMARY KEY,
    collection_id UUID REFERENCES langchain_pg_collection(uuid),
    document TEXT,        -- Fragment content
    embedding vector(768),-- 벡터
    cmetadata JSONB       -- 메타데이터 (parent_id, view, lang, etc.)
);

-- Parent 문서 저장 (맥락 제공용)
CREATE TABLE docstore_parent (
    id TEXT PRIMARY KEY,  -- concept_id
    content TEXT,         -- Concept 전체 내용
    metadata JSONB
);
```

#### 인덱스 구조

```sql
-- 벡터 유사도 검색용 HNSW 인덱스
CREATE INDEX ON langchain_pg_embedding
USING hnsw (embedding vector_cosine_ops);

-- 메타데이터 필터링용 GIN 인덱스
CREATE INDEX ON langchain_pg_embedding
USING GIN (cmetadata jsonb_path_ops);

-- 자주 사용하는 필터 컬럼용 BTREE 인덱스
CREATE INDEX ON langchain_pg_embedding (
    (cmetadata->>'source'),
    (cmetadata->>'view'),
    (cmetadata->>'lang')
);
```

#### 데이터 흐름

```
                    ┌─────────────────┐
                    │  IngestUseCase  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   documents   │  │    concepts   │  │   fragments   │
│    테이블     │  │     테이블    │  │     테이블    │
└───────────────┘  └───────┬───────┘  └───────┬───────┘
                           │                   │
                           ▼                   ▼
                  ┌───────────────┐  ┌────────────────────┐
                  │docstore_parent│  │langchain_pg_embedding│
                  │ (맥락 제공)   │  │  (벡터 검색 대상)    │
                  └───────────────┘  └────────────────────┘
```

---

## 4. 검색 시 맥락 유지가 효과적인 이유

### 4.1 핵심 원칙: SEARCH-SEP

> **검색 대상과 맥락 제공자를 분리한다**

**참조 규칙**: SEARCH-SEP-001 ~ SEARCH-SEP-004

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SEARCH-SEP 원칙                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   검색 대상          │          맥락 제공자                          │
│   ──────────         │          ──────────                          │
│   Fragment 임베딩    │          Parent Concept                       │
│                      │                                               │
│   ┌──────────────┐   │   ┌────────────────────────────────────────┐ │
│   │ 작은 조각    │   │   │ 큰 맥락                                 │ │
│   │ 높은 정밀도  │   │   │ 풍부한 정보                             │ │
│   │ 빠른 검색    │   │   │ 연관 Fragment 포함                      │ │
│   └──────────────┘   │   └────────────────────────────────────────┘ │
│                      │                                               │
│   "Python HTTP"      │   "이 장에서는 Python의 requests 라이브러리  │
│   → 코드 조각 검색   │    를 사용한 HTTP 요청 방법을 설명합니다..." │
│                      │                                               │
└─────────────────────────────────────────────────────────────────────┘
```

#### 역할 혼용 금지 (SEARCH-SEP-004)

```
❌ 잘못된 구현:
   Fragment로 검색하고 Fragment만 반환
   → 맥락 없는 결과

❌ 잘못된 구현:
   Concept (Parent) 전체를 임베딩하고 검색
   → 검색 정밀도 저하

✅ 올바른 구현:
   Fragment로 검색 + Parent로 맥락 제공
   → 정밀한 검색 + 풍부한 맥락
```

---

### 4.2 검색 파이프라인

**참조 파일**: `retrieval/pipeline.py`

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RetrievalPipeline                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Stage 1            Stage 2            Stage 3            Stage 4  │
│   ────────           ────────           ────────           ──────── │
│                                                                      │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌─────────┐│
│   │  Query   │ ───▶ │  Vector  │ ───▶ │  Context │ ───▶ │  Result ││
│   │Interpreter│     │  Search  │      │ Expander │      │ Grouper ││
│   └──────────┘      └──────────┘      └──────────┘      └─────────┘│
│                                                                      │
│   - 쿼리 파싱       - pgvector        - Parent 조회    - 중복 제거  │
│   - 필터 추출         유사도 검색     - 맥락 첨부      - 그룹화     │
│   - 쿼리 임베딩                                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 파이프라인 코드

```python
# retrieval/pipeline.py:41-84
def retrieve(
    self,
    query: str,
    view: Optional[str] = None,
    language: Optional[str] = None,
    top_k: int = 10,
    expand_context: bool = True,
    deduplicate: bool = True,
) -> List[ExpandedResult]:
    """Execute complete retrieval pipeline."""

    # Stage 1: Query interpretation
    query_plan = self.query_interpreter.interpret(
        query=query,
        view=view,
        language=language,
        top_k=top_k,
    )

    # Stage 2: Vector similarity search
    search_results = self.search_engine.search(query_plan)

    # Optional: Deduplicate
    if deduplicate:
        search_results = self.grouper.deduplicate_by_content(search_results)

    # Stage 3: Context expansion
    if expand_context:
        expanded_results = self.context_expander.expand(search_results)
    else:
        expanded_results = [ExpandedResult(result=r) for r in search_results]

    return expanded_results
```

---

### 4.3 ContextExpander의 동작

**참조 파일**: `retrieval/context.py`

#### 동작 흐름

```
입력: [SearchResult, SearchResult, SearchResult, ...]
         │              │              │
         │              │              │
         ▼              ▼              ▼
      parent_id      parent_id      parent_id
      "concept-1"    "concept-2"    "concept-1"  (중복 있음)
         │              │              │
         └──────────────┴──────────────┘
                        │
                        ▼
              unique: {"concept-1", "concept-2"}
                        │
                        ▼
         ┌──────────────────────────────┐
         │      docstore_parent         │
         │         테이블 조회          │
         │                              │
         │  SELECT id, content, metadata│
         │  FROM docstore_parent        │
         │  WHERE id = ANY($parent_ids) │
         └──────────────────────────────┘
                        │
                        ▼
              parent_map = {
                "concept-1": {content: "...", metadata: {...}},
                "concept-2": {content: "...", metadata: {...}},
              }
                        │
                        ▼
              각 SearchResult에 Parent 첨부
                        │
                        ▼
출력: [ExpandedResult, ExpandedResult, ExpandedResult, ...]
           │
           ├── result: SearchResult (원본)
           ├── parent_content: "..." (Parent 전체 내용)
           └── parent_metadata: {...}
```

#### 구현 코드

```python
# retrieval/context.py:57-93
def expand(self, results: List[SearchResult]) -> List[ExpandedResult]:
    """Expand search results with parent context."""
    if not results or not self.config.pg_conn:
        return [ExpandedResult(result=r) for r in results]

    # Extract unique parent IDs
    parent_ids = list({r.parent_id for r in results})

    # Fetch parent documents
    parent_map = self._fetch_parents(parent_ids)

    # Attach parent context to results
    expanded = []
    for result in results:
        parent = parent_map.get(result.parent_id)
        if parent:
            expanded.append(
                ExpandedResult(
                    result=result,
                    parent_content=parent.get("content"),
                    parent_metadata=parent.get("metadata"),
                )
            )
        else:
            expanded.append(ExpandedResult(result=result))

    return expanded
```

---

### 4.4 왜 효과적인가?

#### 문제 1: 단순 청킹의 맥락 손실

```
문제: 고정 크기로 자르면 의미 단위가 분리됨

원본:
┌────────────────────────────────────────────────────────────────────┐
│ HTTP 요청을 보내려면 requests 라이브러리를 사용합니다.             │
│                                                                     │
│ ```python                                                           │
│ import requests                                                     │
│ response = requests.get('https://api.example.com/data')            │
│ print(response.json())                                              │
│ ```                                                                 │
│                                                                     │
│ 위 코드는 GET 요청을 보내고 JSON 응답을 파싱합니다.                │
└────────────────────────────────────────────────────────────────────┘

❌ 고정 크기 청킹 (500자):
   - 청크 1: "HTTP 요청을 보내려면... import requests"  (코드 잘림)
   - 청크 2: "response = requests... 파싱합니다."      (설명과 코드 혼합)

✅ Semantic Unit:
   - Concept: "HTTP 요청 예제"
     - Fragment (pre_text): "HTTP 요청을 보내려면..."
     - Fragment (code): "import requests..."
     - Fragment (post_text): "위 코드는 GET 요청을..."
```

#### 문제 2: 검색 정밀도 vs 맥락 풍부성 Trade-off

```
┌────────────────────────────────────────────────────────────────────┐
│                    전통적 접근 방식의 딜레마                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   선택 A: 큰 덩어리 임베딩                                          │
│   ────────────────────────                                          │
│   [전체 페이지를 하나의 벡터로]                                     │
│                                                                     │
│   장점: 맥락 풍부                                                   │
│   단점: 검색 부정확 (관련 없는 내용이 유사도에 영향)                │
│                                                                     │
│   선택 B: 작은 조각 임베딩                                          │
│   ────────────────────────                                          │
│   [한 문장씩 벡터로]                                                │
│                                                                     │
│   장점: 검색 정밀                                                   │
│   단점: 맥락 부족 (결과만 보면 무슨 내용인지 모름)                  │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘

                              │
                              ▼

┌────────────────────────────────────────────────────────────────────┐
│                    본 시스템의 해결책                               │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   검색: Fragment로 (정밀도 ↑)                                       │
│   결과: Parent와 함께 (맥락 ↑)                                      │
│                                                                     │
│   ┌─────────────┐          ┌─────────────────────────────────────┐ │
│   │  Fragment   │  ──────▶ │        Expanded Result              │ │
│   │  (검색됨)   │          │                                     │ │
│   │             │          │  fragment:                          │ │
│   │ "import     │          │    content: "import requests..."    │ │
│   │  requests"  │          │    view: code                       │ │
│   │             │          │    similarity: 0.95                 │ │
│   └─────────────┘          │                                     │ │
│                            │  parent_content:                    │ │
│                            │    "HTTP 요청을 보내려면 requests   │ │
│                            │     라이브러리를 사용합니다..."      │ │
│                            │                                     │ │
│                            │  sibling_views: [text, code, text]  │ │
│                            └─────────────────────────────────────┘ │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

#### 문제 3: Multi-View 콘텐츠

```
사용자 쿼리: "Python으로 HTTP 요청 보내기"

┌────────────────────────────────────────────────────────────────────┐
│                        검색 과정                                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Step 1: Vector Search (Fragment 대상)                            │
│   ─────────────────────────────────────                            │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │ langchain_pg_embedding                                        │ │
│   │                                                               │ │
│   │ SELECT * FROM ... ORDER BY embedding <=> $query_vec LIMIT 5  │ │
│   │                                                               │ │
│   │ 결과:                                                         │ │
│   │ 1. Fragment: "import requests" (view=code, sim=0.95)         │ │
│   │ 2. Fragment: "requests.get()" (view=code, sim=0.89)          │ │
│   │ 3. Fragment: "HTTP 요청 라이브러리" (view=text, sim=0.82)    │ │
│   └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│   Step 2: Context Expansion (Parent 조회)                          │
│   ───────────────────────────────────────                          │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │ docstore_parent                                               │ │
│   │                                                               │ │
│   │ 각 Fragment의 parent_id로 Concept 조회                        │ │
│   │                                                               │ │
│   │ 결과:                                                         │ │
│   │ Concept "HTTP 요청 가이드":                                   │ │
│   │   - 설명 텍스트 (view=text)                                   │ │
│   │   - 예제 코드 (view=code) ← 검색됨                            │ │
│   │   - 다이어그램 (view=image)                                   │ │
│   │   - 출력 결과 (view=text)                                     │ │
│   └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│   Step 3: 최종 결과                                                │
│   ─────────────────                                                │
│                                                                     │
│   사용자는 검색된 코드 + 관련 설명 + 다이어그램을 함께 받음         │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

#### 결과 구조

```json
{
  "results": [
    {
      "fragment": {
        "id": "frag-123",
        "content": "import requests\nresponse = requests.get('...')",
        "view": "code",
        "language": "python",
        "similarity": 0.95
      },
      "context": {
        "parent_id": "concept-001",
        "parent_content": "HTTP 요청을 보내려면 requests 라이브러리를 사용합니다. 이 라이브러리는 Python에서 가장 널리 사용되는 HTTP 클라이언트입니다...",
        "sibling_fragments": [
          {"view": "text", "content": "HTTP 요청을 보내려면..."},
          {"view": "image", "content": "Figure 1: HTTP 요청 흐름"},
          {"view": "text", "content": "위 코드는 GET 요청을..."}
        ]
      }
    },
    ...
  ]
}
```

---

## 5. 핵심 다이어그램

### 5.1 전체 아키텍처 흐름

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   [파일]        [Parser]         [RawSegment]        [SegmentUnitizer]      │
│      │              │                  │                      │              │
│      │   .md/.pdf   │                  │                      │              │
│      │   .txt       │                  │                      │              │
│      ▼              ▼                  ▼                      ▼              │
│   ┌─────┐      ┌─────────┐      ┌───────────┐      ┌──────────────────┐    │
│   │book │ ───▶ │Markdown │ ───▶ │ text      │ ───▶ │  UnitizedSegment │    │
│   │.md  │      │Parser   │      │ code      │      │                  │    │
│   └─────┘      │         │      │ image     │      │  unit_id: abc    │    │
│                │Pdf      │      │ table     │      │  role: pre_text  │    │
│                │Parser   │      │           │      │                  │    │
│                │         │      │           │      │  unit_id: abc    │    │
│                │Ocr      │      │           │      │  role: python    │    │
│                │Parser   │      │           │      └──────────────────┘    │
│                └─────────┘      └───────────┘              │                │
│                                                             │                │
│                                                             ▼                │
│                                                     ┌──────────────┐        │
│                                                     │ConceptBuilder│        │
│                                                     └──────┬───────┘        │
│                                                             │                │
├─────────────────────────────────────────────────────────────┼────────────────┤
│                                                             │                │
│                                                             ▼                │
│                 ┌─────────────────────────────────────────────────┐         │
│                 │                    domain                        │         │
│                 │                                                  │         │
│                 │   Document ─────▶ Concept ─────▶ Fragment        │         │
│                 │                                      │           │         │
│                 └──────────────────────────────────────┼───────────┘         │
│                                                        │                     │
├────────────────────────────────────────────────────────┼─────────────────────┤
│                                                        │                     │
│                                                        ▼                     │
│                                               ┌────────────────┐             │
│                                               │EmbeddingValidator│           │
│                                               │                 │            │
│                                               │ FRAG-LEN-001 ✓  │            │
│                                               │ EMBED-BAN-* ✓   │            │
│                                               └────────┬────────┘            │
│                                                        │                     │
│                                        ┌───────────────┴───────────────┐     │
│                                        │                               │     │
│                                        ▼                               ▼     │
│                                   [eligible]                      [filtered] │
│                                        │                               │     │
│                                        ▼                               ▼     │
│                               ┌────────────────┐                  (저장만,   │
│                               │EmbeddingProvider│                  임베딩 X)│
│                               │   (Gemini/     │                             │
│                               │    Voyage AI)  │                             │
│                               └────────┬───────┘                             │
│                                        │                                     │
│                                        ▼                                     │
│                                    Embedding                                 │
│                                 [vector[768]]                                │
│                                        │                                     │
├────────────────────────────────────────┼─────────────────────────────────────┤
│                              STORAGE   │                                     │
│                                        ▼                                     │
│    ┌────────────┐  ┌────────────┐  ┌────────────────────┐                   │
│    │ documents  │  │  concepts  │  │langchain_pg_embedding│                 │
│    │   table    │  │   table    │  │       table        │                   │
│    └────────────┘  └─────┬──────┘  └────────────────────┘                   │
│                          │                                                   │
│                          ▼                                                   │
│                   ┌────────────────┐                                         │
│                   │ docstore_parent│  ← 맥락 제공용                          │
│                   │     table      │                                         │
│                   └────────────────┘                                         │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 검색 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RETRIEVAL FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   [사용자 쿼리]                                                              │
│   "Python HTTP 요청"                                                         │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────┐                                                        │
│   │ QueryInterpreter│                                                        │
│   │                 │                                                        │
│   │ - 쿼리 임베딩   │                                                        │
│   │ - 필터 추출    │                                                        │
│   │   view: code   │                                                        │
│   │   lang: python │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │VectorSearchEngine│                                                       │
│   │                 │                                                        │
│   │ pgvector 검색   │                                                        │
│   │ <=> 연산자     │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                      Search Results                                 │    │
│   │                                                                     │    │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │    │
│   │   │  Fragment 1 │  │  Fragment 2 │  │  Fragment 3 │                │    │
│   │   │  sim: 0.95  │  │  sim: 0.89  │  │  sim: 0.82  │                │    │
│   │   │  parent: A  │  │  parent: A  │  │  parent: B  │                │    │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │    │
│   │          │                │                │                        │    │
│   └──────────┼────────────────┼────────────────┼────────────────────────┘    │
│              │                │                │                             │
│              └────────────────┴────────────────┘                             │
│                              │                                               │
│                              ▼                                               │
│                     unique parent_ids                                        │
│                        [A, B]                                                │
│                              │                                               │
│                              ▼                                               │
│                    ┌─────────────────┐                                       │
│                    │ ContextExpander │                                       │
│                    │                 │                                       │
│                    │ docstore_parent │                                       │
│                    │ 테이블 조회     │                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│                             ▼                                                │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                      Expanded Results                               │    │
│   │                                                                     │    │
│   │   ┌───────────────────────────────────────────────────────────┐    │    │
│   │   │  ExpandedResult 1                                          │    │    │
│   │   │  ├── fragment: "import requests..."                        │    │    │
│   │   │  ├── parent_content: "HTTP 요청 가이드 전체 내용..."       │    │    │
│   │   │  └── parent_metadata: {source: "book.md", page: 42}       │    │    │
│   │   └───────────────────────────────────────────────────────────┘    │    │
│   │                                                                     │    │
│   │   ┌───────────────────────────────────────────────────────────┐    │    │
│   │   │  ExpandedResult 2                                          │    │    │
│   │   │  ├── fragment: "response = requests.get()..."             │    │    │
│   │   │  ├── parent_content: (같은 Parent A)                       │    │    │
│   │   │  └── parent_metadata: ...                                  │    │    │
│   │   └───────────────────────────────────────────────────────────┘    │    │
│   │                                                                     │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                             │                                                │
│                             ▼                                                │
│                    ┌─────────────────┐                                       │
│                    │  ResultGrouper  │                                       │
│                    │                 │                                       │
│                    │ - 중복 제거     │                                       │
│                    │ - Parent별 그룹 │                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│                             ▼                                                │
│                       [최종 결과]                                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Parent-Child 검색 모델

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Parent-Child 검색 모델                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         Concept (Parent)                             │   │
│   │                    "Python HTTP 요청 가이드"                         │   │
│   │                                                                      │   │
│   │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │   │
│   │   │  Fragment   │   │  Fragment   │   │  Fragment   │               │   │
│   │   │  (text)     │   │  (code)     │   │  (image)    │               │   │
│   │   │             │   │             │   │             │               │   │
│   │   │ "HTTP 요청  │   │ "import     │   │ "Figure 1:  │               │   │
│   │   │  을 보내    │   │  requests"  │   │  HTTP 흐름" │               │   │
│   │   │  려면..."   │   │             │   │             │               │   │
│   │   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘               │   │
│   │          │                 │                 │                       │   │
│   │          ▼                 ▼                 ▼                       │   │
│   │      Embedding         Embedding         Embedding                   │   │
│   │      vec[768]          vec[768]          vec[768]                    │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                         Vector Search                                 │  │
│   │                                                                       │  │
│   │    쿼리: "Python HTTP 요청 보내기"                                    │  │
│   │                                                                       │  │
│   │    가장 유사한 Fragment: (code) "import requests..."                 │  │
│   │    similarity: 0.95                                                  │  │
│   │                                                                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    ▼                                         │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                       Context Expansion                               │  │
│   │                                                                       │  │
│   │    검색된 Fragment의 parent_id → Concept 조회                         │  │
│   │                                                                       │  │
│   │    ┌──────────────────────────────────────────────────────────────┐  │  │
│   │    │                    최종 결과                                  │  │  │
│   │    │                                                               │  │  │
│   │    │  검색됨: Fragment (code) "import requests..."                │  │  │
│   │    │  +                                                            │  │  │
│   │    │  맥락:                                                        │  │  │
│   │    │    - 설명: "HTTP 요청을 보내려면..."                          │  │  │
│   │    │    - 다이어그램: "Figure 1: HTTP 흐름"                        │  │  │
│   │    │    - 전체 Parent 내용                                        │  │  │
│   │    │                                                               │  │  │
│   │    └──────────────────────────────────────────────────────────────┘  │  │
│   │                                                                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 도메인 규칙 참조

본 문서에서 언급된 도메인 규칙들의 요약입니다. 전체 내용은 `docs/DOMAIN_RULES.md`를 참조하세요.

### 엔티티 계층 규칙 (HIER-*)

| 규칙 ID | 규칙 |
|---------|------|
| HIER-001 | Fragment는 반드시 정확히 하나의 Concept에 귀속되어야 한다 |
| HIER-002 | Concept은 반드시 정확히 하나의 Document에 귀속되어야 한다 |
| HIER-003 | 모든 Fragment는 유효한 `parent_id`를 가져야 한다 |
| HIER-004 | `parent_id`는 Fragment 생성 시점에 확정되며 이후 변경 불가 |

### 임베딩 규칙 (EMBED-*)

| 규칙 ID | 규칙 |
|---------|------|
| EMBED-BAN-001 | 파일 경로 및 메타데이터는 임베딩되어서는 안 된다 |
| EMBED-BAN-002 | 10자 미만의 짧은 텍스트는 임베딩되어서는 안 된다 |
| EMBED-BAN-003 | 반복되는 보일러플레이트는 임베딩되어서는 안 된다 |
| EMBED-BAN-006 | 순수 참조 정보 ("그림 3 참조" 등)는 임베딩되어서는 안 된다 |
| EMBED-ID-002 | `doc_id = hash(parent_id + view + lang + content)` 형식 |
| EMBED-OWN-001 | 모든 임베딩은 정확히 하나의 Fragment에 귀속되어야 한다 |

### Fragment 규칙 (FRAG-*)

| 규칙 ID | 규칙 |
|---------|------|
| FRAG-LEN-001 | 임베딩 대상 Fragment는 최소 10자 이상이어야 한다 |
| FRAG-VIEW-001 | View는 Fragment의 속성이다, 독립 엔티티가 아니다 |
| FRAG-IMMUT-001 | Fragment 생성 시점에 `parent_id`가 확정된다 |
| FRAG-IMMUT-002 | 생성 후 `parent_id` 변경은 금지된다 |

### 검색 규칙 (SEARCH-*)

| 규칙 ID | 규칙 |
|---------|------|
| SEARCH-SEP-001 | 검색 대상(Fragment)과 맥락 제공자(Parent)는 분리되어야 한다 |
| SEARCH-SEP-002 | 검색: Fragment 임베딩을 대상으로 한다 |
| SEARCH-SEP-003 | 맥락: Parent 문서에서 제공한다 |
| SEARCH-SEP-004 | 두 역할을 혼용하는 구현은 금지된다 |
| SEARCH-RES-001 | 검색 결과는 반드시 맥락과 함께 반환되어야 한다 |

### 연쇄 삭제 규칙 (CASCADE-*)

| 규칙 ID | 규칙 |
|---------|------|
| CASCADE-001 | Document 삭제 시 모든 하위 Concept이 연쇄 삭제 |
| CASCADE-002 | Concept 삭제 시 모든 하위 Fragment가 연쇄 삭제 |
| CASCADE-003 | Fragment 삭제 시 해당 임베딩이 연쇄 삭제 |
| CASCADE-004 | 연쇄 삭제 후 고아 엔티티가 남아서는 안 된다 |

### 안티패턴 규칙 (ANTI-*)

| 규칙 ID | 규칙 |
|---------|------|
| ANTI-CHUNK-001 | 의미 경계를 무시하고 고정 크기로 문서를 분할하는 것은 금지 |
| ANTI-CHUNK-002 | 의미 단위를 먼저 식별하고, 그 후에 필요시 청킹해야 한다 |
| ANTI-VIEW-001 | text, code, image를 독립적인 최상위 엔티티로 취급 금지 |
| ANTI-VIEW-002 | View는 Fragment의 속성으로만 취급해야 한다 |

---

## 부록: 참조 파일

| 파일 | 설명 |
|------|------|
| `domain/entities.py` | 핵심 엔티티 정의 (Document, Concept, Fragment, Embedding) |
| `domain/value_objects.py` | View enum 정의 |
| `ingestion/segmentation.py` | SegmentUnitizer - 의미 단위 그룹화 |
| `ingestion/concept_builder.py` | UnitizedSegment → Concept + Fragment 변환 |
| `embedding/validators.py` | EmbeddingValidator - 임베딩 적격 검사 |
| `retrieval/pipeline.py` | RetrievalPipeline - 검색 파이프라인 |
| `retrieval/context.py` | ContextExpander - 맥락 확장 |
| `storage/cascade.py` | CascadeDeleter - 연쇄 삭제 |
| `docs/DOMAIN_RULES.md` | 전체 도메인 규칙집 |
| `docs/PACKAGE_RULES.md` | 패키지 구조 및 의존성 규칙 |

---

*이 문서는 OCR Vector DB 프로젝트의 기술 해설서입니다.*
*작성일: 2026-01-01*
