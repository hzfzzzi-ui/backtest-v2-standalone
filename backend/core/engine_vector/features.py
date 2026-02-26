from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class FeatureMatrices:
    fast_ma: np.ndarray
    slow_ma: np.ndarray
    trend_fast_ma: np.ndarray
    trend_slow_ma: np.ndarray
    atr14: np.ndarray
    strength_ma: np.ndarray


def _rolling_mean_matrix(values: np.ndarray, window: int) -> np.ndarray:
    w = int(window)
    t, n = values.shape
    out = np.full((t, n), np.nan, dtype=float)
    for c in range(n):
        s = pd.Series(values[:, c], dtype=float)
        valid = s.notna()
        if int(valid.sum()) <= 0:
            continue
        sv = s[valid]
        rm = sv.rolling(w, min_periods=w).mean()
        out[valid.to_numpy(), c] = rm.to_numpy(dtype=float)
    return out


def compute_feature_matrices(
    *,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    fast: int = 5,
    slow: int = 20,
    trend_fast: int = 120,
    trend_slow: int = 200,
    atr_n: int = 14,
    strength_ma: int = 120,
) -> FeatureMatrices:
    fast_ma = _rolling_mean_matrix(close, int(fast))
    slow_ma = _rolling_mean_matrix(close, int(slow))
    trend_fast_ma = _rolling_mean_matrix(close, int(trend_fast))
    trend_slow_ma = _rolling_mean_matrix(close, int(trend_slow))
    strength_ma_m = _rolling_mean_matrix(close, int(strength_ma))
    t, n = close.shape
    atr = np.full((t, n), np.nan, dtype=float)
    w_atr = int(atr_n)
    for c in range(n):
        h = pd.Series(high[:, c], dtype=float)
        l = pd.Series(low[:, c], dtype=float)
        cl = pd.Series(close[:, c], dtype=float)
        valid = h.notna() & l.notna() & cl.notna()
        if int(valid.sum()) <= 1:
            continue
        idx = np.where(valid.to_numpy())[0]
        h2 = h.iloc[idx].reset_index(drop=True)
        l2 = l.iloc[idx].reset_index(drop=True)
        c2 = cl.iloc[idx].reset_index(drop=True)
        prev_c = c2.shift(1)
        tr = pd.concat(
            [
                (h2 - l2),
                (h2 - prev_c).abs(),
                (l2 - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr2 = tr.rolling(w_atr, min_periods=w_atr).mean()
        atr[idx, c] = atr2.to_numpy(dtype=float)
    return FeatureMatrices(
        fast_ma=fast_ma,
        slow_ma=slow_ma,
        trend_fast_ma=trend_fast_ma,
        trend_slow_ma=trend_slow_ma,
        atr14=atr,
        strength_ma=strength_ma_m,
    )
