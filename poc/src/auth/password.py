"""Password hashing and verification utilities.

Security notes:
- bcrypt has a 72-byte limit on password length. Passwords longer than 72 bytes
  are silently truncated, meaning two passwords with the same first 72 bytes
  would hash to the same value.
- To handle this, we pre-hash the password with SHA-256 (base64-encoded) before
  passing it to bcrypt. This ensures the full password is considered.
- This is the same approach used by Dropbox and recommended by security experts.
"""

import base64
import hashlib

import bcrypt


def _prehash_password(password: str) -> bytes:
    """
    Pre-hash a password with SHA-256 to handle bcrypt's 72-byte limit.

    This ensures passwords longer than 72 bytes are fully considered,
    and the result is always 44 bytes (base64-encoded SHA-256).

    Args:
        password: The plaintext password

    Returns:
        Base64-encoded SHA-256 hash as bytes
    """
    sha256_hash = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(sha256_hash)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with SHA-256 pre-hashing.

    The password is first hashed with SHA-256 and base64-encoded to handle
    bcrypt's 72-byte limit, then hashed with bcrypt for secure storage.

    Args:
        password: The plaintext password to hash

    Returns:
        The bcrypt hash of the pre-hashed password
    """
    prehashed = _prehash_password(password)
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds is recommended minimum
    return bcrypt.hashpw(prehashed, salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    The password is pre-hashed with SHA-256 before verification to match
    the hashing process.

    Args:
        password: The plaintext password to verify
        hashed: The bcrypt hash to verify against

    Returns:
        True if the password matches the hash, False otherwise
    """
    prehashed = _prehash_password(password)
    return bcrypt.checkpw(prehashed, hashed.encode("utf-8"))
