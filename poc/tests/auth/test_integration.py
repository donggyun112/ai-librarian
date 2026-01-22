"""Integration tests for auth flows against real Supabase.

These tests require a running Supabase instance with proper configuration.
They test the full registration -> login -> refresh -> logout flow.

Run with: uv run pytest tests/auth/test_integration.py -v -s

Note: These tests create real users and clean them up after each test.
"""

import uuid

import pytest
from supabase import Client, create_client

from config import config
from src.auth.jwt_handler import JWTHandler
from src.auth.repository import UserRepository
from src.auth.schemas import LoginRequest, RegisterRequest
from src.auth.service import AuthService


# Skip all tests if Supabase is not configured
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not config.SUPABASE_URL or not config.SUPABASE_SERVICE_ROLE_KEY,
        reason="Supabase not configured (missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY)",
    ),
]


class TestAuthIntegration:
    """Integration tests for authentication flows."""

    @pytest.fixture
    def supabase_client(self) -> Client:
        """Create a Supabase client."""
        return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)

    @pytest.fixture
    def repository(self, supabase_client: Client) -> UserRepository:
        """Create a UserRepository with real Supabase client."""
        return UserRepository(supabase_client)

    @pytest.fixture
    def jwt_handler(self) -> JWTHandler:
        """Create a JWTHandler."""
        return JWTHandler()

    @pytest.fixture
    def auth_service(self, repository: UserRepository, jwt_handler: JWTHandler) -> AuthService:
        """Create an AuthService with real dependencies."""
        return AuthService(repository, jwt_handler)

    @pytest.fixture
    def test_email(self) -> str:
        """Generate a unique test email for each test."""
        unique_id = uuid.uuid4().hex[:8]
        # Use example.com which is reserved for testing (RFC 2606)
        return f"test-{unique_id}@example.com"

    @pytest.fixture
    def test_password(self) -> str:
        """Test password."""
        return "TestPassword123!"

    async def cleanup_user(self, supabase_client: Client, email: str):
        """Clean up a test user by email."""
        try:
            # First, get the user from public.users
            result = supabase_client.table("users").select("id").eq("email", email).maybe_single().execute()
            if result.data:
                user_id = result.data["id"]

                # Delete from public.users (cascades to tokens)
                supabase_client.table("users").delete().eq("id", user_id).execute()

                # Delete from auth.users
                supabase_client.auth.admin.delete_user(user_id)
        except Exception:
            pass  # Ignore cleanup errors

    # =========================================================================
    # Full Flow Tests
    # =========================================================================

    async def test_register_login_refresh_logout_flow(
        self,
        auth_service: AuthService,
        supabase_client: Client,
        test_email: str,
        test_password: str,
    ):
        """Test the complete auth flow: register -> login -> refresh -> logout."""
        try:
            # Step 1: Register
            register_request = RegisterRequest(email=test_email, password=test_password)
            register_result = await auth_service.register(register_request)

            assert register_result.access_token is not None
            assert register_result.refresh_token is not None
            assert register_result.token_type == "bearer"
            print(f"\n  Register: User created with email {test_email}")

            # Step 2: Login with the same credentials
            login_request = LoginRequest(email=test_email, password=test_password)
            login_result = await auth_service.login(login_request)

            assert login_result.access_token is not None
            assert login_result.refresh_token is not None
            print(f"  Login: Successfully authenticated")

            # Step 3: Refresh the token
            refresh_result = await auth_service.refresh(login_result.refresh_token)

            assert refresh_result.access_token is not None
            assert refresh_result.refresh_token is not None
            # New refresh token should be different (token rotation)
            assert refresh_result.refresh_token != login_result.refresh_token
            print(f"  Refresh: Token rotated successfully")

            # Step 4: Logout
            await auth_service.logout(refresh_result.refresh_token)
            print(f"  Logout: Session terminated")

            # Step 5: Verify old refresh token is revoked
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.refresh(refresh_result.refresh_token)
            assert exc_info.value.status_code == 401
            print(f"  Verify: Old refresh token correctly rejected")

        finally:
            # Cleanup
            await self.cleanup_user(supabase_client, test_email)
            print(f"  Cleanup: Test user removed")

    async def test_get_current_user(
        self,
        auth_service: AuthService,
        supabase_client: Client,
        jwt_handler: JWTHandler,
        test_email: str,
        test_password: str,
    ):
        """Test getting current user profile."""
        try:
            # Register and login
            register_request = RegisterRequest(email=test_email, password=test_password)
            register_result = await auth_service.register(register_request)

            # Decode access token to get user_id
            payload = jwt_handler.validate_access_token(register_result.access_token)
            assert payload is not None
            user_id = payload["sub"]

            # Get current user
            user = await auth_service.get_current_user(user_id)

            assert user.id == user_id
            assert user.email == test_email
            assert user.email_verified is False
            print(f"\n  GetMe: Retrieved user profile for {test_email}")

        finally:
            await self.cleanup_user(supabase_client, test_email)

    async def test_duplicate_registration_fails(
        self,
        auth_service: AuthService,
        supabase_client: Client,
        test_email: str,
        test_password: str,
    ):
        """Test that duplicate registration is rejected."""
        try:
            # First registration should succeed
            register_request = RegisterRequest(email=test_email, password=test_password)
            await auth_service.register(register_request)
            print(f"\n  First registration: Success")

            # Second registration should fail
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.register(register_request)

            assert exc_info.value.status_code == 409
            assert "already registered" in exc_info.value.detail
            print(f"  Second registration: Correctly rejected with 409")

        finally:
            await self.cleanup_user(supabase_client, test_email)

    async def test_login_wrong_password_fails(
        self,
        auth_service: AuthService,
        supabase_client: Client,
        test_email: str,
        test_password: str,
    ):
        """Test that wrong password is rejected."""
        try:
            # Register
            register_request = RegisterRequest(email=test_email, password=test_password)
            await auth_service.register(register_request)

            # Login with wrong password
            from fastapi import HTTPException

            wrong_login = LoginRequest(email=test_email, password="WrongPassword123!")
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.login(wrong_login)

            assert exc_info.value.status_code == 401
            print(f"\n  Wrong password: Correctly rejected with 401")

        finally:
            await self.cleanup_user(supabase_client, test_email)

    async def test_logout_all_revokes_all_tokens(
        self,
        auth_service: AuthService,
        supabase_client: Client,
        jwt_handler: JWTHandler,
        test_email: str,
        test_password: str,
    ):
        """Test that logout_all revokes all refresh tokens."""
        try:
            # Register
            register_request = RegisterRequest(email=test_email, password=test_password)
            register_result = await auth_service.register(register_request)

            # Login multiple times to create multiple refresh tokens
            login_request = LoginRequest(email=test_email, password=test_password)
            login_result_1 = await auth_service.login(login_request)
            login_result_2 = await auth_service.login(login_request)

            # Get user_id
            payload = jwt_handler.validate_access_token(register_result.access_token)
            user_id = payload["sub"]

            # Logout all
            await auth_service.logout_all(user_id)
            print(f"\n  Logout all: All sessions terminated")

            # All refresh tokens should be invalid
            from fastapi import HTTPException

            for token, name in [
                (register_result.refresh_token, "register"),
                (login_result_1.refresh_token, "login1"),
                (login_result_2.refresh_token, "login2"),
            ]:
                with pytest.raises(HTTPException) as exc_info:
                    await auth_service.refresh(token)
                assert exc_info.value.status_code == 401
                print(f"  Token from {name}: Correctly rejected")

        finally:
            await self.cleanup_user(supabase_client, test_email)
