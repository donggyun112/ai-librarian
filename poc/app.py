"""Streamlit UI - 슈퍼바이저 ReAct 데모"""
import asyncio
import streamlit as st
import sys
import os

# Add src to python path to allow imports if running directly from poc/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.supervisor import Supervisor


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


async def main():
    st.title("📚 AI Librarian (ReAct Pattern)")
    st.caption("Ask → Think → Act → Observe Loop (Streaming)")

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
        st.divider()

        # 상태 컨테이너
        status_container = st.container()
        answer_container = st.container()

        with status_container:
            status = st.status("🤔 생각하고 행동하는 중...", expanded=True)
            with status:
                logs_placeholder = st.container()

        with answer_container:
            answer_placeholder = st.empty()

        try:
            full_answer = ""
            
            async for event in supervisor.process_stream(question):
                event_type = event["type"]

                # Think - 생각 과정
                if event_type == "think":
                    with logs_placeholder:
                        st.markdown(f"🧠 **Think:** {event['content']}")

                # Act - 도구 호출
                elif event_type == "act":
                    with logs_placeholder:
                        st.markdown(f"🔧 **Act:** `{event['tool']}`")
                        with st.expander("Arguments", expanded=False):
                            st.json(event['args'])

                # Observe - 도구 결과
                elif event_type == "observe":
                    content = event['content']
                    preview = content[:300] + "..." if len(content) > 300 else content
                    with logs_placeholder:
                        st.info(f"👁️ **Observe:** {preview}")

                # Token - 최종 답변 (실시간 스트리밍)
                elif event_type == "token":
                    full_answer += event["content"]
                    answer_placeholder.markdown(full_answer + "▌")

            # 최종 완성 (커서 제거)
            if full_answer:
                answer_placeholder.markdown(full_answer)

            status.update(label="완료!", state="complete", expanded=False)

        except Exception as e:
            st.error(f"오류 발생: {str(e)}")
            if 'status' in locals():
                status.update(label="오류 발생", state="error")


if __name__ == "__main__":
    asyncio.run(main())
