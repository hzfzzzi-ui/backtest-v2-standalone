"""三层层级趋势过滤器 (Market → Sector → Stock)。

输出 RegimeSignal ∈ [0, 1]，用于替代二值 regime_on 判断。
全向量化预计算，日循环中 O(1) 查表。
"""
from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.engine_vector.features import adx_matrix, _ewm_mean_matrix


@dataclass(frozen=True)
class RegimeFilterConfig:
    """RegimeFilter 全部可配置参数。"""

    enabled: bool = True

    # ── 因子参数 ──
    ema_slope_span: int = 50
    slope_lookback: int = 10
    ema_short_span: int = 20
    ema_long_span: int = 60
    adx_period: int = 14

    # ── 因子权重 ──
    w_slope: float = 0.4
    w_spread: float = 0.3
    w_adx: float = 0.3

    # ── 标准化与平滑 ──
    zscore_window: int = 120
    ema_smooth_span: int = 10

    # ── Sigmoid 陡度 ──
    alpha_m: float = 2.0
    alpha_sec: float = 2.0
    alpha_i: float = 2.0

    # ── 阈值 ──
    regime_threshold: float = 0.3


def _sigmoid(x: np.ndarray, alpha: float) -> np.ndarray:
    """Sigmoid 门控: 1 / (1 + exp(-alpha * x))，数值稳定版。"""
    ax = alpha * x
    return np.where(
        ax >= 0,
        1.0 / (1.0 + np.exp(-ax)),
        np.exp(ax) / (1.0 + np.exp(ax)),
    )


def _rolling_zscore(arr: np.ndarray, window: int) -> np.ndarray:
    """Rolling z-score 标准化，支持 1D 和 2D。

    输入 arr 可以是 (T,) 或 (T, N)。
    使用 pandas rolling 计算 mean 和 std。
    """
    if arr.ndim == 1:
        s = pd.Series(arr, dtype=float)
        m = s.rolling(window, min_periods=window).mean()
        st = s.rolling(window, min_periods=window).std(ddof=0)
        st = st.replace(0.0, np.nan)
        return ((s - m) / st).to_numpy(dtype=float)

    df = pd.DataFrame(arr, dtype=float)
    m = df.rolling(window, min_periods=window).mean()
    st = df.rolling(window, min_periods=window).std(ddof=0)
    st = st.replace(0.0, np.nan)
    return ((df - m) / st).to_numpy(dtype=float)


def _compute_layer_gate(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    alpha: float,
    cfg: RegimeFilterConfig,
) -> np.ndarray:
    """单层计算管线：原始价格 → sigmoid 门控。

    输入:
        close/high/low: (T,) 或 (T, N) 价格矩阵
        alpha: sigmoid 陡度
        cfg: 参数配置

    输出:
        gate: 与 close 同形状的门控值 ∈ (0, 1)
    """
    squeeze = False
    if close.ndim == 1:
        close = close[:, np.newaxis]
        high = high[:, np.newaxis]
        low = low[:, np.newaxis]
        squeeze = True

    # ── 因子 1: EMA slope ──
    ema50 = _ewm_mean_matrix(close, cfg.ema_slope_span)
    lookback = cfg.slope_lookback
    slope = np.full_like(ema50, np.nan)
    if ema50.shape[0] > lookback:
        prev = ema50[:-lookback, :]
        # 避免除零
        with np.errstate(divide="ignore", invalid="ignore"):
            slope[lookback:, :] = (ema50[lookback:, :] - prev) / np.where(prev == 0, np.nan, prev)

    # ── 因子 2: EMA spread ──
    ema_short = _ewm_mean_matrix(close, cfg.ema_short_span)
    ema_long = _ewm_mean_matrix(close, cfg.ema_long_span)
    with np.errstate(divide="ignore", invalid="ignore"):
        spread = np.abs(ema_short - ema_long) / np.where(ema_long == 0, np.nan, ema_long)

    # ── 因子 3: ADX ──
    adx = adx_matrix(high, low, close, cfg.adx_period)
    adx_norm = adx / 100.0

    # ── 组合趋势得分 ──
    trend_score = (
        cfg.w_slope * np.nan_to_num(slope, nan=0.0)
        + cfg.w_spread * np.nan_to_num(spread, nan=0.0)
        + cfg.w_adx * np.nan_to_num(adx_norm, nan=0.0)
    )
    # 如果三个因子全是 NaN，trend_score 设为 NaN（冷启动期）
    all_nan = np.isnan(slope) & np.isnan(spread) & np.isnan(adx_norm)
    trend_score[all_nan] = np.nan

    # ── Rolling z-score ──
    z = _rolling_zscore(trend_score, cfg.zscore_window)

    # ── EMA 平滑 ──
    z_smooth = _ewm_mean_matrix(z, cfg.ema_smooth_span)

    # ── Sigmoid 门控 ──
    # NaN → 0 → sigmoid(0) = 0.5（中性）
    z_filled = np.nan_to_num(z_smooth, nan=0.0)
    gate = _sigmoid(z_filled, alpha)

    if squeeze:
        return gate[:, 0]
    return gate


class RegimeFilter:
    """三层层级趋势过滤器。"""

    def __init__(self, cfg: RegimeFilterConfig | None = None) -> None:
        self._cfg = cfg or RegimeFilterConfig()
        self.regime_signals: np.ndarray = np.array([])
        self._gate_m: np.ndarray = np.array([])
        self._gate_sec: np.ndarray = np.array([])
        self._gate_stock: np.ndarray = np.array([])
        self._precompute_seconds: float = 0.0
        self._gate_sec_coverage: float = 0.0

    def precompute(
        self,
        *,
        benchmark_close: np.ndarray,
        benchmark_high: np.ndarray,
        benchmark_low: np.ndarray,
        stock_close: np.ndarray,
        stock_high: np.ndarray,
        stock_low: np.ndarray,
        sector_data: dict[str, pd.DataFrame],
        industry_map: dict[str, str],
        sym_to_col: dict[str, int],
        trading_days: list[date],
    ) -> None:
        """预计算三层门控矩阵。

        Args:
            benchmark_close/high/low: 基准指数 (T,) 序列
            stock_close/high/low: 个股 (T, N) 矩阵
            sector_data: {index_code: DataFrame(trade_date, open, high, low, close)}
            industry_map: {symbol: industry_l1}
            sym_to_col: {symbol: col_idx}
            trading_days: 交易日列表
        """
        t0 = _time.perf_counter()
        cfg = self._cfg
        t, n = stock_close.shape

        # ── Layer 1: Market ──
        self._gate_m = _compute_layer_gate(
            benchmark_close, benchmark_high, benchmark_low,
            cfg.alpha_m, cfg,
        )

        # ── Layer 2: Sector ──
        # 构建行业指数矩阵
        from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP

        # 行业名 → 指数代码 → sector_data 中的 DataFrame
        sector_codes = sorted(set(SW_L1_INDEX_MAP.values()))
        sec_code_to_idx = {code: i for i, code in enumerate(sector_codes)}
        s_count = len(sector_codes)

        # 构建 trading_day → row_idx 映射
        day_to_idx = {d: i for i, d in enumerate(trading_days)}

        # 构建行业 close/high/low 矩阵 (T, S)
        sec_close = np.full((t, s_count), np.nan, dtype=float)
        sec_high = np.full((t, s_count), np.nan, dtype=float)
        sec_low = np.full((t, s_count), np.nan, dtype=float)

        for code in sector_codes:
            if code not in sector_data:
                continue
            si = sec_code_to_idx[code]
            df = sector_data[code]
            for _, row in df.iterrows():
                td = row["trade_date"]
                if isinstance(td, str):
                    td = pd.Timestamp(td).date()
                elif hasattr(td, "date"):
                    td = td.date() if not isinstance(td, date) else td
                ri = day_to_idx.get(td)
                if ri is not None:
                    sec_close[ri, si] = float(row["close"])
                    sec_high[ri, si] = float(row["high"])
                    sec_low[ri, si] = float(row["low"])

        # 计算行业层门控 (T, S)
        gate_sec_raw = _compute_layer_gate(sec_close, sec_high, sec_low, cfg.alpha_sec, cfg)

        # 展开到 (T, N)：每只股票映射到其所属行业
        self._gate_sec = np.ones((t, n), dtype=float)
        covered = 0
        for sym, col in sym_to_col.items():
            l1 = industry_map.get(sym)
            if l1 is None:
                continue
            idx_code = SW_L1_INDEX_MAP.get(l1)
            if idx_code is None:
                continue
            si = sec_code_to_idx.get(idx_code)
            if si is None:
                continue
            col_gate = gate_sec_raw[:, si]
            # 有数据的位置用计算值，NaN 位置保持 1.0（降级）
            valid = ~np.isnan(sec_close[:, si])
            self._gate_sec[valid, col] = col_gate[valid]
            covered += 1

        self._gate_sec_coverage = covered / max(n, 1)

        # ── Layer 3: Stock ──
        self._gate_stock = _compute_layer_gate(
            stock_close, stock_high, stock_low,
            cfg.alpha_i, cfg,
        )

        # ── 三层乘法复合 ──
        gate_m_2d = self._gate_m[:, np.newaxis] if self._gate_m.ndim == 1 else self._gate_m
        self.regime_signals = gate_m_2d * self._gate_sec * self._gate_stock

        self._precompute_seconds = _time.perf_counter() - t0

    @property
    def diagnostics(self) -> dict[str, Any]:
        """诊断数据。"""
        rs = self.regime_signals
        valid = rs[~np.isnan(rs)] if rs.size > 0 else np.array([])
        threshold = self._cfg.regime_threshold

        return {
            "gate_m_mean": float(np.nanmean(self._gate_m)) if self._gate_m.size > 0 else 0.0,
            "gate_sec_coverage": self._gate_sec_coverage,
            "regime_signal_mean": float(np.mean(valid)) if valid.size > 0 else 0.0,
            "regime_signal_above_threshold_pct": (
                float(np.sum(valid >= threshold) / len(valid)) if valid.size > 0 else 0.0
            ),
            "precompute_seconds": self._precompute_seconds,
        }
