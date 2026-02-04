"""Supabase 기반 대화 히스토리 저장소"""
from typing import List, Optional
from datetime import datetime, timezone

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from supabase import AsyncClient
from postgrest.exceptions import APIError
from loguru import logger

from .base import ChatMemory


class SessionAccessDenied(Exception):
    """사용자가 해당 세션에 접근 권한이 없을 때 발생"""


# TODO: Refactor: Move to src/exceptions.py for centralized error handling
class SupabaseOperationError(Exception):
    """Supabase 작업 중 에러 발생 (API, Network 등)"""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class SupabaseChatMemory(ChatMemory):
    """Supabase를 이용한 대화 히스토리 영구 저장소

    테이블 스키마:
      1) chat_sessions
         - id: uuid, pk
         - user_id: uuid, fk (auth.users)
         - ...
      2) chat_messages
         - id: bigint, pk
         - session_id: uuid, fk (chat_sessions)
         - role: text ('human', 'ai', 'system', 'tool')
         - message: jsonb
         - created_at: timestamptz

    Note:
        async 전용 구현체. 동기 메서드는 base class의 NotImplementedError를 상속합니다.
    """

    def __init__(
        self,
        url: str,
        key: str,
        require_user_scoped_client: bool = False,
        async_client: Optional[AsyncClient] = None,
    ) -> None:
        self._url = url
        self._key = key
        self.sessions_table = "chat_sessions"
        self.messages_table = "chat_messages"
        self._require_user_scoped_client = require_user_scoped_client
        self._async_client = async_client

    def _get_async_client(self, client: Optional[AsyncClient]) -> AsyncClient:
        async_client = client or self._async_client
        if async_client is None:
            raise ValueError("Async Supabase client is required for async operations.")
        return async_client

    def _ensure_user_scoped_client(self, user_id: Optional[str], client: Optional[AsyncClient]) -> None:
        if self._require_user_scoped_client and user_id and client is None:
            raise ValueError("User-scoped Supabase client is required for authenticated operations.")

    async def _ensure_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
    ) -> bool:
        """세션이 존재하는지 확인하고 소유권을 검증. 없으면 생성 시도.

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Returns:
            True if session exists and user owns it (or user_id not provided for backwards compat)
            False otherwise
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        if not user_id:
            res = await client.table(self.sessions_table) \
                .select("id") \
                .eq("id", session_id) \
                .execute()

            if res.data:
                return True
            raise ValueError("user_id is required for new sessions")

        # Check if session already exists (with ownership verification)
        res = await client.table(self.sessions_table) \
            .select("id") \
            .eq("id", session_id) \
            .eq("user_id", user_id) \
            .execute()

        if res.data:
            return True

        # Session not found for this user — try to create it
        try:
            await client.table(self.sessions_table) \
                .insert({"id": session_id, "user_id": user_id}) \
                .execute()
            return True
        except APIError as e:
            if e.code == "23505":
                # Unique constraint violation: session exists but belongs to another user
                # (RLS hid it from the SELECT above)
                logger.warning(
                    f"Session {session_id} exists but is not accessible to user {user_id}"
                )
                raise SessionAccessDenied(
                    f"Session {session_id} is not accessible"
                )
            raise SupabaseOperationError(f"Failed to create session: {e}", e)
        except Exception as e:
            raise SupabaseOperationError(f"Failed to create session: {e}", e)


    async def init_session_async(
        self,
        session_id: str,
        user_id: str,
        client: Optional[AsyncClient] = None,
    ) -> bool:
        """빈 세션 초기화 (세션 생성 시 호출)

        Args:
            session_id: 세션 식별자
            user_id: 사용자 ID (필수)

        Returns:
            True if session was created or already exists, False otherwise
        """
        self._ensure_user_scoped_client(user_id, client)
        return await self._ensure_session(session_id, user_id, client=client)

    def _parse_message_rows(self, rows: list) -> List[BaseMessage]:
        """DB 행 목록을 BaseMessage 리스트로 변환"""
        messages: List[BaseMessage] = []
        for row in rows:
            msg_data = row.get("message")
            created_at = row.get("created_at")
            if msg_data:
                restored = messages_from_dict([msg_data])
                if restored:
                    msg = restored[0]
                    if created_at:
                        msg.additional_kwargs["timestamp"] = created_at
                    messages.append(msg)
        return messages

    async def _check_session_ownership_async(
        self,
        session_id: str,
        user_id: str,
        client: AsyncClient,
    ) -> None:
        """세션 소유권 검증 (비동기). 실패 시 SessionAccessDenied 발생."""
        session_check = await client.table(self.sessions_table) \
            .select("id") \
            .eq("id", session_id) \
            .eq("user_id", user_id) \
            .execute()

        if not session_check.data:
            # logger.warning(f"Session access denied: {session_id} for user {user_id}")
            raise SessionAccessDenied(f"User does not own session {session_id}")


    async def get_messages_async(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
        **kwargs,
    ) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        if user_id:
            await self._check_session_ownership_async(session_id, user_id, client)

        try:
            response = await client.table(self.messages_table) \
                .select("message, created_at") \
                .eq("session_id", session_id) \
                .order("created_at", desc=False) \
                .execute()
        except Exception as e:
            logger.error(f"Failed to fetch messages for session {session_id}: {e}")
            raise SupabaseOperationError(f"Failed to fetch messages: {e}", e)

        return self._parse_message_rows(response.data)


    def _get_role(self, message: BaseMessage) -> str:
        if isinstance(message, HumanMessage):
            return "human"
        elif isinstance(message, AIMessage):
            return "ai"
        elif message.type == "system":
            return "system"
        elif message.type == "tool":
            return "tool"
        return "human"  # Default fallback

    async def _add_message_async(self, session_id: str, message: BaseMessage, **kwargs) -> None:
        """메시지 저장 로직 (비동기)"""
        user_id = kwargs.get("user_id")
        client = kwargs.get("client")

        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        if not await self._ensure_session(session_id, user_id, client=client):
            logger.error(f"Cannot add message: Session {session_id} could not be established.")
            raise SessionAccessDenied(f"Session {session_id} could not be established or user does not have access.")

        msg_dict = message_to_dict(message)
        role = self._get_role(message)

        data = {
            "session_id": session_id,
            "role": role,
            "message": msg_dict
        }

        try:
            await client.table(self.messages_table).insert(data).execute()
            await client.table(self.sessions_table) \
                .update({"last_message_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("id", session_id) \
                .execute()

        except Exception as e:
            logger.error(f"Error saving message to Supabase: {type(e).__name__} - {e}")
            raise SupabaseOperationError(f"Failed to save message: {e}", e)


    async def save_conversation_async(self, session_id: str, user_message: str, ai_message: str, **kwargs) -> None:
        """대화 쌍(사용자 + AI) 저장 - 비동기 버전

        Args:
            session_id: 세션 식별자
            user_message: 사용자 메시지
            ai_message: AI 응답
            **kwargs: 추가 메타데이터 (예: user_id)
        """
        metadata = {k: v for k, v in kwargs.items() if k not in ('user_id', 'client', '_ownership_verified')}
        user_msg = HumanMessage(content=user_message, additional_kwargs=metadata)
        ai_msg = AIMessage(content=ai_message, additional_kwargs=metadata)

        await self._add_message_async(session_id, user_msg, **kwargs)
        await self._add_message_async(session_id, ai_msg, **kwargs)

    async def add_user_message_async(self, session_id: str, content: str, **kwargs) -> None:
        """사용자 메시지 단건 추가 (비동기)"""
        metadata = {k: v for k, v in kwargs.items() if k not in ("user_id", "client", "_ownership_verified")}
        message = HumanMessage(content=content, additional_kwargs=metadata)
        await self._add_message_async(session_id, message, **kwargs)

    async def add_ai_message_async(self, session_id: str, content: str, **kwargs) -> None:
        """AI 메시지 단건 추가 (비동기)"""
        metadata = {k: v for k, v in kwargs.items() if k not in ("user_id", "client", "_ownership_verified")}
        message = AIMessage(content=content, additional_kwargs=metadata)
        await self._add_message_async(session_id, message, **kwargs)

    async def clear_async(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
    ) -> None:
        """세션 히스토리 메시지 삭제 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        if user_id:
            await self._check_session_ownership_async(session_id, user_id, client)

        try:
            await client.table(self.messages_table) \
                .delete() \
                .eq("session_id", session_id) \
                .execute()
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {e}")
            raise SupabaseOperationError(f"Failed to clear session: {e}", e)


    async def delete_session_async(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
    ) -> None:
        """세션 및 관련 메시지 완전 삭제 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        try:
            if user_id:
                await self._check_session_ownership_async(session_id, user_id, client)
                await client.table(self.sessions_table) \
                    .delete() \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()
            else:
                await client.table(self.sessions_table) \
                    .delete() \
                    .eq("id", session_id) \
                    .execute()
        except SessionAccessDenied:
            raise
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise SupabaseOperationError(f"Failed to delete session: {e}", e)


    async def list_sessions_async(
        self,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
    ) -> List[str]:
        """모든 세션 ID 조회 (비동기)

        Args:
            user_id: 사용자 ID (제공 시 해당 사용자의 세션만 조회)
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        query = client.table(self.sessions_table).select("id")

        if user_id:
            query = query.eq("user_id", user_id)

        try:
            response = await query.order("last_message_at", desc=True).execute()
            return [item["id"] for item in response.data]
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise SupabaseOperationError(f"Failed to list sessions: {e}", e)


    async def get_message_count_async(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
        **kwargs,
    ) -> int:
        """세션의 메시지 개수 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        if user_id:
            await self._check_session_ownership_async(session_id, user_id, client)

        try:
            response = await client.table(self.messages_table) \
                .select("id", count="exact") \
                .eq("session_id", session_id) \
                .execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Failed to get message count for session {session_id}: {e}")
            raise SupabaseOperationError(f"Failed to get message count: {e}", e)
