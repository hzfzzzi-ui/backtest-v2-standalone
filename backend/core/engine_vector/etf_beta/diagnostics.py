from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from backend.core.engine_vector.signal_provider import DayContext

from .provider_config import *
def _normalize_etf_symbol_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "." in text:
        code, venue = text.split(".", 1)
        code = code.strip()
        venue = venue.strip().lower()
        if code and venue in {"sh", "sse"}:
            return f"sh{code}"
        if code and venue in {"sz", "szse"}:
            return f"sz{code}"
    if len(text) > 2 and text[:2] in {"sh", "sz"}:
        return text
    return text


def _display_etf_symbol(value: Any) -> str:
    normalized = _normalize_etf_symbol_key(value)
    if len(normalized) > 2 and normalized[:2] in {"sh", "sz"} and normalized[2:].isdigit():
        return f"{normalized[2:]}.{normalized[:2].upper()}"
    text = str(value or "").strip().upper()
    return text


_TRANS_UP_REDEPLOY_EDGE_FROM_STATES = {"TRANS_DOWN", "RISK_OFF"}


def _resolve_ctx_symbol_price(
    *,
    ctx: DayContext,
    day: date,
    normalized_symbol: str,
    fallback_price: float | None = None,
) -> float | None:
    display_symbol = _display_etf_symbol(normalized_symbol)
    for key in (
        normalized_symbol,
        normalized_symbol.lower(),
        normalized_symbol.upper(),
        display_symbol,
        display_symbol.lower(),
        display_symbol.upper(),
    ):
        raw_value = dict(ctx.close_idx or {}).get((day, key))
        if raw_value is None:
            continue
        try:
            price = float(raw_value)
        except Exception:
            continue
        if np.isfinite(price) and price > 0.0:
            return price
    if fallback_price is not None and np.isfinite(float(fallback_price)) and float(fallback_price) > 0.0:
        return float(fallback_price)
    return None


def _group_exposure_from_holdings(
    *,
    ctx: DayContext,
    day: date,
    day_idx: int,
    held_qty_by_symbol: dict[str, int],
    group_symbols: list[str],
    sym_to_col: dict[str, int],
    close_matrix: Any,
) -> float:
    nav = float(getattr(ctx, "nav", 0.0) or 0.0)
    if nav <= 0.0:
        return 0.0
    group_set = {_normalize_etf_symbol_key(symbol) for symbol in list(group_symbols or []) if _normalize_etf_symbol_key(symbol)}
    if not group_set:
        return 0.0
    total_exposure = 0.0
    for normalized_symbol, qty in dict(held_qty_by_symbol or {}).items():
        if normalized_symbol not in group_set or int(qty) <= 0:
            continue
        fallback_price = None
        col_idx = sym_to_col.get(normalized_symbol)
        if col_idx is not None:
            try:
                raw_close = float(close_matrix[day_idx, col_idx])
            except Exception:
                raw_close = float("nan")
            if np.isfinite(raw_close) and raw_close > 0.0:
                fallback_price = float(raw_close)
        price = _resolve_ctx_symbol_price(
            ctx=ctx,
            day=day,
            normalized_symbol=normalized_symbol,
            fallback_price=fallback_price,
        )
        if price is None or price <= 0.0:
            continue
        total_exposure += float(int(qty)) * float(price) / float(nav)
    return float(total_exposure)



__all__ = [name for name in globals() if name not in {'__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__spec__'}]

