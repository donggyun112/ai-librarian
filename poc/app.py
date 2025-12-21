"""Streamlit UI - 슈퍼바이저 ReAct 데모"""
import asyncio
import streamlit as st
import sys
import os

# Add src to python path to allow imports if running directly from poc/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.supervisor import Supervisor
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
        st.session_state.supervisor = Supervisor()
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
    st.title("📚 AI Librarian (ReAct Pattern)")
    st.caption("Ask → Think → Act → Observe Loop")

    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        show_log = st.checkbox("실행 로그 표시", value=True)
        
    # 메인 컨텐츠
    supervisor = init_supervisor()

    # 질문 입력
    question = st.text_input(
        "질문을 입력하세요",
        placeholder="예: 2024년 AI 트렌드는?"
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        submit = st.button("질문하기", type="primary", use_container_width=True)

    # 예시 질문
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
        with st.spinner("🤔 생각하고 행동하는 중..."):
            response: SupervisorResponse = run_async(
                supervisor.process(question)
            )
        
        # 답변 표시
        st.divider()
        st.subheader("💡 답변")
        st.markdown(response.answer)

        # 실행 로그 (Think/Act/Observe)
        if show_log and response.execution_log:
            with st.expander("🕵️ 에이전트 생각 흐름 (Trace)", expanded=True):
                for log in response.execution_log:
                    if "도구 호출" in log:
                        st.markdown(f"**🛠️ {log}**")
                    elif "Call:" in log:
                        st.code(log, language="python")
                    elif "Observe:" in log:
                        st.caption(log)
                    else:
                        st.text(log)


if __name__ == "__main__":
    main()
