from contextlib import asynccontextmanager
from fastapi import FastAPI
from supabase import create_async_client, AsyncClient, ClientOptions
from loguru import logger
from config import config

def create_supabase_client() -> AsyncClient:
    """
    Supabase Async Client 생성 (Factory Pattern)
    state 저장을 위한 factory 함수입니다.
    """
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        logger.warning("Supabase configuration missing (URL or ANON_KEY). Auth might fail.")
    
    return create_async_client(
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
    logger.info("Initializing Supabase Client...")
    app.state.supabase = create_supabase_client()
    
    yield
    
    # Shutdown
    # supabase-py's AsyncClient currently doesn't require explicit close, 
    # but if it does in future, add it here.
    logger.info("Closing Supabase Client resources...")
