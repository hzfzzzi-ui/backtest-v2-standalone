from __future__ import annotations

from datetime import date


def compute_nav_snapshot(
    *,
    cash: float,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    day: date,
    hfq_close_idx: dict[tuple[date, str], float] | None = None,
    position_entry_adj: dict[str, float] | None = None,
) -> tuple[float, float, list[tuple[str, float]]]:
    """Compute NAV snapshot from cash, positions and valuation closes."""
    use_hfq = hfq_close_idx is not None and position_entry_adj is not None
    val_idx = hfq_close_idx if use_hfq else close_idx
    entry_adj = position_entry_adj or {}
    market_value = 0.0
    pos_values: list[tuple[str, float]] = []
    for sym, qty in positions.items():
        c = float(val_idx.get((day, sym), 0.0) or 0.0)
        if use_hfq:
            ea = entry_adj.get(sym, 1.0)
            v = c / ea * qty if ea > 1e-8 else c * qty
        else:
            v = c * qty
        market_value += v
        pos_values.append((sym, v))
    nav = float(cash) + float(market_value)
    return nav, market_value, pos_values
