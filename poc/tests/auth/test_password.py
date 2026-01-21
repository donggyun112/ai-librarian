"""Tests for password hashing utilities."""

from src.auth.password import hash_password, verify_password


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_string(self):
        """hash_password should return a string."""
        result = hash_password("test_password")
        assert isinstance(result, str)

    def test_hash_password_returns_different_hash_each_time(self):
        """hash_password should return different hashes for same password (due to salt)."""
        hash1 = hash_password("test_password")
        hash2 = hash_password("test_password")
        assert hash1 != hash2

    def test_hash_password_produces_bcrypt_format(self):
        """hash_password should produce bcrypt format hash."""
        result = hash_password("test_password")
        # bcrypt hashes start with $2b$ or $2a$
        assert result.startswith("$2")

    def test_verify_password_correct_password(self):
        """verify_password should return True for correct password."""
        password = "my_secure_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_wrong_password(self):
        """verify_password should return False for wrong password."""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_empty_password(self):
        """verify_password should handle empty password."""
        hashed = hash_password("some_password")
        assert verify_password("", hashed) is False

    def test_hash_password_unicode(self):
        """hash_password should handle unicode characters."""
        password = "한글비밀번호123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_special_characters(self):
        """hash_password should handle special characters."""
        password = "p@$$w0rd!#$%^&*()"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_long_password(self):
        """hash_password should handle passwords up to bcrypt's 72 byte limit."""
        # bcrypt only uses the first 72 bytes of the password
        password = "a" * 72
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
