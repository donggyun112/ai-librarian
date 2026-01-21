"""Tests for JWT handler."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.auth.jwt_handler import JWTHandler


class TestJWTHandler:
    """Tests for JWTHandler class."""

    @pytest.fixture
    def jwt_handler(self):
        """Create a JWTHandler instance for testing."""
        return JWTHandler(
            secret_key="test-secret-key-for-testing-only",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )

    def test_create_access_token(self, jwt_handler):
        """create_access_token should return a valid JWT."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_correct_claims(self, jwt_handler):
        """Access token should contain correct claims."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        payload = jwt.decode(token, jwt_handler.secret_key, algorithms=[jwt_handler.algorithm])

        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_refresh_token(self, jwt_handler):
        """create_refresh_token should return a token and expiration datetime."""
        token, expires_at = jwt_handler.create_refresh_token("user-123")

        assert isinstance(token, str)
        assert isinstance(expires_at, datetime)
        assert expires_at > datetime.now(timezone.utc)

    def test_create_refresh_token_contains_correct_claims(self, jwt_handler):
        """Refresh token should contain correct claims."""
        token, _ = jwt_handler.create_refresh_token("user-123")
        payload = jwt.decode(token, jwt_handler.secret_key, algorithms=[jwt_handler.algorithm])

        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload
        assert "email" not in payload  # Refresh tokens don't need email

    def test_decode_token_valid(self, jwt_handler):
        """decode_token should return payload for valid token."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        payload = jwt_handler.decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user-123"

    def test_decode_token_expired(self, jwt_handler):
        """decode_token should return None for expired token."""
        # Create an expired token manually
        payload = {
            "sub": "user-123",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(payload, jwt_handler.secret_key, algorithm=jwt_handler.algorithm)

        result = jwt_handler.decode_token(token)
        assert result is None

    def test_decode_token_invalid_signature(self, jwt_handler):
        """decode_token should return None for token with invalid signature."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        # Tamper with the token
        tampered_token = token[:-5] + "xxxxx"

        result = jwt_handler.decode_token(tampered_token)
        assert result is None

    def test_decode_token_malformed(self, jwt_handler):
        """decode_token should return None for malformed token."""
        result = jwt_handler.decode_token("not-a-valid-jwt")
        assert result is None

    def test_validate_access_token_valid(self, jwt_handler):
        """validate_access_token should return payload for valid access token."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        payload = jwt_handler.validate_access_token(token)

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_validate_access_token_rejects_refresh_token(self, jwt_handler):
        """validate_access_token should return None for refresh token."""
        token, _ = jwt_handler.create_refresh_token("user-123")
        payload = jwt_handler.validate_access_token(token)

        assert payload is None

    def test_validate_refresh_token_valid(self, jwt_handler):
        """validate_refresh_token should return payload for valid refresh token."""
        token, _ = jwt_handler.create_refresh_token("user-123")
        payload = jwt_handler.validate_refresh_token(token)

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_validate_refresh_token_rejects_access_token(self, jwt_handler):
        """validate_refresh_token should return None for access token."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        payload = jwt_handler.validate_refresh_token(token)

        assert payload is None

    def test_get_token_expiry_seconds(self, jwt_handler):
        """get_token_expiry_seconds should return correct value."""
        expected = 15 * 60  # 15 minutes in seconds
        assert jwt_handler.get_token_expiry_seconds() == expected

    def test_access_token_expiry_time(self, jwt_handler):
        """Access token should expire at correct time."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        payload = jwt.decode(token, jwt_handler.secret_key, algorithms=[jwt_handler.algorithm])

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

        # Should expire in approximately 15 minutes
        diff = exp - iat
        assert 14 * 60 <= diff.total_seconds() <= 16 * 60

    def test_refresh_token_expiry_time(self, jwt_handler):
        """Refresh token should expire at correct time."""
        token, expires_at = jwt_handler.create_refresh_token("user-123")

        # Should expire in approximately 7 days
        now = datetime.now(timezone.utc)
        diff = expires_at - now
        assert 6.9 * 24 * 60 * 60 <= diff.total_seconds() <= 7.1 * 24 * 60 * 60
