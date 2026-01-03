"""슈퍼바이저 도구 정의"""
from typing import Optional
from langchain_core.tools import tool
from src.workers import WebSearchWorker

# 전역 워커 인스턴스 (lazy initialization 권장)
_web_worker: Optional[WebSearchWorker] = None

def _get_web_worker() -> WebSearchWorker:
    global _web_worker
    if _web_worker is None:
        _web_worker = WebSearchWorker()
    return _web_worker

@tool
async def think(thought: str) -> str:
    """
    생각을 기록합니다. 도구를 호출하거나 답변하기 전에 반드시 이 도구로 생각을 먼저 말하세요.

    Args:
        thought: 현재 상황 분석, 다음 행동 계획, 또는 판단 근거

    예시:
        - "최신 정보가 필요하므로 웹 검색을 해야겠다"
        - "검색 결과에서 A 정보는 얻었지만 B 정보가 부족하다. 추가 검색이 필요하다"
        - "충분한 정보를 얻었다. 이제 답변을 작성하자"
    """
    return thought


@tool
async def aweb_search(query: str) -> str:
    """웹에서 최신 정보를 검색합니다 (비동기)."""
    worker = _get_web_worker()
    result = await worker.execute(query)
    return f"[웹 검색 결과]\n{result.content}"


# Supervisor에서 사용할 도구 목록
TOOLS = [think, aweb_search]
