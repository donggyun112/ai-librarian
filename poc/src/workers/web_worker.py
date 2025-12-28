"""웹 서치 워커 - DuckDuckGo 사용"""
import asyncio

from ddgs import DDGS

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker


class WebSearchWorker(BaseWorker):
    """웹 검색을 수행하는 워커 (DuckDuckGo)"""

    def __init__(self, max_results: int = 10):
        self.ddgs = DDGS()
        self.max_results = max_results

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.WEB_SEARCH

    async def execute(self, query: str) -> WorkerResult:
        """웹 검색 실행"""
        try:
            # 동기 함수를 별도 스레드에서 실행하여 이벤트 루프 블로킹 방지
            results = await asyncio.to_thread(
                lambda: list(self.ddgs.text(query, max_results=self.max_results))
            )

            if not results:
                return self._create_result(
                    query=query,
                    content="검색 결과가 없습니다.",
                    confidence=0.0,
                    sources=[]
                )

            content_parts = []
            sources = []

            for i, result in enumerate(results, 1):
                title = result.get("title", "")
                body = result.get("body", "")
                url = result.get("href", "")

                content_parts.append(f"[{i}] {title}\n{body}\n출처: {url}")
                sources.append(url)

            content = "\n\n".join(content_parts)

            return self._create_result(
                query=query,
                content=content,
                confidence=0.7,  # DuckDuckGo는 점수 없음, 기본값 사용
                sources=sources
            )

        except Exception as e:
            return self._create_result(
                query=query,
                content="",
                success=False,
                error=f"웹 검색 실패: {str(e)}"
            )
