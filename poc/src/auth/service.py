"""Authentication service - business logic for auth operations."""

from typing import Optional

from fastapi import HTTPException, status
from loguru import logger

from config import config

from .jwt_handler import JWTHandler
from .password import hash_password, verify_password
from .repository import UserRepository
from .schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


class AuthService:
    """Service class for authentication operations."""

    def __init__(self, repository: UserRepository, jwt_handler: Optional[JWTHandler] = None):
        """
        Initialize the auth service.

        Args:
            repository: UserRepository instance for database operations
            jwt_handler: JWTHandler instance (optional, creates default if not provided)
        """
        self.repo = repository
        self.jwt = jwt_handler or JWTHandler()

    async def register(
        self,
        request: RegisterRequest,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """
        Register a new user with email and password.

        Args:
            request: Registration request with email and password
            user_agent: Client user agent string
            ip_address: Client IP address

        Returns:
            TokenResponse with access and refresh tokens

        Raises:
            HTTPException: If email is already registered or user creation fails
        """
        # Check if user already exists
        existing = await self.repo.get_user_by_email(request.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        # Hash password and create user
        password_hashed = hash_password(request.password)
        user = await self.repo.create_user(request.email, password_hashed)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

        logger.info(f"User registered: user_id={user['id']}")

        # Generate tokens
        access_token = self.jwt.create_access_token(user["id"], user["email"])
        refresh_token, expires_at = self.jwt.create_refresh_token(user["id"])

        # Save refresh token
        await self.repo.save_refresh_token(
            user_id=user["id"],
            token=refresh_token,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.jwt.get_token_expiry_seconds(),
        )

    async def login(
        self,
        request: LoginRequest,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """
        Authenticate a user with email and password.

        Args:
            request: Login request with email and password
            user_agent: Client user agent string
            ip_address: Client IP address

        Returns:
            TokenResponse with access and refresh tokens

        Raises:
            HTTPException: If credentials are invalid
        """
        # Get user by email
        user = await self.repo.get_user_by_email(request.email)

        if not user or not user.get("password_hash"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify password
        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        logger.info(f"User logged in: user_id={user['id']}")

        # Generate tokens
        access_token = self.jwt.create_access_token(user["id"], user["email"])
        refresh_token, expires_at = self.jwt.create_refresh_token(user["id"])

        # Save refresh token
        await self.repo.save_refresh_token(
            user_id=user["id"],
            token=refresh_token,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.jwt.get_token_expiry_seconds(),
        )

    async def refresh(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponse:
        """
        Refresh access token using a valid refresh token.

        Args:
            refresh_token: The refresh token
            user_agent: Client user agent string
            ip_address: Client IP address

        Returns:
            TokenResponse with new access and refresh tokens

        Raises:
            HTTPException: If refresh token is invalid or expired
        """
        # Validate refresh token in database
        token_data = await self.repo.validate_refresh_token(refresh_token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        # Decode and validate JWT
        payload = self.jwt.validate_refresh_token(refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # Get user
        user = await self.repo.get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Revoke old refresh token (token rotation)
        await self.repo.revoke_refresh_token(refresh_token)

        # Generate new tokens
        access_token = self.jwt.create_access_token(user["id"], user["email"])
        new_refresh_token, expires_at = self.jwt.create_refresh_token(user["id"])

        # Save new refresh token
        await self.repo.save_refresh_token(
            user_id=user["id"],
            token=new_refresh_token,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=self.jwt.get_token_expiry_seconds(),
        )

    async def logout(self, refresh_token: str) -> None:
        """
        Logout by revoking the refresh token.

        Args:
            refresh_token: The refresh token to revoke
        """
        await self.repo.revoke_refresh_token(refresh_token)
        logger.info("User logged out")

    async def logout_all(self, user_id: str) -> None:
        """
        Logout from all devices by revoking all refresh tokens.

        Args:
            user_id: User's unique identifier
        """
        await self.repo.revoke_all_user_tokens(user_id)
        logger.info(f"All sessions revoked: user_id={user_id}")

    async def get_current_user(self, user_id: str) -> UserResponse:
        """
        Get the current user's profile.

        Args:
            user_id: User's unique identifier

        Returns:
            UserResponse with user profile data

        Raises:
            HTTPException: If user is not found
        """
        user = await self.repo.get_user_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return UserResponse(
            id=user["id"],
            email=user["email"],
            email_verified=user["email_verified"],
            created_at=user["created_at"],
        )

    async def verify_email(self, token: str) -> bool:
        """
        Verify a user's email with verification token.

        Args:
            token: The email verification token

        Returns:
            True if verification successful

        Raises:
            HTTPException: If token is invalid or expired
        """
        # Validate token
        token_data = await self.repo.validate_email_verification_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token",
            )

        # Mark email as verified
        success = await self.repo.verify_user_email(token_data["user_id"])
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify email",
            )

        # Mark token as used
        await self.repo.mark_email_verification_used(token)

        logger.info(f"Email verified: user_id={token_data['user_id']}")
        return True

    async def request_password_reset(self, email: str) -> Optional[str]:
        """
        Request a password reset for a user.

        Args:
            email: User's email address

        Returns:
            Reset token if user exists, None otherwise (don't reveal if user exists)
        """
        user = await self.repo.get_user_by_email(email)
        if not user:
            # Don't reveal if user exists - return None silently
            return None

        token = await self.repo.create_password_reset_token(user["id"])
        if token:
            logger.info(f"Password reset requested: user_id={user['id']}")
        return token

    async def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset a user's password with reset token.

        Args:
            token: The password reset token
            new_password: The new password

        Returns:
            True if reset successful

        Raises:
            HTTPException: If token is invalid or expired
        """
        # Validate token
        token_data = await self.repo.validate_password_reset_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )

        # Update password
        password_hashed = hash_password(new_password)
        success = await self.repo.update_password(token_data["user_id"], password_hashed)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password",
            )

        # Mark token as used
        await self.repo.mark_password_reset_used(token)

        # Revoke all existing refresh tokens (security measure)
        await self.repo.revoke_all_user_tokens(token_data["user_id"])

        logger.info(f"Password reset: user_id={token_data['user_id']}")
        return True
