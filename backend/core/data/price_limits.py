from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

_EQUITY_TICK = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        text = format(float(value), ".12f")
    except Exception:
        text = str(value).strip()
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def price_tick_for_symbol(symbol: str) -> Decimal:
    # A股股票价格最小变动单位统一按 0.01 元处理。
    _ = str(symbol or "").strip().lower()
    return _EQUITY_TICK


def round_price_to_tick(value: Any, symbol: str) -> float | None:
    number = _to_decimal(value)
    if number is None:
        return None
    tick = price_tick_for_symbol(symbol)
    return float(number.quantize(tick, rounding=ROUND_HALF_UP))


def limit_pct_for_symbol(symbol: str, *, is_st: bool) -> float:
    normalized = str(symbol or "").strip().lower()
    if normalized.startswith("bj"):
        return 0.30
    if normalized.startswith("sh688") or normalized.startswith("sz300") or normalized.startswith("sz301"):
        return 0.20
    if is_st:
        return 0.05
    return 0.10


def compute_limit_prices(prev_close: Any, symbol: str, *, is_st: bool) -> tuple[float | None, float | None]:
    previous = _to_decimal(prev_close)
    if previous is None or previous <= Decimal("0"):
        return None, None
    pct = Decimal(str(limit_pct_for_symbol(symbol, is_st=is_st)))
    limit_up = round_price_to_tick(previous * (Decimal("1") + pct), symbol)
    limit_down = round_price_to_tick(previous * (Decimal("1") - pct), symbol)
    return limit_up, limit_down
