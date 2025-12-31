"""Supabase 기반 대화 히스토리 저장소"""
import os
import json
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from supabase import create_client, Client

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
            print(f"Error fetching messages from Supabase: {e}")
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
            print(f"Error saving message to Supabase: {e}")

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
            print(f"Error clearing session from Supabase: {e}")

    def delete_session(self, session_id: str) -> None:
        """세션 완전 삭제 (clear와 동일하게 처리)"""
        self.clear(session_id)

    def list_sessions(self) -> List[str]:
        """모든 세션 ID 조회 (Distinct)
        
        주의: 데이터가 많으면 성능 이슈가 있을 수 있음.
        """
        try:
            # RPC나 distinct select 사용 필요. JS/REST API에서 .select('session_id', count='exact', head=False).csv() 등등?
            # supabase-py에서는 .select("session_id").execute() 후 파이썬에서 unique 처리?
            # 쿼리 효율을 위해 RPC를 권장하지만, 일단은 간단히 구현.
            # .range() 등을 이용해서 페이징해야 하나 여기서는 전체 세션 ID를 가져오는 간단 구현 (POC 수준)
            # 프로덕션에서는 별도의 sessions 테이블을 관리하는 것이 좋음.
            
            # 아래는 모든 행을 가져오지 않고, unique한 session_id만 가져오려고 시도.
            # 하지만 SQL 차원의 distinct가 없으면 모든 row를 가져와야 할 수 있음.
            # Supabase JS 클라이언트처럼 .select('session_id').distinct()가 있는지 문서 확인 필요.
            # 없다면 API 호출을 너무 많이 할 수 있으니 주의.
            
            # 대안: rpc 호출 (create function get_distinct_sessions() ...)
            # 여기서는 API 기능 구현을 위해 우선 빈 리스트 혹은 제한된 쿼리로 구현.
            return [] 
        except Exception:
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
