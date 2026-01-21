"""Authentication dependencies for FastAPI."""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from supabase import Client, create_client

from config import config

from .jwt_handler import JWTHandler
from .repository import UserRepository
from .service import AuthService


# Singleton instances
_supabase_client: Optional[Client] = None
_jwt_handler: Optional[JWTHandler] = None


def get_supabase_client() -> Client:
    """Get or create the Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_ROLE_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase not configured",
            )
        _supabase_client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client


def get_jwt_handler() -> JWTHandler:
    """Get or create the JWT handler singleton."""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler()
    return _jwt_handler


def get_user_repository(client: Client = Depends(get_supabase_client)) -> UserRepository:
    """Get a UserRepository instance."""
    return UserRepository(client)


def get_auth_service(
    repository: UserRepository = Depends(get_user_repository),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> AuthService:
    """Get an AuthService instance."""
    return AuthService(repository, jwt_handler)


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> str:
    """
    Extract and validate user_id from JWT access token.

    Args:
        authorization: Authorization header value
        jwt_handler: JWT handler instance

    Returns:
        User ID from the token

    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Validate JWT
    payload = jwt_handler.validate_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload["sub"]


async def get_optional_user_id(
    authorization: Optional[str] = Header(None),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> Optional[str]:
    """
    Extract user_id from JWT if provided, otherwise return None.

    Args:
        authorization: Authorization header value
        jwt_handler: JWT handler instance

    Returns:
        User ID from the token or None if not provided
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    payload = jwt_handler.validate_access_token(token)

    if not payload:
        return None

    return payload["sub"]
