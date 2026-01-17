"""Shared exception classes for OCR Vector DB."""


class SharedError(Exception):
    """Base exception for shared utilities."""

    pass


class ConfigurationError(SharedError):
    """Raised when configuration is invalid or missing."""

    pass


class DatabaseNotConfiguredError(SharedError):
    """Raised when database connection is not configured.
    
    API layer should map this to 503 Service Unavailable.
    """

    pass


__all__ = ["SharedError", "ConfigurationError", "DatabaseNotConfiguredError"]
