"""Base repository interface for domain entities.

Defines common CRUD operations for all repositories.

Rules:
- PKG-STO-001: Repository interface definition responsibility
- DEP-STO-ALLOW-001~002: MAY import domain, shared
"""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

from src.rag.domain import Concept, Document, Fragment

# Type variable for domain entities
T = TypeVar("T", Document, Concept, Fragment)


class BaseRepository(ABC, Generic[T]):
    """Abstract base class for all repositories.

    Provides common CRUD operations that must be implemented by
    concrete repository classes.
    """

    @abstractmethod
    def save(self, entity: T) -> T:
        """Save an entity to the database.

        Args:
            entity: Domain entity to save

        Returns:
            Saved entity (may include generated fields)
        """
        pass

    @abstractmethod
    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find an entity by its ID.

        Args:
            entity_id: Entity ID to search for

        Returns:
            Entity if found, None otherwise
        """
        pass

    @abstractmethod
    def find_all(self) -> List[T]:
        """Find all entities of this type.

        Returns:
            List of all entities
        """
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> None:
        """Delete an entity by ID.

        Args:
            entity_id: ID of entity to delete

        Note:
            This does NOT perform cascade deletion.
            Use CascadeDeleter for cascade operations.
        """
        pass

    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: Entity ID to check

        Returns:
            True if entity exists, False otherwise
        """
        pass


__all__ = ["BaseRepository"]
