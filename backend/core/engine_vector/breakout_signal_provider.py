"""Breakout trend signal provider."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Signal
from backend.core.engine_vector.breakout_provider_day_signals import (
    build_breakout_day_signals as _build_breakout_day_signals,
    evaluate_profit_decay_exits as _evaluate_profit_decay_exits_helper,
)
from backend.core.engine_vector.breakout_provider_models import (
    apply_breakout_provider_config as _apply_breakout_provider_config,
    build_breakout_provider_config as _build_breakout_provider_config,
    capture_breakout_runtime_state as _capture_breakout_runtime_state,
)
from backend.core.engine_vector.breakout_provider_precompute import (
    finalize_breakout_provider_precompute as _finalize_breakout_provider_precompute,
)
from backend.core.engine_vector.breakout_provider_precompute import (
    _compute_residual_ranking_matrices,
)
from backend.core.engine_vector.breakout_support import (
    build_industry_assignment_matrices as _build_industry_assignment_matrices,
    return_matrix as _return_matrix,
    rolling_any as _rolling_any,
    rolling_max_matrix as _rolling_max_matrix,
    rolling_min_matrix as _rolling_min_matrix,
)
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices
from backend.core.engine_vector.signal_provider import DayContext, DaySignals, ExitCounts



class BreakoutTrendProvider:
    """20-day breakout provider.

    Buy signals come from prior-high breakouts and sells are delegated to
    `evaluate_engine_exits`.
    """
    def __init__(self) -> None:
        # Hooks consumed by the shared fill pipeline.
        self._config: Any = None
        self._runtime_state: Any = None
        self.extra_clear_dicts: list[dict] = []
        self.last_sell_day: dict[str, date] | None = None
        self.entry_day: dict[str, date] = {}
        self.entry_bar_index: dict[str, int] = {}
        self.entry_breakout_floor_raw: dict[str, float] = {}
        self.entry_day_overwrite: bool = True
        self.peak_state_on_buy: dict[str, float] | None = None

        # Precomputed runtime state populated by `precompute()`. 
        self._mx: Any = None
        self._feats: Any = None
        self._breakout_up: np.ndarray = np.array([])
        self._breakout_up_short: np.ndarray = np.array([])
        self._breakout_up_long: np.ndarray = np.array([])
        self._dual_breakout_slow_gate_ok: np.ndarray = np.array([])
        self._high_max_short: np.ndarray = np.array([])
        self._high_max_long: np.ndarray = np.array([])
        self._high_max_main: np.ndarray = np.array([])
        self._v2_trend_ok: np.ndarray = np.array([])
        self._entry_confirm_ok: np.ndarray = np.array([])
        self._entry_delay_ok: np.ndarray = np.array([])
        self._entry_above_slow_ma: np.ndarray = np.array([])
        self._entry_slow_ma_slope_pos: np.ndarray = np.array([])
        self._cand_idx: Any = None
        self._bench_close: np.ndarray = np.array([])
        self._risk_on: np.ndarray = np.array([])
        self._strong_risk_on: np.ndarray = np.array([])
        self._breakout_buy: np.ndarray = np.array([])
        self._pullback_pb1: np.ndarray = np.array([])
        self._pullback_pb2: np.ndarray = np.array([])
        self._pullback_pb3: np.ndarray = np.array([])
        self._pullback_tight1: np.ndarray = np.array([])
        self._pullback_tight2: np.ndarray = np.array([])
        self._pullback_raw_selected: np.ndarray = np.array([])
        self._pullback_overlap: np.ndarray = np.array([])
        self._pullback_buy: np.ndarray = np.array([])
        self._breakout_margin_raw: np.ndarray = np.array([])
        self._breakout_fade_raw: np.ndarray = np.array([])
        self._breakout_open_gap_raw: np.ndarray = np.array([])
        self._residual_strength_raw: np.ndarray = np.array([])
        self._residual_vs_bench_raw: np.ndarray = np.array([])
        self._residual_vs_sector_raw: np.ndarray = np.array([])
        self._sector_proxy_residual_raw: np.ndarray = np.array([])
        self._industry_median_excess_raw: np.ndarray = np.array([])
        self._sector_beta_tailwind_raw: np.ndarray = np.array([])
        self._residual_window_effective: np.ndarray = np.array([])
        self._residual_benchmark_weight_effective: np.ndarray = np.array([])
        self._residual_industry_weight_effective: np.ndarray = np.array([])
        self._industry_relative_mode_effective: np.ndarray = np.array([], dtype=object)
        self._breakout_margin_score: np.ndarray = np.array([])
        self._breakout_quality_score: np.ndarray = np.array([])
        self._breakout_quality_pass: np.ndarray = np.array([])
        self._residual_strength_score: np.ndarray = np.array([])
        self._sector_strength_score: np.ndarray = np.array([])
        self._volume_price_quality_score: np.ndarray = np.array([])
        self._conditional_tiebreak_score: np.ndarray = np.array([])
        self._conditional_factor_leader_score: np.ndarray = np.array([])
        self._conditional_institution_proxy_score: np.ndarray = np.array([])
        self._conditional_crowding_score: np.ndarray = np.array([])
        self._conditional_recent_limit_hit_3d: np.ndarray = np.array([])
        self._conditional_near_limit_up: np.ndarray = np.array([])
        self._industry_second_stage_score: np.ndarray = np.array([])
        self._industry_second_stage_not_hot_score: np.ndarray = np.array([])
        self._industry_second_stage_uncrowded_score: np.ndarray = np.array([])
        self._industry_second_stage_breadth_timing_score: np.ndarray = np.array([])
        self._industry_second_stage_persistence_10d: np.ndarray = np.array([])
        self._industry_second_stage_active: np.ndarray = np.array([], dtype=bool)
        self._leadership_route_score: np.ndarray = np.array([])
        self._leadership_route_rank: np.ndarray = np.array([])
        self._leadership_route_bucket: np.ndarray = np.array([], dtype=int)
        self._final_score: np.ndarray = np.array([])
        self._sym_to_col: dict[str, int] = {}
        self._ec: ExitConfig = ExitConfig()
        self._peak_close_state: dict[str, float] = {}
        self._risk_off_partial_state: dict[str, bool] = {}

        # strategy 閸欏倹鏆?
        self._breakout_window: int = 20
        self._enable_dual_breakout: bool = False
        self._breakout_window_short: int = 20
        self._breakout_window_long: int = 55
        self._dual_breakout_mode: str = "or"
        self._dual_breakout_gate_ma_window: int = 120
        self._dual_breakout_gate_slope_lookback: int = 10
        self._breakout_entry_buffer_pct: float = 0.0
        self._entry_confirm_mode: str = "none"
        self._entry_delay_mode: str = "none"
        self._enable_entry_above_slow_ma: bool = False
        self._enable_entry_slow_ma_slope: bool = False
        self._entry_slope_lookback: int = 5
        self._enable_atr_stop: bool = False
        self._enable_atr_trail: bool = False
        self._atr_stop_k: float = 2.0
        self._atr_trail_k: float = 3.0
        self._order_size: int = 1000
        self._max_hold_days: int = 0
        self._min_hold_days: int = 0
        self._cooldown_days: int = 0
        self._enable_risk_off_exit: bool = False
        self._risk_off_exit_mode: str = "risk_on_off"
        self._risk_off_exit_partial_pct: float = 1.0
        self._risk_off_exit_partial_mode: str = "all_states"
        self._risk_off_exit_partial_only_if_profitable: bool = False
        self._risk_off_exit_trans_down_max_positions: int = 0
        self._risk_off_exit_trans_down_min_residual_score: float = 0.0
        self._enable_profit_decay_exit: bool = False
        self._profit_decay_exit_profit_pct: float = 0.15
        self._profit_decay_exit_min_hold_bars: int = 10
        self._profit_decay_exit_residual_score_threshold: float = 0.35
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
        self._residual_benchmark_weight: float = 0.5
        self._residual_industry_weight: float = 0.5
        self._industry_relative_mode: str = "sector_proxy"
        self._industry_relative_regime_mode: str = "off"
        self._residual_weight_regime_mode: str = "off"
        self._residual_benchmark_weight_fallback: float = 0.5
        self._residual_industry_weight_fallback: float = 0.5
        self._ranking_mode: str = "none"
        self._leadership_route_bucket_count: int = 3
        self._breakout_quality_gate_min_score: float = 0.55
        self._breakout_quality_margin_cap_pct: float = 0.08
        self._breakout_quality_fade_cap_pct: float = 0.035
        self._breakout_quality_open_gap_cap_pct: float = 0.04
        self._residual_window_regime_mode: str = "off"
        self._residual_window_fallback: int = 60
        self._residual_window_regime_fast_ma: int = 120
        self._residual_window_regime_slow_ma: int = 200
        self._source_aware_residual_mode: str = "off"
        self._residual_refine_mode: str = "off"
        self._residual_refine_weight: float = 0.0
        self._industry_second_stage_min_industry_score: float = 0.85
        self._enable_sector_quality_ranking: bool = False
        self._sector_strength_window_short: int = 20
        self._sector_strength_window_long: int = 60
        self._volume_quality_window: int = 20
        self._residual_weight: float = 0.5
        self._sector_weight: float = 0.3
        self._quality_weight: float = 0.2
        self._enable_v2_trend_filter: bool = True
        self._v2_trend_short_ma: int = 20
        self._v2_trend_long_ma: int = 60

        # Diagnostic counters populated during precompute/day signal evaluation.
        self.total_buy_signals: int = 0
        self.min_hold_block_count: int = 0
        self.cooldown_block_count: int = 0
        self.entry_above_slow_ma_block_count: int = 0
        self.entry_slope_block_count: int = 0
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
        membership_history = kwargs.get("membership_history")
        config = _build_breakout_provider_config(strategy, kwargs=kwargs)
        _apply_breakout_provider_config(self, config, exit_cfg=exit_cfg)
        strength_ma = int(config.strength_ma)
        regime_ma = int(config.regime_ma)
        enable_v2_trend_filter = bool(config.enable_v2_trend_filter)
        v2_trend_short_ma = int(config.v2_trend_short_ma)
        v2_trend_long_ma = int(config.v2_trend_long_ma)
        pre_t0 = _time.perf_counter()
        sector_data = kwargs.get("sector_data")
        industry_map = kwargs.get("industry_map")
        industry_history = kwargs.get("industry_history")


        # -- OHLC + feature 閻晠妯€ --
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

        self._mx = build_ohlc_matrices_from_history(
            hist,
            trading_days,
            st_history=st_history,
            membership_history=membership_history,
            min_price=float(config.min_price),
            min_list_days=int(config.min_list_days),
            min_avg_turnover_20d=float(config.min_avg_turnover_20d),
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

        # -- benchmark 閺佹壆绮?--
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
        strong_fast_ma = max(2, int(self._residual_window_regime_fast_ma))
        strong_slow_ma = max(strong_fast_ma + 1, int(self._residual_window_regime_slow_ma))
        bench_fast_ma_s = bench_close_s.rolling(strong_fast_ma, min_periods=strong_fast_ma).mean()
        bench_slow_ma_s = bench_close_s.rolling(strong_slow_ma, min_periods=strong_slow_ma).mean()
        bmap_fast_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_fast_ma_s)}
        bmap_slow_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_slow_ma_s)}
        bench_fast_ma = np.array([bmap_fast_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_slow_ma = np.array([bmap_slow_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._strong_risk_on = np.zeros(t, dtype=bool)
        valid_strong = ~np.isnan(bench_fast_ma) & ~np.isnan(bench_slow_ma)
        self._strong_risk_on[valid_strong] = bench_fast_ma[valid_strong] > bench_slow_ma[valid_strong]

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
        self._breakout_margin_raw = np.full((t, n), np.nan, dtype=float)
        self._breakout_fade_raw = np.full((t, n), np.nan, dtype=float)
        self._breakout_open_gap_raw = np.full((t, n), np.nan, dtype=float)
        self._dual_breakout_slow_gate_ok = np.ones((t, n), dtype=bool)
        if t > 1:
            curr_close = mx.close[1:, :]
            _buf = max(0.0, float(self._breakout_entry_buffer_pct))

            prev_hmax_short = self._high_max_short[:-1, :]
            prev_hmax_long = self._high_max_long[:-1, :]
            valid_short = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_short)
            valid_long = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_long)
            self._breakout_up_short[1:, :] = (curr_close > (prev_hmax_short * (1.0 + _buf))) & valid_short
            self._breakout_up_long[1:, :] = (curr_close > (prev_hmax_long * (1.0 + _buf))) & valid_long
            breakout_ref = np.full((t, n), np.nan, dtype=float)
            if self._enable_dual_breakout:
                breakout_ref[1:, :] = prev_hmax_short
            elif int(self._breakout_window) == int(self._breakout_window_short):
                breakout_ref[1:, :] = prev_hmax_short
            elif int(self._breakout_window) == int(self._breakout_window_long):
                breakout_ref[1:, :] = prev_hmax_long
            else:
                breakout_ref[1:, :] = self._high_max_main[:-1, :]
            breakout_ref = breakout_ref * (1.0 + _buf)
            valid_breakout_ref = ~np.isnan(mx.close) & ~np.isnan(breakout_ref) & (breakout_ref > 1e-8)
            self._breakout_margin_raw[valid_breakout_ref] = (
                mx.close[valid_breakout_ref] / breakout_ref[valid_breakout_ref] - 1.0
            )
            prev_close = np.full((t, n), np.nan, dtype=float)
            prev_close[1:, :] = mx.close[:-1, :]
            valid_open_gap = ~np.isnan(mx.open) & ~np.isnan(prev_close) & (prev_close > 1e-8)
            self._breakout_open_gap_raw[valid_open_gap] = np.maximum(
                mx.open[valid_open_gap] / prev_close[valid_open_gap] - 1.0,
                0.0,
            )
            valid_fade = ~np.isnan(mx.high) & ~np.isnan(mx.close) & (mx.close > 1e-8)
            self._breakout_fade_raw[valid_fade] = np.maximum(
                mx.high[valid_fade] / mx.close[valid_fade] - 1.0,
                0.0,
            )

            if self._dual_breakout_mode == "slow_gate_fast_trigger":
                gate_window = max(2, int(self._dual_breakout_gate_ma_window))
                gate_lb = max(1, int(self._dual_breakout_gate_slope_lookback))
                slow_gate_ma = pd.DataFrame(mx.close).rolling(gate_window, min_periods=gate_window).mean().to_numpy(dtype=float)
                slow_gate_prev = np.full((t, n), np.nan, dtype=float)
                if t > gate_lb:
                    slow_gate_prev[gate_lb:, :] = slow_gate_ma[:-gate_lb, :]
                self._dual_breakout_slow_gate_ok = (
                    ~np.isnan(mx.close)
                    & ~np.isnan(slow_gate_ma)
                    & ~np.isnan(slow_gate_prev)
                    & (mx.close > slow_gate_ma)
                    & (slow_gate_ma > slow_gate_prev)
                )

            if self._enable_dual_breakout:
                if self._dual_breakout_mode == "slow_gate_fast_trigger":
                    self._breakout_up = self._breakout_up_short & self._dual_breakout_slow_gate_ok
                else:
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
        elif self._entry_confirm_mode == "volume_ratio_confirm":
            vol_ma20 = pd.DataFrame(mx.volume).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            vol_ma20_prev = np.empty_like(vol_ma20)
            vol_ma20_prev[:] = np.nan
            if t > 1:
                vol_ma20_prev[1:, :] = vol_ma20[:-1, :]
            self._entry_confirm_ok = (~np.isnan(mx.volume)) & (~np.isnan(vol_ma20_prev)) & (mx.volume > (vol_ma20_prev * 1.5))
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

        self._entry_above_slow_ma = np.ones((t, n), dtype=bool)
        if self._enable_entry_above_slow_ma:
            self._entry_above_slow_ma = (
                ~np.isnan(mx.close)
                & ~np.isnan(feats.sma60)
                & (mx.close > feats.sma60)
            )

        self._entry_slow_ma_slope_pos = np.ones((t, n), dtype=bool)
        if self._enable_entry_slow_ma_slope:
            lb = max(1, int(self._entry_slope_lookback))
            self._entry_slow_ma_slope_pos[:] = False
            if t > lb:
                slow_ma_diff = np.full((t, n), np.nan, dtype=float)
                slow_ma_diff[lb:, :] = feats.sma60[lb:, :] - feats.sma60[:-lb, :]
                self._entry_slow_ma_slope_pos = (
                    ~np.isnan(slow_ma_diff)
                    & (slow_ma_diff > 0.0)
                )

        # -- V2 娑擃亣鍋傜搾瀣◢鏉╁洦鎶?--
        self._v2_trend_ok = np.ones((t, n), dtype=bool)
        if enable_v2_trend_filter:
            self._v2_trend_ok = (
                ~np.isnan(mx.close)
                & ~np.isnan(feats.sma20)
                & ~np.isnan(feats.sma60)
                & (mx.close > feats.sma60)
                & (feats.sma20 > feats.sma60)
            )

        # -- Momentum 閸撳秶鐤嗘潻鍥ㄦ姢: 60閺冦儱濮╅柌?top N% --
        momentum_top_pct = float(getattr(strategy, "momentum_top_pct", 0.0))
        momentum_window = 60
        self._momentum_ok = np.ones((t, n), dtype=bool)
        if momentum_top_pct > 0:
            # 60閺冦儲鏁归惄濠勫芳 = close[t] / close[t-60] - 1
            mom = np.full((t, n), np.nan, dtype=float)
            if t > momentum_window:
                prev_close = mx.close[:-momentum_window, :]
                curr_close = mx.close[momentum_window:, :]
                safe_prev = np.where(prev_close > 1e-8, prev_close, np.nan)
                mom[momentum_window:, :] = curr_close / safe_prev - 1.0
            # 濮ｅ繑妫╅幒鎺戞倳, 閸欘亜褰?top N%
            self._momentum_ok = np.zeros((t, n), dtype=bool)
            for _di in range(t):
                row = mom[_di, :]
                valid_mask = ~np.isnan(row) & mx.tradable[_di, :]
                valid_count = int(np.sum(valid_mask))
                if valid_count == 0:
                    continue
                topk = max(1, int(valid_count * momentum_top_pct))
                # 閹?top-K 閻ㄥ嫰妲囬崐?                valid_vals = row[valid_mask]
                threshold = np.partition(valid_vals, -topk)[-topk]
                self._momentum_ok[_di, :] = valid_mask & (row >= threshold)

        # -- 缂佺厧鎮庢稊鏉垮弳閸婃瑩鈧鐓╅梼?--
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

        _finalize_breakout_provider_precompute(
            self,
            raw_history=raw_history,
            mx=mx,
            sector_data=sector_data if isinstance(sector_data, dict) else None,
            industry_map=industry_map if isinstance(industry_map, dict) else None,
            industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
        )
        # -- fill hooks 閸掓繂顫愰崠?--
        self._peak_close_state = {}
        self._risk_off_partial_state = {}
        self.entry_day = {}
        self.last_sell_day = {}
        self.entry_bar_index = {}
        self.entry_breakout_floor_raw = {}
        self.extra_clear_dicts = [
            self._peak_close_state,
            self._risk_off_partial_state,
            self.entry_bar_index,
            self.entry_breakout_floor_raw,
        ]
        self.peak_state_on_buy = self._peak_close_state
        _capture_breakout_runtime_state(self)

        self.precompute_seconds = float(_time.perf_counter() - pre_t0)

    def _evaluate_profit_decay_exits(
        self,
        *,
        day: date,
        day_idx: int,
        positions: dict[str, int],
        position_avg_cost: dict[str, float],
        close_idx: dict[tuple[date, str], float],
        exit_syms: set[str],
        exit_counts: ExitCounts,
    ) -> list[Signal]:
        return _evaluate_profit_decay_exits_helper(
            self,
            day=day,
            day_idx=day_idx,
            positions=positions,
            position_avg_cost=position_avg_cost,
            close_idx=close_idx,
            exit_syms=exit_syms,
            exit_counts=exit_counts,
        )

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        return _build_breakout_day_signals(self, day, day_idx, ctx)
