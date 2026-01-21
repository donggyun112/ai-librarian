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
            json={"email": "not-an-email", "password": "password123"},
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
            json={"email": "not-an-email", "password": "password123"},
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
