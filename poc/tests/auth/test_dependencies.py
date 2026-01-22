"""Tests for authentication dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.auth.dependencies import (
    get_current_user_id,
    get_jwt_handler,
    get_optional_user_id,
    get_supabase_client,
)
from src.auth.jwt_handler import JWTHandler


class TestGetSupabaseClient:
    """Tests for get_supabase_client dependency."""

    def test_raises_when_not_configured(self):
        """Should raise 503 when Supabase is not configured."""
        # Reset the singleton
        import src.auth.dependencies as deps
        deps._supabase_client = None

        with patch.object(deps.config, "SUPABASE_URL", None):
            with pytest.raises(HTTPException) as exc_info:
                get_supabase_client()

            assert exc_info.value.status_code == 503
            assert "not configured" in exc_info.value.detail

    def test_raises_when_service_key_missing(self):
        """Should raise 503 when service role key is missing."""
        import src.auth.dependencies as deps
        deps._supabase_client = None

        with patch.object(deps.config, "SUPABASE_URL", "https://test.supabase.co"):
            with patch.object(deps.config, "SUPABASE_SERVICE_ROLE_KEY", None):
                with pytest.raises(HTTPException) as exc_info:
                    get_supabase_client()

                assert exc_info.value.status_code == 503


class TestGetJWTHandler:
    """Tests for get_jwt_handler dependency."""

    def test_returns_jwt_handler_instance(self):
        """Should return a JWTHandler instance."""
        import src.auth.dependencies as deps
        deps._jwt_handler = None

        with patch.object(deps.config, "JWT_SECRET_KEY", "a" * 32):
            handler = get_jwt_handler()
            assert isinstance(handler, JWTHandler)

    def test_returns_singleton(self):
        """Should return the same instance on multiple calls."""
        import src.auth.dependencies as deps
        deps._jwt_handler = None

        with patch.object(deps.config, "JWT_SECRET_KEY", "a" * 32):
            handler1 = get_jwt_handler()
            handler2 = get_jwt_handler()
            assert handler1 is handler2


@pytest.mark.asyncio
class TestGetCurrentUserId:
    """Tests for get_current_user_id dependency."""

    @pytest.fixture
    def jwt_handler(self):
        """Create a JWTHandler for testing."""
        return JWTHandler(
            secret_key="test-secret-key-for-testing-only-32chars",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )

    async def test_extracts_user_id_from_valid_token(self, jwt_handler):
        """Should extract user_id from a valid access token."""
        token = jwt_handler.create_access_token("user-123", "test@example.com")
        auth_header = f"Bearer {token}"

        user_id = await get_current_user_id(
            authorization=auth_header,
            jwt_handler=jwt_handler,
        )

        assert user_id == "user-123"

    async def test_raises_when_header_missing(self, jwt_handler):
        """Should raise 401 when Authorization header is missing."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(authorization=None, jwt_handler=jwt_handler)

        assert exc_info.value.status_code == 401
        assert "header required" in exc_info.value.detail

    async def test_raises_when_header_malformed(self, jwt_handler):
        """Should raise 401 when Authorization header format is wrong."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(
                authorization="NotBearer token",
                jwt_handler=jwt_handler,
            )

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    async def test_raises_when_only_bearer_keyword(self, jwt_handler):
        """Should raise 401 when header is just 'Bearer' without token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(
                authorization="Bearer",
                jwt_handler=jwt_handler,
            )

        assert exc_info.value.status_code == 401

    async def test_raises_when_token_invalid(self, jwt_handler):
        """Should raise 401 when token is invalid."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(
                authorization="Bearer invalid-token",
                jwt_handler=jwt_handler,
            )

        assert exc_info.value.status_code == 401
        assert "Invalid or expired" in exc_info.value.detail

    async def test_raises_when_refresh_token_used(self, jwt_handler):
        """Should raise 401 when refresh token is used instead of access token."""
        refresh_token, _ = jwt_handler.create_refresh_token("user-123")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(
                authorization=f"Bearer {refresh_token}",
                jwt_handler=jwt_handler,
            )

        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
class TestGetOptionalUserId:
    """Tests for get_optional_user_id dependency."""

    @pytest.fixture
    def jwt_handler(self):
        """Create a JWTHandler for testing."""
        return JWTHandler(
            secret_key="test-secret-key-for-testing-only-32chars",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )

    async def test_returns_user_id_when_valid_token(self, jwt_handler):
        """Should return user_id when valid token is provided."""
        token = jwt_handler.create_access_token("user-456", "test@example.com")

        user_id = await get_optional_user_id(
            authorization=f"Bearer {token}",
            jwt_handler=jwt_handler,
        )

        assert user_id == "user-456"

    async def test_returns_none_when_no_header(self, jwt_handler):
        """Should return None when no Authorization header."""
        user_id = await get_optional_user_id(
            authorization=None,
            jwt_handler=jwt_handler,
        )

        assert user_id is None

    async def test_returns_none_when_malformed_header(self, jwt_handler):
        """Should return None for malformed header (not raise)."""
        user_id = await get_optional_user_id(
            authorization="NotBearer token",
            jwt_handler=jwt_handler,
        )

        assert user_id is None

    async def test_returns_none_when_invalid_token(self, jwt_handler):
        """Should return None for invalid token (not raise)."""
        user_id = await get_optional_user_id(
            authorization="Bearer invalid-token",
            jwt_handler=jwt_handler,
        )

        assert user_id is None

    async def test_returns_none_when_refresh_token_used(self, jwt_handler):
        """Should return None when refresh token is used."""
        refresh_token, _ = jwt_handler.create_refresh_token("user-123")

        user_id = await get_optional_user_id(
            authorization=f"Bearer {refresh_token}",
            jwt_handler=jwt_handler,
        )

        assert user_id is None
