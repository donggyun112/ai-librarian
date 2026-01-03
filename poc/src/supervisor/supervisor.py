"""
Supervisor - LangGraph 기반 ReAct Agent

구조:
    START → supervisor (LLM + Tool Calling) → tools → supervisor → ... → END

스트리밍:
    - on_chat_model_stream: LLM 토큰 실시간 출력
    - on_tool_start/end: 도구 호출/결과 출력

Adapter 패턴:
    - 프로바이더별 차이점(청크 형식, 인스턴스 전략)을 Adapter로 캡슐화
    - Supervisor는 Adapter 인터페이스만 사용
"""

from typing import List, Literal, TypedDict, Annotated, AsyncIterator, Optional

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

from src.schemas.models import SupervisorResponse, StreamEventType, LangGraphEventName
from src.memory import ChatMemory, InMemoryChatMemory
from src.adapters import get_adapter, BaseLLMAdapter, ToolChoiceType
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

# LangGraph 이벤트 타입 (타입 안전)
EVENT_CHAT_MODEL_STREAM: LangGraphEventName = "on_chat_model_stream"
EVENT_TOOL_START: LangGraphEventName = "on_tool_start"
EVENT_TOOL_END: LangGraphEventName = "on_tool_end"


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
    - 교체 가능한 메모리 백엔드 (기본: InMemory)
    - Adapter 패턴으로 멀티 프로바이더 지원

    사용 예시:
        # 기본 (OpenAI)
        supervisor = Supervisor()

        # Gemini 사용
        supervisor = Supervisor(provider="gemini")

        # SQL 메모리로 교체
        from src.memory.sql import SQLChatMemory
        memory = SQLChatMemory(connection_string="postgresql://...")
        supervisor = Supervisor(memory=memory)
    """

    def __init__(
        self,
        model: str = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        memory: ChatMemory = None,
        provider: str = None
    ):
        self.model = model
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.memory = memory or InMemoryChatMemory()

        # Adapter 초기화
        provider_name = provider or config.LLM_PROVIDER
        self.adapter: BaseLLMAdapter = get_adapter(provider_name)

        # ToolNode (프로바이더 무관하게 공유)
        self.tool_node = ToolNode(TOOLS)

        # Graph 캐시
        self._cached_graph = None

    def _build_graph(self) -> StateGraph:
        """
        Graph 구조:
            START → supervisor → (tool_calls?) → tools → supervisor
                            └── (no tools) → END

        Native Thinking:
            - Gemini 2.5+에서 thinking_budget으로 자동 활성화
            - think 도구 강제 호출 불필요
        """
        # Adapter를 통해 LLM 생성 (Native Thinking 포함)
        llm = self.adapter.create_llm(
            model=self.model,
            temperature=0.7,
            max_tokens=self.max_tokens
        )

        # 검색/액션 도구만 바인딩 (think 도구 제외)
        action_tools = [t for t in TOOLS if t.name != THINK_TOOL]
        llm_with_tools = self.adapter.bind_tools(llm, action_tools)

        async def supervisor_node(state: AgentState) -> dict:
            """Supervisor 노드: LLM 호출

            Native Thinking 전략:
            - LLM이 내부적으로 thinking 수행 (thinking_budget으로 제어)
            - 별도의 think 도구 강제 불필요
            """
            messages = state["messages"]
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}

        workflow = StateGraph(AgentState)

        # 노드 추가
        workflow.add_node("supervisor", supervisor_node)
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

    def _get_graph(self):
        """Graph 반환 (캐싱)"""
        if self._cached_graph is None:
            self._cached_graph = self._build_graph()
        return self._cached_graph

    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """도구 호출 여부에 따라 분기"""
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "continue"
        return "end"

    # ============================================================
    # 히스토리 관리
    # ============================================================
    def _build_messages(self, session_id: str, question: str) -> List[BaseMessage]:
        """시스템 프롬프트 + 히스토리 + 새 질문으로 메시지 구성"""
        # 도구 정보를 동적으로 주입하여 프롬프트 생성
        messages = [SystemMessage(content=get_system_prompt(tools=TOOLS))]
        messages.extend(self.memory.get_messages(session_id))  # 이전 대화 히스토리
        messages.append(HumanMessage(content=question))
        return messages

    def _save_to_history(self, session_id: str, question: str, answer: str, **kwargs) -> None:
        """대화 히스토리에 저장"""
        self.memory.save_conversation(session_id, question, answer, **kwargs)

    def clear_history(self, session_id: str) -> None:
        """세션 히스토리 초기화"""
        self.memory.clear(session_id)

    # ============================================================
    # 비스트리밍 처리
    # ============================================================
    async def process(
        self,
        question: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> SupervisorResponse:
        """질문 처리 (Non-streaming)

        Args:
            question: 사용자 질문
            session_id: 세션 ID (None이면 히스토리 없이 처리)
            **kwargs: 추가 메타데이터 (예: user_id)
        """
        if session_id:
            messages = self._build_messages(session_id, question)
        else:
            # 도구 정보를 동적으로 주입하여 프롬프트 생성
            messages = [
                SystemMessage(content=get_system_prompt(tools=TOOLS)),
                HumanMessage(content=question)
            ]

        final_state = await self._get_graph().ainvoke(
            {"messages": messages},
            config={"recursion_limit": self.max_steps * 2}
        )

        result_messages = final_state["messages"]
        last_message = result_messages[-1]

        # Adapter로 응답 정규화
        if isinstance(last_message, AIMessage):
            normalized = self.adapter.normalize_chunk(last_message)
            answer = normalized.text
        else:
            answer = ""

        # 히스토리에 저장
        if session_id:
            self._save_to_history(session_id, question, answer, **kwargs)

        return SupervisorResponse(
            answer=answer,
            sources=self._extract_sources(result_messages),
            execution_log=self._parse_execution_log(result_messages),
            total_confidence=1.0
        )

    # ============================================================
    # 스트리밍 처리
    # ============================================================
    async def process_stream(
        self,
        question: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[dict]:
        """
        스트리밍 처리 - 토큰 단위 실시간 출력

        Args:
            question: 사용자 질문
            session_id: 세션 ID (None이면 히스토리 없이 처리)

        Yields:
            {"type": "token", "content": str}   - LLM 토큰
            {"type": "act", "tool": str, "args": dict} - 도구 호출
            {"type": "observe", "content": str} - 도구 결과
        """
        if session_id:
            messages = self._build_messages(session_id, question)
        else:
            # 도구 정보를 동적으로 주입하여 프롬프트 생성
            messages = [
                SystemMessage(content=get_system_prompt(tools=TOOLS)),
                HumanMessage(content=question)
            ]

        # 답변 수집용 (히스토리 저장을 위해)
        collected_answer = []

        async for event in self._get_graph().astream_events(
            {"messages": messages},
            config={"recursion_limit": self.max_steps * 2},
            version="v2"
        ):
            event_type = event["event"]
            data = event.get("data", {})

            # 1. LLM 토큰 스트리밍 (최종 답변 + Native Thinking)
            if event_type == EVENT_CHAT_MODEL_STREAM:
                chunk = data.get("chunk")
                # DeepSeek thinking: content="" but additional_kwargs.reasoning_content 있음
                has_content = chunk and (chunk.content or chunk.additional_kwargs)
                if has_content:
                    # Adapter로 청크 정규화
                    normalized = self.adapter.normalize_chunk(chunk)

                    # Native Thinking 청크 처리 (Gemini 2.5+)
                    if normalized.thinking:
                        yield {"type": StreamEventType.THINK, "content": normalized.thinking}

                    # 일반 텍스트 청크 처리
                    if normalized.text:
                        collected_answer.append(normalized.text)
                        yield {"type": StreamEventType.TOKEN, "content": normalized.text}

            # 2. 도구 호출 시작
            elif event_type == EVENT_TOOL_START:
                tool_name = event.get("name", "")
                tool_input = data.get("input", {})

                # 검색 도구 → 액션 표시
                if tool_name in SEARCH_TOOLS:
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
            self._save_to_history(session_id, question, full_answer, **kwargs)

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
                    # Adapter로 정규화하여 로그 추출
                    normalized = self.adapter.normalize_chunk(msg)
                    log.append(f"Response: {normalized.text[:100]}...")
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        log.append(f"Tool: {tc['name']}({tc['args']})")
            elif isinstance(msg, ToolMessage):
                log.append(f"Result: {len(str(msg.content))} chars")
        return log
