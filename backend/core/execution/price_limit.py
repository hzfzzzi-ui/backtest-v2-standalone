from __future__ import annotations

import math


def round_to_tick(price: float, tick_size: float) -> float:
    if tick_size <= 0:
        return float(price)
    return round(round(price / tick_size) * tick_size, 6)


def limit_prices(prev_close: float, limit_pct: float, tick_size: float) -> tuple[float, float]:
    up = round_to_tick(prev_close * (1.0 + limit_pct), tick_size)
    dn = round_to_tick(prev_close * (1.0 - limit_pct), tick_size)
    return up, dn


def infer_limit_pct(symbol: str, board: str | None, default_pct: float, star_pct: float, gem_pct: float) -> float:
    b = (board or "").upper()
    sym = symbol.upper()
    if b in {"STAR", "KCB", "GEM"}:
        return gem_pct
    if b in {"ST", "*ST"}:
        return star_pct
    if sym.startswith("688") or sym.startswith("300") or sym.startswith("SH688") or sym.startswith("SZ300"):
        return gem_pct
    return default_pct


def floor_lot(qty: int, lot_size: int) -> int:
    if lot_size <= 1:
        return max(0, qty)
    return int(math.floor(max(0, qty) / lot_size) * lot_size)
