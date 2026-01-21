"""JWT token creation and validation."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from loguru import logger

from config import config


class JWTHandler:
    """Handles JWT token creation and validation."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        access_token_expire_minutes: Optional[int] = None,
        refresh_token_expire_days: Optional[int] = None,
    ):
        self.secret_key = secret_key or config.JWT_SECRET_KEY
        self.algorithm = algorithm or config.JWT_ALGORITHM
        self.access_token_expire_minutes = access_token_expire_minutes or config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = refresh_token_expire_days or config.JWT_REFRESH_TOKEN_EXPIRE_DAYS

        if not self.secret_key:
            logger.warning("JWT_SECRET_KEY not configured - authentication will not work")

    def create_access_token(self, user_id: str, email: str) -> str:
        """
        Create a short-lived access token.

        Args:
            user_id: The user's unique identifier
            email: The user's email address

        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "type": "access",
            "exp": now + timedelta(minutes=self.access_token_expire_minutes),
            "iat": now,
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> tuple[str, datetime]:
        """
        Create a long-lived refresh token.

        Args:
            user_id: The user's unique identifier

        Returns:
            Tuple of (encoded JWT refresh token, expiration datetime)
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self.refresh_token_expire_days)
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expires_at,
            "iat": now,
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, expires_at

    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate a JWT token.

        Args:
            token: The JWT token to decode

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.info("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.info(f"Invalid token: {e}")
            return None

    def validate_access_token(self, token: str) -> Optional[dict]:
        """
        Validate an access token and ensure it's the correct type.

        Args:
            token: The JWT token to validate

        Returns:
            Decoded payload if valid access token, None otherwise
        """
        payload = self.decode_token(token)
        if payload and payload.get("type") == "access":
            return payload
        return None

    def validate_refresh_token(self, token: str) -> Optional[dict]:
        """
        Validate a refresh token and ensure it's the correct type.

        Args:
            token: The JWT token to validate

        Returns:
            Decoded payload if valid refresh token, None otherwise
        """
        payload = self.decode_token(token)
        if payload and payload.get("type") == "refresh":
            return payload
        return None

    def get_token_expiry_seconds(self) -> int:
        """Get the access token expiry time in seconds."""
        return self.access_token_expire_minutes * 60
