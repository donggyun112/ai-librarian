"""Supabase 기반 대화 히스토리 저장소"""
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from supabase import create_client, Client
from loguru import logger
import anyio

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

    def get_messages(self, session_id: str, user_id: Optional[str] = None) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)

        Note:
            이 메서드는 ChatMemory 인터페이스와의 호환성을 위해 동기 메서드로 유지합니다.
            내부적으로 anyio.from_thread.run_sync를 통해 비동기 작업을 처리할 수 있지만,
            현재 구현에서는 Supervisor가 비동기 컨텍스트에서 호출하므로 동기 호출을 유지합니다.
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증
            if user_id:
                session_check = self.supabase.table(self.sessions_table) \
                    .select("id") \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()

                if not session_check.data:
                    logger.warning(f"User {user_id} does not own session {session_id}")
                    return []

            response = self.supabase.table(self.messages_table) \
                .select("message") \
                .eq("session_id", session_id) \
                .order("created_at", desc=False) \
                .execute()

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
            def _update_session():
                return self.supabase.table(self.sessions_table)\
                    .update({"last_message_at": "now()"})\
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
        import asyncio
        try:
            # 현재 실행 중인 이벤트 루프가 있는 경우
            asyncio.get_running_loop()
            # 비동기 컨텍스트에서 호출된 경우 경고
            logger.warning("_add_message called from async context. Consider using _add_message_async directly.")
            # anyio.from_thread를 사용하여 비동기 함수 호출
            from anyio.from_thread import run_sync
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

    def clear(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 히스토리 메시지 삭제 (세션 자체는 유지할 수도 있고, 정책에 따라 다름)
        여기서는 chat_messages만 삭제하는 것으로 구현.

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증
            if user_id:
                session_check = self.supabase.table(self.sessions_table) \
                    .select("id") \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()

                if not session_check.data:
                    logger.warning(f"User {user_id} cannot clear session {session_id}")
                    return

            self.supabase.table(self.messages_table) \
                .delete() \
                .eq("session_id", session_id) \
                .execute()
        except Exception as e:
            logger.error(f"Error clearing messages for session {session_id}: {e}")

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        """세션 및 관련 메시지 완전 삭제 (Cascade 설정되어 있으면 세션만 삭제하면 됨)

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증 후 삭제
            if user_id:
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
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")

    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """모든 세션 ID 조회

        Args:
            user_id: 사용자 ID (제공 시 해당 사용자의 세션만 조회)
        """
        try:
            query = self.supabase.table(self.sessions_table).select("id")

            if user_id:
                query = query.eq("user_id", user_id)

            response = query.order("last_message_at", desc=True).execute()
            return [item['id'] for item in response.data]
        except Exception as e:
            logger.error(f"Error listing sessions from Supabase: {e}")
            return []

    def get_message_count(self, session_id: str, user_id: Optional[str] = None) -> int:
        """세션의 메시지 개수

        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (제공 시 소유권 검증)
        """
        try:
            # user_id가 제공된 경우 세션 소유권 검증
            if user_id:
                session_check = self.supabase.table(self.sessions_table) \
                    .select("id") \
                    .eq("id", session_id) \
                    .eq("user_id", user_id) \
                    .execute()

                if not session_check.data:
                    return 0

            response = self.supabase.table(self.messages_table) \
                .select("id", count="exact") \
                .eq("session_id", session_id) \
                .execute()
            return response.count if response.count is not None else 0
        except Exception:
            return 0
