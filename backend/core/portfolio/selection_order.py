from __future__ import annotations

from typing import Any


def normalize_candidate_order(symbols: list[str]) -> list[str]:
    return sorted([str(s).lower() for s in symbols])


def sort_by_strength_with_tiebreak(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # strength desc, tie -> symbol asc, None strength always last.
    return sorted(
        items,
        key=lambda x: (
            1 if x.get("strength") is None else 0,
            -(float(x.get("strength")) if x.get("strength") is not None else float("-inf")),
            str(x.get("symbol", "")).lower(),
        ),
    )
