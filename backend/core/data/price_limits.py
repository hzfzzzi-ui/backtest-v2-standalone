from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

_EQUITY_TICK = Decimal("0.01")
_ETF_TICK = Decimal("0.001")


class UnsupportedMarketProfileError(ValueError):
    pass


def _ensure_supported_market(
    *,
    asset_scope: str | None = None,
    market_key: str | None = None,
) -> None:
    normalized_scope = str(asset_scope or "").strip().lower()
    normalized_market = str(market_key or "").strip().upper()
    if normalized_scope and normalized_scope not in {"cn_a_equity", "cn_etf"}:
        raise UnsupportedMarketProfileError(
            f"price limit rules unavailable for asset_scope: {asset_scope}"
        )
    if normalized_market and normalized_market != "CN_A":
        raise UnsupportedMarketProfileError(
            f"price limit rules unavailable for market_key: {market_key}"
        )


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


def price_tick_for_symbol(
    symbol: str,
    *,
    asset_scope: str | None = None,
    market_key: str | None = None,
) -> Decimal:
    _ = str(symbol or "").strip().lower()
    _ensure_supported_market(asset_scope=asset_scope, market_key=market_key)
    if str(asset_scope or "").strip().lower() == "cn_etf":
        return _ETF_TICK
    return _EQUITY_TICK


def round_price_to_tick(
    value: Any,
    symbol: str,
    *,
    asset_scope: str | None = None,
    market_key: str | None = None,
) -> float | None:
    number = _to_decimal(value)
    if number is None:
        return None
    tick = price_tick_for_symbol(symbol, asset_scope=asset_scope, market_key=market_key)
    return float(number.quantize(tick, rounding=ROUND_HALF_UP))


def limit_pct_for_symbol(
    symbol: str,
    *,
    is_st: bool,
    asset_scope: str | None = None,
    market_key: str | None = None,
) -> float:
    _ensure_supported_market(asset_scope=asset_scope, market_key=market_key)
    if str(asset_scope or "").strip().lower() == "cn_etf":
        return 0.10
    normalized = str(symbol or "").strip().lower()
    if normalized.startswith("bj"):
        return 0.30
    if normalized.startswith("sh688") or normalized.startswith("sz300") or normalized.startswith("sz301"):
        return 0.20
    if is_st:
        return 0.05
    return 0.10


def compute_limit_prices(
    prev_close: Any,
    symbol: str,
    *,
    is_st: bool,
    asset_scope: str | None = None,
    market_key: str | None = None,
) -> tuple[float | None, float | None]:
    previous = _to_decimal(prev_close)
    if previous is None or previous <= Decimal("0"):
        return None, None
    pct = Decimal(
        str(
            limit_pct_for_symbol(
                symbol,
                is_st=is_st,
                asset_scope=asset_scope,
                market_key=market_key,
            )
        )
    )
    limit_up = round_price_to_tick(
        previous * (Decimal("1") + pct),
        symbol,
        asset_scope=asset_scope,
        market_key=market_key,
    )
    limit_down = round_price_to_tick(
        previous * (Decimal("1") - pct),
        symbol,
        asset_scope=asset_scope,
        market_key=market_key,
    )
    return limit_up, limit_down
