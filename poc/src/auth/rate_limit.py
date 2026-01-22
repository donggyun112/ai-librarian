"""Rate limiting for authentication endpoints.

This module provides rate limiting to prevent brute force attacks on
login, registration, and password reset endpoints.

For production, consider using Redis-backed rate limiting for
distributed environments. This in-memory implementation is suitable
for single-instance deployments.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Request, status
from loguru import logger


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests: int  # Maximum requests allowed
    window_seconds: int  # Time window in seconds
    block_seconds: int  # How long to block after limit exceeded


# Default rate limit configurations
LOGIN_RATE_LIMIT = RateLimitConfig(max_requests=5, window_seconds=60, block_seconds=300)
REGISTER_RATE_LIMIT = RateLimitConfig(max_requests=3, window_seconds=60, block_seconds=600)
PASSWORD_RESET_RATE_LIMIT = RateLimitConfig(max_requests=3, window_seconds=60, block_seconds=600)


class InMemoryRateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    Thread-safe implementation suitable for single-instance deployments.
    For distributed systems, replace with Redis-backed implementation.
    """

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._blocked: dict[str, float] = {}
        self._lock = Lock()

    def _get_key(self, identifier: str, action: str) -> str:
        """Generate a unique key for rate limiting."""
        return f"{action}:{identifier}"

    def _cleanup_old_requests(self, key: str, window_seconds: int) -> None:
        """Remove requests outside the current window."""
        now = time.time()
        cutoff = now - window_seconds
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]

    def is_blocked(self, identifier: str, action: str) -> tuple[bool, Optional[int]]:
        """
        Check if an identifier is currently blocked.

        Returns:
            Tuple of (is_blocked, seconds_remaining)
        """
        key = self._get_key(identifier, action)
        with self._lock:
            if key in self._blocked:
                blocked_until = self._blocked[key]
                now = time.time()
                if now < blocked_until:
                    return True, int(blocked_until - now)
                else:
                    del self._blocked[key]
        return False, None

    def check_rate_limit(
        self, identifier: str, action: str, config: RateLimitConfig
    ) -> tuple[bool, Optional[int]]:
        """
        Check if request is allowed and record it.

        Args:
            identifier: Client identifier (IP address or user ID)
            action: Action being performed (e.g., "login", "register")
            config: Rate limit configuration

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        key = self._get_key(identifier, action)
        now = time.time()

        with self._lock:
            # Check if blocked
            if key in self._blocked:
                blocked_until = self._blocked[key]
                if now < blocked_until:
                    return False, int(blocked_until - now)
                else:
                    del self._blocked[key]

            # Cleanup old requests
            self._cleanup_old_requests(key, config.window_seconds)

            # Check rate limit
            if len(self._requests[key]) >= config.max_requests:
                # Block the identifier
                self._blocked[key] = now + config.block_seconds
                logger.warning(
                    f"Rate limit exceeded: action={action}, identifier={identifier}, "
                    f"blocked_for={config.block_seconds}s"
                )
                return False, config.block_seconds

            # Record this request
            self._requests[key].append(now)
            return True, None

    def reset(self, identifier: str, action: str) -> None:
        """Reset rate limit for an identifier (e.g., after successful login)."""
        key = self._get_key(identifier, action)
        with self._lock:
            self._requests.pop(key, None)
            self._blocked.pop(key, None)


# Global rate limiter instance
_rate_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


def get_client_identifier(request: Request) -> str:
    """
    Get a unique identifier for the client.

    Uses IP address as the identifier. In production with a reverse proxy,
    you may need to use X-Forwarded-For or X-Real-IP headers.
    """
    # Check for forwarded headers (common with reverse proxies)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def check_login_rate_limit(request: Request) -> None:
    """
    Dependency to check login rate limit.

    Raises HTTPException with 429 if rate limit exceeded.
    """
    identifier = get_client_identifier(request)
    allowed, retry_after = _rate_limiter.check_rate_limit(
        identifier, "login", LOGIN_RATE_LIMIT
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def check_register_rate_limit(request: Request) -> None:
    """
    Dependency to check registration rate limit.

    Raises HTTPException with 429 if rate limit exceeded.
    """
    identifier = get_client_identifier(request)
    allowed, retry_after = _rate_limiter.check_rate_limit(
        identifier, "register", REGISTER_RATE_LIMIT
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def check_password_reset_rate_limit(request: Request) -> None:
    """
    Dependency to check password reset rate limit.

    Raises HTTPException with 429 if rate limit exceeded.
    """
    identifier = get_client_identifier(request)
    allowed, retry_after = _rate_limiter.check_rate_limit(
        identifier, "password_reset", PASSWORD_RESET_RATE_LIMIT
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def reset_login_rate_limit(request: Request) -> None:
    """Reset login rate limit after successful login."""
    identifier = get_client_identifier(request)
    _rate_limiter.reset(identifier, "login")
