from __future__ import annotations

import heapq
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def stable_topk(items: Iterable[T], k: int, *, key: Callable[[T], object]) -> list[T]:
    """Return the first k items by key without sorting the full population.

    `heapq.nsmallest` preserves the same selected set and order as a stable full
    sort for total ordering keys, while reducing selection cost to O(n log k).
    """
    limit = max(0, int(k))
    values = list(items)
    if limit <= 0:
        return []
    if limit >= len(values):
        return sorted(values, key=key)
    return list(heapq.nsmallest(limit, values, key=key))
