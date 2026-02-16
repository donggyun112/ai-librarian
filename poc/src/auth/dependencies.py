from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import AsyncClient, create_async_client
from loguru import logger
from config import config
from .schemas import User

# Bearer Token Scheme mainly for Swagger UI
oauth2_scheme = HTTPBearer(auto_error=False)

def get_supabase_client(request: Request) -> AsyncClient:
    """
    Dependency to get Supabase Client (ANON_KEY)
    RLS는 JWT에 따라 적용됩니다.
    """
    if not hasattr(request.app.state, "supabase"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase client not initialized"
        )
    return request.app.state.supabase


async def verify_current_user(request: Request) -> User:
    """
    미들웨어에서 검증된 사용자 정보를 가져옵니다.

    AuthMiddleware가 request.state.user에 Supabase User 객체를 저장하므로,
    이 의존성은 해당 정보를 User 스키마로 변환만 합니다.
    """
    supabase_user = getattr(request.state, "user", None)
    if not supabase_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return User(
        id=supabase_user.id,
        aud=supabase_user.aud,
        role=supabase_user.role or "authenticated",
        email=supabase_user.email,
        email_confirmed_at=supabase_user.email_confirmed_at,
        phone=supabase_user.phone,
        confirmed_at=supabase_user.confirmed_at,
        last_sign_in_at=supabase_user.last_sign_in_at,
        app_metadata=supabase_user.app_metadata or {},
        user_metadata=supabase_user.user_metadata or {},
        identities=supabase_user.identities or [],
        created_at=supabase_user.created_at,
        updated_at=supabase_user.updated_at,
    )


async def get_user_scoped_client(
    request: Request,
) -> AsyncGenerator[AsyncClient, None]:
    """
    미들웨어에서 저장된 토큰으로 per-request Supabase client를 생성합니다.
    RLS가 적용된 사용자 범위 쿼리에 사용합니다.
    """
    token = getattr(request.state, "token", None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        client: AsyncClient = await create_async_client(
            config.SUPABASE_URL,
            config.SUPABASE_ANON_KEY
        )
    except Exception as e:
        logger.error(f"Failed to create user-scoped Supabase client: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize database connection"
        )

    try:
        client.postgrest.auth(token)
        yield client
    finally:
        await client.aclose()
