from __future__ import annotations

from datetime import date


def compute_nav_snapshot(
    *,
    cash: float,
    dividend_receivable: float = 0.0,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    day: date,
    hfq_close_idx: dict[tuple[date, str], float] | None = None,
    position_entry_adj: dict[str, float] | None = None,
) -> tuple[float, float, list[tuple[str, float]]]:
    """Compute NAV snapshot from cash, positions and valuation closes."""
    use_hfq = hfq_close_idx is not None and position_entry_adj is not None
    entry_adj = position_entry_adj or {}
    market_value = 0.0
    pos_values: list[tuple[str, float]] = []
    for sym, qty in positions.items():
        raw_close = float(close_idx.get((day, sym), 0.0) or 0.0)
        if use_hfq:
            hfq_close = float((hfq_close_idx or {}).get((day, sym), 0.0) or 0.0)
            ea = float(entry_adj.get(sym, 0.0) or 0.0)
            if hfq_close > 0.0 and ea > 1e-8:
                v = hfq_close / ea * qty
            else:
                v = raw_close * qty
        else:
            v = raw_close * qty
        market_value += v
        pos_values.append((sym, v))
    nav = float(cash) + float(dividend_receivable) + float(market_value)
    return nav, market_value, pos_values
