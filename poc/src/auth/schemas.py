"""Authentication request/response schemas."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# =============================================================================
# Password Validation
# =============================================================================

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128  # Reasonable max to prevent DoS

# OWASP recommended: at least one uppercase, lowercase, digit, and special char
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~])[A-Za-z\d!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]{8,}$"
)


def validate_password_strength(password: str) -> str:
    """
    Validate password meets complexity requirements.

    Requirements (OWASP guidelines):
    - Minimum 8 characters
    - Maximum 128 characters
    - At least one lowercase letter
    - At least one uppercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]", password):
        raise ValueError("Password must contain at least one special character")
    return password


# =============================================================================
# Request Models
# =============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="Password: 8-128 chars, must include uppercase, lowercase, digit, and special char",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str = Field(..., max_length=PASSWORD_MAX_LENGTH)


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset request."""

    token: str
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="Password: 8-128 chars, must include uppercase, lowercase, digit, and special char",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


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
