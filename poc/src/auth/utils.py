from contextlib import asynccontextmanager
from collections import defaultdict, deque
import asyncio
from fastapi import FastAPI
from supabase import create_async_client, AsyncClient, ClientOptions
from loguru import logger
from config import config
from src.memory import SupabaseChatMemory
from src.supervisor import Supervisor


async def create_supabase_client() -> AsyncClient:
    """
    Supabase Client 생성 (ANON_KEY 사용)

    RLS가 활성화된 사용자 범위 접근을 위해 사용합니다.
    JWT 검증 등 인증 작업에도 사용됩니다.
    """
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        raise RuntimeError(
            "Supabase configuration missing. Set SUPABASE_URL and SUPABASE_ANON_KEY."
        )

    return await create_async_client(
        config.SUPABASE_URL,
        config.SUPABASE_ANON_KEY,
        options=ClientOptions(
            postgrest_client_timeout=10,
            storage_client_timeout=10,
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager
    애플리케이션 시작/종료 시 리소스를 관리합니다.
    """
    # Startup
    try:
        logger.info("Initializing Supabase Client...")
        app.state.supabase = await create_supabase_client()

        logger.info(f"Supabase Memory enabled: {config.SUPABASE_URL}")
        app.state.memory = SupabaseChatMemory(
            url=config.SUPABASE_URL,
            key=config.SUPABASE_ANON_KEY,
            require_user_scoped_client=True,
        )

        app.state.supervisor = Supervisor(memory=app.state.memory)
        app.state.rate_limiter = {
            "lock": asyncio.Lock(),
            "hits": defaultdict(deque),
        }
    except RuntimeError as e:
        logger.error(
            f"Startup failed: {e} | "
            f"SUPABASE_URL={'set' if config.SUPABASE_URL else 'MISSING'}, "
            f"SUPABASE_ANON_KEY={'set' if config.SUPABASE_ANON_KEY else 'MISSING'}"
        )
        raise

    yield

    # Shutdown
    logger.info("Closing Supabase Client...")
    if hasattr(app.state, "supabase") and app.state.supabase:
        await app.state.supabase.aclose()
