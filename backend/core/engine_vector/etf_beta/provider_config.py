from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from backend.core.config.etf_beta_contract import *
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


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_choice(value: Any, *, default: str, allowed: set[str]) -> str:
    text = _normalize_text(value).lower()
    if text in allowed:
        return text
    return default


def _normalize_optional_choice(value: Any, *, allowed: set[str]) -> str | None:
    text = _normalize_text(value).lower()
    if not text:
        return None
    if text in allowed:
        return text
    return None


def _normalize_symbol_map(value: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(value, dict):
        return out
    for key, raw in value.items():
        symbol = _display_etf_symbol(key).upper()
        text = _normalize_text(raw)
        if not symbol or not text:
            continue
        out[symbol] = text
    return out


def _normalize_symbol_pairs(value: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(value, dict):
        return out
    for key, raw in value.items():
        symbol = _display_etf_symbol(key).upper()
        replacement = _display_etf_symbol(raw).upper()
        if not symbol or not replacement:
            continue
        out[symbol] = replacement
    return out


def _absolute_filter_reason_codes(mode: str) -> list[str]:
    if mode == "positive_12m":
        return ["ABSOLUTE_RET12_PASS"]
    if mode == "ma200_only":
        return ["ABSOLUTE_MA200_PASS"]
    if mode == "ma150_and_positive_12m":
        return ["ABSOLUTE_MA150_PASS", "ABSOLUTE_RET12_PASS"]
    if mode == "ma200_and_positive_12m":
        return ["ABSOLUTE_MA200_PASS", "ABSOLUTE_RET12_PASS"]
    return ["ABSOLUTE_MA120_PASS"]


def _rebalance_selection_reason_code(frequency: str, *, rebalance_day: bool) -> str:
    mapping = {
        "weekly": ("WEEKLY_REBALANCE", "HOLD_UNTIL_REBALANCE"),
        "biweekly": ("BIWEEKLY_REBALANCE", "HOLD_UNTIL_REBALANCE"),
        "monthly": ("MONTHLY_REBALANCE", "HOLD_UNTIL_REBALANCE"),
    }
    on_rebalance, off_rebalance = mapping.get(str(frequency or "").strip().lower(), mapping["weekly"])
    return on_rebalance if rebalance_day else off_rebalance


def _selection_active_reason_code(frequency: str) -> str:
    mapping = {
        "weekly": "ETF_BETA_WEEKLY_SELECTION_ACTIVE",
        "biweekly": "ETF_BETA_BIWEEKLY_SELECTION_ACTIVE",
        "monthly": "ETF_BETA_MONTHLY_SELECTION_ACTIVE",
    }
    return mapping.get(str(frequency or "").strip().lower(), "ETF_BETA_WEEKLY_SELECTION_ACTIVE")


def _await_rebalance_reason_code(frequency: str) -> str:
    mapping = {
        "weekly": "ETF_BETA_AWAIT_WEEKLY_REBALANCE",
        "biweekly": "ETF_BETA_AWAIT_BIWEEKLY_REBALANCE",
        "monthly": "ETF_BETA_AWAIT_MONTHLY_REBALANCE",
    }
    return mapping.get(str(frequency or "").strip().lower(), "ETF_BETA_AWAIT_WEEKLY_REBALANCE")


def _entry_reason_code(frequency: str) -> str:
    mapping = {
        "weekly": "ETF_BETA_WEEKLY_RS",
        "biweekly": "ETF_BETA_BIWEEKLY_RS",
        "monthly": "ETF_BETA_MONTHLY_RS",
    }
    return mapping.get(str(frequency or "").strip().lower(), "ETF_BETA_WEEKLY_RS")


_FORMAL_CORE_SCOPE = tuple(_normalize_etf_symbol_key(symbol) for symbol in CN_ETF_BETA_CORE_SYMBOLS)
_STATE_SLOT_CAPS = {
    "BULL": 2,
    "TRANS_UP": 2,
    "TRANS_DOWN": 0,
    "RISK_OFF": 0,
}
_FORMAL_PHASE1_BOUNDARY_SLOT_CAPS = {
    "BULL": 2,
    "TRANS_UP": 1,
    "TRANS_DOWN": 1,
    "RISK_OFF": 1,
}
_TRADE_MODE_SLOT_CAPS = {
    "TREND_MAIN": 2,
    "TREND_LIGHT": 1,
    "NO_TRADE": 0,
}
_ABSOLUTE_FILTER_PROFILE_TO_MODE = {
    "ma200_ret12": "ma200_and_positive_12m",
    "ma200_only": "ma200_only",
    "ma150_ret12": "ma150_and_positive_12m",
}
_PROXY_EXPANDED_BUCKETS = {
    "broad_equity",
    "large_cap_equity",
    "mid_cap_equity",
    "small_cap_equity",
    "dividend_low_vol",
    "growth_equity",
    "technology_growth",
}
_STANDARD_OVERLAP_BUCKETS = {
    "broad_equity",
    "large_cap_equity",
    "mid_cap_equity",
    "small_cap_equity_standard",
    "dividend_standard",
    "growth_equity",
    "technology_growth",
}
_GROWTH_BUCKETS = {"growth_equity", "technology_growth"}
_STANDARD_BUCKETS = {"small_cap_equity_standard", "dividend_standard"}
_PROXY_BUCKETS = {"small_cap_equity", "dividend_low_vol"}


def _slot_cap_from_trade_mode(value: Any) -> int:
    return int(_TRADE_MODE_SLOT_CAPS.get(str(value or "").strip().upper(), 0))


def _trade_mode_from_slot_cap(slot_cap: Any) -> str:
    count = int(slot_cap or 0)
    if count >= 2:
        return "TREND_MAIN"
    if count == 1:
        return "TREND_LIGHT"
    return "NO_TRADE"


def _trade_mode_code_from_name(value: Any) -> int:
    text = str(value or "").strip().upper()
    if text == "TREND_MAIN":
        return 0
    if text == "TREND_LIGHT":
        return 1
    return 2


def _formal_phase1_slot_cap_from_state(value: Any) -> int:
    return int(_FORMAL_PHASE1_BOUNDARY_SLOT_CAPS.get(str(value or "").strip().upper(), 0))

def _sequence_payload(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _safe_return(close_now: float, close_prev: float) -> float | None:
    if close_now != close_now or close_prev != close_prev:
        return None
    if close_prev <= 0.0:
        return None
    return float(close_now / close_prev - 1.0)


def _realized_vol_annualized(daily_returns: np.ndarray, row_idx: int, window: int) -> float | None:
    if row_idx <= 0 or window <= 1:
        return None
    start_idx = max(0, row_idx - int(window) + 1)
    sample = np.asarray(daily_returns[start_idx : row_idx + 1], dtype=float)
    sample = sample[np.isfinite(sample)]
    if sample.size < max(3, int(window) // 2):
        return None
    vol = float(np.std(sample, ddof=1)) * float(np.sqrt(252.0))
    if not np.isfinite(vol) or vol <= 0.0:
        return None
    return vol


def _coerce_day(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, np.datetime64):
        return date.fromisoformat(np.datetime_as_string(value, unit="D"))
    return date.fromisoformat(str(value)[:10])


def _rebalance_flags(trading_days: list[Any], *, frequency: str) -> np.ndarray:
    flags = np.zeros(len(trading_days), dtype=bool)
    if not trading_days:
        return flags
    frequency_text = str(frequency or "").strip().lower()
    if frequency_text == "monthly":
        for idx, day in enumerate(trading_days):
            current_day = _coerce_day(day)
            if idx == len(trading_days) - 1:
                flags[idx] = True
                continue
            next_day = _coerce_day(trading_days[idx + 1])
            flags[idx] = (current_day.year, current_day.month) != (next_day.year, next_day.month)
        return flags
    bucket_divisor = 2 if frequency_text == "biweekly" else 1
    for idx, day in enumerate(trading_days):
        current_day = _coerce_day(day)
        if idx == len(trading_days) - 1:
            flags[idx] = True
            continue
        next_day = _coerce_day(trading_days[idx + 1])
        current_iso = current_day.isocalendar()
        next_iso = next_day.isocalendar()
        current_bucket = (current_iso[0], max(current_iso[1] - 1, 0) // bucket_divisor)
        next_bucket = (next_iso[0], max(next_iso[1] - 1, 0) // bucket_divisor)
        flags[idx] = current_bucket != next_bucket
    return flags


def _rank_score(values: dict[int, float]) -> dict[int, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    total = max(len(ordered), 1)
    return {col: float(rank) / float(total) for rank, (col, _value) in enumerate(ordered, start=1)}


def _array_item(arr: Any, idx: int) -> Any:
    if isinstance(arr, np.ndarray) and idx < len(arr):
        return arr[idx]
    return None


def _has_text_payload(arr: Any) -> bool:
    if not isinstance(arr, np.ndarray) or len(arr) == 0:
        return False
    for value in arr.tolist():
        if str(value or "").strip():
            return True
    return False



__all__ = [name for name in globals() if name not in {'__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__spec__'}]

