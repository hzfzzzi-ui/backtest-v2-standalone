"""横截面 breadth/dispersion score 计算 + 动态 max_positions 映射。

向量化实现：T 维度循环可接受，N 维度（~700 股）全部向量化。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class BreadthScoreResult:
    scores_A: np.ndarray   # (T,) breadth_up SMA5
    scores_B: np.ndarray   # (T,) breadth_momo SMA5
    scores_C: np.ndarray   # (T,) dispersion zscore -> [0,1]
    scores_combo: np.ndarray  # (T,) 0.5*B + 0.5*C


def _sma_1d(arr: np.ndarray, window: int) -> np.ndarray:
    """1D rolling mean with min_periods=window, NaN elsewhere."""
    return pd.Series(arr, dtype=float).rolling(window, min_periods=window).mean().to_numpy(dtype=float)


def _ewm_mean_matrix(values: np.ndarray, span: int) -> np.ndarray:
    """EWM mean on (T, N) matrix using pandas for vectorized column-wise computation."""
    return pd.DataFrame(values).ewm(span=int(span), min_periods=int(span)).mean().to_numpy(dtype=float)


def compute_breadth_scores(
    close: np.ndarray,
    tradable: np.ndarray,
    ema_fast_period: int = 8,
    ema_slow_period: int = 25,
) -> BreadthScoreResult:
    """计算三类横截面 breadth score。

    Parameters
    ----------
    close : (T, N) hfq 收盘价矩阵
    tradable : (T, N) bool 可交易掩码
    ema_fast_period : EMA 快线周期（用于 breadth_momo）
    ema_slow_period : EMA 慢线周期（用于 breadth_momo）

    Returns
    -------
    BreadthScoreResult with scores_A/B/C/combo, each (T,)
    """
    t, n = close.shape

    # ── 日收益矩阵 r_1d (T, N) ──
    r_1d = np.full((t, n), np.nan, dtype=float)
    prev = close[:-1, :]
    curr = close[1:, :]
    safe_prev = np.where(np.abs(prev) > 1e-8, prev, np.nan)
    r_1d[1:, :] = curr / safe_prev - 1.0

    # ── 指标 A: breadth_up ──
    # 每日上涨股票占可交易股票比例
    up_mask = r_1d > 0  # (T, N) bool
    # 将不可交易 / NaN 收益设为 NaN 以排除
    up_valid = np.where(tradable & ~np.isnan(r_1d), up_mask.astype(float), np.nan)
    raw_breadth_up = np.nanmean(up_valid, axis=1)  # (T,)
    scores_A = _sma_1d(raw_breadth_up, 5)

    # ── 指标 B: breadth_momo ──
    # EMA fast/slow on close matrix, then fraction with fast > slow
    ema_fast = _ewm_mean_matrix(close, ema_fast_period)  # (T, N)
    ema_slow = _ewm_mean_matrix(close, ema_slow_period)  # (T, N)
    momo_mask = ema_fast > ema_slow  # (T, N) bool
    momo_valid = np.where(tradable & ~np.isnan(ema_fast) & ~np.isnan(ema_slow), momo_mask.astype(float), np.nan)
    raw_breadth_momo = np.nanmean(momo_valid, axis=1)  # (T,)
    scores_B = _sma_1d(raw_breadth_momo, 5)

    # ── 指标 C: dispersion ──
    # 横截面收益标准差 -> 20日 rolling zscore -> 映射到 [0, 1]
    # 将不可交易的收益设为 NaN
    r_masked = np.where(tradable & ~np.isnan(r_1d), r_1d, np.nan)
    raw_disp = np.nanstd(r_masked, axis=1)  # (T,)

    # 20日 rolling zscore
    disp_s = pd.Series(raw_disp, dtype=float)
    disp_mean_20 = disp_s.rolling(20, min_periods=20).mean()
    disp_std_20 = disp_s.rolling(20, min_periods=20).std()
    z = ((disp_s - disp_mean_20) / disp_std_20.replace(0.0, np.nan)).to_numpy(dtype=float)

    # 映射: z=-3 -> 1.0 (低离散=强势), z=+3 -> 0.0 (高离散=弱势)
    scores_C = np.clip(1.0 - (z + 1.0) / 4.0, 0.0, 1.0)

    # ── Combo: 0.5*B + 0.5*C ──
    scores_combo = 0.5 * np.where(np.isnan(scores_B), 0.0, scores_B) + \
                   0.5 * np.where(np.isnan(scores_C), 0.0, scores_C)
    # 如果 B 和 C 都是 NaN，combo 也应为 NaN
    both_nan = np.isnan(scores_B) & np.isnan(scores_C)
    scores_combo[both_nan] = np.nan

    return BreadthScoreResult(
        scores_A=scores_A,
        scores_B=scores_B,
        scores_C=scores_C,
        scores_combo=scores_combo,
    )


def compute_dynamic_maxpos(
    scores: np.ndarray,
    mapping_mode: str = "smooth",
    min_pos: int = 3,
    max_pos: int = 15,
    step_high: float = 0.60,
    step_mid: float = 0.45,
    smooth_lo: float = 0.40,
    smooth_range: float = 0.20,
) -> np.ndarray:
    """将 breadth score (T,) 映射为每日 max_positions (T,) int 数组。

    Parameters
    ----------
    scores : (T,) breadth score, 值域 [0, 1]
    mapping_mode : "step" 阶梯映射 / "smooth" 平滑映射
    min_pos, max_pos : 仓位上下限
    step_high, step_mid : 阶梯阈值
    smooth_lo, smooth_range : 平滑映射参数

    Returns
    -------
    (T,) int array, NaN score 的日期使用 max_pos（保守回退）
    """
    t = len(scores)
    result = np.full(t, max_pos, dtype=int)

    valid = ~np.isnan(scores)

    if mapping_mode == "step":
        result[valid & (scores >= step_high)] = max_pos
        result[valid & (scores >= step_mid) & (scores < step_high)] = (min_pos + max_pos) // 2
        result[valid & (scores < step_mid)] = min_pos
    else:
        # smooth: linear interpolation
        scale = np.clip((scores[valid] - smooth_lo) / smooth_range, 0.0, 1.0)
        result[valid] = np.round(min_pos + scale * (max_pos - min_pos)).astype(int)

    return result
