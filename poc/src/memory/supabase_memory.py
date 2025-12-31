"""Supabase 기반 대화 히스토리 저장소"""
import os
import json
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from supabase import create_client, Client
from loguru import logger

from .base import ChatMemory
from config import config

class SupabaseChatMemory(ChatMemory):
    """Supabase를 이용한 대화 히스토리 영구 저장소
    
    테이블 스키마 (chat_history):
        id: uuid, pk
        session_id: text
        user_id: text (optional)
        message: jsonb (LangChain message dump)
        created_at: timestamp
    """

    def __init__(self, url: str, key: str):
        self.supabase: Client = create_client(url, key)
        self.table_name = "chat_history"

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """세션의 전체 대화 히스토리 조회 (생성 시간 오름차순)"""
        try:
            response = self.supabase.table(self.table_name) \
                .select("message") \
                .eq("session_id", session_id) \
                .order("created_at", desc=False) \
                .execute()
            
            messages = []
            for row in response.data:
                # message 필드 자체가 LangChain의 JSON dump라고 가정
                # 만약 message_to_dict로 저장했다면 messages_from_dict로 복원 가능
                # 여기서는 단건 처리를 위해 간단히 파싱
                msg_data = row.get("message")
                if msg_data:
                    # messages_from_dict는 리스트를 받으므로 리스트로 감싸서 처리 후 0번째 요소 추출
                    restored = messages_from_dict([msg_data])
                    if restored:
                        messages.append(restored[0])
            return messages
        except Exception as e:
            # 로그 처리 필요 (여기서는 print 혹은 무시)
            logger.error(f"Error fetching messages from Supabase: {e}")
            return []

    def _add_message(self, session_id: str, message: BaseMessage, **kwargs) -> None:
        """공통 메시지 저장 로직"""
        # LangChain 메시지를 dict로 변환
        msg_dict = message_to_dict(message)
        
        data = {
            "session_id": session_id,
            "message": msg_dict
        }
        
        # user_id 등 추가 메타데이터가 있으면 최상위 컬럼에 매핑 (테이블에 해당 컬럼이 존재해야 함)
        if "user_id" in kwargs:
            data["user_id"] = kwargs["user_id"]
            
        try:
            self.supabase.table(self.table_name).insert(data).execute()
        except Exception as e:
            logger.error(f"Error saving message to Supabase: {e}")

    def add_user_message(self, session_id: str, content: str, **kwargs) -> None:
        """사용자 메시지 추가"""
        msg = HumanMessage(content=content)
        self._add_message(session_id, msg, **kwargs)

    def add_ai_message(self, session_id: str, content: str, **kwargs) -> None:
        """AI 메시지 추가"""
        msg = AIMessage(content=content)
        self._add_message(session_id, msg, **kwargs)

    def clear(self, session_id: str) -> None:
        """세션 히스토리 초기화"""
        try:
            self.supabase.table(self.table_name) \
                .delete() \
                .eq("session_id", session_id) \
                .execute()
        except Exception as e:
            logger.error(f"Error clearing session from Supabase: {e}")

    def delete_session(self, session_id: str) -> None:
        """세션 완전 삭제 (clear와 동일하게 처리)"""
        self.clear(session_id)

    def list_sessions(self) -> List[str]:
        """모든 세션 ID 조회 (Distinct)
        
        Requires 'get_distinct_sessions' RPC function in Supabase.
        """
        try:
            response = self.supabase.rpc("get_distinct_sessions").execute()
            # response.data should be a list of dicts: [{'session_id': '...'}]
            return [item['session_id'] for item in response.data]
        except Exception as e:
            logger.error(f"Error listing sessions from Supabase: {e}")
            return []

    def get_message_count(self, session_id: str) -> int:
        """세션의 메시지 개수"""
        try:
            # count='exact', head=True -> 데이터 없이 개수만
            response = self.supabase.table(self.table_name) \
                .select("id", count="exact") \
                .eq("session_id", session_id) \
                .execute()
            return response.count if response.count is not None else 0
        except Exception:
            return 0
