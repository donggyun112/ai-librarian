# Phase 4: Streamlit UI 구현

## 목표
슈퍼바이저 시스템을 테스트하고 시연할 수 있는 단순한 Streamlit UI를 구현합니다.

---

## Task 4.1: 메인 앱 구조

### 작업 내용: `poc/app.py`

```python
"""Streamlit UI - 슈퍼바이저 패턴 데모"""
import asyncio
import streamlit as st

from src.supervisor import Supervisor
from src.workers import create_all_workers
from src.schemas.models import SupervisorResponse


# 페이지 설정
st.set_page_config(
    page_title="AI Librarian",
    page_icon="📚",
    layout="wide"
)


def init_supervisor():
    """슈퍼바이저 초기화 (캐싱)"""
    if "supervisor" not in st.session_state:
        workers = create_all_workers()
        st.session_state.supervisor = Supervisor(workers=workers)
    return st.session_state.supervisor


def run_async(coro):
    """비동기 함수 실행 헬퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def main():
    st.title("📚 AI Librarian")
    st.caption("슈퍼바이저 패턴 기반 지능형 질문 응답 시스템")

    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        show_log = st.checkbox("실행 로그 표시", value=True)
        show_sources = st.checkbox("출처 표시", value=True)

        st.divider()
        st.header("📊 정보")
        if "last_response" in st.session_state:
            resp = st.session_state.last_response
            st.metric("사용된 워커", len(resp.workers_used))
            st.metric("신뢰도", f"{resp.total_confidence:.1%}")

    # 메인 컨텐츠
    supervisor = init_supervisor()

    # 질문 입력
    question = st.text_input(
        "질문을 입력하세요",
        placeholder="예: LangChain이 무엇인가요?"
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        submit = st.button("질문하기", type="primary", use_container_width=True)

    # 예시 질문
    st.caption("예시 질문:")
    examples = [
        "LangChain이 무엇인가요?",
        "2024년 AI 트렌드는?",
        "RAG와 파인튜닝의 차이점은?"
    ]

    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        if cols[i].button(ex, key=f"ex_{i}"):
            question = ex
            submit = True

    # 질문 처리
    if submit and question:
        with st.spinner("🤔 생각 중..."):
            response: SupervisorResponse = run_async(
                supervisor.process(question)
            )
            st.session_state.last_response = response

        # 답변 표시
        st.divider()
        st.subheader("💡 답변")
        st.markdown(response.answer)

        # 워커 정보
        worker_names = [w.value for w in response.workers_used]
        st.caption(f"사용된 워커: {', '.join(worker_names)}")

        # 출처 표시
        if show_sources and response.sources:
            with st.expander("📎 출처", expanded=False):
                for source in response.sources:
                    st.markdown(f"- {source}")

        # 실행 로그
        if show_log and response.execution_log:
            with st.expander("📋 실행 로그", expanded=False):
                for log in response.execution_log:
                    st.text(log)


if __name__ == "__main__":
    main()
```

### 완료 조건
- 단순하고 깔끔한 UI
- 질문 입력 및 답변 표시
- 실행 로그 및 출처 표시 옵션

---

## Task 4.2: 추가 유틸리티 함수

### 작업 내용: `poc/src/utils.py`

```python
"""유틸리티 함수"""
import asyncio
from typing import Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """동기 환경에서 비동기 함수 실행"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 이벤트 루프가 실행 중인 경우 (Jupyter 등)
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # 이벤트 루프가 없는 경우
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
```

### 완료 조건
- 비동기 실행 헬퍼 구현

---

## Task 4.3: 실행 스크립트

### 작업 내용: `poc/run.py`

```python
"""간단한 CLI 테스트"""
import asyncio
from src.supervisor import Supervisor
from src.workers import create_all_workers


async def main():
    print("=" * 50)
    print("AI Librarian - 슈퍼바이저 패턴 테스트")
    print("=" * 50)

    # 초기화
    workers = create_all_workers()
    supervisor = Supervisor(workers=workers)

    # 테스트 질문
    test_questions = [
        "LangChain이 무엇인가요?",
        "2024년 AI 트렌드는 무엇인가요?",
    ]

    for question in test_questions:
        print(f"\n📝 질문: {question}")
        print("-" * 40)

        response = await supervisor.process(question)

        print(f"\n💡 답변:\n{response.answer}")
        print(f"\n🔧 사용된 워커: {[w.value for w in response.workers_used]}")
        print(f"📊 신뢰도: {response.total_confidence:.1%}")

        print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
```

### 완료 조건
- CLI 테스트 스크립트 구현

---

## Task 4.4: .env 템플릿

### 작업 내용: `poc/.env.example`

```env
# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Milvus/Zilliz
ZILLIZ_HOST=https://your-cluster.zillizcloud.com
ZILLIZ_TOKEN=your-token-here
MILVUS_COLLECTION=documents

# Tavily (Web Search)
TAVILY_API_KEY=tvly-your-key-here
```

### 완료 조건
- 필요한 환경변수 문서화

---

## Phase 4 완료 체크리스트

- [ ] app.py - Streamlit UI
- [ ] src/utils.py - 유틸리티 함수
- [ ] run.py - CLI 테스트 스크립트
- [ ] .env.example - 환경변수 템플릿

---

## 전체 프로젝트 완료 체크리스트

### Phase 1: 프로젝트 구조
- [ ] 기존 코드 정리
- [ ] 새 디렉토리 구조 생성
- [ ] config.py 작성
- [ ] schemas/models.py 작성

### Phase 2: 슈퍼바이저
- [ ] prompts.py 작성
- [ ] supervisor.py 작성

### Phase 3: 워커
- [ ] base.py 작성
- [ ] rag_worker.py 작성
- [ ] web_worker.py 작성
- [ ] llm_worker.py 작성
- [ ] factory.py 작성

### Phase 4: UI
- [ ] app.py 작성
- [ ] run.py 작성
- [ ] .env.example 작성

---

## 실행 방법

```bash
# 의존성 설치
cd poc
poetry install

# 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 API 키 입력

# CLI 테스트
python run.py

# Streamlit 실행
streamlit run app.py
```
