# 02. Adapter 패턴 심층 분석

> LLM 프로바이더 차이점 캡슐화 - OpenAI와 Gemini의 차이를 숨기다

---

## 1. 파일 정보

| 파일 | 라인 수 | 역할 |
|------|---------|------|
| `src/adapters/__init__.py` | 40줄 | 레지스트리 및 팩토리 |
| `src/adapters/base.py` | 63줄 | 추상 베이스 클래스 |
| `src/adapters/openai.py` | 50줄 | OpenAI 어댑터 |
| `src/adapters/gemini.py` | 57줄 | Gemini 어댑터 |

---

## 2. 왜 Adapter 패턴이 필요한가?

### 2.1 LLM 프로바이더별 차이점

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      프로바이더별 차이점                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────┐    ┌─────────────────────────────┐    │
│   │          OpenAI             │    │          Gemini             │    │
│   ├─────────────────────────────┤    ├─────────────────────────────┤    │
│   │                             │    │                             │    │
│   │ chunk.content 형식:         │    │ chunk.content 형식:         │    │
│   │ "텍스트" (str)              │    │ [{"type": "text",           │    │
│   │                             │    │   "text": "텍스트"}]        │    │
│   │                             │    │ (list[dict])                │    │
│   │                             │    │                             │    │
│   │ 인스턴스 재사용:            │    │ 인스턴스 재사용:            │    │
│   │ ✅ 가능                     │    │ ⚠️ 제한적                   │    │
│   │                             │    │ (httpx 이벤트 루프 바인딩)  │    │
│   │                             │    │                             │    │
│   │ 스트리밍 안정성:            │    │ 스트리밍 안정성:            │    │
│   │ ✅ 높음                     │    │ ⚠️ 이벤트 루프 주의         │    │
│   │                             │    │                             │    │
│   └─────────────────────────────┘    └─────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Adapter 패턴으로 해결

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Adapter 패턴 적용                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                       ┌─────────────────────┐                           │
│                       │     Supervisor      │                           │
│                       │                     │                           │
│                       │ adapter.create_llm()│                           │
│                       │ adapter.normalize() │                           │
│                       └──────────┬──────────┘                           │
│                                  │                                       │
│                                  │ 인터페이스만 알면 됨                  │
│                                  ▼                                       │
│                       ┌─────────────────────┐                           │
│                       │   BaseLLMAdapter    │                           │
│                       │     (Abstract)      │                           │
│                       │                     │                           │
│                       │ + create_llm()      │                           │
│                       │ + normalize_chunk() │                           │
│                       │ + provider_name     │                           │
│                       └──────────┬──────────┘                           │
│                                  │                                       │
│                    ┌─────────────┴─────────────┐                        │
│                    │                           │                         │
│                    ▼                           ▼                         │
│         ┌─────────────────────┐    ┌─────────────────────┐             │
│         │   OpenAIAdapter     │    │   GeminiAdapter     │             │
│         │                     │    │                     │             │
│         │ str → str           │    │ list → str          │             │
│         │ (변환 불필요)        │    │ (파싱 필요)         │             │
│         └─────────────────────┘    └─────────────────────┘             │
│                                                                          │
│   ✅ Supervisor는 프로바이더 차이를 몰라도 됨                            │
│   ✅ 새 프로바이더 추가 시 Supervisor 코드 수정 불필요                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 코드 분석

### 3.1 base.py - 추상 베이스 클래스

```python
# src/adapters/base.py

"""LLM Adapter 베이스 클래스"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel


@dataclass
class NormalizedChunk:
    """정규화된 스트리밍 청크

    모든 LLM 프로바이더의 청크를 통일된 형식으로 변환
    """
    text: str


class BaseLLMAdapter(ABC):
    """LLM Adapter 추상 베이스 클래스

    각 LLM 프로바이더별 차이점을 캡슐화:
    - LLM 인스턴스 생성 방식
    - 스트리밍 청크 형식 정규화
    - 인스턴스 재사용 전략 (캐싱 vs 매번 생성)
    """

    @abstractmethod
    def create_llm(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        """LLM 인스턴스 생성"""
        pass

    @abstractmethod
    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """스트리밍 청크를 정규화된 형식으로 변환"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """프로바이더 이름 (로깅/디버깅용)"""
        pass
```

### 인터페이스 설계 원칙

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     BaseLLMAdapter 인터페이스                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ create_llm(model, temperature, max_tokens) → BaseChatModel      │   │
│   │                                                                  │   │
│   │ 책임: LLM 인스턴스 생성                                          │   │
│   │ 입력: 모델명, 온도, 최대 토큰                                    │   │
│   │ 출력: LangChain BaseChatModel (모든 LLM의 공통 인터페이스)       │   │
│   │                                                                  │   │
│   │ OpenAI: ChatOpenAI 반환                                         │   │
│   │ Gemini: ChatGoogleGenerativeAI 반환                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ normalize_chunk(chunk) → NormalizedChunk                        │   │
│   │                                                                  │   │
│   │ 책임: 스트리밍 청크 정규화                                       │   │
│   │ 입력: 프로바이더별 원본 청크 (AIMessageChunk)                    │   │
│   │ 출력: 통일된 NormalizedChunk(text=str)                          │   │
│   │                                                                  │   │
│   │ OpenAI: chunk.content (str) → NormalizedChunk(text=str)         │   │
│   │ Gemini: chunk.content (list) → 파싱 → NormalizedChunk(text=str) │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ provider_name: str (property)                                   │   │
│   │                                                                  │   │
│   │ 책임: 프로바이더 식별                                            │   │
│   │ 용도: 로깅, 디버깅, 헬스체크 응답                                │   │
│   │                                                                  │   │
│   │ OpenAI: "openai"                                                │   │
│   │ Gemini: "gemini"                                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 3.2 openai.py - OpenAI 어댑터

```python
# src/adapters/openai.py

"""OpenAI LLM Adapter"""
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from .base import BaseLLMAdapter, NormalizedChunk
from config import config


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI LLM Adapter

    특징:
    - chunk.content가 str 형식
    - 인스턴스 재사용 가능 (캐싱 OK)
    - 이벤트 루프 문제 없음
    """

    def create_llm(
        self,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        return ChatOpenAI(
            model=model or config.OPENAI_MODEL,    # 기본: gpt-4o
            temperature=temperature,
            api_key=config.OPENAI_API_KEY,
            max_tokens=max_tokens,
            streaming=True                          # 스트리밍 활성화
        )

    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """OpenAI 청크 정규화

        OpenAI 형식: chunk.content = "텍스트" (str)
        """
        content = chunk.content if chunk else ""

        if isinstance(content, str):
            return NormalizedChunk(text=content)

        # 예상치 못한 형식 처리 (방어 코드)
        return NormalizedChunk(text=str(content) if content else "")

    @property
    def provider_name(self) -> str:
        return "openai"
```

### OpenAI 청크 구조

```python
# OpenAI 스트리밍 청크 예시

# on_chat_model_stream 이벤트에서 받는 chunk
AIMessageChunk(
    content="안녕",           # ← str 형식 (단순)
    id="run-abc123",
    response_metadata={...}
)

# 다음 청크
AIMessageChunk(
    content="하세요",
    id="run-abc123",
    ...
)

# normalize_chunk 결과
NormalizedChunk(text="안녕")
NormalizedChunk(text="하세요")
```

---

### 3.3 gemini.py - Gemini 어댑터

```python
# src/adapters/gemini.py

"""Gemini LLM Adapter"""
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel

from .base import BaseLLMAdapter, NormalizedChunk
from config import config


class GeminiAdapter(BaseLLMAdapter):
    """Google Gemini LLM Adapter

    특징:
    - chunk.content가 list[dict] 형식: [{"type": "text", "text": "..."}]
    - httpx 클라이언트가 첫 번째 이벤트 루프에 바인딩됨
    - Streamlit 환경에서 매 요청마다 새 인스턴스 필요
    """

    def create_llm(
        self,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        return ChatGoogleGenerativeAI(
            model=model or config.GEMINI_MODEL,    # 기본: gemini-2.0-flash
            google_api_key=config.GOOGLE_API_KEY,
            temperature=temperature,
            max_output_tokens=max_tokens,
            # streaming 파라미터 없음 - 기본 지원
        )

    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """Gemini 청크 정규화

        Gemini 형식: chunk.content = [{"type": "text", "text": "..."}] (list)
        """
        content = chunk.content if chunk else ""

        # Case 1: 이미 str인 경우 (비스트리밍 응답)
        if isinstance(content, str):
            return NormalizedChunk(text=content)

        # Case 2: list[dict] 형식 (스트리밍 청크)
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    texts.append(item.get("text", ""))
            return NormalizedChunk(text="".join(texts))

        # Case 3: 예상치 못한 형식 (방어 코드)
        return NormalizedChunk(text=str(content) if content else "")

    @property
    def provider_name(self) -> str:
        return "gemini"
```

### Gemini 청크 구조

```python
# Gemini 스트리밍 청크 예시

# on_chat_model_stream 이벤트에서 받는 chunk
AIMessageChunk(
    content=[                           # ← list[dict] 형식 (복잡)
        {
            "type": "text",
            "text": "안녕"
        }
    ],
    id="run-xyz789",
    response_metadata={...}
)

# 다음 청크
AIMessageChunk(
    content=[
        {
            "type": "text",
            "text": "하세요"
        }
    ],
    ...
)

# normalize_chunk 결과 (동일한 출력)
NormalizedChunk(text="안녕")
NormalizedChunk(text="하세요")
```

### OpenAI vs Gemini 비교

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        청크 정규화 비교                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   OpenAI 원본:                    Gemini 원본:                          │
│   ┌─────────────────────┐         ┌─────────────────────────────────┐   │
│   │ chunk.content =     │         │ chunk.content = [               │   │
│   │   "안녕하세요"       │         │   {"type": "text",              │   │
│   │                     │         │    "text": "안녕하세요"}        │   │
│   │ (str)               │         │ ]                               │   │
│   └─────────────────────┘         │ (list[dict])                    │   │
│            │                       └─────────────────────────────────┘   │
│            │                                    │                        │
│            ▼                                    ▼                        │
│   ┌─────────────────────┐         ┌─────────────────────────────────┐   │
│   │ normalize_chunk()   │         │ normalize_chunk()               │   │
│   │                     │         │                                 │   │
│   │ if isinstance(str): │         │ if isinstance(list):            │   │
│   │   return as-is      │         │   for item in content:          │   │
│   │                     │         │     texts.append(item["text"])  │   │
│   └─────────────────────┘         │   return "".join(texts)         │   │
│            │                       └─────────────────────────────────┘   │
│            │                                    │                        │
│            ▼                                    ▼                        │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │              NormalizedChunk(text="안녕하세요")                  │   │
│   │                                                                  │   │
│   │              ✅ 동일한 출력 형식!                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 3.4 __init__.py - 레지스트리 및 팩토리

```python
# src/adapters/__init__.py

"""LLM Adapters - 프로바이더별 차이점 캡슐화"""
from .base import BaseLLMAdapter, NormalizedChunk
from .openai import OpenAIAdapter
from .gemini import GeminiAdapter

# 프로바이더 이름 → Adapter 클래스 매핑
ADAPTER_REGISTRY: dict[str, type[BaseLLMAdapter]] = {
    "openai": OpenAIAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(provider: str) -> BaseLLMAdapter:
    """프로바이더 이름으로 Adapter 인스턴스 반환

    Args:
        provider: 프로바이더 이름 ("openai", "gemini")

    Returns:
        해당 프로바이더의 Adapter 인스턴스

    Raises:
        ValueError: 지원하지 않는 프로바이더
    """
    adapter_cls = ADAPTER_REGISTRY.get(provider.lower())
    if adapter_cls is None:
        supported = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(f"Unknown provider: {provider}. Supported: {supported}")
    return adapter_cls()


__all__ = [
    "BaseLLMAdapter",
    "NormalizedChunk",
    "OpenAIAdapter",
    "GeminiAdapter",
    "get_adapter",
    "ADAPTER_REGISTRY",
]
```

### Factory 패턴 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         get_adapter() 팩토리                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   get_adapter("openai")                                                 │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ ADAPTER_REGISTRY.get("openai")                                  │   │
│   │                                                                  │   │
│   │ ADAPTER_REGISTRY = {                                            │   │
│   │     "openai": OpenAIAdapter,  ◄── 클래스 참조                   │   │
│   │     "gemini": GeminiAdapter,                                    │   │
│   │ }                                                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        │ adapter_cls = OpenAIAdapter                                    │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ return adapter_cls()                                            │   │
│   │        │                                                         │   │
│   │        └── OpenAIAdapter() 인스턴스 생성                         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│        │                                                                 │
│        ▼                                                                 │
│   OpenAIAdapter 인스턴스 반환                                           │
│                                                                          │
│   ─────────────────────────────────────────────────────────────────     │
│                                                                          │
│   get_adapter("anthropic")  # 지원하지 않는 프로바이더                  │
│        │                                                                 │
│        ▼                                                                 │
│   ValueError: Unknown provider: anthropic. Supported: openai, gemini   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 사용 예시

### 4.1 Supervisor에서의 사용

```python
# src/supervisor/supervisor.py

class Supervisor:
    def __init__(self, provider: str = None, ...):
        # 1. Adapter 획득
        provider_name = provider or config.LLM_PROVIDER
        self.adapter = get_adapter(provider_name)

    def _build_graph(self):
        # 2. LLM 생성 (Adapter 통해)
        llm = self.adapter.create_llm(
            model=self.model,
            temperature=0.7,
            max_tokens=self.max_tokens
        )
        llm_with_tools = llm.bind_tools(TOOLS)
        ...

    async def process_stream(self, ...):
        ...
        # 3. 청크 정규화 (Adapter 통해)
        if event_type == EVENT_CHAT_MODEL_STREAM:
            chunk = data.get("chunk")
            if chunk and chunk.content:
                normalized = self.adapter.normalize_chunk(chunk)
                if normalized.text:
                    yield {"type": "token", "content": normalized.text}
```

### 4.2 헬스체크에서의 사용

```python
# src/api/routes.py

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        provider=supervisor.adapter.provider_name  # "openai" 또는 "gemini"
    )
```

---

## 5. 확장 가이드

### 5.1 새 프로바이더 추가하기

```python
# 1. src/adapters/anthropic.py 생성

"""Anthropic (Claude) LLM Adapter"""
from typing import Any
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from .base import BaseLLMAdapter, NormalizedChunk
from config import config


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic Claude LLM Adapter"""

    def create_llm(
        self,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> BaseChatModel:
        return ChatAnthropic(
            model=model or "claude-3-sonnet-20240229",
            api_key=config.ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
        """Anthropic 청크 정규화

        Anthropic 형식: chunk.content = "텍스트" (str) - OpenAI와 동일
        """
        content = chunk.content if chunk else ""
        if isinstance(content, str):
            return NormalizedChunk(text=content)
        return NormalizedChunk(text=str(content) if content else "")

    @property
    def provider_name(self) -> str:
        return "anthropic"
```

```python
# 2. src/adapters/__init__.py 수정

from .anthropic import AnthropicAdapter

ADAPTER_REGISTRY: dict[str, type[BaseLLMAdapter]] = {
    "openai": OpenAIAdapter,
    "gemini": GeminiAdapter,
    "anthropic": AnthropicAdapter,  # 추가
}

__all__ = [
    ...,
    "AnthropicAdapter",
]
```

```python
# 3. config.py 수정

class Config:
    ...
    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
```

```bash
# 4. .env 수정

LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### 확장 후 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         확장된 Adapter 구조                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                       ┌─────────────────────┐                           │
│                       │   BaseLLMAdapter    │                           │
│                       │     (Abstract)      │                           │
│                       └──────────┬──────────┘                           │
│                                  │                                       │
│              ┌───────────────────┼───────────────────┐                  │
│              │                   │                   │                   │
│              ▼                   ▼                   ▼                   │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│   │  OpenAIAdapter  │ │  GeminiAdapter  │ │AnthropicAdapter │          │
│   └─────────────────┘ └─────────────────┘ └─────────────────┘          │
│                                                                          │
│   ADAPTER_REGISTRY = {                                                  │
│       "openai": OpenAIAdapter,                                          │
│       "gemini": GeminiAdapter,                                          │
│       "anthropic": AnthropicAdapter,  ← 새로 추가                       │
│   }                                                                      │
│                                                                          │
│   ✅ Supervisor 코드 수정 불필요!                                        │
│   ✅ OCP(Open-Closed Principle) 준수                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 주요 이슈 및 개선점

### 6.1 Critical Issues

없음

### 6.2 Medium Issues

#### Issue 1: API 키 검증 없음 (openai.py:29, gemini.py:28)

```python
# 현재 - API 키가 None이어도 LLM 생성 시도
return ChatOpenAI(
    api_key=config.OPENAI_API_KEY,  # None 가능
    ...
)

# 개선안 1: 생성자에서 검증
class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self):
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")

# 개선안 2: create_llm에서 검증
def create_llm(self, ...):
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required")
    return ChatOpenAI(...)
```

#### Issue 2: 타입 힌트 불일치 (openai.py:21)

```python
# 현재
model: str = None  # None은 str 타입이 아님

# 수정
model: Optional[str] = None
```

### 6.3 Low Issues

#### Issue 3: 예상치 못한 형식 로깅 없음 (gemini.py:52)

```python
# 현재 - 조용히 빈 문자열 반환
return NormalizedChunk(text=str(content) if content else "")

# 개선안 - 로깅 추가
import logging
logger = logging.getLogger(__name__)

def normalize_chunk(self, chunk: Any) -> NormalizedChunk:
    content = chunk.content if chunk else ""

    if isinstance(content, str):
        return NormalizedChunk(text=content)

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                texts.append(item.get("text", ""))
            else:
                logger.warning(f"Unexpected item type in chunk: {type(item)}")
        return NormalizedChunk(text="".join(texts))

    logger.warning(f"Unexpected content type: {type(content)}")
    return NormalizedChunk(text=str(content) if content else "")
```

---

## 7. 테스트 포인트

```python
# tests/test_adapters.py

1. 팩토리 테스트
   - get_adapter("openai") → OpenAIAdapter 반환
   - get_adapter("gemini") → GeminiAdapter 반환
   - get_adapter("unknown") → ValueError

2. OpenAIAdapter 테스트
   - create_llm() → ChatOpenAI 반환
   - normalize_chunk(str) → NormalizedChunk
   - normalize_chunk(None) → NormalizedChunk(text="")
   - provider_name → "openai"

3. GeminiAdapter 테스트
   - create_llm() → ChatGoogleGenerativeAI 반환
   - normalize_chunk(list) → NormalizedChunk (파싱)
   - normalize_chunk(str) → NormalizedChunk (비스트리밍)
   - normalize_chunk(None) → NormalizedChunk(text="")
   - provider_name → "gemini"

4. 통합 테스트
   - OpenAI로 Supervisor 실행
   - Gemini로 Supervisor 실행
   - 스트리밍 청크 정규화 확인
```

---

## 8. 요약

| 항목 | 내용 |
|------|------|
| **책임** | LLM 프로바이더 차이 캡슐화 |
| **패턴** | Adapter, Factory |
| **핵심 인터페이스** | `create_llm()`, `normalize_chunk()`, `provider_name` |
| **지원 프로바이더** | OpenAI, Gemini |
| **확장성** | 새 프로바이더 추가 시 Supervisor 수정 불필요 |
| **주요 이슈** | API 키 검증 없음, 타입 힌트 |

---

*다음: [03-workers.md](./03-workers.md) - Workers 심층 분석*
