"""User repository for database operations."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import anyio
from loguru import logger
from supabase import Client


class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, client: Client):
        """
        Initialize the repository with a Supabase client.

        Args:
            client: Supabase client instance
        """
        self.client = client
        self.users_table = "users"
        self.refresh_tokens_table = "refresh_tokens"
        self.email_verification_table = "email_verification_tokens"
        self.password_reset_table = "password_reset_tokens"

    def _hash_token(self, token: str) -> str:
        """Hash a token using SHA-256."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _generate_token(self) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    # =========================================================================
    # User Operations
    # =========================================================================

    async def create_user(
        self, email: str, password_hash: Optional[str] = None, raw_password: Optional[str] = None
    ) -> Optional[dict]:
        """
        Create a new user using Supabase Auth Admin API.

        This creates the user in auth.users first (required due to FK constraint),
        then stores additional data in public.users.

        Args:
            email: User's email address
            password_hash: Hashed password for public.users (None for OAuth/magic-link users)
            raw_password: Raw password for Supabase Auth (required for email/password auth)

        Returns:
            Created user data or None if failed
        """
        def _create_auth_user():
            # Create user in auth.users via Supabase Auth Admin API
            user_data = {"email": email, "email_confirm": False}
            if raw_password:
                user_data["password"] = raw_password
            return self.client.auth.admin.create_user(user_data)

        def _create_public_user(user_id: str):
            # Create corresponding record in public.users
            return self.client.table(self.users_table).insert({
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "email_verified": False,
            }).execute()

        try:
            # Step 1: Create in auth.users
            auth_result = await anyio.to_thread.run_sync(_create_auth_user)
            if not auth_result.user:
                logger.error("Failed to create auth user: no user returned")
                return None

            user_id = str(auth_result.user.id)

            # Step 2: Create in public.users with the same ID
            public_result = await anyio.to_thread.run_sync(lambda: _create_public_user(user_id))
            if public_result.data:
                logger.info(f"User created: {user_id}")
                return public_result.data[0]

            # Rollback: delete auth user if public user creation failed
            logger.error("Failed to create public user, rolling back auth user")
            await anyio.to_thread.run_sync(
                lambda: self.client.auth.admin.delete_user(user_id)
            )
            return None
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """
        Get a user by email address.

        Args:
            email: User's email address

        Returns:
            User data or None if not found
        """
        def _get():
            return self.client.table(self.users_table).select("*").eq("email", email).maybe_single().execute()

        try:
            result = await anyio.to_thread.run_sync(_get)
            # maybe_single() returns None for result.data when no row found
            return result.data if result else None
        except Exception as e:
            # APIError with code PGRST116 means no rows found - this is expected
            if "PGRST116" in str(e):
                return None
            logger.error(f"Failed to get user by email: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """
        Get a user by ID.

        Args:
            user_id: User's unique identifier

        Returns:
            User data or None if not found
        """
        def _get():
            return self.client.table(self.users_table).select("*").eq("id", user_id).maybe_single().execute()

        try:
            result = await anyio.to_thread.run_sync(_get)
            return result.data if result else None
        except Exception as e:
            if "PGRST116" in str(e):
                return None
            logger.error(f"Failed to get user by id: {e}")
            return None

    async def verify_user_email(self, user_id: str) -> bool:
        """
        Mark a user's email as verified.

        Args:
            user_id: User's unique identifier

        Returns:
            True if successful, False otherwise
        """
        def _verify():
            return self.client.table(self.users_table).update({
                "email_verified": True,
                "email_verified_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", user_id).execute()

        try:
            await anyio.to_thread.run_sync(_verify)
            logger.info(f"Email verified for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to verify email: {e}")
            return False

    async def update_password(self, user_id: str, password_hash: str) -> bool:
        """
        Update a user's password.

        Args:
            user_id: User's unique identifier
            password_hash: New hashed password

        Returns:
            True if successful, False otherwise
        """
        def _update():
            return self.client.table(self.users_table).update({
                "password_hash": password_hash,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", user_id).execute()

        try:
            await anyio.to_thread.run_sync(_update)
            logger.info(f"Password updated for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update password: {e}")
            return False

    # =========================================================================
    # Refresh Token Operations
    # =========================================================================

    async def save_refresh_token(
        self,
        user_id: str,
        token: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Save a refresh token to the database.

        Args:
            user_id: User's unique identifier
            token: The refresh token (will be hashed before storing)
            expires_at: Token expiration datetime
            user_agent: Client user agent string
            ip_address: Client IP address

        Returns:
            True if successful, False otherwise
        """
        token_hash = self._hash_token(token)

        def _save():
            return self.client.table(self.refresh_tokens_table).insert({
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at.isoformat(),
                "user_agent": user_agent,
                "ip_address": ip_address,
            }).execute()

        try:
            await anyio.to_thread.run_sync(_save)
            return True
        except Exception as e:
            logger.error(f"Failed to save refresh token: {e}")
            return False

    async def validate_refresh_token(self, token: str) -> Optional[dict]:
        """
        Validate a refresh token exists and is not expired/revoked.

        Args:
            token: The refresh token to validate

        Returns:
            Token data if valid, None otherwise
        """
        token_hash = self._hash_token(token)

        def _validate():
            return (
                self.client.table(self.refresh_tokens_table)
                .select("*")
                .eq("token_hash", token_hash)
                .is_("revoked_at", "null")
                .maybe_single()
                .execute()
            )

        try:
            result = await anyio.to_thread.run_sync(_validate)
            if result and result.data:
                expires_at = datetime.fromisoformat(result.data["expires_at"].replace("Z", "+00:00"))
                if expires_at > datetime.now(timezone.utc):
                    return result.data
            return None
        except Exception as e:
            if "PGRST116" in str(e):
                return None
            logger.error(f"Failed to validate refresh token: {e}")
            return None

    async def revoke_refresh_token(self, token: str) -> bool:
        """
        Revoke a specific refresh token.

        Args:
            token: The refresh token to revoke

        Returns:
            True if successful, False otherwise
        """
        token_hash = self._hash_token(token)

        def _revoke():
            return (
                self.client.table(self.refresh_tokens_table)
                .update({"revoked_at": datetime.now(timezone.utc).isoformat()})
                .eq("token_hash", token_hash)
                .execute()
            )

        try:
            await anyio.to_thread.run_sync(_revoke)
            return True
        except Exception as e:
            logger.error(f"Failed to revoke refresh token: {e}")
            return False

    async def revoke_all_user_tokens(self, user_id: str) -> bool:
        """
        Revoke all refresh tokens for a user.

        Args:
            user_id: User's unique identifier

        Returns:
            True if successful, False otherwise
        """
        def _revoke_all():
            return (
                self.client.table(self.refresh_tokens_table)
                .update({"revoked_at": datetime.now(timezone.utc).isoformat()})
                .eq("user_id", user_id)
                .is_("revoked_at", "null")
                .execute()
            )

        try:
            await anyio.to_thread.run_sync(_revoke_all)
            logger.info(f"All tokens revoked for user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke all tokens: {e}")
            return False

    # =========================================================================
    # Email Verification Token Operations
    # =========================================================================

    async def create_email_verification_token(self, user_id: str, expires_in_hours: int = 24) -> Optional[str]:
        """
        Create an email verification token.

        Args:
            user_id: User's unique identifier
            expires_in_hours: Hours until token expires

        Returns:
            The verification token or None if failed
        """
        token = self._generate_token()
        token_hash = self._hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        def _create():
            return self.client.table(self.email_verification_table).insert({
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at.isoformat(),
            }).execute()

        try:
            await anyio.to_thread.run_sync(_create)
            return token
        except Exception as e:
            logger.error(f"Failed to create email verification token: {e}")
            return None

    async def validate_email_verification_token(self, token: str) -> Optional[dict]:
        """
        Validate an email verification token.

        Args:
            token: The verification token

        Returns:
            Token data if valid, None otherwise
        """
        token_hash = self._hash_token(token)

        def _validate():
            return (
                self.client.table(self.email_verification_table)
                .select("*")
                .eq("token_hash", token_hash)
                .is_("used_at", "null")
                .maybe_single()
                .execute()
            )

        try:
            result = await anyio.to_thread.run_sync(_validate)
            if result and result.data:
                expires_at = datetime.fromisoformat(result.data["expires_at"].replace("Z", "+00:00"))
                if expires_at > datetime.now(timezone.utc):
                    return result.data
            return None
        except Exception as e:
            if "PGRST116" in str(e):
                return None
            logger.error(f"Failed to validate email verification token: {e}")
            return None

    async def mark_email_verification_used(self, token: str) -> bool:
        """
        Mark an email verification token as used.

        Args:
            token: The verification token

        Returns:
            True if successful, False otherwise
        """
        token_hash = self._hash_token(token)

        def _mark_used():
            return (
                self.client.table(self.email_verification_table)
                .update({"used_at": datetime.now(timezone.utc).isoformat()})
                .eq("token_hash", token_hash)
                .execute()
            )

        try:
            await anyio.to_thread.run_sync(_mark_used)
            return True
        except Exception as e:
            logger.error(f"Failed to mark email verification token as used: {e}")
            return False

    # =========================================================================
    # Password Reset Token Operations
    # =========================================================================

    async def create_password_reset_token(self, user_id: str, expires_in_hours: int = 1) -> Optional[str]:
        """
        Create a password reset token.

        Args:
            user_id: User's unique identifier
            expires_in_hours: Hours until token expires

        Returns:
            The reset token or None if failed
        """
        token = self._generate_token()
        token_hash = self._hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        def _create():
            return self.client.table(self.password_reset_table).insert({
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at.isoformat(),
            }).execute()

        try:
            await anyio.to_thread.run_sync(_create)
            return token
        except Exception as e:
            logger.error(f"Failed to create password reset token: {e}")
            return None

    async def validate_password_reset_token(self, token: str) -> Optional[dict]:
        """
        Validate a password reset token.

        Args:
            token: The reset token

        Returns:
            Token data if valid, None otherwise
        """
        token_hash = self._hash_token(token)

        def _validate():
            return (
                self.client.table(self.password_reset_table)
                .select("*")
                .eq("token_hash", token_hash)
                .is_("used_at", "null")
                .maybe_single()
                .execute()
            )

        try:
            result = await anyio.to_thread.run_sync(_validate)
            if result and result.data:
                expires_at = datetime.fromisoformat(result.data["expires_at"].replace("Z", "+00:00"))
                if expires_at > datetime.now(timezone.utc):
                    return result.data
            return None
        except Exception as e:
            if "PGRST116" in str(e):
                return None
            logger.error(f"Failed to validate password reset token: {e}")
            return None

    async def mark_password_reset_used(self, token: str) -> bool:
        """
        Mark a password reset token as used.

        Args:
            token: The reset token

        Returns:
            True if successful, False otherwise
        """
        token_hash = self._hash_token(token)

        def _mark_used():
            return (
                self.client.table(self.password_reset_table)
                .update({"used_at": datetime.now(timezone.utc).isoformat()})
                .eq("token_hash", token_hash)
                .execute()
            )

        try:
            await anyio.to_thread.run_sync(_mark_used)
            return True
        except Exception as e:
            logger.error(f"Failed to mark password reset token as used: {e}")
            return False
