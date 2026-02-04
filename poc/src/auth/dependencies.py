from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import AsyncClient, create_async_client
from loguru import logger
from config import config
from .schemas import User

# Bearer Token Scheme mainly for Swagger UI
oauth2_scheme = HTTPBearer(auto_error=True)

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

async def get_user_scoped_client(
    token: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a per-request Supabase client with the caller's JWT for RLS.

    Per-request creation is intentional: concurrent requests must not
    share auth headers, so each request gets its own client instance.
    """
    client: AsyncClient | None = None
    try:
        client = await create_async_client(
            config.SUPABASE_URL,
            config.SUPABASE_ANON_KEY
        )
        client.postgrest.auth(token.credentials)

        yield client

    except Exception as e:
        logger.error(f"Failed to create user-scoped Supabase client: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize database connection"
        )
    finally:
        if client is not None:
            await client.aclose()

async def verify_current_user(
    token: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    client: AsyncClient = Depends(get_supabase_client)
) -> User:
    """
    Verify the JWT token with Supabase Auth.
    Returns the User object if valid, raises 401 otherwise.

    This works for all login methods: OAuth, Magic-link, Passkey
    """
    try:
        # client.auth.get_user(token) verifies signature, expiry, and revocation
        response = await client.auth.get_user(token.credentials)

        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Convert Supabase User to our User schema
        supabase_user = response.user

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

    except HTTPException:
        raise
    except Exception as e:
        # Security: log error type only, not full message (may contain sensitive info)
        logger.error(f"Token verification failed: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
