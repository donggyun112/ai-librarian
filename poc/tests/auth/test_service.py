"""Tests for AuthService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.auth.jwt_handler import JWTHandler
from src.auth.repository import UserRepository
from src.auth.schemas import LoginRequest, RegisterRequest
from src.auth.service import AuthService


pytestmark = pytest.mark.asyncio


class TestAuthService:
    """Tests for AuthService class."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock UserRepository."""
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def jwt_handler(self):
        """Create a JWTHandler instance for testing."""
        return JWTHandler(
            secret_key="test-secret-key-for-testing-only",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )

    @pytest.fixture
    def auth_service(self, mock_repository, jwt_handler):
        """Create an AuthService instance for testing."""
        return AuthService(mock_repository, jwt_handler)

    # =========================================================================
    # Registration Tests
    # =========================================================================

    async def test_register_success(self, auth_service, mock_repository):
        """register should create user and return tokens."""
        mock_repository.get_user_by_email.return_value = None
        mock_repository.create_user.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "email_verified": False,
        }
        mock_repository.save_refresh_token.return_value = True

        request = RegisterRequest(email="test@example.com", password="Password123!")
        result = await auth_service.register(request)

        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.token_type == "bearer"
        assert result.expires_in == 15 * 60

        mock_repository.get_user_by_email.assert_called_once_with("test@example.com")
        mock_repository.create_user.assert_called_once()
        mock_repository.save_refresh_token.assert_called_once()

    async def test_register_email_already_exists(self, auth_service, mock_repository):
        """register should raise 409 if email already exists."""
        mock_repository.get_user_by_email.return_value = {"id": "existing-user"}

        request = RegisterRequest(email="test@example.com", password="Password123!")

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.register(request)

        assert exc_info.value.status_code == 409
        assert "already registered" in exc_info.value.detail

    async def test_register_user_creation_fails(self, auth_service, mock_repository):
        """register should raise 500 if user creation fails."""
        mock_repository.get_user_by_email.return_value = None
        mock_repository.create_user.return_value = None

        request = RegisterRequest(email="test@example.com", password="Password123!")

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.register(request)

        assert exc_info.value.status_code == 500

    # =========================================================================
    # Login Tests
    # =========================================================================

    async def test_login_success(self, auth_service, mock_repository):
        """login should authenticate user and return tokens."""
        from src.auth.password import hash_password

        password_hash = hash_password("Password123!")
        mock_repository.get_user_by_email.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "password_hash": password_hash,
        }
        mock_repository.save_refresh_token.return_value = True

        request = LoginRequest(email="test@example.com", password="Password123!")
        result = await auth_service.login(request)

        assert result.access_token is not None
        assert result.refresh_token is not None
        mock_repository.save_refresh_token.assert_called_once()

    async def test_login_user_not_found(self, auth_service, mock_repository):
        """login should raise 401 if user not found."""
        mock_repository.get_user_by_email.return_value = None

        request = LoginRequest(email="test@example.com", password="Password123!")

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(request)

        assert exc_info.value.status_code == 401

    async def test_login_wrong_password(self, auth_service, mock_repository):
        """login should raise 401 if password is wrong."""
        from src.auth.password import hash_password

        mock_repository.get_user_by_email.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "password_hash": hash_password("correct_password"),
        }

        request = LoginRequest(email="test@example.com", password="wrong_password")

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(request)

        assert exc_info.value.status_code == 401

    async def test_login_no_password_hash(self, auth_service, mock_repository):
        """login should raise 401 if user has no password (OAuth user)."""
        mock_repository.get_user_by_email.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "password_hash": None,
        }

        request = LoginRequest(email="test@example.com", password="Password123!")

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(request)

        assert exc_info.value.status_code == 401

    # =========================================================================
    # Token Refresh Tests
    # =========================================================================

    async def test_refresh_success(self, auth_service, mock_repository, jwt_handler):
        """refresh should return new tokens."""
        # Create a valid refresh token
        refresh_token, _ = jwt_handler.create_refresh_token("user-123")

        mock_repository.validate_refresh_token.return_value = {
            "id": "token-id",
            "user_id": "user-123",
        }
        mock_repository.get_user_by_id.return_value = {
            "id": "user-123",
            "email": "test@example.com",
        }
        mock_repository.revoke_refresh_token.return_value = True
        mock_repository.save_refresh_token.return_value = True

        result = await auth_service.refresh(refresh_token)

        assert result.access_token is not None
        assert result.refresh_token is not None
        mock_repository.revoke_refresh_token.assert_called_once_with(refresh_token)

    async def test_refresh_invalid_token_in_db(self, auth_service, mock_repository):
        """refresh should raise 401 if token not in database."""
        mock_repository.validate_refresh_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh("invalid-token")

        assert exc_info.value.status_code == 401

    async def test_refresh_expired_jwt(self, auth_service, mock_repository):
        """refresh should raise 401 if JWT is expired."""
        mock_repository.validate_refresh_token.return_value = {
            "id": "token-id",
            "user_id": "user-123",
        }
        # Pass an invalid JWT that will fail decode
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh("invalid-jwt-token")

        assert exc_info.value.status_code == 401

    # =========================================================================
    # Logout Tests
    # =========================================================================

    async def test_logout_success(self, auth_service, mock_repository):
        """logout should revoke the refresh token."""
        mock_repository.revoke_refresh_token.return_value = True

        await auth_service.logout("refresh-token")

        mock_repository.revoke_refresh_token.assert_called_once_with("refresh-token")

    async def test_logout_all_success(self, auth_service, mock_repository):
        """logout_all should revoke all user tokens."""
        mock_repository.revoke_all_user_tokens.return_value = True

        await auth_service.logout_all("user-123")

        mock_repository.revoke_all_user_tokens.assert_called_once_with("user-123")

    # =========================================================================
    # Get Current User Tests
    # =========================================================================

    async def test_get_current_user_success(self, auth_service, mock_repository):
        """get_current_user should return user profile."""
        mock_repository.get_user_by_id.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        result = await auth_service.get_current_user("user-123")

        assert result.id == "user-123"
        assert result.email == "test@example.com"
        assert result.email_verified is True

    async def test_get_current_user_not_found(self, auth_service, mock_repository):
        """get_current_user should raise 404 if user not found."""
        mock_repository.get_user_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.get_current_user("user-123")

        assert exc_info.value.status_code == 404

    # =========================================================================
    # Email Verification Tests
    # =========================================================================

    async def test_verify_email_success(self, auth_service, mock_repository):
        """verify_email should mark email as verified."""
        mock_repository.validate_email_verification_token.return_value = {
            "user_id": "user-123",
        }
        mock_repository.verify_user_email.return_value = True
        mock_repository.mark_email_verification_used.return_value = True

        result = await auth_service.verify_email("valid-token")

        assert result is True
        mock_repository.verify_user_email.assert_called_once_with("user-123")

    async def test_verify_email_invalid_token(self, auth_service, mock_repository):
        """verify_email should raise 400 if token is invalid."""
        mock_repository.validate_email_verification_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.verify_email("invalid-token")

        assert exc_info.value.status_code == 400

    # =========================================================================
    # Password Reset Tests
    # =========================================================================

    async def test_request_password_reset_user_exists(self, auth_service, mock_repository):
        """request_password_reset should return token if user exists."""
        mock_repository.get_user_by_email.return_value = {"id": "user-123"}
        mock_repository.create_password_reset_token.return_value = "reset-token"

        result = await auth_service.request_password_reset("test@example.com")

        assert result == "reset-token"

    async def test_request_password_reset_user_not_found(self, auth_service, mock_repository):
        """request_password_reset should return None if user not found."""
        mock_repository.get_user_by_email.return_value = None

        result = await auth_service.request_password_reset("test@example.com")

        assert result is None

    async def test_reset_password_success(self, auth_service, mock_repository):
        """reset_password should update password and revoke tokens."""
        mock_repository.validate_password_reset_token.return_value = {
            "user_id": "user-123",
        }
        mock_repository.update_password.return_value = True
        mock_repository.mark_password_reset_used.return_value = True
        mock_repository.revoke_all_user_tokens.return_value = True

        result = await auth_service.reset_password("valid-token", "new_password")

        assert result is True
        mock_repository.update_password.assert_called_once()
        mock_repository.revoke_all_user_tokens.assert_called_once_with("user-123")

    async def test_reset_password_invalid_token(self, auth_service, mock_repository):
        """reset_password should raise 400 if token is invalid."""
        mock_repository.validate_password_reset_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.reset_password("invalid-token", "new_password")

        assert exc_info.value.status_code == 400
