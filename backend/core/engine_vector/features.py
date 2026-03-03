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
    rsi: np.ndarray


def _ewm_mean_matrix(values: np.ndarray, span: int) -> np.ndarray:
    """EWM（指数加权）均值矩阵 — DataFrame 级别并行计算。"""
    return pd.DataFrame(values).ewm(span=int(span), min_periods=int(span)).mean().to_numpy(dtype=float)


def _rsi_matrix(close: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothed RSI 矩阵，列式计算。"""
    p = int(period)
    t, n = close.shape
    out = np.full((t, n), np.nan, dtype=float)
    for c in range(n):
        s = pd.Series(close[:, c], dtype=float)
        valid = s.notna()
        if int(valid.sum()) <= p:
            continue
        sv = s[valid].reset_index(drop=True)
        delta = sv.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)
        avg_gain = gain.ewm(alpha=1.0 / p, min_periods=p, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / p, min_periods=p, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - 100.0 / (1.0 + rs)
        idx = np.where(valid.to_numpy())[0]
        out[idx, c] = rsi.to_numpy(dtype=float)
    return out


def adx_matrix(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """向量化 ADX(period) 矩阵 — Wilder 平滑，逐列计算。

    支持 2D (T, N) 和 1D (T,) 输入。
    """
    p = int(period)
    squeeze = False
    if high.ndim == 1:
        high = high[:, np.newaxis]
        low = low[:, np.newaxis]
        close = close[:, np.newaxis]
        squeeze = True

    t, n = close.shape
    out = np.full((t, n), np.nan, dtype=float)

    for c in range(n):
        h = pd.Series(high[:, c], dtype=float)
        l = pd.Series(low[:, c], dtype=float)
        cl = pd.Series(close[:, c], dtype=float)

        valid = h.notna() & l.notna() & cl.notna()
        if int(valid.sum()) < 2 * p + 1:
            continue

        # 提取有效子序列
        h_v = h[valid].reset_index(drop=True)
        l_v = l[valid].reset_index(drop=True)
        cl_v = cl[valid].reset_index(drop=True)
        vlen = len(h_v)

        prev_c = cl_v.shift(1)
        prev_h = h_v.shift(1)
        prev_l = l_v.shift(1)

        # True Range
        tr = pd.concat([
            h_v - l_v,
            (h_v - prev_c).abs(),
            (l_v - prev_c).abs(),
        ], axis=1).max(axis=1)

        # +DM / -DM
        up_move = h_v - prev_h
        down_move = prev_l - l_v
        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), dtype=float)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), dtype=float)

        # Wilder 平滑（递推式）
        smooth_tr = np.full(vlen, np.nan, dtype=float)
        smooth_pdm = np.full(vlen, np.nan, dtype=float)
        smooth_mdm = np.full(vlen, np.nan, dtype=float)

        # 初始值 = 前 period 天的 sum（跳过第 0 行的 NaN）
        if vlen < p + 1:
            continue
        smooth_tr[p] = tr.iloc[1:p + 1].sum()
        smooth_pdm[p] = plus_dm.iloc[1:p + 1].sum()
        smooth_mdm[p] = minus_dm.iloc[1:p + 1].sum()

        for j in range(p + 1, vlen):
            smooth_tr[j] = smooth_tr[j - 1] - smooth_tr[j - 1] / p + tr.iloc[j]
            smooth_pdm[j] = smooth_pdm[j - 1] - smooth_pdm[j - 1] / p + plus_dm.iloc[j]
            smooth_mdm[j] = smooth_mdm[j - 1] - smooth_mdm[j - 1] / p + minus_dm.iloc[j]

        with np.errstate(divide="ignore", invalid="ignore"):
            plus_di = 100.0 * smooth_pdm / smooth_tr
            minus_di = 100.0 * smooth_mdm / smooth_tr
            dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)

        # ADX: Wilder 平滑 DX
        adx_arr = np.full(vlen, np.nan, dtype=float)
        # 初始 ADX = DX[p:2p] 的均值
        if vlen < 2 * p:
            continue
        first_adx_vals = dx[p:2 * p]
        valid_dx = first_adx_vals[~np.isnan(first_adx_vals)]
        if len(valid_dx) == 0:
            continue
        adx_arr[2 * p - 1] = np.mean(valid_dx)
        for j in range(2 * p, vlen):
            if np.isnan(dx[j]):
                adx_arr[j] = adx_arr[j - 1]
            else:
                adx_arr[j] = (adx_arr[j - 1] * (p - 1) + dx[j]) / p

        # 写回到原始索引
        idx = np.where(valid.to_numpy())[0]
        out[idx, c] = adx_arr

    if squeeze:
        return out[:, 0]
    return out


def _rolling_mean_matrix(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling mean 矩阵 — DataFrame 级别并行计算。"""
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).mean().to_numpy(dtype=float)


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
    ma_type: str = "SMA",
    rsi_period: int = 6,
) -> FeatureMatrices:
    # 信号用均线：根据 ma_type 选择 SMA 或 EMA
    _ma_fn = _ewm_mean_matrix if str(ma_type).upper() == "EMA" else _rolling_mean_matrix
    fast_ma = _ma_fn(close, int(fast))
    slow_ma = _ma_fn(close, int(slow))
    trend_fast_ma = _rolling_mean_matrix(close, int(trend_fast))
    trend_slow_ma = _rolling_mean_matrix(close, int(trend_slow))
    strength_ma_m = _rolling_mean_matrix(close, int(strength_ma))
    t, n = close.shape
    w_atr = int(atr_n)
    # True Range 向量化：numpy 广播一次完成全矩阵
    prev_close = np.empty_like(close)
    prev_close[0, :] = np.nan
    prev_close[1:, :] = close[:-1, :]
    tr_m = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
    )
    # Rolling mean — DataFrame 级别并行
    atr = pd.DataFrame(tr_m).rolling(w_atr, min_periods=w_atr).mean().to_numpy(dtype=float)
    rsi = _rsi_matrix(close, int(rsi_period)) if int(rsi_period) > 0 else np.full((t, n), np.nan, dtype=float)
    return FeatureMatrices(
        fast_ma=fast_ma,
        slow_ma=slow_ma,
        trend_fast_ma=trend_fast_ma,
        trend_slow_ma=trend_slow_ma,
        atr14=atr,
        strength_ma=strength_ma_m,
        rsi=rsi,
    )
