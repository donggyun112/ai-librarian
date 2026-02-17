from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import AsyncClient, create_async_client
from loguru import logger
from config import config
from .schemas import User, UserIdentity

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

    def _to_str(val: Any) -> Optional[str]:
        if val is None:
            return None
        return val.isoformat() if hasattr(val, "isoformat") else str(val)

    identities = []
    for ident in supabase_user.identities or []:
        identities.append(UserIdentity(
            id=ident.id,
            user_id=ident.user_id,
            identity_data=getattr(ident, "identity_data", {}),
            provider=ident.provider,
            created_at=_to_str(getattr(ident, "created_at", None)),
            last_sign_in_at=_to_str(getattr(ident, "last_sign_in_at", None)),
            updated_at=_to_str(getattr(ident, "updated_at", None)),
        ))

    return User(
        id=supabase_user.id,
        aud=supabase_user.aud,
        role=supabase_user.role or "authenticated",
        email=supabase_user.email,
        email_confirmed_at=_to_str(supabase_user.email_confirmed_at),
        phone=supabase_user.phone,
        confirmed_at=_to_str(supabase_user.confirmed_at),
        last_sign_in_at=_to_str(supabase_user.last_sign_in_at),
        app_metadata=supabase_user.app_metadata or {},
        user_metadata=supabase_user.user_metadata or {},
        identities=identities,
        created_at=_to_str(supabase_user.created_at),
        updated_at=_to_str(supabase_user.updated_at),
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

    client.postgrest.auth(token)
    yield client
