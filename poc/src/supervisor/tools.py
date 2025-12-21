"""슈퍼바이저 도구 정의"""
import asyncio
from typing import Optional
from langchain_core.tools import tool
from src.workers import RAGWorker, WebSearchWorker
from src.schemas.models import WorkerType

# 전역 워커 인스턴스 (lazy initialization 권장)
_rag_worker: Optional[RAGWorker] = None
_web_worker: Optional[WebSearchWorker] = None

def _get_rag_worker() -> RAGWorker:
    global _rag_worker
    if _rag_worker is None:
        _rag_worker = RAGWorker()
    return _rag_worker

def _get_web_worker() -> WebSearchWorker:
    global _web_worker
    if _web_worker is None:
        _web_worker = WebSearchWorker()
    return _web_worker

@tool
def rag_search(query: str) -> str:
    """
    내부 문서(기술 문서, 매뉴얼 등)에서 정보를 검색합니다.
    회사 내부 정보나 기술적인 상세 내용이 필요할 때 사용하세요.
    """
    worker = _get_rag_worker()
    # 비동기 실행을 위한 헬퍼 (LangChain Tool은 기본적으로 동기 실행 가정 시)
    # 하지만 여기서는 간단히 asyncio.run을 쓰거나, 
    # Supervisor가 비동기로 호출할 것이므로 비동기 래퍼가 필요할 수 있음.
    # LangChain의 @tool은 async 함수도 지원함.
    
    # 여기서는 동기 컨텍스트에서 호출될 경우를 대비해 loop 확인
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        # 이미 루프가 도는 경우 (비동기 환경)
        # 이 함수가 async로 정의되면 좋지만, @tool은 동기/비동기 버전을 별도로 관리 가능
        # 임시로 동기 호출을 지원하기 위해 loop.run_until_complete 사용 불가
        raise RuntimeError("Async event loop is already running. Use arag_search instead.")
    
    return loop.run_until_complete(worker.execute(query)).content

@tool
async def arag_search(query: str) -> str:
    """내부 문서에서 정보를 검색합니다 (비동기)."""
    worker = _get_rag_worker()
    result = await worker.execute(query)
    return f"[RAG 검색 결과]\n{result.content}"

@tool
async def aweb_search(query: str) -> str:
    """웹에서 최신 정보를 검색합니다 (비동기)."""
    worker = _get_web_worker()
    result = await worker.execute(query)
    return f"[웹 검색 결과]\n{result.content}"

# Supervisor에서 사용할 도구 목록
TOOLS = [arag_search, aweb_search]
