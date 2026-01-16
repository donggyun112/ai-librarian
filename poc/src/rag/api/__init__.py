"""API layer for OCR Vector DB.

Provides external interfaces (CLI, REST), request validation, and response formatting.

Rules:
- PKG-API-001~004: External interfaces, request validation, response formatting, orchestration
- PKG-API-BAN-001~003: MUST NOT implement business logic, access DB directly, or define entities
- DEP-API-ALLOW-001~006: MAY import domain, ingestion, embedding, retrieval, storage, shared
- DEP-API-001: SHOULD NOT import shared's internal implementation
"""

__all__ = []
