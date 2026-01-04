"""Supabase 기반 대화 히스토리 저장소"""
from typing import List, Optional
import asyncio
from datetime import datetime, timezone

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from supabase import create_client, Client
from loguru import logger
import anyio
from anyio.from_thread import run_sync

from .base import ChatMemory

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

    def __init__(self, url: str, key: str) -> None:
        self.supabase: Client = create_client(url, key)
        self.sessions_table = "chat_sessions"
        self.messages_table = "chat_messages"

    async def _ensure_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """세션이 존재하는지 확인하고, 없으면 생성 시도.
        user_id가 필수값(auth.users 참조)이므로 제공되지 않으면 생성 실패 가능성 있음.
        """
        try:
            # 1. Check existence
            def _check_session():
                return self.supabase.table(self.sessions_table)\
                    .select("id")\
                    .eq("id", session_id)\
                    .execute()

            res = await anyio.to_thread.run_sync(_check_session)

            if res.data:
                return True

            # 2. If not exists, create one
            if not user_id:
                logger.warning(f"Creating session {session_id} failed: 'user_id' is required for new sessions.")
                return False

            data = {
                "id": session_id,
                "user_id": user_id,
                # title 등은 추후 업데이트하거나 기본값
            }

            def _create_session():
                return self.supabase.table(self.sessions_table).insert(data).execute()

            await anyio.to_thread.run_sync(_create_session)
            return True
        except Exception as e:
            logger.error(f"Error ensuring session {session_id}: {e}")
            return False

    async def get_messages_async(self, session_id: str, user_id: Optional[str] = None) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증
            if user_id:
                def _check_ownership():
                    return self.supabase.table(self.sessions_table) \
                        .select("id") \
                        .eq("id", session_id) \
                        .eq("user_id", user_id) \
                        .execute()

                session_check = await anyio.to_thread.run_sync(_check_ownership)

                if not session_check.data:
                    logger.warning(f"User {user_id} does not own session {session_id}")
                    return []

            def _fetch_messages():
                return self.supabase.table(self.messages_table) \
                    .select("message") \
                    .eq("session_id", session_id) \
                    .order("created_at", desc=False) \
                    .execute()

            response = await anyio.to_thread.run_sync(_fetch_messages)

            messages = []
            for row in response.data:
                msg_data = row.get("message")
                if msg_data:
                    restored = messages_from_dict([msg_data])
                    if restored:
                        messages.append(restored[0])
            return messages
        except Exception as e:
            logger.error(f"Error fetching messages from Supabase: {e}")
            return []

    def get_messages(self, session_id: str, user_id: Optional[str] = None) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Note:
            이 메서드는 ChatMemory 인터페이스와의 호환성을 위해 유지합니다.
            비동기 컨텍스트에서는 get_messages_async를 사용하세요.
        """
        try:
            asyncio.get_running_loop()
            logger.warning("get_messages called from async context. Consider using get_messages_async directly.")
            return run_sync(self.get_messages_async, session_id, user_id)
        except RuntimeError:
            return asyncio.run(self.get_messages_async(session_id, user_id))

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

        # 세션이 있는지 확인 (또는 생성)
        if not await self._ensure_session(session_id, user_id):
            logger.error(f"Cannot add message: Session {session_id} could not be established.")
            return

        msg_dict = message_to_dict(message)
        role = self._get_role(message)

        data = {
            "session_id": session_id,
            "role": role,
            "message": msg_dict
        }

        try:
            def _insert_message():
                return self.supabase.table(self.messages_table).insert(data).execute()

            await anyio.to_thread.run_sync(_insert_message)

            # (선택) chat_sessions의 last_message_at 업데이트
            # Use Python datetime instead of SQL string "now()" which PostgREST can't cast
            def _update_session():
                return self.supabase.table(self.sessions_table)\
                    .update({"last_message_at": datetime.now(timezone.utc).isoformat()})\
                    .eq("id", session_id)\
                    .execute()

            await anyio.to_thread.run_sync(_update_session)

        except Exception as e:
            logger.error(f"Error saving message to Supabase: {e}")

    def _add_message(self, session_id: str, message: BaseMessage, **kwargs) -> None:
        """메시지 저장 로직 (동기 wrapper)

        Note:
            이 동기 메서드는 레거시 호환성을 위해 유지됩니다.
            비동기 컨텍스트에서는 _add_message_async를 직접 사용하세요.
        """
        try:
            # 현재 실행 중인 이벤트 루프가 있는 경우
            asyncio.get_running_loop()
            # 비동기 컨텍스트에서 호출된 경우 경고
            logger.warning("_add_message called from async context. Consider using _add_message_async directly.")
            # anyio.from_thread를 사용하여 비동기 함수 호출
            run_sync(self._add_message_async, session_id, message, **kwargs)
        except RuntimeError:
            # 이벤트 루프가 없는 경우 (동기 컨텍스트)
            asyncio.run(self._add_message_async(session_id, message, **kwargs))

    def add_user_message(self, session_id: str, content: str, **kwargs) -> None:
        """사용자 메시지 추가"""
        # kwargs에서 메타데이터 추출 및 additional_kwargs로 전달
        metadata = {k: v for k, v in kwargs.items() if k != 'user_id'}
        msg = HumanMessage(content=content, additional_kwargs=metadata)
        self._add_message(session_id, msg, **kwargs)

    def add_ai_message(self, session_id: str, content: str, **kwargs) -> None:
        """AI 메시지 추가"""
        # kwargs에서 메타데이터 추출 및 additional_kwargs로 전달
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

    async def clear_async(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 히스토리 메시지 삭제 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증
            if user_id:
                def _check_ownership():
                    return self.supabase.table(self.sessions_table) \
                        .select("id") \
                        .eq("id", session_id) \
                        .eq("user_id", user_id) \
                        .execute()

                session_check = await anyio.to_thread.run_sync(_check_ownership)

                if not session_check.data:
                    logger.warning(f"User {user_id} cannot clear session {session_id}")
                    return

            def _clear_messages():
                return self.supabase.table(self.messages_table) \
                    .delete() \
                    .eq("session_id", session_id) \
                    .execute()

            await anyio.to_thread.run_sync(_clear_messages)
        except Exception as e:
            logger.error(f"Error clearing messages for session {session_id}: {e}")

    def clear(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 히스토리 메시지 삭제 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            asyncio.get_running_loop()
            logger.warning("clear called from async context. Consider using clear_async directly.")
            run_sync(self.clear_async, session_id, user_id)
        except RuntimeError:
            asyncio.run(self.clear_async(session_id, user_id))

    async def delete_session_async(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 및 관련 메시지 완전 삭제 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증 후 삭제
            if user_id:
                def _delete_with_user():
                    return self.supabase.table(self.sessions_table) \
                        .delete() \
                        .eq("id", session_id) \
                        .eq("user_id", user_id) \
                        .execute()

                await anyio.to_thread.run_sync(_delete_with_user)
            else:
                def _delete_session():
                    return self.supabase.table(self.sessions_table) \
                        .delete() \
                        .eq("id", session_id) \
                        .execute()

                await anyio.to_thread.run_sync(_delete_session)
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 및 관련 메시지 완전 삭제 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            asyncio.get_running_loop()
            logger.warning("delete_session called from async context. Consider using delete_session_async directly.")
            run_sync(self.delete_session_async, session_id, user_id)
        except RuntimeError:
            asyncio.run(self.delete_session_async(session_id, user_id))

    async def list_sessions_async(self, user_id: Optional[str] = None) -> List[str]:
        """모든 세션 ID 조회 (비동기)

        Args:
            user_id: 사용자 ID (제공 시 해당 사용자의 세션만 조회)
        """
        try:
            def _list_sessions():
                query = self.supabase.table(self.sessions_table).select("id")

                if user_id:
                    query = query.eq("user_id", user_id)

                response = query.order("last_message_at", desc=True).execute()
                return [item['id'] for item in response.data]

            return await anyio.to_thread.run_sync(_list_sessions)
        except Exception as e:
            logger.error(f"Error listing sessions from Supabase: {e}")
            return []

    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """모든 세션 ID 조회 (동기 wrapper - 레거시 호환용)

        Args:
            user_id: 사용자 ID (제공 시 해당 사용자의 세션만 조회)
        """
        try:
            asyncio.get_running_loop()
            logger.warning("list_sessions called from async context. Consider using list_sessions_async directly.")
            return run_sync(self.list_sessions_async, user_id)
        except RuntimeError:
            return asyncio.run(self.list_sessions_async(user_id))

    async def get_message_count_async(self, session_id: str, user_id: Optional[str] = None) -> int:
        """세션의 메시지 개수 (비동기)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증
            if user_id:
                def _check_ownership():
                    return self.supabase.table(self.sessions_table) \
                        .select("id") \
                        .eq("id", session_id) \
                        .eq("user_id", user_id) \
                        .execute()

                session_check = await anyio.to_thread.run_sync(_check_ownership)

                if not session_check.data:
                    return 0

            def _count_messages():
                response = self.supabase.table(self.messages_table) \
                    .select("id", count="exact") \
                    .eq("session_id", session_id) \
                    .execute()
                return response.count if response.count is not None else 0

            return await anyio.to_thread.run_sync(_count_messages)
        except Exception:
            return 0

    def get_message_count(self, session_id: str, user_id: Optional[str] = None) -> int:
        """세션의 메시지 개수 (동기 wrapper - 레거시 호환용)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            asyncio.get_running_loop()
            logger.warning("get_message_count called from async context. Consider using get_message_count_async directly.")
            return run_sync(self.get_message_count_async, session_id, user_id)
        except RuntimeError:
            return asyncio.run(self.get_message_count_async(session_id, user_id))
