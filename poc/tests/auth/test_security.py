"""Tests for security features: password complexity, rate limiting, bcrypt handling."""

import pytest
from pydantic import ValidationError

from src.auth.password import hash_password, verify_password
from src.auth.schemas import RegisterRequest, ResetPasswordRequest


class TestPasswordComplexity:
    """Tests for password complexity validation."""

    def test_password_too_short(self):
        """Password shorter than 8 characters should fail."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="test@example.com", password="Ab1!")
        assert "at least 8 characters" in str(exc_info.value)

    def test_password_no_lowercase(self):
        """Password without lowercase should fail."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="test@example.com", password="PASSWORD123!")
        assert "lowercase" in str(exc_info.value)

    def test_password_no_uppercase(self):
        """Password without uppercase should fail."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="test@example.com", password="password123!")
        assert "uppercase" in str(exc_info.value)

    def test_password_no_digit(self):
        """Password without digit should fail."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="test@example.com", password="PasswordABC!")
        assert "digit" in str(exc_info.value)

    def test_password_no_special_char(self):
        """Password without special character should fail."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="test@example.com", password="Password123")
        assert "special character" in str(exc_info.value)

    def test_password_too_long(self):
        """Password longer than 128 characters should fail."""
        long_password = "Aa1!" + "x" * 125  # 129 chars
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="test@example.com", password=long_password)
        assert "at most 128" in str(exc_info.value) or "128" in str(exc_info.value)

    def test_valid_password_accepted(self):
        """Valid password should be accepted."""
        request = RegisterRequest(email="test@example.com", password="Password123!")
        assert request.password == "Password123!"

    def test_valid_password_with_various_special_chars(self):
        """Various special characters should be accepted."""
        valid_passwords = [
            "Password123!",
            "Password123@",
            "Password123#",
            "Password123$",
            "Password123%",
            "Password123^",
            "Password123&",
            "Password123*",
            "Password123-",
            "Password123_",
        ]
        for pwd in valid_passwords:
            request = RegisterRequest(email="test@example.com", password=pwd)
            assert request.password == pwd

    def test_reset_password_also_validates(self):
        """ResetPasswordRequest should also validate password complexity."""
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="some-token", new_password="weak")


class TestBcrypt72ByteLimit:
    """Tests for bcrypt 72-byte password limit handling."""

    def test_short_password_works(self):
        """Short passwords should hash and verify correctly."""
        password = "Password123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed)

    def test_72_byte_password_works(self):
        """Exactly 72 byte password should work."""
        # 72 ASCII characters = 72 bytes
        password = "A" * 60 + "a1!" + "B" * 9  # 72 chars with complexity
        hashed = hash_password(password)
        assert verify_password(password, hashed)

    def test_long_password_works(self):
        """Passwords longer than 72 bytes should work correctly."""
        # This password is > 72 bytes
        password = "Password123!" + "x" * 100
        hashed = hash_password(password)
        assert verify_password(password, hashed)

    def test_long_passwords_with_same_prefix_are_different(self):
        """Two long passwords with same first 72 chars should hash differently.

        This is the key test - without pre-hashing, bcrypt would truncate
        both to 72 bytes and they'd have the same hash.
        """
        prefix = "Password123!" + "x" * 60  # 72 chars
        password1 = prefix + "AAAA"
        password2 = prefix + "BBBB"

        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        # The important part: each password only verifies against its own hash
        assert verify_password(password1, hash1)
        assert verify_password(password2, hash2)
        assert not verify_password(password1, hash2)
        assert not verify_password(password2, hash1)

    def test_unicode_password_works(self):
        """Unicode passwords should work correctly."""
        password = "Pässwörd123!한글"
        hashed = hash_password(password)
        assert verify_password(password, hashed)


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_allows_requests_within_limit(self):
        """Requests within limit should be allowed."""
        from src.auth.rate_limit import InMemoryRateLimiter, RateLimitConfig

        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=5, window_seconds=60, block_seconds=300)

        # First 5 requests should be allowed
        for i in range(5):
            allowed, _ = limiter.check_rate_limit(f"test-{i % 5}", "test_action", config)
            assert allowed, f"Request {i} should be allowed"

    def test_rate_limiter_blocks_after_limit(self):
        """Requests after limit exceeded should be blocked."""
        from src.auth.rate_limit import InMemoryRateLimiter, RateLimitConfig

        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=3, window_seconds=60, block_seconds=300)

        # Use up the limit
        for _ in range(3):
            allowed, _ = limiter.check_rate_limit("blocked-ip", "test", config)
            assert allowed

        # Next request should be blocked
        allowed, retry_after = limiter.check_rate_limit("blocked-ip", "test", config)
        assert not allowed
        assert retry_after == 300

    def test_rate_limiter_different_identifiers_independent(self):
        """Different identifiers should have independent limits."""
        from src.auth.rate_limit import InMemoryRateLimiter, RateLimitConfig

        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=2, window_seconds=60, block_seconds=300)

        # Exhaust limit for user1
        limiter.check_rate_limit("user1", "login", config)
        limiter.check_rate_limit("user1", "login", config)

        # user1 should be blocked
        allowed1, _ = limiter.check_rate_limit("user1", "login", config)
        assert not allowed1

        # user2 should still be allowed
        allowed2, _ = limiter.check_rate_limit("user2", "login", config)
        assert allowed2

    def test_rate_limiter_different_actions_independent(self):
        """Different actions should have independent limits."""
        from src.auth.rate_limit import InMemoryRateLimiter, RateLimitConfig

        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=2, window_seconds=60, block_seconds=300)

        # Exhaust limit for login
        limiter.check_rate_limit("user", "login", config)
        limiter.check_rate_limit("user", "login", config)
        limiter.check_rate_limit("user", "login", config)  # This should block

        # register should still be allowed
        allowed, _ = limiter.check_rate_limit("user", "register", config)
        assert allowed

    def test_rate_limiter_reset(self):
        """Reset should clear rate limit for identifier."""
        from src.auth.rate_limit import InMemoryRateLimiter, RateLimitConfig

        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=2, window_seconds=60, block_seconds=300)

        # Exhaust limit
        limiter.check_rate_limit("user", "login", config)
        limiter.check_rate_limit("user", "login", config)
        allowed, _ = limiter.check_rate_limit("user", "login", config)
        assert not allowed

        # Reset
        limiter.reset("user", "login")

        # Should be allowed again
        allowed, _ = limiter.check_rate_limit("user", "login", config)
        assert allowed
