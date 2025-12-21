"""웹 서치 워커 - DuckDuckGo 사용"""
from ddgs import DDGS

from src.schemas.models import WorkerResult, WorkerType
from src.workers.base import BaseWorker


class WebSearchWorker(BaseWorker):
    """웹 검색을 수행하는 워커 (DuckDuckGo)"""

    def __init__(self):
        self.ddgs = DDGS()
        self.max_results = 5

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.WEB_SEARCH

    async def execute(self, query: str) -> WorkerResult:
        """웹 검색 실행"""
        try:
            # 동기 함수인 self.ddgs.text를 비동기 루프에서 실행해야 하지만, 
            # 간단한 구현을 위해 여기서는 직접 호출합니다. 
            # 필요시 asyncio.to_thread로 감쌀 수 있습니다.
            results = list(self.ddgs.text(query, max_results=self.max_results))

            if not results:
                return self._create_result(
                    query=query,
                    content="검색 결과가 없습니다.",
                    confidence=0.0,
                    sources=[]
                )

            content_parts = []
            sources = []

            for result in results:
                title = result.get("title", "")
                body = result.get("body", "")
                url = result.get("href", "")

                content_parts.append(f"[{title}]\n{body}")
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
