"""Request validation for API layer.

Implements PKG-API-002: Request validation.

Rules:
- DEP-API-ALLOW-001: MAY import domain
- PKG-API-BAN-003: MUST NOT define domain entities
"""

import os
from typing import List, Optional

from src.rag.domain import View


class ValidationError(Exception):
    """Raised when request validation fails."""

    pass


class RequestValidator:
    """Validates API requests.

    Implements PKG-API-002 (request validation).
    """

    @staticmethod
    def validate_file_path(path: str) -> None:
        """Validate that a file path exists and is readable.

        Args:
            path: File path to validate

        Raises:
            ValidationError: If file doesn't exist or isn't readable
        """
        if not path:
            raise ValidationError("File path cannot be empty")
        if not os.path.exists(path):
            raise ValidationError(f"File not found: {path}")
        if not os.path.isfile(path):
            raise ValidationError(f"Path is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise ValidationError(f"File is not readable: {path}")

    @staticmethod
    def validate_file_paths(paths: List[str]) -> None:
        """Validate multiple file paths.

        Args:
            paths: List of file paths to validate

        Raises:
            ValidationError: If any file is invalid
        """
        if not paths:
            raise ValidationError("No file paths provided")
        for path in paths:
            RequestValidator.validate_file_path(path)

    @staticmethod
    def validate_view(view: Optional[str]) -> None:
        """Validate view parameter.

        Args:
            view: View string to validate (text, code, image, etc.)

        Raises:
            ValidationError: If view is invalid
        """
        if view is None:
            return
        try:
            View(view.lower())
        except ValueError:
            valid_views = [v.value for v in View]
            raise ValidationError(
                f"Invalid view: {view}. Must be one of: {', '.join(valid_views)}"
            )

    @staticmethod
    def validate_top_k(top_k: int) -> None:
        """Validate top_k parameter.

        Args:
            top_k: Number of results to retrieve

        Raises:
            ValidationError: If top_k is invalid
        """
        if top_k < 1:
            raise ValidationError(f"top_k must be at least 1, got {top_k}")
        if top_k > 1000:
            raise ValidationError(f"top_k must be at most 1000, got {top_k}")

    @staticmethod
    def validate_query(query: str) -> None:
        """Validate search query.

        Args:
            query: Query string to validate

        Raises:
            ValidationError: If query is invalid
        """
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty")
        if len(query) > 10000:
            raise ValidationError(f"Query too long (max 10000 chars): {len(query)}")


__all__ = ["RequestValidator", "ValidationError"]
