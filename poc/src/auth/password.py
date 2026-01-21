"""Password hashing and verification utilities."""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: The plaintext password to hash

    Returns:
        The bcrypt hash of the password
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        password: The plaintext password to verify
        hashed: The bcrypt hash to verify against

    Returns:
        True if the password matches the hash, False otherwise
    """
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
