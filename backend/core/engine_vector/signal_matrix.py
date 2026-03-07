from __future__ import annotations

import numpy as np
import pandas as pd

from backend.core.strategies.signals_core import buy_raw_ok_vectorized, compute_cross_down_vec, compute_cross_up_vec


def build_signal_matrices(
    *,
    close: np.ndarray,
    fast_ma: np.ndarray,
    slow_ma: np.ndarray,
    trend_fast_ma: np.ndarray,
    trend_slow_ma: np.ndarray,
    tradable: np.ndarray,
    entry_buffer: float,
    enable_trend_filter: bool,
    enable_trend_tier: bool = False,
    enable_trend_slope_filter: bool = False,
    slope_lookback: int = 5,
    enable_trend_continuity_filter: bool = False,
    continuity_n: int = 10,
    risk_on: np.ndarray,
    # 入场趋势过滤（基于信号 slow_ma）
    enable_entry_above_slow_ma: bool = False,
    enable_entry_slow_ma_slope: bool = False,
    entry_slope_lookback: int = 5,
    # V2 个股趋势过滤 (close > sma60 AND sma20 > sma60)
    sma20: np.ndarray | None = None,
    sma60: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    t, n = close.shape
    cross_up = np.zeros((t, n), dtype=bool)
    cross_down = np.zeros((t, n), dtype=bool)
    trend_ok = np.ones((t, n), dtype=bool)
    buffer_ok = np.zeros((t, n), dtype=bool)

    if t > 1:
        fast_now = fast_ma[1:, :]
        slow_now = slow_ma[1:, :]
        fast_prev = fast_ma[:-1, :]
        slow_prev = slow_ma[:-1, :]
        valid = (
            ~np.isnan(fast_now)
            & ~np.isnan(slow_now)
            & ~np.isnan(fast_prev)
            & ~np.isnan(slow_prev)
            & ~np.isnan(close[1:, :])
        )
        cross_up[1:, :] = compute_cross_up_vec(fast_now, slow_now, fast_prev, slow_prev) & valid
        cross_down[1:, :] = compute_cross_down_vec(fast_now, slow_now, fast_prev, slow_prev) & valid
        buffer_ok[1:, :] = (close[1:, :] > (slow_now * (1.0 + float(entry_buffer)))) & valid

    base_trend_on = (
        ~np.isnan(trend_fast_ma)
        & ~np.isnan(trend_slow_ma)
        & (trend_fast_ma > trend_slow_ma)
    )
    legacy_trend_ok = (
        ~np.isnan(trend_fast_ma)
        & ~np.isnan(trend_slow_ma)
        & ~np.isnan(close)
        & (close > trend_fast_ma)
        & (trend_fast_ma > trend_slow_ma)
    )
    slope_pass = np.ones((t, n), dtype=bool)
    if bool(enable_trend_slope_filter):
        lb = max(1, int(slope_lookback))
        slope_pass[:] = False
        if t > lb:
            slope_fast = np.full((t, n), np.nan, dtype=float)
            slope_slow = np.full((t, n), np.nan, dtype=float)
            slope_fast[lb:, :] = trend_fast_ma[lb:, :] - trend_fast_ma[:-lb, :]
            slope_slow[lb:, :] = trend_slow_ma[lb:, :] - trend_slow_ma[:-lb, :]
            slope_pass = (
                ~np.isnan(slope_fast)
                & ~np.isnan(slope_slow)
                & (slope_fast > 0.0)
                & (slope_slow >= 0.0)
            )
    continuity_pass = np.ones((t, n), dtype=bool)
    if bool(enable_trend_continuity_filter):
        cn = max(1, int(continuity_n))
        continuity_pass[:] = False
        # vectorized via pandas rolling over full matrix (column-wise C-optimized path).
        base_df = pd.DataFrame(base_trend_on.astype(float))
        cont_df = (base_df.rolling(cn, min_periods=cn).sum() == float(cn))
        continuity_pass = cont_df.to_numpy(dtype=bool)
    quality_trend_on = base_trend_on.copy()
    if bool(enable_trend_slope_filter):
        quality_trend_on &= slope_pass
    if bool(enable_trend_continuity_filter):
        quality_trend_on &= continuity_pass
    if enable_trend_filter:
        trend_ok = quality_trend_on if (bool(enable_trend_slope_filter) or bool(enable_trend_continuity_filter)) else legacy_trend_ok

    risk_on_matrix = np.repeat(risk_on.reshape(-1, 1), n, axis=1)
    ma_is_valid = (
        ~np.isnan(fast_ma)
        & ~np.isnan(slow_ma)
        & ~np.isnan(close)
    )
    buy_base = buy_raw_ok_vectorized(
        cross_up=cross_up,
        close=close,
        slow_ma=slow_ma,
        trend_fast=trend_fast_ma,
        trend_slow=trend_slow_ma,
        entry_buffer=float(entry_buffer),
        enable_trend_filter=bool(enable_trend_filter)
        and (
            (not bool(enable_trend_tier))
            or bool(enable_trend_slope_filter)
            or bool(enable_trend_continuity_filter)
        ),
        regime_ok=risk_on_matrix,
        ma_is_valid=ma_is_valid,
        tradable=tradable,
        apply_tradable_in_raw=False,
    )
    # 入场过滤矩阵：close > slow_ma
    entry_above_slow_ma = np.ones((t, n), dtype=bool)
    if bool(enable_entry_above_slow_ma):
        entry_above_slow_ma = (
            ~np.isnan(close)
            & ~np.isnan(slow_ma)
            & (close > slow_ma)
        )

    # 入场过滤矩阵：slow_ma 斜率 > 0
    entry_slow_ma_slope_pos = np.ones((t, n), dtype=bool)
    if bool(enable_entry_slow_ma_slope):
        elb = max(1, int(entry_slope_lookback))
        entry_slow_ma_slope_pos[:] = False
        if t > elb:
            slow_ma_diff = np.full((t, n), np.nan, dtype=float)
            slow_ma_diff[elb:, :] = slow_ma[elb:, :] - slow_ma[:-elb, :]
            entry_slow_ma_slope_pos = (
                ~np.isnan(slow_ma_diff)
                & (slow_ma_diff > 0.0)
            )

    # V2 个股趋势过滤：close > sma60 AND sma20 > sma60
    v2_trend_ok = np.ones((t, n), dtype=bool)
    if sma20 is not None and sma60 is not None:
        v2_trend_ok = (
            ~np.isnan(close)
            & ~np.isnan(sma20)
            & ~np.isnan(sma60)
            & (close > sma60)
            & (sma20 > sma60)
        )

    return {
        "cross_up": cross_up,
        "cross_down": cross_down,
        "trend_ok": trend_ok,
        "base_trend_on": base_trend_on,
        "slope_pass": slope_pass,
        "continuity_pass": continuity_pass,
        "quality_trend_on": quality_trend_on,
        "buffer_ok": buffer_ok,
        "ma_is_valid": ma_is_valid,
        "buy_base": buy_base,
        "risk_on_matrix": risk_on_matrix,
        "entry_above_slow_ma": entry_above_slow_ma,
        "entry_slow_ma_slope_pos": entry_slow_ma_slope_pos,
        "v2_trend_ok": v2_trend_ok,
    }
