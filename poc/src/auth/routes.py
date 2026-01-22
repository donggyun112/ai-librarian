"""Authentication API routes."""

from fastapi import APIRouter, Depends, Request

from .dependencies import get_auth_service, get_current_user_id
from .rate_limit import (
    check_login_rate_limit,
    check_password_reset_rate_limit,
    check_register_rate_limit,
    reset_login_rate_limit,
)
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

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract user agent and IP address from request."""
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post("/register", response_model=TokenResponse, dependencies=[Depends(check_register_rate_limit)])
async def register(
    request_body: RegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Register a new user with email and password.

    Returns access and refresh tokens on successful registration.
    Rate limited: 3 requests per minute, 10 minute block on exceed.
    """
    user_agent, ip_address = _get_client_info(request)
    return await auth_service.register(request_body, user_agent, ip_address)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(check_login_rate_limit)])
async def login(
    request_body: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Login with email and password.

    Returns access and refresh tokens on successful authentication.
    Rate limited: 5 requests per minute, 5 minute block on exceed.
    """
    user_agent, ip_address = _get_client_info(request)
    result = await auth_service.login(request_body, user_agent, ip_address)
    # Reset rate limit on successful login
    reset_login_rate_limit(request)
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request_body: RefreshTokenRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Refresh access token using a valid refresh token.

    The old refresh token is revoked and a new one is issued (token rotation).
    """
    user_agent, ip_address = _get_client_info(request)
    return await auth_service.refresh(request_body.refresh_token, user_agent, ip_address)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request_body: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Logout by revoking the refresh token.

    The access token will remain valid until it expires.
    """
    await auth_service.logout(request_body.refresh_token)
    return MessageResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    user_id: str = Depends(get_current_user_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Logout from all devices by revoking all refresh tokens.

    Requires a valid access token.
    """
    await auth_service.logout_all(user_id)
    return MessageResponse(message="Successfully logged out from all devices")


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: str = Depends(get_current_user_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """
    Get the current user's profile.

    Requires a valid access token.
    """
    return await auth_service.get_current_user(user_id)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    request_body: VerifyEmailRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Verify email address using verification token.

    The token is sent via email during registration.
    """
    await auth_service.verify_email(request_body.token)
    return MessageResponse(message="Email verified successfully")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(check_password_reset_rate_limit)],
)
async def forgot_password(
    request_body: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Request a password reset email.

    Always returns success to prevent email enumeration.
    Rate limited: 3 requests per minute, 10 minute block on exceed.
    """
    # Note: In production, send email here with the token
    _token = await auth_service.request_password_reset(request_body.email)
    # TODO: Send email with reset link: {FRONTEND_URL}/reset-password?token={_token}

    # Always return success to prevent email enumeration
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request_body: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Reset password using reset token.

    All existing sessions are revoked after password reset.
    """
    await auth_service.reset_password(request_body.token, request_body.new_password)
    return MessageResponse(message="Password reset successfully")
