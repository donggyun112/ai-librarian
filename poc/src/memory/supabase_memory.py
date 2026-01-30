"""Supabase 기반 대화 히스토리 저장소"""
from typing import List, Optional
from datetime import datetime, timezone

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from supabase import create_client, Client, AsyncClient
from loguru import logger

from .base import ChatMemory


class SessionAccessDenied(Exception):
    """사용자가 해당 세션에 접근 권한이 없을 때 발생"""


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
        self._sync_client: Optional[Client] = None
        self.sessions_table = "chat_sessions"
        self.messages_table = "chat_messages"
        self._require_user_scoped_client = require_user_scoped_client
        self._async_client = async_client

    @property
    def supabase(self) -> Client:
        """Lazy-init sync client (레거시 호환용으로만 사용)"""
        if self._sync_client is None:
            self._sync_client = create_client(self._url, self._key)
        return self._sync_client

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

        res = await client.table(self.sessions_table) \
            .select("id") \
            .eq("id", session_id) \
            .execute()

        if res.data:
            if user_id:
                await self._check_session_ownership_async(session_id, user_id, client)
            return True

        if not user_id:
            raise ValueError("user_id is required for new sessions")

        await client.table(self.sessions_table) \
            .insert({"id": session_id, "user_id": user_id}) \
            .execute()
        return True

    def _ensure_session_sync(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """세션이 존재하는지 확인하고 소유권을 검증. 없으면 생성 시도 (동기)"""
        res = self.supabase.table(self.sessions_table) \
            .select("id") \
            .eq("id", session_id) \
            .execute()

        if res.data:
            if user_id:
                self._check_session_ownership_sync(session_id, user_id)
            return True

        if not user_id:
            raise ValueError("user_id is required for new sessions")

        self.supabase.table(self.sessions_table) \
            .insert({"id": session_id, "user_id": user_id}) \
            .execute()
        return True

    def init_session(self, session_id: str, **kwargs) -> None:
        """빈 세션 초기화 (동기 래퍼)

        Args:
            session_id: 세션 식별자
            **kwargs: user_id 등 추가 메타데이터

        Raises:
            ValueError: user_id 누락 시
            RuntimeError: 세션 생성 실패 시
        """
        user_id = kwargs.get("user_id")
        if not user_id:
            raise ValueError("user_id is required for Supabase session initialization")

        success = self._ensure_session_sync(session_id, user_id)

        if not success:
            raise RuntimeError(f"Failed to initialize session {session_id}")

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
            raise SessionAccessDenied(f"User does not own session {session_id}")

    def _check_session_ownership_sync(
        self,
        session_id: str,
        user_id: str,
    ) -> None:
        """세션 소유권 검증 (동기). 실패 시 SessionAccessDenied 발생."""
        session_check = self.supabase.table(self.sessions_table) \
            .select("id") \
            .eq("id", session_id) \
            .eq("user_id", user_id) \
            .execute()

        if not session_check.data:
            raise SessionAccessDenied(f"User does not own session {session_id}")

    async def get_messages_async(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
        *,
        _ownership_verified: bool = False,
    ) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
            _ownership_verified: 내부용 - 호출자가 이미 소유권을 검증한 경우 True

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        if user_id and not _ownership_verified:
            await self._check_session_ownership_async(session_id, user_id, client)

        response = await client.table(self.messages_table) \
            .select("message, created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=False) \
            .execute()

        return self._parse_message_rows(response.data)

    def get_messages(self, session_id: str, user_id: Optional[str] = None) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        if user_id:
            self._check_session_ownership_sync(session_id, user_id)

        response = self.supabase.table(self.messages_table) \
            .select("message, created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=False) \
            .execute()

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
            raise ValueError(f"Session {session_id} could not be established. user_id may be required.")

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
            logger.error(f"Error saving message to Supabase: {type(e).__name__}")
            raise

    def _add_message(self, session_id: str, message: BaseMessage, **kwargs) -> None:
        """메시지 저장 로직 (동기 wrapper)

        Note:
            이 동기 메서드는 레거시 호환성을 위해 유지됩니다.
            비동기 컨텍스트에서는 _add_message_async를 직접 사용하세요.
        """
        user_id = kwargs.get("user_id")
        if not self._ensure_session_sync(session_id, user_id):
            logger.error(f"Cannot add message: Session {session_id} could not be established.")
            raise ValueError(f"Session {session_id} could not be established. user_id may be required.")

        msg_dict = message_to_dict(message)
        role = self._get_role(message)

        data = {
            "session_id": session_id,
            "role": role,
            "message": msg_dict
        }

        try:
            self.supabase.table(self.messages_table).insert(data).execute()
            self.supabase.table(self.sessions_table) \
                .update({"last_message_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("id", session_id) \
                .execute()
        except Exception as e:
            logger.error(f"Error saving message to Supabase: {type(e).__name__}")
            raise

    def add_user_message(self, session_id: str, content: str, **kwargs) -> None:
        """사용자 메시지 추가"""
        metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
        msg = HumanMessage(content=content, additional_kwargs=metadata)
        self._add_message(session_id, msg, **kwargs)

    def add_ai_message(self, session_id: str, content: str, **kwargs) -> None:
        """AI 메시지 추가"""
        metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
        msg = AIMessage(content=content, additional_kwargs=metadata)
        self._add_message(session_id, msg, **kwargs)

    async def save_conversation_async(self, session_id: str, user_message: str, ai_message: str, **kwargs) -> None:
        """대화 쌍(사용자 + AI) 저장 - 비동기 버전

        Args:
            session_id: 세션 식별자
            user_message: 사용자 메시지
            ai_message: AI 응답
            **kwargs: 추가 메타데이터 (예: user_id)
        """
        metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
        user_msg = HumanMessage(content=user_message, additional_kwargs=metadata)
        ai_msg = AIMessage(content=ai_message, additional_kwargs=metadata)

        await self._add_message_async(session_id, user_msg, **kwargs)
        await self._add_message_async(session_id, ai_msg, **kwargs)

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

        await client.table(self.messages_table) \
            .delete() \
            .eq("session_id", session_id) \
            .execute()

    def clear(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 히스토리 메시지 삭제 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        if user_id:
            self._check_session_ownership_sync(session_id, user_id)

        self.supabase.table(self.messages_table) \
            .delete() \
            .eq("session_id", session_id) \
            .execute()

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

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 및 관련 메시지 완전 삭제 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        if user_id:
            self._check_session_ownership_sync(session_id, user_id)
            self.supabase.table(self.sessions_table) \
                .delete() \
                .eq("id", session_id) \
                .eq("user_id", user_id) \
                .execute()
        else:
            self.supabase.table(self.sessions_table) \
                .delete() \
                .eq("id", session_id) \
                .execute()

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

        response = await query.order("last_message_at", desc=True).execute()
        return [item["id"] for item in response.data]

    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """모든 세션 ID 조회 (동기 wrapper - 레거시 호환용)

        Args:
            user_id: 사용자 ID (제공 시 해당 사용자의 세션만 조회)
        """
        query = self.supabase.table(self.sessions_table).select("id")
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.order("last_message_at", desc=True).execute()
        return [item["id"] for item in response.data]

    async def get_message_count_async(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        client: Optional[AsyncClient] = None,
        *,
        _ownership_verified: bool = False,
    ) -> int:
        """세션의 메시지 개수 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
            _ownership_verified: 내부용 - 호출자가 이미 소유권을 검증한 경우 True

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        self._ensure_user_scoped_client(user_id, client)
        client = self._get_async_client(client)

        if user_id and not _ownership_verified:
            await self._check_session_ownership_async(session_id, user_id, client)

        response = await client.table(self.messages_table) \
            .select("id", count="exact") \
            .eq("session_id", session_id) \
            .execute()
        return response.count if response.count is not None else 0

    def get_message_count(self, session_id: str, user_id: Optional[str] = None) -> int:
        """세션의 메시지 개수 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Raises:
            SessionAccessDenied: 소유권 검증 실패
        """
        if user_id:
            self._check_session_ownership_sync(session_id, user_id)

        response = self.supabase.table(self.messages_table) \
            .select("id", count="exact") \
            .eq("session_id", session_id) \
            .execute()
        return response.count if response.count is not None else 0
