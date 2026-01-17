"""Base parser interface for ingestion layer."""

from abc import ABC, abstractmethod
from typing import List

from src.rag.shared.text_utils import TextNormalizerUtil

from ..dto import RawSegment


class BaseSegmentParser(ABC):
    """Abstract base class for file parsers."""

    def __init__(self, preprocessor: TextNormalizerUtil) -> None:
        self.preprocessor = preprocessor

    @abstractmethod
    def parse(self, path: str) -> List[RawSegment]:
        """
        Parse a file into raw segments.

        Args:
            path: File path to parse

        Returns:
            List of RawSegment objects
        """
        ...


__all__ = ["BaseSegmentParser"]
