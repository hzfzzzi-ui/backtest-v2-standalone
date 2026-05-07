from __future__ import annotations

from typing import Any

import numpy as np

from backend.core.data.cn_etf_catalog import get_catalog_entry

from .provider_config import *
def _symbol_bucket(symbol: Any) -> str:
    entry = get_catalog_entry(symbol)
    if entry is None:
        return ""
    return str(entry.exposure_bucket or "").strip().lower()


def _candidate_pool_reason_codes(
    *,
    symbol: str,
    profile: str | None,
    configured_scope: set[str],
) -> tuple[bool, list[str]]:
    bucket = _symbol_bucket(symbol)
    profile_excluded_reason = f"POOL_PROFILE_EXCLUDED::{bucket.upper()}" if bucket else "POOL_PROFILE_EXCLUDED::UNSUPPORTED_SYMBOL"
    if profile == "a0_proxy_pool":
        if symbol.upper() in configured_scope:
            return True, ["POOL::A0_PROXY_SCOPE"]
        if not bucket:
            return False, [profile_excluded_reason, "POOL_EXCLUDED_UNSUPPORTED_SYMBOL"]
        return False, [profile_excluded_reason, "POOL_EXCLUDED_NOT_IN_A0_PROXY_SCOPE"]
    if profile == "proxy_expanded_pool":
        if bucket in _PROXY_EXPANDED_BUCKETS:
            return True, [f"POOL_BUCKET::{bucket.upper()}"]
        if not bucket:
            return False, [profile_excluded_reason, "POOL_EXCLUDED_UNSUPPORTED_SYMBOL"]
        if bucket in _STANDARD_BUCKETS:
            return False, [profile_excluded_reason, "POOL_EXCLUDED_STANDARD_ONLY_SYMBOL"]
        return False, [profile_excluded_reason, f"POOL_EXCLUDED_BUCKET::{bucket.upper()}"]
    if profile == "standard_overlap_pool":
        if bucket in _STANDARD_OVERLAP_BUCKETS:
            return True, [f"POOL_BUCKET::{bucket.upper()}"]
        if not bucket:
            return False, [profile_excluded_reason, "POOL_EXCLUDED_UNSUPPORTED_SYMBOL"]
        if bucket in _PROXY_BUCKETS:
            return False, [profile_excluded_reason, "POOL_EXCLUDED_PROXY_ONLY_SYMBOL"]
        return False, [profile_excluded_reason, f"POOL_EXCLUDED_BUCKET::{bucket.upper()}"]
    return symbol.upper() in configured_scope, ["POOL::CONFIGURED_SCOPE"] if symbol.upper() in configured_scope else [profile_excluded_reason, "POOL_EXCLUDED_NOT_IN_CONFIGURED_SCOPE"]


def _candidate_pool_coverage_summary(
    *,
    candidate_pool_symbols: list[str],
    close: np.ndarray,
    dates: list[Any],
    sym_to_col: dict[str, int],
) -> dict[str, Any]:
    if not candidate_pool_symbols:
        return {}
    starts: list[str] = []
    ends: list[str] = []
    proxy_symbol_count = 0
    standard_symbol_count = 0
    growth_symbol_count = 0
    for symbol in candidate_pool_symbols:
        bucket = _symbol_bucket(symbol)
        if bucket in _PROXY_BUCKETS:
            proxy_symbol_count += 1
        if bucket in _STANDARD_BUCKETS:
            standard_symbol_count += 1
        if bucket in _GROWTH_BUCKETS:
            growth_symbol_count += 1
        col_idx = sym_to_col.get(_normalize_etf_symbol_key(symbol))
        if col_idx is None:
            continue
        finite_idx = np.where(np.isfinite(close[:, col_idx]))[0]
        if finite_idx.size <= 0:
            continue
        starts.append(str(_coerce_day(dates[int(finite_idx[0])]).isoformat()))
        ends.append(str(_coerce_day(dates[int(finite_idx[-1])]).isoformat()))
    return {
        "symbol_count": len(candidate_pool_symbols),
        "proxy_symbol_count": proxy_symbol_count,
        "standard_symbol_count": standard_symbol_count,
        "growth_symbol_count": growth_symbol_count,
        "overlap_start": max(starts) if starts else None,
        "overlap_end": min(ends) if ends else None,
    }



__all__ = [name for name in globals() if name not in {'__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__spec__'}]

