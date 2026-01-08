"""Shared exception classes for OCR Vector DB."""


class SharedError(Exception):
    """Base exception for shared utilities."""

    pass


class ConfigurationError(SharedError):
    """Raised when configuration is invalid or missing."""

    pass


__all__ = ["SharedError", "ConfigurationError"]
