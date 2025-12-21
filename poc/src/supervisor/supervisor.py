"""슈퍼바이저 메인 로직 (LangGraph Structured Output ReAct)"""
import json
import uuid
from typing import List, Optional, Literal, TypedDict, Annotated
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.schemas.models import SupervisorResponse
from .prompts import SYSTEM_PROMPT
from .tools import TOOLS
from config import config

# 1. State 정의
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# 2. Structured Output Schema 정의
class ThinkAndAct(BaseModel):
    """생각과 행동을 결정하는 구조"""
    thought: str = Field(description="현재 상황에 대한 분석과 판단 (자연어)")
    tool_name: Optional[Literal["arag_search", "aweb_search"]] = Field(default=None, description="호출할 도구 이름")
    tool_args: Optional[str] = Field(default=None, description="도구 호출 인자 (JSON 문자열)")
    final_answer: Optional[str] = Field(default=None, description="최종 답변 (도구 호출이 없는 경우)")

class Supervisor:
    """LangGraph + Structured Output 기반 슈퍼바이저"""

    def __init__(
        self,
        model: str = None,
        max_steps: int = 10
    ):
        self.model = model or config.OPENAI_MODEL
        self.max_steps = max_steps
        
        # LLM 초기화
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=0,
            api_key=config.OPENAI_API_KEY
        )
        
        # Structured Output LLM
        self.structured_llm = self.llm.with_structured_output(ThinkAndAct)
        
        # ToolNode 초기화
        self.tool_node = ToolNode(TOOLS)
        
        # 그래프 빌드
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """LangGraph 그래프 구성"""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("tools", self.tool_node)
        
        workflow.add_edge(START, "supervisor")
        workflow.add_conditional_edges(
            "supervisor",
            self._should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        workflow.add_edge("tools", "supervisor")
        
        return workflow.compile()

    async def _supervisor_node(self, state: AgentState):
        """슈퍼바이저 노드: Structured Output 생성 및 메시지 변환"""
        messages = state["messages"]
        
        # LLM 호출
        result: ThinkAndAct = await self.structured_llm.ainvoke(messages)
        
        # AIMessage로 변환 (ToolNode 호환성 및 히스토리 기록용)
        # content에 thought를 포함시켜 "생각"을 기록
        content = f"Thinking: {result.thought}"
        if result.final_answer:
             content += f"\n\nAnswer: {result.final_answer}"
        
        tool_calls = []
        if result.tool_name and result.tool_args:
            # tool_args 처리 로직 강화
            if isinstance(result.tool_args, dict):
                args = result.tool_args
            elif isinstance(result.tool_args, str):
                try:
                    parsed = json.loads(result.tool_args)
                    if isinstance(parsed, dict):
                        args = parsed
                    else:
                        # JSON 파싱은 되었으나 dict가 아닌 경우 (예: "검색어")
                        args = {"query": str(parsed)}
                except json.JSONDecodeError:
                    # JSON 파싱 실패 시 원본 문자열을 쿼리로 사용
                    args = {"query": result.tool_args}
            else:
                args = {"query": str(result.tool_args)}
                
            tool_calls.append({
                "id": str(uuid.uuid4()),
                "name": result.tool_name,
                "args": args
            })
            
        message = AIMessage(content=content, tool_calls=tool_calls)
        return {"messages": [message]}

    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """다음 단계 결정"""
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "continue"
        return "end"

    def _parse_execution_log(self, messages: List[BaseMessage]) -> List[str]:
        """메시지 히스토리에서 실행 로그 추출"""
        log = []
        for msg in messages:
            if isinstance(msg, AIMessage):
                # Structured Output으로 생성된 content (Thinking: ...)
                if "Thinking:" in str(msg.content):
                    log.append(msg.content)
                
                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        log.append(f"Act: {tool_call['name']}({tool_call['args']})")
                        
            elif isinstance(msg, ToolMessage):
                log.append(f"Observe: {len(msg.content)} chars")
        return log

    def _extract_sources(self, messages: List[BaseMessage]) -> List[str]:
        sources = set()
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    sources.add(tool_call['name'])
        return list(sources)

    async def process(self, question: str) -> SupervisorResponse:
        """질문 처리 메인 플로우"""
        
        # 시스템 프롬프트 주입
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)]
        
        # 그래프 실행
        final_state = await self.graph.ainvoke(
            {"messages": messages},
            config={"recursion_limit": self.max_steps * 2}
        )
        
        messages = final_state["messages"]
        last_message = messages[-1]
        
        # 최종 답변 추출
        answer = ""
        if isinstance(last_message, AIMessage):
            # "Answer: " 뒷부분 추출하거나 전체 content 반환
            if "Answer:" in str(last_message.content):
                answer = str(last_message.content).split("Answer:", 1)[1].strip()
            else:
                answer = last_message.content
        
        return SupervisorResponse(
            answer=answer,
            sources=self._extract_sources(messages),
            execution_log=self._parse_execution_log(messages),
            total_confidence=1.0
        )
