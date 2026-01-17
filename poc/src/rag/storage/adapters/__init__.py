"""Adapters for external persistence libraries.

Converts domain entities to/from external formats (e.g., LangChain Document).
"""

from .langchain_adapter import LangChainAdapter

__all__ = ["LangChainAdapter"]
