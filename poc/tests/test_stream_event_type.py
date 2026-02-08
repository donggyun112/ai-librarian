"""StreamEventName Literal 타입 테스트

이 파일은 LangChain에 제안할 StreamEventName 타입을 테스트합니다.
"""
from typing import Literal
from typing_extensions import TypedDict, NotRequired

# 제안하는 StreamEventName Literal 타입
StreamEventName = Literal[
    # LLM (non-chat models)
    "on_llm_start",
    "on_llm_stream",
    "on_llm_end",
    "on_llm_error",
    # Chat Model
    "on_chat_model_start",
    "on_chat_model_stream",
    "on_chat_model_end",
    # Tool
    "on_tool_start",
    "on_tool_end",
    "on_tool_error",
    # Chain
    "on_chain_start",
    "on_chain_stream",
    "on_chain_end",
    "on_chain_error",
    # Retriever
    "on_retriever_start",
    "on_retriever_end",
    "on_retriever_error",
    # Prompt
    "on_prompt_start",
    "on_prompt_end",
    # Custom
    "on_custom_event",
]


# 수정된 BaseStreamEvent (제안)
class BaseStreamEventTyped(TypedDict):
    """Typed version of BaseStreamEvent"""
    event: StreamEventName  # str -> StreamEventName
    run_id: str
    tags: NotRequired[list[str]]
    metadata: NotRequired[dict]


# ============================================================
# 테스트: 타입 안전성 검증
# ============================================================

def test_valid_event_names():
    """유효한 이벤트 이름들이 작동하는지 확인"""
    valid_events: list[StreamEventName] = [
        "on_llm_start",
        "on_chat_model_stream",
        "on_tool_start",
        "on_tool_end",
        "on_chain_start",
        "on_custom_event",
    ]
    assert len(valid_events) == 6


def test_event_is_str_subtype():
    """StreamEventName이 str의 서브타입인지 확인 (하위 호환성)"""
    event: StreamEventName = "on_tool_start"

    # str로 사용 가능해야 함
    assert isinstance(event, str)
    assert event == "on_tool_start"
    assert event.startswith("on_")


def test_typed_event_dict():
    """TypedDict에서 StreamEventName 사용 테스트"""
    event: BaseStreamEventTyped = {
        "event": "on_chat_model_stream",
        "run_id": "123",
    }

    assert event["event"] == "on_chat_model_stream"


def test_event_comparison():
    """이벤트 비교 테스트 (기존 코드 호환성)"""
    event: BaseStreamEventTyped = {
        "event": "on_tool_start",
        "run_id": "456",
    }

    # 기존 방식으로 비교 가능
    if event["event"] == "on_tool_start":
        result = "tool started"
    else:
        result = "other"

    assert result == "tool started"


def test_all_event_names_defined():
    """모든 주요 이벤트가 정의되었는지 확인"""
    import typing

    # Literal에서 값들 추출
    if hasattr(typing, 'get_args'):
        args = typing.get_args(StreamEventName)

        # 주요 이벤트들이 포함되어 있는지
        assert "on_llm_start" in args
        assert "on_chat_model_stream" in args
        assert "on_tool_start" in args
        assert "on_tool_end" in args
        assert "on_chain_start" in args
        assert "on_custom_event" in args

        # 총 개수 확인
        assert len(args) == 20  # 정의한 이벤트 개수


# ============================================================
# 타입 체커 테스트 (주석으로 표시)
# ============================================================

def type_checker_should_catch_typo():
    """
    이 함수는 타입 체커(mypy/pyright)가 오타를 잡아야 함

    아래 코드는 타입 에러를 발생시켜야 함:

    event: StreamEventName = "on_tool_strat"  # typo!
    event: StreamEventName = "invalid_event"  # not in Literal
    """
    # 올바른 사용
    event: StreamEventName = "on_tool_start"
    assert event == "on_tool_start"
