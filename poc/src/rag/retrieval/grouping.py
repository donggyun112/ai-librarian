"""Result grouping and aggregation.

Groups search results by parent, view, language, or other criteria.

Rules:
- PKG-RET-004: Search result grouping (SHOULD)
- DEP-RET-ALLOW-001: MAY import domain
"""

from collections import defaultdict
from typing import Dict, List

from src.rag.domain import View

from .context import ExpandedResult
from .search import SearchResult


class ResultGrouper:
    """Groups search results by various criteria.

    Implements PKG-RET-004 (result grouping).

    Example:
        >>> grouper = ResultGrouper()
        >>> results = [SearchResult(...), ...]
        >>> by_view = grouper.group_by_view(results)
        >>> by_view[View.CODE]  # All code results
    """

    @staticmethod
    def group_by_parent(results: List[SearchResult]) -> Dict[str, List[SearchResult]]:
        """Group results by parent Concept.

        Args:
            results: List of search results

        Returns:
            Dictionary mapping parent_id to list of results
        """
        groups: Dict[str, List[SearchResult]] = defaultdict(list)
        for result in results:
            groups[result.parent_id].append(result)
        return dict(groups)

    @staticmethod
    def group_by_view(results: List[SearchResult]) -> Dict[View, List[SearchResult]]:
        """Group results by view type.

        Args:
            results: List of search results

        Returns:
            Dictionary mapping View to list of results
        """
        groups: Dict[View, List[SearchResult]] = defaultdict(list)
        for result in results:
            groups[result.view].append(result)
        return dict(groups)

    @staticmethod
    def group_by_language(results: List[SearchResult]) -> Dict[str, List[SearchResult]]:
        """Group results by language.

        Args:
            results: List of search results

        Returns:
            Dictionary mapping language to list of results
        """
        groups: Dict[str, List[SearchResult]] = defaultdict(list)
        for result in results:
            lang = result.language or "unknown"
            groups[lang].append(result)
        return dict(groups)

    @staticmethod
    def deduplicate_by_content(results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results with identical content.

        Args:
            results: List of search results

        Returns:
            Deduplicated list (keeps first occurrence)
        """
        seen = set()
        unique = []
        for result in results:
            key = result.content or result.metadata.get("doc_id") or result.fragment_id
            if key not in seen:
                seen.add(key)
                unique.append(result)
        return unique

    @staticmethod
    def top_n_per_parent(
        results: List[SearchResult],
        n: int = 3,
    ) -> List[SearchResult]:
        """Keep only top N results per parent.

        Args:
            results: List of search results (should be sorted by similarity)
            n: Number of results to keep per parent

        Returns:
            Filtered list with max N results per parent
        """
        parent_counts: Dict[str, int] = defaultdict(int)
        filtered = []

        for result in results:
            if parent_counts[result.parent_id] < n:
                filtered.append(result)
                parent_counts[result.parent_id] += 1

        return filtered


__all__ = ["ResultGrouper"]
