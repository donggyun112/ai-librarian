"""Authentication module for ai-librarian."""

from .dependencies import (
    get_auth_service,
    get_current_user_id,
    get_jwt_handler,
    get_optional_user_id,
    get_supabase_client,
    get_user_repository,
)
from .jwt_handler import JWTHandler
from .password import hash_password, verify_password
from .repository import UserRepository
from .routes import router as auth_router
from .schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from .service import AuthService

__all__ = [
    # Router
    "auth_router",
    # Schemas
    "RegisterRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "VerifyEmailRequest",
    "TokenResponse",
    "UserResponse",
    "MessageResponse",
    # Core
    "JWTHandler",
    "hash_password",
    "verify_password",
    "AuthService",
    "UserRepository",
    # Dependencies
    "get_supabase_client",
    "get_jwt_handler",
    "get_user_repository",
    "get_auth_service",
    "get_current_user_id",
    "get_optional_user_id",
]
