"""워커 베이스 클래스"""
from abc import ABC, abstractmethod
from src.schemas.models import WorkerResult, WorkerType


class BaseWorker(ABC):
    """모든 워커의 베이스 클래스"""

    @property
    @abstractmethod
    def worker_type(self) -> WorkerType:
        """워커 타입 반환"""
        pass

    @abstractmethod
    async def execute(self, query: str) -> WorkerResult:
        """
        쿼리를 실행하고 결과를 반환합니다.

        Args:
            query: 실행할 쿼리

        Returns:
            WorkerResult: 실행 결과
        """
        pass

    def _create_result(
        self,
        query: str,
        content: str,
        confidence: float = 0.0,
        sources: list = None,
        success: bool = True,
        error: str = None
    ) -> WorkerResult:
        """결과 객체 생성 헬퍼"""
        return WorkerResult(
            worker=self.worker_type,
            query=query,
            content=content,
            confidence=confidence,
            sources=sources or [],
            success=success,
            error=error
        )
