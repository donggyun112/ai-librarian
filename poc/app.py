"""Streamlit UI - 슈퍼바이저 ReAct 데모"""
import asyncio
import uuid
import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.supervisor import Supervisor



st.set_page_config(
    page_title="AI Librarian",
    page_icon="📚",
    layout="wide"
)


def load_css():
    """커스텀 CSS 로드"""
    css_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.css")
    if os.path.exists(css_file):
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()


def init_session():
    """세션 초기화"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "supervisor" not in st.session_state:
        st.session_state.supervisor = Supervisor()
    if "messages" not in st.session_state:
        st.session_state.messages = []


def clear_chat():
    """대화 히스토리 초기화"""
    st.session_state.supervisor.clear_history(st.session_state.session_id)
    st.session_state.messages = []
    st.session_state.session_id = str(uuid.uuid4())


async def main():
    init_session()

    st.title("📚 AI Librarian")
    st.caption("ReAct Pattern with Conversation Memory")

    # 사이드바
    with st.sidebar:
        st.header("Settings")
        show_log = st.checkbox("Show execution log", value=True)
        st.divider()

        st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
        if st.button("Clear Chat", use_container_width=True):
            clear_chat()
            st.rerun()

    supervisor = st.session_state.supervisor
    session_id = st.session_state.session_id

    # 이전 대화 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 질문 입력
    question = st.chat_input("Ask a question...")

    if question:
        # 사용자 메시지 표시
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # AI 응답
        with st.chat_message("assistant"):
            if show_log:
                status = st.status("Thinking...", expanded=True)
                logs_placeholder = status.container()
            answer_placeholder = st.empty()

            try:
                full_answer = ""

                async for event in supervisor.process_stream(question, session_id=session_id):
                    event_type = event["type"]

                    if event_type == "think" and show_log:
                        with logs_placeholder:
                            st.markdown(f"🧠 **Think:** {event['content']}")

                    elif event_type == "act" and show_log:
                        with logs_placeholder:
                            st.markdown(f"🔧 **Act:** `{event['tool']}`")
                            with st.expander("Arguments", expanded=False):
                                st.json(event['args'])

                    elif event_type == "observe" and show_log:
                        content = event['content']
                        preview = content[:300] + "..." if len(content) > 300 else content
                        with logs_placeholder:
                            st.info(f"👁️ **Observe:** {preview}")

                    elif event_type == "token":
                        full_answer += event["content"]
                        answer_placeholder.markdown(full_answer + "▌")

                if full_answer:
                    answer_placeholder.markdown(full_answer)
                    st.session_state.messages.append({"role": "assistant", "content": full_answer})

                if show_log:
                    status.update(label="Done", state="complete", expanded=False)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                if show_log and 'status' in locals():
                    status.update(label="Error", state="error")


if __name__ == "__main__":
    asyncio.run(main())
