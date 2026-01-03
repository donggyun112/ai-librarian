"""워커 팩토리"""
from typing import Dict
from src.schemas.models import WorkerType
from src.workers.base import BaseWorker
from src.workers.web_worker import WebSearchWorker


def create_all_workers() -> Dict[WorkerType, BaseWorker]:
    """모든 워커 인스턴스 생성"""
    return {
        WorkerType.WEB_SEARCH: WebSearchWorker(),
    }


def create_worker(worker_type: WorkerType) -> BaseWorker:
    """특정 워커 인스턴스 생성"""
    workers = {
        WorkerType.WEB_SEARCH: WebSearchWorker,
    }
    return workers[worker_type]()
