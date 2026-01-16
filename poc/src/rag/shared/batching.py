"""Batching utilities for embedding requests.

Provides character-budget-aware batching to avoid exceeding
model token limits and rate limits.
"""

from typing import Callable, Generator, List, Optional, TypeVar

T = TypeVar("T")


def iter_by_char_budget(
    items: List[T],
    char_budget: int,
    max_batch_size: int,
    max_items_per_request: int = 0,
    get_content: Optional[Callable[[T], str]] = None,
) -> Generator[List[T], None, None]:
    """Iterate items in batches respecting character budget.

    Groups items into batches that:
    1. Don't exceed char_budget total characters
    2. Don't exceed max_batch_size items
    3. Don't exceed max_items_per_request items (if > 0)

    Args:
        items: List of items to batch
        char_budget: Maximum total characters per batch (0 = unlimited)
        max_batch_size: Maximum items per batch
        max_items_per_request: Additional item limit per batch (0 = use max_batch_size)
        get_content: Function to extract content string from item (default: item.page_content)

    Yields:
        Lists of items forming each batch
    """
    if not items:
        return
    # Default content extractor for LangChain Documents
    if get_content is None:
        get_content = lambda x: getattr(x, "page_content", str(x))

    # Determine effective limits
    item_limit = max_items_per_request if max_items_per_request > 0 else max_batch_size
    item_limit = min(item_limit, max_batch_size)

    batch: List[T] = []
    batch_chars = 0

    for item in items:
        item_chars = len(get_content(item))

        # Check if adding this item would exceed limits
        would_exceed_chars = char_budget > 0 and batch_chars + item_chars > char_budget
        would_exceed_items = len(batch) >= item_limit

        if batch and (would_exceed_chars or would_exceed_items):
            yield batch
            batch = []
            batch_chars = 0

        batch.append(item)
        batch_chars += item_chars

    if batch:
        yield batch


__all__ = ["iter_by_char_budget"]
