"""유틸리티 함수"""
import asyncio
from typing import Coroutine, TypeVar

import nest_asyncio

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """동기 환경에서 비동기 함수 실행"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 이벤트 루프가 실행 중인 경우 (Jupyter 등)
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # 이벤트 루프가 없는 경우
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
