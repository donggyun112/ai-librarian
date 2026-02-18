from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI
from supabase import create_async_client, AsyncClient, ClientOptions
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI Lifespan Context Manager
    애플리케이션 시작/종료 시 리소스를 관리합니다.
    """
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is required for LangGraph checkpointer. "
            "Set it to the Supabase Postgres direct connection string."
        )

    try:
        logger.info("Initializing Supabase Client...")
        app.state.supabase = await create_supabase_client()

        logger.info(f"Supabase Memory enabled: {config.SUPABASE_URL}")
        app.state.memory = SupabaseChatMemory(
            url=config.SUPABASE_URL,
            key=config.SUPABASE_ANON_KEY,
            require_user_scoped_client=True,
        )

        logger.info("Initializing LangGraph checkpointer (Postgres)...")
        async with AsyncConnectionPool(
            config.DATABASE_URL,
            max_size=10,
            kwargs={
                "autocommit": True,
                # None = prepared statement 완전 비활성화
                # Supabase 세션 풀러는 커넥션을 재사용하므로
                # 이전 세션의 prepared statement가 남아 DuplicatePreparedStatement 발생
                "prepare_threshold": None,
                "options": "-c search_path=public",
            },
        ) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            # checkpointer 테이블 자동 생성 (idempotent)
            await checkpointer.setup()

            app.state.supervisor = Supervisor(
                memory=app.state.memory,
                checkpointer=checkpointer,
            )
            logger.info("LangGraph checkpointer initialized")

            yield

    except RuntimeError as e:
        logger.error(
            f"Startup failed: {e} | "
            f"SUPABASE_URL={'set' if config.SUPABASE_URL else 'MISSING'}, "
            f"SUPABASE_ANON_KEY={'set' if config.SUPABASE_ANON_KEY else 'MISSING'}, "
            f"DATABASE_URL={'set' if config.DATABASE_URL else 'MISSING'}"
        )
        raise
    finally:
        # Shutdown
        logger.info("Closing Supabase Client...")
        if hasattr(app.state, "supabase") and app.state.supabase:
            await app.state.supabase.postgrest.session.aclose()
            logger.info("Supabase Client closed successfully")
