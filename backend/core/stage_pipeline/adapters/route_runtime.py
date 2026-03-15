from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from backend.core.config.models import BenchmarkRegimeConfig, BreadthConfig, ExitConfig, MarketFilterConfig, RiskBudgetConfig, SizingConfig
from backend.core.engine_vector.breadth import compute_breadth_scores, compute_dynamic_maxpos
from backend.core.engine_vector.route_registry import build_signal_provider_for_strategy
from backend.core.engine_vector.signal_provider import SignalProvider
from backend.core.tools.data_bundle_builder import DataBundle


@dataclass(frozen=True, slots=True)
class RouteControls:
    mf_enabled: bool
    mf_state_arr: np.ndarray
    mf_mult_arr: np.ndarray
    br_enabled: bool
    br_gate_arr: np.ndarray
    breadth_enabled: bool
    breadth_score_arr: np.ndarray
    breadth_maxpos_arr: np.ndarray


def build_signal_provider(strategy: Any) -> tuple[str, SignalProvider]:
    return build_signal_provider_for_strategy(strategy)


def coerce_market_filter_cfg(value: MarketFilterConfig | Mapping[str, Any] | None) -> MarketFilterConfig | None:
    if isinstance(value, MarketFilterConfig):
        return value
    if isinstance(value, Mapping):
        fields = {k: v for k, v in value.items() if k in MarketFilterConfig.__dataclass_fields__}
        return MarketFilterConfig(**fields)
    return None


def coerce_benchmark_regime_cfg(
    value: BenchmarkRegimeConfig | Mapping[str, Any] | None,
) -> BenchmarkRegimeConfig | None:
    if isinstance(value, BenchmarkRegimeConfig):
        return value
    if isinstance(value, Mapping):
        fields = {k: v for k, v in value.items() if k in BenchmarkRegimeConfig.__dataclass_fields__}
        return BenchmarkRegimeConfig(**fields)
    return None


def initialize_route_controls(
    *,
    route_id: str,
    data_bundle: DataBundle,
    market_filter_cfg: MarketFilterConfig | None,
    benchmark_regime_cfg: BenchmarkRegimeConfig | None,
    breadth_cfg: BreadthConfig | None = None,
    provider: Any | None = None,
) -> RouteControls:
    day_count = len(data_bundle.trading_days)
    mf_state_arr = np.zeros(day_count, dtype=np.int8)
    mf_mult_arr = np.ones(day_count, dtype=float)
    br_gate_arr = np.ones(day_count, dtype=bool)
    breadth_score_arr = np.full(day_count, np.nan, dtype=float)
    breadth_maxpos_arr = np.full(day_count, 0, dtype=np.int32)
    mf_enabled = False
    br_enabled = False
    breadth_enabled = False

    if str(route_id) != "provider_breakout_runtime":
        return RouteControls(
            mf_enabled=mf_enabled,
            mf_state_arr=mf_state_arr,
            mf_mult_arr=mf_mult_arr,
            br_enabled=br_enabled,
            br_gate_arr=br_gate_arr,
            breadth_enabled=breadth_enabled,
            breadth_score_arr=breadth_score_arr,
            breadth_maxpos_arr=breadth_maxpos_arr,
        )

    benchmark = data_bundle.benchmark
    day_ts_list = [pd.Timestamp(d).normalize() for d in data_bundle.trading_days]

    mf_enabled = bool(market_filter_cfg is not None and market_filter_cfg.enabled)
    if mf_enabled and not benchmark.empty:
        bench_df = benchmark.copy()
        bench_df["date"] = pd.to_datetime(bench_df["date"]).dt.normalize()
        bench_df = bench_df.sort_values("date")
        bench_close = pd.Series(
            pd.to_numeric(bench_df["close"], errors="coerce").to_numpy(dtype=float),
            index=bench_df["date"],
        ).reindex(day_ts_list)
        slope_window = max(1, int(market_filter_cfg.slope_window))
        slope_ma_period = max(2, int(getattr(market_filter_cfg, "slope_ma_period", 50)))
        ema_series = bench_close.ewm(span=slope_ma_period, adjust=False).mean()
        momentum = (ema_series - ema_series.shift(slope_window)) / ema_series.shift(slope_window)
        ma200 = bench_close.rolling(200, min_periods=200).mean()
        bench_close_arr = bench_close.to_numpy(dtype=float)
        momentum_arr = momentum.to_numpy(dtype=float)
        ma200_arr = ma200.to_numpy(dtype=float)
        valid = ~np.isnan(bench_close_arr) & ~np.isnan(momentum_arr) & ~np.isnan(ma200_arr)
        above = bench_close_arr > ma200_arr
        slope_pos = momentum_arr >= 0.0
        mf_state_arr = np.zeros(day_count, dtype=np.int8)
        mf_mult_arr = np.ones(day_count, dtype=float)
        mf_state_arr[valid & above & ~slope_pos] = 1
        mf_state_arr[valid & ~above & slope_pos] = 2
        mf_state_arr[valid & ~above & ~slope_pos] = 3
        mf_mult_arr[mf_state_arr == 0] = float(market_filter_cfg.bull_multiplier)
        td_mult = getattr(market_filter_cfg, "trans_down_multiplier", None)
        tu_mult = getattr(market_filter_cfg, "trans_up_multiplier", None)
        bear_mult = getattr(market_filter_cfg, "bear_multiplier", None)
        mf_mult_arr[mf_state_arr == 1] = float(td_mult if td_mult is not None else market_filter_cfg.light_multiplier)
        mf_mult_arr[mf_state_arr == 2] = float(tu_mult if tu_mult is not None else market_filter_cfg.light_multiplier)
        mf_mult_arr[mf_state_arr == 3] = float(bear_mult if bear_mult is not None else 0.0)

    br_enabled = bool(benchmark_regime_cfg is not None and benchmark_regime_cfg.enabled)
    if br_enabled and not benchmark.empty:
        bench_df = benchmark.copy()
        bench_df["date"] = pd.to_datetime(bench_df["date"]).dt.normalize()
        bench_df = bench_df.sort_values("date")
        bench_close = pd.Series(
            pd.to_numeric(bench_df["close"], errors="coerce").to_numpy(dtype=float),
            index=bench_df["date"],
        ).reindex(day_ts_list)
        fast = max(2, int(benchmark_regime_cfg.fast_period))
        slow = max(fast + 1, int(benchmark_regime_cfg.slow_period))
        slope_window = max(1, int(benchmark_regime_cfg.slope_window))
        ma_fast = bench_close.rolling(fast, min_periods=fast).mean()
        ma_slow = bench_close.rolling(slow, min_periods=slow).mean()
        slow_slope = ma_slow - ma_slow.shift(slope_window)
        allow = (ma_fast > ma_slow) & (slow_slope >= 0.0)
        br_gate_arr = allow.fillna(False).to_numpy(dtype=bool)

    breadth_enabled = bool(breadth_cfg is not None and breadth_cfg.enabled)
    if breadth_enabled:
        mx = getattr(provider, "_mx", None)
        close = getattr(mx, "close", None)
        tradable = getattr(mx, "tradable", None)
        if isinstance(close, np.ndarray) and isinstance(tradable, np.ndarray) and close.shape == tradable.shape and close.shape[0] == day_count:
            breadth = compute_breadth_scores(
                close=close,
                tradable=tradable.astype(bool),
                ema_fast_period=max(2, int(breadth_cfg.ema_fast)),
                ema_slow_period=max(int(breadth_cfg.ema_fast) + 1, int(breadth_cfg.ema_slow)),
            )
            score_type = str(breadth_cfg.score_type or "B").strip().upper()
            score_map = {
                "A": breadth.scores_A,
                "B": breadth.scores_B,
                "C": breadth.scores_C,
                "COMBO": breadth.scores_combo,
            }
            breadth_score_arr = np.array(score_map.get(score_type, breadth.scores_B), dtype=float)
            breadth_maxpos_arr = compute_dynamic_maxpos(
                scores=breadth_score_arr,
                mapping_mode=str(breadth_cfg.mapping_mode or "smooth"),
                min_pos=max(0, int(breadth_cfg.min_positions)),
                max_pos=max(0, int(breadth_cfg.max_positions)),
                step_high=float(breadth_cfg.step_high),
                step_mid=float(breadth_cfg.step_mid),
                smooth_lo=float(breadth_cfg.smooth_lo),
                smooth_range=max(float(breadth_cfg.smooth_range), 1e-6),
            ).astype(np.int32)
        else:
            breadth_enabled = False

    return RouteControls(
        mf_enabled=mf_enabled,
        mf_state_arr=mf_state_arr,
        mf_mult_arr=mf_mult_arr,
        br_enabled=br_enabled,
        br_gate_arr=br_gate_arr,
        breadth_enabled=breadth_enabled,
        breadth_score_arr=breadth_score_arr,
        breadth_maxpos_arr=breadth_maxpos_arr,
    )


def precompute_signal_provider(
    provider: SignalProvider,
    *,
    data_bundle: DataBundle,
    strategy: Any,
    exit_cfg: ExitConfig | None,
    strength_ma: int,
    initial_cash: float,
    max_positions: int,
    history_lookback_days: int | None,
    enable_multifactor_rank: bool,
    mf_rank_gate_mode: str,
    market_filter_cfg: MarketFilterConfig | None,
    benchmark_regime_cfg: BenchmarkRegimeConfig | None,
    sizing_cfg: SizingConfig | None,
    risk_budget_cfg: RiskBudgetConfig | None,
) -> None:
    provider.precompute(
        history=data_bundle.signal_history,
        benchmark=data_bundle.benchmark,
        raw_history=data_bundle.raw_history,
        trading_days=data_bundle.trading_days,
        strategy=strategy,
        exit_cfg=exit_cfg if exit_cfg is not None else ExitConfig(),
        st_history=data_bundle.st_history,
        strength_ma=int(strength_ma),
        base_order_value=float(initial_cash) / float(max(max_positions, 1)),
        sector_data=data_bundle.sector_data,
        industry_map=data_bundle.industry_map,
        industry_history=data_bundle.industry_history,
        membership_history=data_bundle.membership_history,
        history_lookback_days=history_lookback_days,
        enable_multifactor_rank=bool(enable_multifactor_rank),
        mf_rank_gate_mode=str(mf_rank_gate_mode or "ALWAYS_ON"),
        market_filter_cfg=market_filter_cfg,
        benchmark_regime_cfg=benchmark_regime_cfg,
        sizing_cfg=sizing_cfg,
        risk_budget_cfg=risk_budget_cfg,
        regime_filter_cfg=getattr(strategy, "regime_filter_cfg", None),
    )
