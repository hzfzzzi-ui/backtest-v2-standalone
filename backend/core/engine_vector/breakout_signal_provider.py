"""Breakout Trend 信号提供者。

V2 Stage 6: close > max(high[-20:]) 突破入场信号。
使用 SignalProvider 协议，可被引擎统一循环调用。
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.candidate_index import build_daily_candidate_index
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
    evaluate_engine_exits,
)


def _rolling_max_matrix(values: np.ndarray, window: int) -> np.ndarray:
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).max().to_numpy(dtype=float)


def _rolling_min_matrix(values: np.ndarray, window: int) -> np.ndarray:
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).min().to_numpy(dtype=float)


def _rolling_any(mask: np.ndarray, window: int) -> np.ndarray:
    rolled = pd.DataFrame(mask.astype(float)).rolling(int(window), min_periods=1).max().to_numpy(dtype=float)
    return rolled > 0


def _return_matrix(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    w = int(window)
    if w <= 0 or values.shape[0] <= w:
        return out
    prev = values[:-w, :]
    curr = values[w:, :]
    safe_prev = np.where(prev > 1e-8, prev, np.nan)
    out[w:, :] = curr / safe_prev - 1.0
    return out


def _return_series(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    w = int(window)
    if w <= 0 or values.shape[0] <= w:
        return out
    prev = values[:-w]
    curr = values[w:]
    safe_prev = np.where(prev > 1e-8, prev, np.nan)
    out[w:] = curr / safe_prev - 1.0
    return out


def _row_rank_pct(values: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    row_count = int(values.shape[0])
    for i in range(row_count):
        row = values[i, :]
        row_valid = valid_mask[i, :] & ~np.isnan(row)
        idx = np.flatnonzero(row_valid)
        count = int(idx.size)
        if count == 0:
            continue
        if count == 1:
            out[i, idx[0]] = 0.5
            continue
        order = np.argsort(row[idx], kind="mergesort")
        ranks = np.empty(count, dtype=float)
        denom = float(max(count - 1, 1))
        ranks[order] = np.arange(count, dtype=float) / denom
        out[i, idx] = ranks
    return out


def _weighted_score(
    components: list[tuple[np.ndarray, float]],
    shape: tuple[int, int],
) -> np.ndarray:
    score = np.zeros(shape, dtype=float)
    weight_sum = np.zeros(shape, dtype=float)
    for matrix, weight in components:
        if float(weight) <= 0:
            continue
        valid = ~np.isnan(matrix)
        score[valid] += matrix[valid] * float(weight)
        weight_sum[valid] += float(weight)
    out = np.full(shape, np.nan, dtype=float)
    ok = weight_sum > 1e-12
    out[ok] = score[ok] / weight_sum[ok]
    return out


def _build_sector_feature_matrices(
    *,
    sector_data: dict[str, pd.DataFrame] | None,
    industry_map: dict[str, str] | None,
    symbols: list[str],
    dates: np.ndarray,
    short_window: int,
    long_window: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sector_ret_short = np.full((len(dates), len(symbols)), np.nan, dtype=float)
    sector_ret_long = np.full((len(dates), len(symbols)), np.nan, dtype=float)
    sector_trend = np.full((len(dates), len(symbols)), np.nan, dtype=float)
    if not sector_data or not industry_map or not symbols:
        return sector_ret_short, sector_ret_long, sector_trend

    from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP

    name_to_code = dict(SW_L1_INDEX_MAP)
    available_codes = sorted(set(name_to_code.values()) & set(str(k) for k in sector_data.keys()))
    if not available_codes:
        return sector_ret_short, sector_ret_long, sector_trend

    date_to_idx = {pd.Timestamp(d).normalize(): i for i, d in enumerate(dates)}
    code_to_col = {code: idx for idx, code in enumerate(available_codes)}
    sector_close = np.full((len(dates), len(available_codes)), np.nan, dtype=float)

    for code in available_codes:
        df = sector_data.get(code)
        if df is None or df.empty:
            continue
        date_col = "trade_date" if "trade_date" in df.columns else "date"
        if date_col not in df.columns or "close" not in df.columns:
            continue
        col_idx = code_to_col[code]
        for row in df.itertuples(index=False):
            ts = pd.Timestamp(getattr(row, date_col)).normalize()
            row_idx = date_to_idx.get(ts)
            if row_idx is None:
                continue
            try:
                sector_close[row_idx, col_idx] = float(getattr(row, "close"))
            except Exception:
                continue

    sector_ret_short_raw = _return_matrix(sector_close, int(short_window))
    sector_ret_long_raw = _return_matrix(sector_close, int(long_window))
    sector_ma20 = pd.DataFrame(sector_close).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
    sector_ma60 = pd.DataFrame(sector_close).rolling(60, min_periods=60).mean().to_numpy(dtype=float)
    sector_trend_raw = np.where(
        (~np.isnan(sector_close)) & (~np.isnan(sector_ma20)) & (~np.isnan(sector_ma60)),
        ((sector_close > sector_ma20).astype(float) + (sector_ma20 > sector_ma60).astype(float)) / 2.0,
        np.nan,
    )

    sym_to_sector_col: dict[str, int] = {}
    for sym in symbols:
        sector_name = industry_map.get(str(sym).lower())
        code = name_to_code.get(str(sector_name)) if sector_name is not None else None
        if code is None:
            continue
        col_idx = code_to_col.get(code)
        if col_idx is not None:
            sym_to_sector_col[str(sym)] = col_idx

    for sym_idx, sym in enumerate(symbols):
        sector_col = sym_to_sector_col.get(str(sym))
        if sector_col is None:
            continue
        sector_ret_short[:, sym_idx] = sector_ret_short_raw[:, sector_col]
        sector_ret_long[:, sym_idx] = sector_ret_long_raw[:, sector_col]
        sector_trend[:, sym_idx] = sector_trend_raw[:, sector_col]
    return sector_ret_short, sector_ret_long, sector_trend


class BreakoutTrendProvider:
    """20-Day High Breakout 信号提供者。

    买入信号: close[t] > high_max20[t-1]  (昨日 20 日最高价突破)
    卖出信号: 由 evaluate_engine_exits 统一评估
    """

    def __init__(self) -> None:
        # fill hooks（统一循环传给 _process_pending_fills）
        self.extra_clear_dicts: list[dict] = []
        self.last_sell_day: dict[str, date] | None = None
        self.entry_day: dict[str, date] = {}
        self.entry_day_overwrite: bool = True
        self.peak_state_on_buy: dict[str, float] | None = None

        # 内部状态（precompute 后填充）
        self._mx: Any = None
        self._feats: Any = None
        self._breakout_up: np.ndarray = np.array([])
        self._breakout_up_short: np.ndarray = np.array([])
        self._breakout_up_long: np.ndarray = np.array([])
        self._high_max_short: np.ndarray = np.array([])
        self._high_max_long: np.ndarray = np.array([])
        self._high_max_main: np.ndarray = np.array([])
        self._v2_trend_ok: np.ndarray = np.array([])
        self._entry_confirm_ok: np.ndarray = np.array([])
        self._entry_delay_ok: np.ndarray = np.array([])
        self._cand_idx: Any = None
        self._bench_close: np.ndarray = np.array([])
        self._risk_on: np.ndarray = np.array([])
        self._breakout_buy: np.ndarray = np.array([])
        self._pullback_pb1: np.ndarray = np.array([])
        self._pullback_pb2: np.ndarray = np.array([])
        self._pullback_pb3: np.ndarray = np.array([])
        self._pullback_tight1: np.ndarray = np.array([])
        self._pullback_tight2: np.ndarray = np.array([])
        self._pullback_raw_selected: np.ndarray = np.array([])
        self._pullback_overlap: np.ndarray = np.array([])
        self._pullback_buy: np.ndarray = np.array([])
        self._residual_strength_raw: np.ndarray = np.array([])
        self._residual_strength_score: np.ndarray = np.array([])
        self._sector_strength_score: np.ndarray = np.array([])
        self._volume_price_quality_score: np.ndarray = np.array([])
        self._final_score: np.ndarray = np.array([])
        self._sym_to_col: dict[str, int] = {}
        self._ec: ExitConfig = ExitConfig()
        self._peak_close_state: dict[str, float] = {}

        # strategy 参数
        self._breakout_window: int = 20
        self._enable_dual_breakout: bool = False
        self._breakout_window_short: int = 20
        self._breakout_window_long: int = 55
        self._breakout_entry_buffer_pct: float = 0.0
        self._entry_confirm_mode: str = "none"
        self._entry_delay_mode: str = "none"
        self._enable_atr_stop: bool = False
        self._enable_atr_trail: bool = False
        self._atr_stop_k: float = 2.0
        self._atr_trail_k: float = 3.0
        self._order_size: int = 1000
        self._max_hold_days: int = 0
        self._min_hold_days: int = 0
        self._cooldown_days: int = 0
        self._enable_risk_off_exit: bool = False
        self._min_hold_exempt_set: set[str] = set()
        self._base_order_value: float = 0.0
        self._enable_pullback_candidates: bool = False
        self._pullback_variant_mode: str = "pb_reclaim_ma20"
        self._pullback_touch_lookback: int = 12
        self._pullback_reclaim_window: int = 3
        self._pullback_ma20_touch_band_pct: float = 0.01
        self._pullback_low_lookback: int = 10
        self._pullback_low_band_pct: float = 0.02
        self._pullback_box_window: int = 5
        self._pullback_box_range_pct_max: float = 0.08
        self._enable_residual_ranking: bool = False
        self._residual_window: int = 60
        self._source_aware_residual_mode: str = "off"
        self._enable_sector_quality_ranking: bool = False
        self._sector_strength_window_short: int = 20
        self._sector_strength_window_long: int = 60
        self._volume_quality_window: int = 20
        self._residual_weight: float = 0.5
        self._sector_weight: float = 0.3
        self._quality_weight: float = 0.2

        # 累计计数器
        self.total_buy_signals: int = 0
        self.min_hold_block_count: int = 0
        self.cooldown_block_count: int = 0
        self.precompute_seconds: float = 0.0
        self.diag_reason_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # precompute
    # ------------------------------------------------------------------

    def precompute(
        self,
        *,
        history: pd.DataFrame,
        benchmark: pd.DataFrame,
        raw_history: pd.DataFrame | None,
        trading_days: list[date],
        strategy: Any,
        **kwargs: Any,
    ) -> None:
        import time as _time

        exit_cfg = kwargs.get("exit_cfg") or ExitConfig()
        st_history = kwargs.get("st_history")
        strength_ma = int(kwargs.get("strength_ma", 120))
        self._base_order_value = float(kwargs.get("base_order_value", 0.0))

        self._ec = exit_cfg
        pre_t0 = _time.perf_counter()

        # -- strategy 参数提取 --
        self._breakout_window = int(getattr(strategy, "breakout_window", 20))
        self._enable_dual_breakout = bool(getattr(strategy, "enable_dual_breakout", False))
        self._breakout_window_short = int(getattr(strategy, "breakout_window_short", 20))
        self._breakout_window_long = int(getattr(strategy, "breakout_window_long", max(self._breakout_window, 55)))
        self._breakout_entry_buffer_pct = float(getattr(strategy, "breakout_entry_buffer_pct", 0.0))
        self._entry_confirm_mode = str(getattr(strategy, "entry_confirm_mode", "none") or "none").strip().lower()
        self._entry_delay_mode = str(getattr(strategy, "entry_delay_mode", "none") or "none").strip().lower()
        self._enable_atr_stop = bool(getattr(strategy, "enable_atr_stop", False))
        self._enable_atr_trail = bool(getattr(strategy, "enable_atr_trail", False))
        self._atr_stop_k = float(kwargs.get("atr_stop_k", getattr(strategy, "atr_stop_k", 2.0)))
        self._atr_trail_k = float(getattr(strategy, "atr_trail_k", 3.0))
        self._order_size = int(getattr(strategy, "order_size", 1000))
        regime_ma = int(getattr(strategy, "regime_ma", 60))
        self._max_hold_days = int(getattr(strategy, "max_hold_days", 0))
        self._min_hold_days = int(getattr(strategy, "min_hold_days", 0))
        self._cooldown_days = int(getattr(strategy, "cooldown_days", 0))
        self._min_hold_exempt_set = set(getattr(strategy, "min_hold_exempt_reasons", []) or [])
        self._enable_risk_off_exit = bool(getattr(strategy, "enable_risk_off_exit", False))
        self._enable_pullback_candidates = bool(getattr(strategy, "enable_pullback_candidates", False))
        self._pullback_variant_mode = str(getattr(strategy, "pullback_variant_mode", "pb_reclaim_ma20") or "pb_reclaim_ma20").strip().lower()
        self._pullback_touch_lookback = int(getattr(strategy, "pullback_touch_lookback", 12))
        self._pullback_reclaim_window = int(getattr(strategy, "pullback_reclaim_window", 3))
        self._pullback_ma20_touch_band_pct = float(getattr(strategy, "pullback_ma20_touch_band_pct", 0.01))
        self._pullback_low_lookback = int(getattr(strategy, "pullback_low_lookback", 10))
        self._pullback_low_band_pct = float(getattr(strategy, "pullback_low_band_pct", 0.02))
        self._pullback_box_window = int(getattr(strategy, "pullback_box_window", 5))
        self._pullback_box_range_pct_max = float(getattr(strategy, "pullback_box_range_pct_max", 0.08))
        self._enable_residual_ranking = bool(getattr(strategy, "enable_residual_ranking", False))
        self._residual_window = int(getattr(strategy, "residual_window", 60))
        self._source_aware_residual_mode = str(getattr(strategy, "source_aware_residual_mode", "off") or "off").strip().lower()
        self._enable_sector_quality_ranking = bool(getattr(strategy, "enable_sector_quality_ranking", False))
        self._sector_strength_window_short = int(getattr(strategy, "sector_strength_window_short", 20))
        self._sector_strength_window_long = int(getattr(strategy, "sector_strength_window_long", 60))
        self._volume_quality_window = int(getattr(strategy, "volume_quality_window", 20))
        self._residual_weight = float(getattr(strategy, "residual_weight", 0.5))
        self._sector_weight = float(getattr(strategy, "sector_weight", 0.3))
        self._quality_weight = float(getattr(strategy, "quality_weight", 0.2))

        enable_v2_trend_filter = bool(getattr(strategy, "enable_v2_trend_filter", True))
        v2_trend_short_ma = int(getattr(strategy, "v2_trend_short_ma", 20))
        v2_trend_long_ma = int(getattr(strategy, "v2_trend_long_ma", 60))
        sector_data = kwargs.get("sector_data")
        industry_map = kwargs.get("industry_map")

        # -- OHLC + feature 矩阵 --
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

        _uf = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
        _min_price = float(_uf.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0)
        _min_list_days = int(_uf.get("min_list_days", 0) or 0)
        _min_avg_turnover_20d = float(_uf.get("min_avg_turnover_20d", 0.0) or 0.0)
        self._mx = build_ohlc_matrices_from_history(
            hist,
            trading_days,
            st_history=st_history,
            min_price=_min_price,
            min_list_days=_min_list_days,
            min_avg_turnover_20d=_min_avg_turnover_20d,
        )
        mx = self._mx
        t, n = mx.close.shape
        if n == 0:
            raise ValueError("history has no symbols")

        self._feats = compute_feature_matrices(
            close=mx.close, high=mx.high, low=mx.low,
            fast=5, slow=20,
            trend_fast=120, trend_slow=200,
            atr_n=14, strength_ma=strength_ma,
            v2_trend_short_ma=v2_trend_short_ma,
            v2_trend_long_ma=v2_trend_long_ma,
            breakout_window=max(self._breakout_window, self._breakout_window_short, self._breakout_window_long),
        )
        feats = self._feats

        # -- benchmark 数组 --
        bench = benchmark.copy()
        bench["date"] = pd.to_datetime(bench["date"])
        bench = bench.sort_values("date")
        bench_close_s = pd.to_numeric(bench["close"], errors="coerce")
        bench_ma_s = bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()
        bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
        bmap_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma_s)}
        self._bench_close = np.array([bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_ma = np.array([bmap_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._risk_on = np.ones(t, dtype=bool)
        valid_bench = ~np.isnan(self._bench_close) & ~np.isnan(bench_ma)
        self._risk_on[valid_bench] = self._bench_close[valid_bench] > bench_ma[valid_bench]

        # -- breakout signal matrix: close[t] > high_max(window)[t-1] * (1+buffer) --
        def _rolling_high_max(arr: np.ndarray, window: int) -> np.ndarray:
            w = max(2, int(window))
            return pd.DataFrame(arr).rolling(w, min_periods=w).max().to_numpy(dtype=float)

        self._high_max_short = _rolling_high_max(mx.high, self._breakout_window_short)
        self._high_max_long = _rolling_high_max(mx.high, self._breakout_window_long)
        self._high_max_main = _rolling_high_max(mx.high, self._breakout_window)
        self._breakout_up_short = np.zeros((t, n), dtype=bool)
        self._breakout_up_long = np.zeros((t, n), dtype=bool)
        self._breakout_up = np.zeros((t, n), dtype=bool)
        if t > 1:
            curr_close = mx.close[1:, :]
            _buf = max(0.0, float(self._breakout_entry_buffer_pct))

            prev_hmax_short = self._high_max_short[:-1, :]
            prev_hmax_long = self._high_max_long[:-1, :]
            valid_short = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_short)
            valid_long = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_long)
            self._breakout_up_short[1:, :] = (curr_close > (prev_hmax_short * (1.0 + _buf))) & valid_short
            self._breakout_up_long[1:, :] = (curr_close > (prev_hmax_long * (1.0 + _buf))) & valid_long

            if self._enable_dual_breakout:
                self._breakout_up = self._breakout_up_short | self._breakout_up_long
            else:
                if int(self._breakout_window) == int(self._breakout_window_short):
                    self._breakout_up = self._breakout_up_short.copy()
                elif int(self._breakout_window) == int(self._breakout_window_long):
                    self._breakout_up = self._breakout_up_long.copy()
                else:
                    prev_hmax_main = self._high_max_main[:-1, :]
                    valid_main = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_main)
                    self._breakout_up[1:, :] = (curr_close > (prev_hmax_main * (1.0 + _buf))) & valid_main

        # -- entry confirmation matrix --
        self._entry_confirm_ok = np.ones((t, n), dtype=bool)
        _eps = 1e-8
        if self._entry_confirm_mode == "close_strength":
            spread = mx.high - mx.low
            close_pos = np.where(spread > _eps, (mx.close - mx.low) / spread, np.nan)
            self._entry_confirm_ok = (~np.isnan(close_pos)) & (close_pos > 0.6)
        elif self._entry_confirm_mode == "volume_confirm":
            vol_ma20 = pd.DataFrame(mx.volume).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            self._entry_confirm_ok = (~np.isnan(mx.volume)) & (~np.isnan(vol_ma20)) & (mx.volume > vol_ma20)
        elif self._entry_confirm_mode == "volatility_confirm":
            prev_close = np.empty_like(mx.close)
            prev_close[:] = np.nan
            if t > 1:
                prev_close[1:, :] = mx.close[:-1, :]
            tr1 = mx.high - mx.low
            tr2 = np.abs(mx.high - prev_close)
            tr3 = np.abs(mx.low - prev_close)
            tr = np.fmax(tr1, np.fmax(tr2, tr3))
            atr20 = pd.DataFrame(tr).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            self._entry_confirm_ok = (~np.isnan(tr)) & (~np.isnan(atr20)) & (tr > (atr20 * 0.8))
        elif self._entry_confirm_mode not in {"none", ""}:
            self._entry_confirm_mode = "none"

        # -- entry delay confirmation matrix --
        self._entry_delay_ok = self._breakout_up.copy()
        if self._entry_delay_mode == "t1_confirm":
            _prev = np.zeros_like(self._breakout_up, dtype=bool)
            if t > 1:
                _prev[1:, :] = self._breakout_up[:-1, :]
            self._entry_delay_ok = self._breakout_up & _prev
        elif self._entry_delay_mode == "t2_confirm":
            _prev2 = np.zeros_like(self._breakout_up, dtype=bool)
            if t > 2:
                _prev2[2:, :] = self._breakout_up[:-2, :]
            self._entry_delay_ok = self._breakout_up & _prev2
        elif self._entry_delay_mode == "pullback_confirm":
            self._entry_delay_ok = np.zeros((t, n), dtype=bool)
            if t > 1:
                prev_breakout = self._breakout_up[:-1, :]
                level = self._high_max_main[:-1, :]
                low_touch = (~np.isnan(mx.low[1:, :])) & (~np.isnan(level)) & (mx.low[1:, :] <= level)
                close_reclaim = (~np.isnan(mx.close[1:, :])) & (~np.isnan(level)) & (mx.close[1:, :] > level)
                self._entry_delay_ok[1:, :] = prev_breakout & low_touch & close_reclaim
        elif self._entry_delay_mode not in {"none", ""}:
            self._entry_delay_mode = "none"

        # -- V2 个股趋势过滤 --
        self._v2_trend_ok = np.ones((t, n), dtype=bool)
        if enable_v2_trend_filter:
            self._v2_trend_ok = (
                ~np.isnan(mx.close)
                & ~np.isnan(feats.sma20)
                & ~np.isnan(feats.sma60)
                & (mx.close > feats.sma60)
                & (feats.sma20 > feats.sma60)
            )

        # -- Momentum 前置过滤: 60日动量 top N% --
        momentum_top_pct = float(getattr(strategy, "momentum_top_pct", 0.0))
        momentum_window = 60
        self._momentum_ok = np.ones((t, n), dtype=bool)
        if momentum_top_pct > 0:
            # 60日收益率 = close[t] / close[t-60] - 1
            mom = np.full((t, n), np.nan, dtype=float)
            if t > momentum_window:
                prev_close = mx.close[:-momentum_window, :]
                curr_close = mx.close[momentum_window:, :]
                safe_prev = np.where(prev_close > 1e-8, prev_close, np.nan)
                mom[momentum_window:, :] = curr_close / safe_prev - 1.0
            # 每日排名, 只取 top N%
            self._momentum_ok = np.zeros((t, n), dtype=bool)
            for _di in range(t):
                row = mom[_di, :]
                valid_mask = ~np.isnan(row) & mx.tradable[_di, :]
                valid_count = int(np.sum(valid_mask))
                if valid_count == 0:
                    continue
                topk = max(1, int(valid_count * momentum_top_pct))
                # 找 top-K 的阈值
                valid_vals = row[valid_mask]
                threshold = np.partition(valid_vals, -topk)[-topk]
                self._momentum_ok[_di, :] = valid_mask & (row >= threshold)

        # -- 综合买入候选矩阵 --
        trend_base = (
            ~np.isnan(mx.close)
            & ~np.isnan(feats.sma20)
            & ~np.isnan(feats.sma60)
            & (mx.close > feats.sma60)
            & (feats.sma20 > feats.sma60)
        )
        reclaim_window = max(2, int(self._pullback_reclaim_window))
        touch_lookback = max(2, int(self._pullback_touch_lookback))
        pb_high = _rolling_max_matrix(mx.high, reclaim_window)
        pb_high_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            pb_high_prev[1:, :] = pb_high[:-1, :]
        ma20_touch = (
            ~np.isnan(mx.low)
            & ~np.isnan(feats.sma20)
            & (mx.low <= (feats.sma20 * (1.0 + max(0.0, float(self._pullback_ma20_touch_band_pct)))))
        )
        recent_ma20_touch = _rolling_any(ma20_touch, touch_lookback)
        self._pullback_pb1 = (
            trend_base
            & recent_ma20_touch
            & ~np.isnan(pb_high_prev)
            & (mx.close > pb_high_prev)
            & (mx.close > feats.sma20)
        )

        low_window = max(3, int(self._pullback_low_lookback))
        low_min = _rolling_min_matrix(mx.low, low_window)
        low_min_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            low_min_prev[1:, :] = low_min[:-1, :]
        self._pullback_pb2 = (
            trend_base
            & ~np.isnan(low_min_prev)
            & (mx.low <= low_min_prev * (1.0 + max(0.0, float(self._pullback_low_band_pct))))
            & (mx.close > mx.open)
            & ~np.isnan(pb_high_prev)
            & (mx.close > pb_high_prev)
        )

        box_window = max(3, int(self._pullback_box_window))
        box_high = _rolling_max_matrix(mx.high, box_window)
        box_low = _rolling_min_matrix(mx.low, box_window)
        box_high_prev = np.full((t, n), np.nan, dtype=float)
        box_low_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            box_high_prev[1:, :] = box_high[:-1, :]
            box_low_prev[1:, :] = box_low[:-1, :]
        box_range_pct = np.full((t, n), np.nan, dtype=float)
        valid_box = ~np.isnan(box_high_prev) & ~np.isnan(box_low_prev) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        box_range_pct[valid_box] = (box_high_prev[valid_box] - box_low_prev[valid_box]) / mx.close[valid_box]
        self._pullback_pb3 = (
            trend_base
            & ~np.isnan(box_range_pct)
            & (box_range_pct <= max(0.0, float(self._pullback_box_range_pct_max)))
            & ~np.isnan(box_high_prev)
            & (mx.close > box_high_prev)
        )

        high120 = _rolling_max_matrix(mx.high, 120)
        high120_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            high120_prev[1:, :] = high120[:-1, :]
        sma60_prev10 = np.full((t, n), np.nan, dtype=float)
        if t > 10:
            sma60_prev10[10:, :] = feats.sma60[:-10, :]
        ret20 = _return_matrix(mx.close, 20)
        close_pos = np.full((t, n), np.nan, dtype=float)
        day_range = mx.high - mx.low
        valid_close_pos = ~np.isnan(day_range) & (day_range > 1e-8) & ~np.isnan(mx.close) & ~np.isnan(mx.low)
        close_pos[valid_close_pos] = (mx.close[valid_close_pos] - mx.low[valid_close_pos]) / day_range[valid_close_pos]
        vol_ma20 = pd.DataFrame(mx.volume).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
        vol_ratio20 = np.full((t, n), np.nan, dtype=float)
        valid_vol20 = ~np.isnan(mx.volume) & ~np.isnan(vol_ma20) & (vol_ma20 > 1e-8)
        vol_ratio20[valid_vol20] = mx.volume[valid_vol20] / vol_ma20[valid_vol20]
        high20 = _rolling_max_matrix(mx.high, 20)
        high20_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            high20_prev[1:, :] = high20[:-1, :]
        pullback_depth = np.full((t, n), np.nan, dtype=float)
        valid_depth = ~np.isnan(high20_prev) & (high20_prev > 1e-8) & ~np.isnan(mx.close)
        pullback_depth[valid_depth] = (high20_prev[valid_depth] - mx.close[valid_depth]) / high20_prev[valid_depth]
        recent_low8 = _rolling_min_matrix(mx.low, 8)
        low_structure_ok = ~np.isnan(recent_low8) & ~np.isnan(feats.sma60) & (recent_low8 >= (feats.sma60 * 0.98))
        tight_reclaim_high = _rolling_max_matrix(mx.high, 5)
        tight_reclaim_high_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            tight_reclaim_high_prev[1:, :] = tight_reclaim_high[:-1, :]
        trend_tight = (
            trend_base
            & ~np.isnan(sma60_prev10)
            & (feats.sma60 > sma60_prev10)
            & ~np.isnan(high120_prev)
            & (mx.close >= (high120_prev * 0.88))
            & ~np.isnan(ret20)
            & (ret20 > 0.03)
        )
        shallow_pullback = ~np.isnan(pullback_depth) & (pullback_depth >= 0.03) & (pullback_depth <= 0.12)
        restart_quality = (
            ~np.isnan(close_pos)
            & (close_pos >= 0.65)
            & ~np.isnan(vol_ratio20)
            & (vol_ratio20 >= 0.90)
            & (vol_ratio20 <= 2.50)
        )
        self._pullback_tight1 = (
            trend_tight
            & recent_ma20_touch
            & shallow_pullback
            & low_structure_ok
            & ~np.isnan(tight_reclaim_high_prev)
            & (mx.close > tight_reclaim_high_prev)
            & (mx.close > feats.sma20)
            & restart_quality
        )

        tight_box_window = 6
        tight_box_high = _rolling_max_matrix(mx.high, tight_box_window)
        tight_box_low = _rolling_min_matrix(mx.low, tight_box_window)
        tight_box_high_prev = np.full((t, n), np.nan, dtype=float)
        tight_box_low_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            tight_box_high_prev[1:, :] = tight_box_high[:-1, :]
            tight_box_low_prev[1:, :] = tight_box_low[:-1, :]
        tight_box_range_pct = np.full((t, n), np.nan, dtype=float)
        valid_tight_box = ~np.isnan(tight_box_high_prev) & ~np.isnan(tight_box_low_prev) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        tight_box_range_pct[valid_tight_box] = (tight_box_high_prev[valid_tight_box] - tight_box_low_prev[valid_tight_box]) / mx.close[valid_tight_box]
        self._pullback_tight2 = (
            trend_tight
            & shallow_pullback
            & ~np.isnan(tight_box_range_pct)
            & (tight_box_range_pct <= 0.05)
            & ~np.isnan(tight_box_low_prev)
            & ~np.isnan(feats.sma20)
            & (tight_box_low_prev >= (feats.sma20 * 0.97))
            & ~np.isnan(tight_box_high_prev)
            & (mx.close > tight_box_high_prev)
            & restart_quality
        )

        if self._enable_pullback_candidates:
            variant_mode = str(self._pullback_variant_mode or "pb_reclaim_ma20").lower()
            if variant_mode in {"pb_reversal_near_low", "pb2"}:
                self._pullback_raw_selected = self._pullback_pb2.copy()
            elif variant_mode in {"pb_tight_box", "pb_tight_box_break", "tight_box"}:
                self._pullback_raw_selected = self._pullback_tight2.copy()
            elif variant_mode in {"pb_reclaim_ma20_plus_box", "pb1_pb3"}:
                self._pullback_raw_selected = self._pullback_pb1 | self._pullback_pb3
            elif variant_mode in {"pb_tight_combo", "tight_combo", "pb_tight"}:
                self._pullback_raw_selected = self._pullback_tight1 | self._pullback_tight2
            elif variant_mode in {"pb_tight_reclaim", "tight_reclaim"}:
                self._pullback_raw_selected = self._pullback_tight1.copy()
            elif variant_mode == "all":
                self._pullback_raw_selected = self._pullback_pb1 | self._pullback_pb2 | self._pullback_pb3
            else:
                self._pullback_raw_selected = self._pullback_pb1.copy()
        else:
            self._pullback_raw_selected = np.zeros((t, n), dtype=bool)

        stock_ret = _return_matrix(mx.close, int(self._residual_window))
        bench_ret = _return_series(self._bench_close, int(self._residual_window))
        bench_ret_m = np.repeat(bench_ret.reshape(-1, 1), n, axis=1)
        sector_ret_short, sector_ret_long, sector_trend = _build_sector_feature_matrices(
            sector_data=sector_data if isinstance(sector_data, dict) else None,
            industry_map=industry_map if isinstance(industry_map, dict) else None,
            symbols=mx.symbols,
            dates=mx.dates,
            short_window=int(self._sector_strength_window_short),
            long_window=int(max(self._sector_strength_window_long, self._residual_window)),
        )
        residual_vs_bench = stock_ret - bench_ret_m
        residual_vs_sector = stock_ret - sector_ret_long
        self._residual_strength_raw = _weighted_score(
            [(residual_vs_bench, 0.5), (residual_vs_sector, 0.5)],
            shape=(t, n),
        )
        self._residual_strength_score = _row_rank_pct(self._residual_strength_raw, mx.tradable)

        sector_short_rank = _row_rank_pct(sector_ret_short, mx.tradable)
        sector_long_rank = _row_rank_pct(sector_ret_long, mx.tradable)
        self._sector_strength_score = _weighted_score(
            [(sector_short_rank, 0.4), (sector_long_rank, 0.4), (sector_trend, 0.2)],
            shape=(t, n),
        )

        vol_window = max(5, int(self._volume_quality_window))
        vol_ma = pd.DataFrame(mx.volume).rolling(vol_window, min_periods=vol_window).mean().to_numpy(dtype=float)
        vol_ratio = np.full((t, n), np.nan, dtype=float)
        valid_vol = ~np.isnan(mx.volume) & ~np.isnan(vol_ma) & (vol_ma > 1e-8)
        vol_ratio[valid_vol] = mx.volume[valid_vol] / vol_ma[valid_vol]
        vol_quality_raw = np.full((t, n), np.nan, dtype=float)
        valid_vr = ~np.isnan(vol_ratio) & (vol_ratio > 1e-8)
        vol_quality_raw[valid_vr] = -np.abs(np.log(vol_ratio[valid_vr] / 1.2))
        atr_pct = np.full((t, n), np.nan, dtype=float)
        valid_atr_pct = ~np.isnan(feats.atr14) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        atr_pct[valid_atr_pct] = feats.atr14[valid_atr_pct] / mx.close[valid_atr_pct]
        range_high = _rolling_max_matrix(mx.high, vol_window)
        range_low = _rolling_min_matrix(mx.low, vol_window)
        range_pct = np.full((t, n), np.nan, dtype=float)
        valid_range = ~np.isnan(range_high) & ~np.isnan(range_low) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        range_pct[valid_range] = (range_high[valid_range] - range_low[valid_range]) / mx.close[valid_range]
        quality_raw = _weighted_score(
            [(vol_quality_raw, 0.5), (-atr_pct, 0.3), (-range_pct, 0.2)],
            shape=(t, n),
        )
        self._volume_price_quality_score = _row_rank_pct(quality_raw, mx.tradable)

        if self._enable_residual_ranking or self._enable_sector_quality_ranking:
            score_components: list[tuple[np.ndarray, float]] = []
            if self._enable_residual_ranking:
                score_components.append((self._residual_strength_score, float(self._residual_weight)))
            if self._enable_sector_quality_ranking:
                score_components.append((self._sector_strength_score, float(self._sector_weight)))
                score_components.append((self._volume_price_quality_score, float(self._quality_weight)))
            self._final_score = _weighted_score(score_components, shape=(t, n))
        else:
            self._final_score = np.full((t, n), 0.5, dtype=float)

        risk_on_m = np.repeat(self._risk_on.reshape(-1, 1), n, axis=1)
        common_gate = risk_on_m & mx.tradable & self._momentum_ok
        self._breakout_buy = self._entry_delay_ok & self._entry_confirm_ok & self._v2_trend_ok & common_gate
        pullback_gate = self._entry_confirm_ok & common_gate
        if enable_v2_trend_filter:
            pullback_gate = pullback_gate & self._v2_trend_ok
        self._pullback_raw_selected = self._pullback_raw_selected & pullback_gate
        self._pullback_overlap = self._pullback_raw_selected & self._breakout_buy
        self._pullback_buy = self._pullback_raw_selected & ~self._breakout_buy
        if self._source_aware_residual_mode in {"pullback_only", "pullback_only_rank"} and self._enable_residual_ranking:
            residual_safe = np.where(np.isnan(self._residual_strength_score), 0.5, self._residual_strength_score)
            breakout_only = self._breakout_buy & ~self._pullback_overlap
            self._final_score[breakout_only] = 2.0
            self._final_score[self._pullback_overlap] = 2.1
            self._final_score[self._pullback_buy] = residual_safe[self._pullback_buy]
        buy_base = self._breakout_buy | self._pullback_buy
        self._cand_idx = build_daily_candidate_index(buy_base)
        self._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}

        # -- fill hooks 初始化 --
        self._peak_close_state = {}
        self.entry_day = {}
        self.last_sell_day = {}
        self.extra_clear_dicts = [self._peak_close_state]
        self.peak_state_on_buy = self._peak_close_state

        self.precompute_seconds = float(_time.perf_counter() - pre_t0)

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        i = day_idx
        mx = self._mx
        feats = self._feats
        positions = ctx.positions
        position_avg_cost = ctx.position_avg_cost
        close_idx = ctx.close_idx
        nav = ctx.nav
        max_positions = ctx.max_positions
        base_order_value = ctx.base_order_value
        n = mx.close.shape[1]

        # ── 卖出信号: engine 级退出规则 ──
        def _get_atr(sym: str, d: date) -> float | None:
            col = self._sym_to_col.get(sym)
            if col is None:
                return None
            v = float(feats.atr14[i, col])
            return v if not np.isnan(v) else None

        def _check_ma20(sym: str) -> bool:
            col = self._sym_to_col.get(sym)
            if col is None:
                return False
            adj_c = float(mx.close[i, col])
            sma20_v = float(feats.sma20[i, col])
            if np.isnan(adj_c) or np.isnan(sma20_v):
                return False
            return adj_c < sma20_v

        def _check_low10(sym: str) -> bool:
            col = self._sym_to_col.get(sym)
            if col is None:
                return False
            adj_c = float(mx.close[i, col])
            low10_v = float(feats.low_min10[i, col])
            if np.isnan(adj_c) or np.isnan(low10_v):
                return False
            return adj_c < low10_v

        sell_sigs, exit_syms, exit_counts = evaluate_engine_exits(
            positions=positions,
            day=day,
            close_idx=close_idx,
            position_avg_cost=position_avg_cost,
            peak_state=self._peak_close_state,
            entry_day=self.entry_day,
            exit_cfg=self._ec,
            get_atr=_get_atr,
            risk_on=bool(self._risk_on[i]),
            enable_risk_off_exit=self._enable_risk_off_exit,
            max_hold_days=self._max_hold_days,
            atr_stop_k=self._atr_stop_k,
            check_ma20_exit=_check_ma20,
            check_low10_exit=_check_low10,
        )
        for _ss in sell_sigs:
            _rc = str(_ss.reason_code)
            self.diag_reason_counts[_rc] = int(self.diag_reason_counts.get(_rc, 0)) + 1

        # ── 买入信号 ──
        day_cands = self._cand_idx[i]
        buy_sigs: list[Signal] = []
        mf_score_map: dict[str, float] = {}
        strength_map: dict[str, float] = {}
        breakout_count = 0
        pullback_count = 0
        overlap_count = 0
        self.total_buy_signals += int(len(day_cands))

        for c in day_cands:
            sym = mx.symbols[int(c)]
            # 已持有跳过
            if sym in positions and int(positions[sym]) > 0:
                continue
            # min_hold 约束
            if self._min_hold_days > 0 and sym in self.entry_day:
                held = (day - self.entry_day[sym]).days
                if held < self._min_hold_days:
                    self.min_hold_block_count += 1
                    continue
            # cooldown 约束
            if self._cooldown_days > 0 and self.last_sell_day and sym in self.last_sell_day:
                since_sell = (day - self.last_sell_day[sym]).days
                if since_sell < self._cooldown_days:
                    self.cooldown_block_count += 1
                    continue

            close_val = float(mx.close[i, c]) if not np.isnan(mx.close[i, c]) else None
            slow_ma_val = float(feats.sma60[i, c]) if not np.isnan(feats.sma60[i, c]) else None
            atr_val = float(feats.atr14[i, c]) if not np.isnan(feats.atr14[i, c]) else None
            hmax_prev_short = float(self._high_max_short[i - 1, c]) if (i > 0 and not np.isnan(self._high_max_short[i - 1, c])) else None
            hmax_prev_long = float(self._high_max_long[i - 1, c]) if (i > 0 and not np.isnan(self._high_max_long[i - 1, c])) else None
            hit_short = bool(self._breakout_up_short[i, c]) if self._breakout_up_short.size else False
            hit_long = bool(self._breakout_up_long[i, c]) if self._breakout_up_long.size else False
            from_breakout = bool(self._breakout_buy[i, c]) if self._breakout_buy.size else False
            from_pullback = bool(self._pullback_buy[i, c]) if self._pullback_buy.size else False
            is_overlap = bool(self._pullback_overlap[i, c]) if self._pullback_overlap.size else False
            if from_breakout:
                breakout_count += 1
            if from_pullback:
                pullback_count += 1
            if is_overlap:
                overlap_count += 1
            residual_raw = float(self._residual_strength_raw[i, c]) if self._residual_strength_raw.size and not np.isnan(self._residual_strength_raw[i, c]) else None
            residual_score = float(self._residual_strength_score[i, c]) if self._residual_strength_score.size and not np.isnan(self._residual_strength_score[i, c]) else None
            sector_score = float(self._sector_strength_score[i, c]) if self._sector_strength_score.size and not np.isnan(self._sector_strength_score[i, c]) else None
            quality_score = float(self._volume_price_quality_score[i, c]) if self._volume_price_quality_score.size and not np.isnan(self._volume_price_quality_score[i, c]) else None
            final_score = float(self._final_score[i, c]) if self._final_score.size and not np.isnan(self._final_score[i, c]) else 0.5
            mf_score_map[sym] = float(final_score)
            strength_map[sym] = float(residual_score if residual_score is not None else final_score)
            pullback_variant = ""
            if self._pullback_tight1.size and bool(self._pullback_tight1[i, c]) and self._pullback_tight2.size and bool(self._pullback_tight2[i, c]):
                pullback_variant = "pb_tight_combo"
            elif self._pullback_tight1.size and bool(self._pullback_tight1[i, c]):
                pullback_variant = "pb_tight_reclaim"
            elif self._pullback_tight2.size and bool(self._pullback_tight2[i, c]):
                pullback_variant = "pb_tight_box"
            elif self._pullback_pb1.size and bool(self._pullback_pb1[i, c]):
                pullback_variant = "pb_reclaim_ma20"
            elif self._pullback_pb2.size and bool(self._pullback_pb2[i, c]):
                pullback_variant = "pb_reversal_near_low"
            elif self._pullback_pb3.size and bool(self._pullback_pb3[i, c]):
                pullback_variant = "pb_box_break"
            alpha_source = "breakout"
            reason = "BREAKOUT_DUAL_OR" if self._enable_dual_breakout else "BREAKOUT_HIGH"
            reason_code = reason
            if is_overlap and from_breakout:
                alpha_source = "pullback_overlap"
                reason = "BREAKOUT_PULLBACK_CONFLUENCE"
                reason_code = "BREAKOUT_PULLBACK_CONFLUENCE"
            elif from_pullback:
                alpha_source = "pullback_only"
                reason = "PULLBACK_TREND"
                reason_code = "PULLBACK_TREND"
            else:
                pullback_variant = ""

            buy_sigs.append(Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=self._order_size,
                reason=reason,
                reason_code=reason_code,
                meta={
                    "close": close_val,
                    "slow_ma": slow_ma_val,
                    "atr_last": atr_val,
                    "alpha_source": alpha_source,
                    "overlap_flag": bool(is_overlap),
                    "pullback_variant": pullback_variant,
                    "residual_strength_raw": residual_raw,
                    "residual_strength_score": residual_score,
                    "sector_strength_score": sector_score,
                    "volume_price_quality_score": quality_score,
                    "final_score": final_score,
                    "source_aware_residual_mode": str(self._source_aware_residual_mode),
                    "breakout_window_main": int(self._breakout_window),
                    "breakout_window_short": int(self._breakout_window_short),
                    "breakout_window_long": int(self._breakout_window_long),
                    "breakout_entry_buffer_pct": float(self._breakout_entry_buffer_pct),
                    "entry_confirm_mode": str(self._entry_confirm_mode),
                    "entry_delay_mode": str(self._entry_delay_mode),
                    "high_max_short_prev": hmax_prev_short,
                    "high_max_long_prev": hmax_prev_long,
                    "breakout_hit_short": hit_short,
                    "breakout_hit_long": hit_long,
                    "v2_trend_ok": bool(self._v2_trend_ok[i, c]),
                    "regime_on": bool(self._risk_on[i]),
                },
            ))

        return DaySignals(
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            exit_syms=exit_syms,
            strength_map=strength_map,
            mf_score_map=mf_score_map,
            mf_gate_on_today=False,
            strong_risk_on=False,
            exit_counts=exit_counts,
            diagnostics={
                "raw_buy_signal_count": int(len(day_cands)),
                "breakout_candidates": int(max(breakout_count - overlap_count, 0)),
                "pullback_candidates": int(pullback_count),
                "pullback_overlap_candidates": int(overlap_count),
                "pullback_total_candidates": int(pullback_count + overlap_count),
                "buy_signals_generated": int(len(buy_sigs)),
            },
        )
