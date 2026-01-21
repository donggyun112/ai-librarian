"""Authentication request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# Request Models
# =============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset request."""

    token: str
    new_password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class VerifyEmailRequest(BaseModel):
    """Email verification request."""

    token: str


# =============================================================================
# Response Models
# =============================================================================


class TokenResponse(BaseModel):
    """Authentication token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class UserResponse(BaseModel):
    """User profile response."""

    model_config = {"from_attributes": True}

    id: str
    email: str
    email_verified: bool
    created_at: datetime


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class AuthErrorResponse(BaseModel):
    """Authentication error response."""

    detail: str
    error_code: Optional[str] = None
