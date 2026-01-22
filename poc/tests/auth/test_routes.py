"""Tests for auth API routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.routes import router
from src.auth.service import AuthService


@pytest.fixture
def app():
    """Create a FastAPI app with auth routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth_service():
    """Create a mock AuthService."""
    return AsyncMock(spec=AuthService)


class TestRegisterEndpoint:
    """Tests for POST /v1/auth/register."""

    def test_register_invalid_email(self, client):
        """Register should return 422 for invalid email."""
        response = client.post(
            "/v1/auth/register",
            json={"email": "not-an-email", "password": "Password123!"},
        )
        assert response.status_code == 422

    def test_register_short_password(self, client):
        """Register should return 422 for short password."""
        response = client.post(
            "/v1/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )
        assert response.status_code == 422


class TestLoginEndpoint:
    """Tests for POST /v1/auth/login."""

    def test_login_missing_fields(self, client):
        """Login should return 422 for missing fields."""
        response = client.post("/v1/auth/login", json={})
        assert response.status_code == 422

    def test_login_invalid_email(self, client):
        """Login should return 422 for invalid email."""
        response = client.post(
            "/v1/auth/login",
            json={"email": "not-an-email", "password": "Password123!"},
        )
        assert response.status_code == 422


class TestRefreshEndpoint:
    """Tests for POST /v1/auth/refresh."""

    def test_refresh_missing_token(self, client):
        """Refresh should return 422 for missing token."""
        response = client.post("/v1/auth/refresh", json={})
        assert response.status_code == 422


class TestLogoutEndpoint:
    """Tests for POST /v1/auth/logout."""

    def test_logout_missing_token(self, client):
        """Logout should return 422 for missing token."""
        response = client.post("/v1/auth/logout", json={})
        assert response.status_code == 422


class TestLogoutAllEndpoint:
    """Tests for POST /v1/auth/logout-all."""

    def test_logout_all_requires_auth(self, client):
        """Logout-all should require authorization."""
        response = client.post("/v1/auth/logout-all")
        assert response.status_code == 401


class TestMeEndpoint:
    """Tests for GET /v1/auth/me."""

    def test_me_requires_auth(self, client):
        """Me should require authorization."""
        response = client.get("/v1/auth/me")
        assert response.status_code == 401

    def test_me_invalid_token(self, client):
        """Me should return 401 for invalid token."""
        response = client.get(
            "/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_me_malformed_header(self, client):
        """Me should return 401 for malformed auth header."""
        response = client.get(
            "/v1/auth/me",
            headers={"Authorization": "NotBearer token"},
        )
        assert response.status_code == 401


class TestVerifyEmailEndpoint:
    """Tests for POST /v1/auth/verify-email."""

    def test_verify_email_missing_token(self, client):
        """Verify-email should return 422 for missing token."""
        response = client.post("/v1/auth/verify-email", json={})
        assert response.status_code == 422


class TestForgotPasswordEndpoint:
    """Tests for POST /v1/auth/forgot-password."""

    def test_forgot_password_missing_email(self, client):
        """Forgot-password should return 422 for missing email."""
        response = client.post("/v1/auth/forgot-password", json={})
        assert response.status_code == 422

    def test_forgot_password_invalid_email(self, client):
        """Forgot-password should return 422 for invalid email."""
        response = client.post(
            "/v1/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422


class TestResetPasswordEndpoint:
    """Tests for POST /v1/auth/reset-password."""

    def test_reset_password_missing_fields(self, client):
        """Reset-password should return 422 for missing fields."""
        response = client.post("/v1/auth/reset-password", json={})
        assert response.status_code == 422

    def test_reset_password_short_password(self, client):
        """Reset-password should return 422 for short password."""
        response = client.post(
            "/v1/auth/reset-password",
            json={"token": "some-token", "new_password": "short"},
        )
        assert response.status_code == 422


# =============================================================================
# Integration Tests with Mocked Dependencies
# =============================================================================


class TestAuthFlowsIntegration:
    """Integration tests for complete auth flows with mocked dependencies."""

    @pytest.fixture
    def jwt_handler(self):
        """Create a real JWTHandler for testing."""
        from src.auth.jwt_handler import JWTHandler
        return JWTHandler(
            secret_key="test-secret-key-for-testing-only-32chars",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )

    @pytest.fixture
    def app_with_mocks(self, mock_auth_service, jwt_handler):
        """Create app with mocked auth service."""
        from src.auth.dependencies import get_auth_service, get_jwt_handler

        app = FastAPI()
        app.include_router(router)

        # Override dependencies
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_jwt_handler] = lambda: jwt_handler

        return app

    @pytest.fixture
    def client_with_mocks(self, app_with_mocks):
        """Create test client with mocked dependencies."""
        return TestClient(app_with_mocks)

    def test_register_success(self, client_with_mocks, mock_auth_service):
        """Register should return tokens on success."""
        from src.auth.schemas import TokenResponse

        mock_auth_service.register.return_value = TokenResponse(
            access_token="access-token-123",
            refresh_token="refresh-token-456",
            expires_in=900,
        )

        response = client_with_mocks.post(
            "/v1/auth/register",
            json={"email": "test@example.com", "password": "Password123!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access-token-123"
        assert data["refresh_token"] == "refresh-token-456"
        assert data["token_type"] == "bearer"

    def test_login_success(self, client_with_mocks, mock_auth_service):
        """Login should return tokens on success."""
        from src.auth.schemas import TokenResponse

        mock_auth_service.login.return_value = TokenResponse(
            access_token="access-token-789",
            refresh_token="refresh-token-012",
            expires_in=900,
        )

        response = client_with_mocks.post(
            "/v1/auth/login",
            json={"email": "test@example.com", "password": "Password123!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access-token-789"
        assert data["token_type"] == "bearer"

    def test_refresh_success(self, client_with_mocks, mock_auth_service):
        """Refresh should return new tokens."""
        from src.auth.schemas import TokenResponse

        mock_auth_service.refresh.return_value = TokenResponse(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            expires_in=900,
        )

        response = client_with_mocks.post(
            "/v1/auth/refresh",
            json={"refresh_token": "old-refresh-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new-access-token"

    def test_logout_success(self, client_with_mocks, mock_auth_service):
        """Logout should return success message."""
        mock_auth_service.logout.return_value = None

        response = client_with_mocks.post(
            "/v1/auth/logout",
            json={"refresh_token": "some-refresh-token"},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

    def test_me_with_valid_token(self, client_with_mocks, mock_auth_service, jwt_handler):
        """Me endpoint should return user profile with valid token."""
        from datetime import datetime, timezone
        from src.auth.schemas import UserResponse

        # Create a valid token
        token = jwt_handler.create_access_token("user-123", "test@example.com")

        mock_auth_service.get_current_user.return_value = UserResponse(
            id="user-123",
            email="test@example.com",
            email_verified=True,
            created_at=datetime.now(timezone.utc),
        )

        response = client_with_mocks.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "user-123"
        assert data["email"] == "test@example.com"

    def test_forgot_password_always_succeeds(self, client_with_mocks, mock_auth_service):
        """Forgot password should always return success (prevent enumeration)."""
        mock_auth_service.request_password_reset.return_value = None

        response = client_with_mocks.post(
            "/v1/auth/forgot-password",
            json={"email": "unknown@example.com"},
        )

        assert response.status_code == 200
        assert "reset link" in response.json()["message"].lower()

