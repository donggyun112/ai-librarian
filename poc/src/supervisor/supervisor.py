"""
Supervisor - LangGraph 기반 ReAct Agent

구조:
    START → supervisor (LLM + Tool Calling) → tools → supervisor → ... → END

스트리밍:
    - on_chat_model_stream: LLM 토큰 실시간 출력
    - on_tool_start/end: 도구 호출/결과 출력
"""

from typing import List, Literal, TypedDict, Annotated, AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
    AIMessage,
    BaseMessage
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.schemas.models import SupervisorResponse
from .prompts import get_system_prompt
from .tools import TOOLS
from config import config


# ============================================================
# 상수 정의
# ============================================================
SEARCH_TOOLS = ["arag_search", "aweb_search"]
THINK_TOOL = "think"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_STEPS = 10


# ============================================================
# State 정의
# ============================================================
class AgentState(TypedDict):
    """LangGraph Agent 상태"""
    messages: Annotated[List[BaseMessage], add_messages]


# ============================================================
# Supervisor 클래스
# ============================================================
class Supervisor:
    """
    LangGraph 기반 ReAct Agent

    - Tool Calling으로 도구 호출
    - astream_events로 토큰 스트리밍
    """

    def __init__(
        self,
        model: str = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        max_tokens: int = DEFAULT_MAX_TOKENS
    ):
        self.model = model or config.OPENAI_MODEL
        self.max_steps = max_steps
        self.max_tokens = max_tokens

        # LLM 초기화 (스트리밍 활성화)
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=0.7,
            api_key=config.OPENAI_API_KEY,
            max_tokens=self.max_tokens,
            streaming=True
        )

        # Tool Binding
        self.llm_with_tools = self.llm.bind_tools(TOOLS)

        # ToolNode
        self.tool_node = ToolNode(TOOLS)

        # Graph 빌드
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Graph 구조:
            START → supervisor → (tool_calls?) → tools → supervisor
                            └── (no tools) → END
        """
        workflow = StateGraph(AgentState)

        # 노드 추가
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("tools", self.tool_node)

        # 엣지 연결
        workflow.add_edge(START, "supervisor")
        workflow.add_conditional_edges(
            "supervisor",
            self._should_continue,
            {"continue": "tools", "end": END}
        )
        workflow.add_edge("tools", "supervisor")

        return workflow.compile()

    async def _supervisor_node(self, state: AgentState) -> dict:
        """Supervisor 노드: LLM 호출"""
        messages = state["messages"]
        response = await self.llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """도구 호출 여부에 따라 분기"""
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "continue"
        return "end"

    # ============================================================
    # 비스트리밍 처리
    # ============================================================
    async def process(self, question: str) -> SupervisorResponse:
        """질문 처리 (Non-streaming)"""
        messages = [
            SystemMessage(content=get_system_prompt()),
            HumanMessage(content=question)
        ]

        final_state = await self.graph.ainvoke(
            {"messages": messages},
            config={"recursion_limit": self.max_steps * 2}
        )

        messages = final_state["messages"]
        last_message = messages[-1]

        answer = str(last_message.content) if isinstance(last_message, AIMessage) else ""

        return SupervisorResponse(
            answer=answer,
            sources=self._extract_sources(messages),
            execution_log=self._parse_execution_log(messages),
            total_confidence=1.0
        )

    # ============================================================
    # 스트리밍 처리
    # ============================================================
    async def process_stream(self, question: str) -> AsyncIterator[dict]:
        """
        스트리밍 처리 - 토큰 단위 실시간 출력

        Yields:
            {"type": "token", "content": str}   - LLM 토큰
            {"type": "act", "tool": str, "args": dict} - 도구 호출
            {"type": "observe", "content": str} - 도구 결과
        """
        messages = [
            SystemMessage(content=get_system_prompt()),
            HumanMessage(content=question)
        ]

        async for event in self.graph.astream_events(
            {"messages": messages},
            config={"recursion_limit": self.max_steps * 2},
            version="v2"
        ):
            event_type = event["event"]
            data = event.get("data", {})

            # 1. LLM 토큰 스트리밍 (최종 답변)
            if event_type == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk and chunk.content:
                    yield {"type": "token", "content": chunk.content}

            # 2. 도구 호출 시작
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = data.get("input", {})

                # think 도구 → 생각 표시
                if tool_name == THINK_TOOL:
                    thought = tool_input.get("thought", "")
                    yield {"type": "think", "content": thought}

                # 검색 도구 → 액션 표시
                elif tool_name in SEARCH_TOOLS:
                    yield {
                        "type": "act",
                        "tool": tool_name,
                        "args": tool_input
                    }

            # 3. 도구 결과 반환 (검색 도구만)
            elif event_type == "on_tool_end":
                tool_name = event.get("name", "")
                if tool_name in SEARCH_TOOLS:
                    yield {
                        "type": "observe",
                        "content": str(data.get("output", ""))
                    }

    # ============================================================
    # 유틸리티 메서드
    # ============================================================
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
                    log.append(f"Response: {str(msg.content)[:100]}...")
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        log.append(f"Tool: {tc['name']}({tc['args']})")
            elif isinstance(msg, ToolMessage):
                log.append(f"Result: {len(str(msg.content))} chars")
        return log
