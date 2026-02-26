from __future__ import annotations

import numpy as np


def compute_cross_up(fast_now: float, slow_now: float, fast_prev: float, slow_prev: float) -> bool:
    return bool(fast_now > slow_now and fast_prev <= slow_prev)


def compute_cross_down(fast_now: float, slow_now: float, fast_prev: float, slow_prev: float) -> bool:
    return bool(fast_now < slow_now and fast_prev >= slow_prev)


def compute_entry_buffer_ok(close: float, slow_ma: float, entry_buffer: float) -> bool:
    return bool(close > slow_ma * (1.0 + float(entry_buffer)))


def compute_trend_ok(close: float, trend_fast: float | None, trend_slow: float | None, enable_trend_filter: bool) -> bool:
    if not bool(enable_trend_filter):
        return True
    if trend_fast is None or trend_slow is None:
        return False
    return bool(close > trend_fast and trend_fast > trend_slow)


def compute_atr_stop_ok(close: float, entry_price: float, atr: float | None, k: float, enable: bool) -> bool:
    if not bool(enable) or atr is None:
        return False
    return bool(close <= (entry_price - float(k) * atr))


def compute_atr_trail_ok(close: float, peak_close: float, atr: float | None, k: float, enable: bool) -> bool:
    if not bool(enable) or atr is None:
        return False
    return bool(close <= (peak_close - float(k) * atr))


def compute_regime_ok(benchmark_close: float | None, benchmark_ma: float | None) -> bool:
    if benchmark_close is None or benchmark_ma is None:
        return True
    return bool(benchmark_close > benchmark_ma)


def compute_cross_up_vec(fast_now: np.ndarray, slow_now: np.ndarray, fast_prev: np.ndarray, slow_prev: np.ndarray) -> np.ndarray:
    return (fast_now > slow_now) & (fast_prev <= slow_prev)


def compute_cross_down_vec(
    fast_now: np.ndarray,
    slow_now: np.ndarray,
    fast_prev: np.ndarray,
    slow_prev: np.ndarray,
) -> np.ndarray:
    return (fast_now < slow_now) & (fast_prev >= slow_prev)


def buy_raw_ok_scalar(
    *,
    cross_up: bool,
    close: float | None,
    slow_ma: float | None,
    trend_fast: float | None,
    trend_slow: float | None,
    entry_buffer: float,
    enable_trend_filter: bool,
    regime_ok: bool,
    ma_is_valid: bool,
    tradable: bool = True,
    apply_tradable_in_raw: bool = False,
) -> bool:
    if not bool(ma_is_valid):
        return False
    if not bool(cross_up):
        return False
    if close is None or slow_ma is None:
        return False
    if not bool(regime_ok):
        return False
    if not compute_entry_buffer_ok(float(close), float(slow_ma), float(entry_buffer)):
        return False
    if not compute_trend_ok(float(close), trend_fast, trend_slow, bool(enable_trend_filter)):
        return False
    if bool(apply_tradable_in_raw) and (not bool(tradable)):
        return False
    return True


def buy_raw_ok_vectorized(
    *,
    cross_up: np.ndarray,
    close: np.ndarray,
    slow_ma: np.ndarray,
    trend_fast: np.ndarray,
    trend_slow: np.ndarray,
    entry_buffer: float,
    enable_trend_filter: bool,
    regime_ok: np.ndarray,
    ma_is_valid: np.ndarray,
    tradable: np.ndarray | None = None,
    apply_tradable_in_raw: bool = False,
) -> np.ndarray:
    close_ok = ~np.isnan(close)
    slow_ok = ~np.isnan(slow_ma)
    buffer_ok = close_ok & slow_ok & (close > (slow_ma * (1.0 + float(entry_buffer))))
    if bool(enable_trend_filter):
        trend_ok = (
            (~np.isnan(trend_fast))
            & (~np.isnan(trend_slow))
            & close_ok
            & (close > trend_fast)
            & (trend_fast > trend_slow)
        )
    else:
        trend_ok = np.ones_like(cross_up, dtype=bool)
    out = cross_up & ma_is_valid & regime_ok & buffer_ok & trend_ok
    if bool(apply_tradable_in_raw) and tradable is not None:
        out = out & tradable
    return out


# Backward compatibility aliases.
buy_raw_ok = buy_raw_ok_scalar
buy_raw_ok_vec = buy_raw_ok_vectorized
