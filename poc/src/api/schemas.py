"""API 스키마 정의"""
from typing import Optional, List
from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    """메시지 전송 요청 (session_id는 path parameter, user_id는 Authorization header)"""
    message: str = Field(..., min_length=1, description="사용자 메시지")
    stream: bool = Field(default=False, description="스트리밍 응답 여부")


class ChatResponse(BaseModel):
    """채팅 응답 (Non-streaming)"""
    answer: str = Field(..., description="AI 응답")
    sources: List[str] = Field(default_factory=list, description="사용된 도구 목록")
    session_id: Optional[str] = Field(None, description="세션 ID")


class SessionCreateResponse(BaseModel):
    """세션 생성 응답"""
    session_id: str = Field(..., description="생성된 세션 ID")
    created_at: str = Field(..., description="세션 생성 시간 (ISO 8601)")


class SessionInfo(BaseModel):
    """세션 정보"""
    session_id: str
    message_count: int


class SessionDetailResponse(BaseModel):
    """세션 상세 정보"""
    session_id: str = Field(..., description="세션 ID")
    message_count: int = Field(..., description="메시지 개수")
    created_at: Optional[str] = Field(None, description="세션 생성 시간")
    last_activity: Optional[str] = Field(None, description="마지막 활동 시간")


class SessionListResponse(BaseModel):
    """세션 목록 응답"""
    sessions: List[SessionInfo]


class MessageInfo(BaseModel):
    """메시지 정보"""
    role: str = Field(..., description="메시지 역할 (human, ai, system, tool)")
    content: str = Field(..., description="메시지 내용")
    timestamp: Optional[str] = Field(None, description="메시지 생성 시간")


class SessionHistoryResponse(BaseModel):
    """세션 히스토리 응답"""
    session_id: str
    messages: List[MessageInfo]


class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str = "ok"
    provider: str


# AI SDK 호환 스키마
class AIChatPart(BaseModel):
    """AI SDK 메시지 파트"""
    type: str
    text: Optional[str] = None

    model_config = {"extra": "allow"}


class AIChatMessage(BaseModel):
    """AI SDK 메시지"""
    role: str
    parts: Optional[List[AIChatPart]] = None

    model_config = {"extra": "allow"}

    def get_text(self) -> str:
        """텍스트 추출"""
        if self.parts:
            for part in self.parts:
                if part.type == "text" and part.text:
                    return part.text
        return ""


class AIChatRequest(BaseModel):
    """AI SDK useChat() 요청"""
    messages: List[AIChatMessage]

    model_config = {"extra": "allow"}


class ChatPromptRequest(BaseModel):
    """Claude 방식 채팅 요청 — 프롬프트 + 세션 참조만 전송

    서버가 히스토리를 관리하며, 클라이언트는 새 메시지만 보냅니다.
    session_id가 없으면 새 세션을 생성합니다.
    """
    prompt: str = Field(..., min_length=1, description="사용자 메시지")
    session_id: Optional[str] = Field(None, description="기존 세션 ID (없으면 새 세션 생성)")


# Assistant Transport Protocol 스키마
class AssistantMessagePart(BaseModel):
    """메시지 파트"""
    type: str
    text: Optional[str] = None

    model_config = {"extra": "allow"}


class AssistantMessage(BaseModel):
    """Assistant Transport 메시지"""
    role: str
    parts: Optional[List[AssistantMessagePart]] = None

    model_config = {"extra": "allow"}

    def get_text(self) -> str:
        """텍스트 추출"""
        if self.parts:
            for part in self.parts:
                if part.type == "text" and part.text:
                    return part.text
        return ""


class AssistantCommand(BaseModel):
    """Assistant Transport 커맨드"""
    type: str
    message: Optional[AssistantMessage] = None

    model_config = {"extra": "allow"}


class AssistantTransportRequest(BaseModel):
    """Assistant Transport Protocol 요청"""
    commands: List[AssistantCommand] = Field(default_factory=list)
    system: Optional[str] = None
    tools: Optional[dict] = None
    state: Optional[dict] = None

    model_config = {"extra": "allow"}

    def get_last_user_message(self) -> Optional[str]:
        """마지막 사용자 메시지 텍스트 추출"""
        for command in reversed(self.commands):
            if command.type == "add-message" and command.message:
                if command.message.role == "user":
                    return command.message.get_text()
        return None
