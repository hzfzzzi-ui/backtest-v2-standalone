from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.core.strategies.signals_core import compute_cross_down_vec, compute_cross_up_vec


@dataclass(slots=True)
class DailyMasks:
    cross_up: np.ndarray
    cross_down: np.ndarray
    trend_ok: np.ndarray
    buffer_ok: np.ndarray
    regime_on: bool


def build_daily_masks(
    *,
    i: int,
    close: np.ndarray,
    fast_ma: np.ndarray,
    slow_ma: np.ndarray,
    trend_fast_ma: np.ndarray,
    trend_slow_ma: np.ndarray,
    benchmark_close: np.ndarray,
    benchmark_ma: np.ndarray,
    entry_buffer: float,
    enable_trend_filter: bool,
) -> DailyMasks:
    n = close.shape[1]
    if i <= 0:
        return DailyMasks(
            cross_up=np.zeros(n, dtype=bool),
            cross_down=np.zeros(n, dtype=bool),
            trend_ok=np.zeros(n, dtype=bool) if enable_trend_filter else np.ones(n, dtype=bool),
            buffer_ok=np.zeros(n, dtype=bool),
            regime_on=True,
        )

    fast_now = fast_ma[i]
    slow_now = slow_ma[i]
    fast_prev = fast_ma[i - 1]
    slow_prev = slow_ma[i - 1]
    valid = ~np.isnan(fast_now) & ~np.isnan(slow_now) & ~np.isnan(fast_prev) & ~np.isnan(slow_prev) & ~np.isnan(close[i])
    cross_up = compute_cross_up_vec(fast_now, slow_now, fast_prev, slow_prev) & valid
    cross_down = compute_cross_down_vec(fast_now, slow_now, fast_prev, slow_prev) & valid
    buffer_ok = (close[i] > (slow_now * (1.0 + float(entry_buffer)))) & valid

    if enable_trend_filter:
        tf = trend_fast_ma[i]
        ts = trend_slow_ma[i]
        trend_ok = (~np.isnan(tf)) & (~np.isnan(ts)) & (~np.isnan(close[i])) & (close[i] > tf) & (tf > ts)
    else:
        trend_ok = np.ones(n, dtype=bool)

    regime_on = True
    if i < len(benchmark_close) and i < len(benchmark_ma):
        bc = benchmark_close[i]
        bm = benchmark_ma[i]
        if not np.isnan(bc) and not np.isnan(bm):
            regime_on = bool(bc > bm)

    return DailyMasks(
        cross_up=cross_up,
        cross_down=cross_down,
        trend_ok=trend_ok,
        buffer_ok=buffer_ok,
        regime_on=regime_on,
    )

