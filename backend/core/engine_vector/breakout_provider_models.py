"""Config/runtime owners for the breakout provider."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import numpy as np

from backend.core.config.models import ExitConfig


def _empty_float_array() -> np.ndarray:
    return np.array([], dtype=float)


def _empty_bool_array() -> np.ndarray:
    return np.array([], dtype=bool)


@dataclass(slots=True)
class BreakoutProviderConfig:
    breakout_window: int = 20
    enable_dual_breakout: bool = False
    breakout_window_short: int = 20
    breakout_window_long: int = 55
    dual_breakout_mode: str = "or"
    dual_breakout_gate_ma_window: int = 120
    dual_breakout_gate_slope_lookback: int = 10
    breakout_entry_buffer_pct: float = 0.0
    entry_confirm_mode: str = "none"
    entry_delay_mode: str = "none"
    enable_entry_above_slow_ma: bool = False
    enable_entry_slow_ma_slope: bool = False
    entry_slope_lookback: int = 5
    enable_atr_stop: bool = False
    enable_atr_trail: bool = False
    atr_stop_k: float = 2.0
    atr_trail_k: float = 3.0
    order_size: int = 1000
    regime_ma: int = 60
    max_hold_days: int = 0
    min_hold_days: int = 0
    cooldown_days: int = 0
    min_hold_exempt_reasons: tuple[str, ...] = ()
    enable_risk_off_exit: bool = False
    risk_off_exit_mode: str = "risk_on_off"
    risk_off_exit_partial_pct: float = 1.0
    risk_off_exit_partial_mode: str = "all_states"
    risk_off_exit_partial_only_if_profitable: bool = False
    risk_off_exit_trans_down_max_positions: int = 0
    risk_off_exit_trans_down_min_residual_score: float = 0.0
    enable_profit_decay_exit: bool = False
    profit_decay_exit_profit_pct: float = 0.15
    profit_decay_exit_min_hold_bars: int = 10
    profit_decay_exit_residual_score_threshold: float = 0.35
    enable_pullback_candidates: bool = False
    pullback_variant_mode: str = "pb_reclaim_ma20"
    pullback_touch_lookback: int = 12
    pullback_reclaim_window: int = 3
    pullback_ma20_touch_band_pct: float = 0.01
    pullback_low_lookback: int = 10
    pullback_low_band_pct: float = 0.02
    pullback_box_window: int = 5
    pullback_box_range_pct_max: float = 0.08
    enable_residual_ranking: bool = False
    residual_window: int = 60
    residual_benchmark_weight: float = 0.5
    residual_industry_weight: float = 0.5
    residual_weight_regime_mode: str = "off"
    residual_benchmark_weight_fallback: float = 0.5
    residual_industry_weight_fallback: float = 0.5
    ranking_mode: str = "none"
    leadership_route_bucket_count: int = 3
    breakout_quality_gate_min_score: float = 0.55
    breakout_quality_margin_cap_pct: float = 0.08
    breakout_quality_fade_cap_pct: float = 0.035
    breakout_quality_open_gap_cap_pct: float = 0.04
    residual_window_regime_mode: str = "off"
    residual_window_fallback: int = 60
    residual_window_regime_fast_ma: int = 120
    residual_window_regime_slow_ma: int = 200
    industry_relative_mode: str = "sector_proxy"
    industry_relative_regime_mode: str = "off"
    source_aware_residual_mode: str = "off"
    residual_refine_mode: str = "off"
    residual_refine_weight: float = 0.0
    industry_second_stage_min_industry_score: float = 0.85
    enable_sector_quality_ranking: bool = False
    sector_strength_window_short: int = 20
    sector_strength_window_long: int = 60
    volume_quality_window: int = 20
    residual_weight: float = 0.5
    sector_weight: float = 0.3
    quality_weight: float = 0.2
    enable_v2_trend_filter: bool = True
    v2_trend_short_ma: int = 20
    v2_trend_long_ma: int = 60
    strength_ma: int = 120
    base_order_value: float = 0.0
    min_price: float = 0.0
    min_list_days: int = 0
    min_avg_turnover_20d: float = 0.0


@dataclass(slots=True)
class BreakoutProviderRuntimeState:
    mx: Any = None
    feats: Any = None
    bench_close: np.ndarray = field(default_factory=_empty_float_array)
    risk_on: np.ndarray = field(default_factory=_empty_bool_array)
    strong_risk_on: np.ndarray = field(default_factory=_empty_bool_array)
    cand_idx: Any = None
    sym_to_col: dict[str, int] = field(default_factory=dict)


def build_breakout_provider_config(
    strategy: Any,
    *,
    kwargs: dict[str, Any],
) -> BreakoutProviderConfig:
    universe_filters = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
    breakout_window = int(getattr(strategy, "breakout_window", 20))
    residual_benchmark_weight = float(getattr(strategy, "residual_benchmark_weight", 0.5) or 0.0)
    residual_industry_weight = float(getattr(strategy, "residual_industry_weight", 0.5) or 0.0)
    residual_benchmark_weight_fallback = getattr(
        strategy,
        "residual_benchmark_weight_fallback",
        residual_benchmark_weight,
    )
    residual_industry_weight_fallback = getattr(
        strategy,
        "residual_industry_weight_fallback",
        residual_industry_weight,
    )
    return BreakoutProviderConfig(
        breakout_window=breakout_window,
        enable_dual_breakout=bool(getattr(strategy, "enable_dual_breakout", False)),
        breakout_window_short=int(getattr(strategy, "breakout_window_short", 20)),
        breakout_window_long=int(getattr(strategy, "breakout_window_long", max(breakout_window, 55))),
        dual_breakout_mode=str(getattr(strategy, "dual_breakout_mode", "or") or "or").strip().lower(),
        dual_breakout_gate_ma_window=int(getattr(strategy, "dual_breakout_gate_ma_window", 120)),
        dual_breakout_gate_slope_lookback=int(getattr(strategy, "dual_breakout_gate_slope_lookback", 10)),
        breakout_entry_buffer_pct=float(getattr(strategy, "breakout_entry_buffer_pct", 0.0)),
        entry_confirm_mode=str(getattr(strategy, "entry_confirm_mode", "none") or "none").strip().lower(),
        entry_delay_mode=str(getattr(strategy, "entry_delay_mode", "none") or "none").strip().lower(),
        enable_entry_above_slow_ma=bool(getattr(strategy, "enable_entry_above_slow_ma", False)),
        enable_entry_slow_ma_slope=bool(getattr(strategy, "enable_entry_slow_ma_slope", False)),
        entry_slope_lookback=int(getattr(strategy, "entry_slope_lookback", 5)),
        enable_atr_stop=bool(getattr(strategy, "enable_atr_stop", False)),
        enable_atr_trail=bool(getattr(strategy, "enable_atr_trail", False)),
        atr_stop_k=float(kwargs.get("atr_stop_k", getattr(strategy, "atr_stop_k", 2.0))),
        atr_trail_k=float(getattr(strategy, "atr_trail_k", 3.0)),
        order_size=int(getattr(strategy, "order_size", 1000)),
        regime_ma=int(getattr(strategy, "regime_ma", 60)),
        max_hold_days=int(getattr(strategy, "max_hold_days", 0)),
        min_hold_days=int(getattr(strategy, "min_hold_days", 0)),
        cooldown_days=int(getattr(strategy, "cooldown_days", 0)),
        min_hold_exempt_reasons=tuple(getattr(strategy, "min_hold_exempt_reasons", []) or ()),
        enable_risk_off_exit=bool(getattr(strategy, "enable_risk_off_exit", False)),
        risk_off_exit_mode=str(getattr(strategy, "risk_off_exit_mode", "risk_on_off") or "risk_on_off").strip().lower(),
        risk_off_exit_partial_pct=float(getattr(strategy, "risk_off_exit_partial_pct", 1.0) or 1.0),
        risk_off_exit_partial_mode=str(getattr(strategy, "risk_off_exit_partial_mode", "all_states") or "all_states").strip().lower(),
        risk_off_exit_partial_only_if_profitable=bool(getattr(strategy, "risk_off_exit_partial_only_if_profitable", False)),
        risk_off_exit_trans_down_max_positions=int(getattr(strategy, "risk_off_exit_trans_down_max_positions", 0) or 0),
        risk_off_exit_trans_down_min_residual_score=float(getattr(strategy, "risk_off_exit_trans_down_min_residual_score", 0.0) or 0.0),
        enable_profit_decay_exit=bool(getattr(strategy, "enable_profit_decay_exit", False)),
        profit_decay_exit_profit_pct=float(getattr(strategy, "profit_decay_exit_profit_pct", 0.15) or 0.15),
        profit_decay_exit_min_hold_bars=int(getattr(strategy, "profit_decay_exit_min_hold_bars", 10) or 10),
        profit_decay_exit_residual_score_threshold=float(
            getattr(strategy, "profit_decay_exit_residual_score_threshold", 0.35) or 0.35
        ),
        enable_pullback_candidates=bool(getattr(strategy, "enable_pullback_candidates", False)),
        pullback_variant_mode=str(getattr(strategy, "pullback_variant_mode", "pb_reclaim_ma20") or "pb_reclaim_ma20").strip().lower(),
        pullback_touch_lookback=int(getattr(strategy, "pullback_touch_lookback", 12)),
        pullback_reclaim_window=int(getattr(strategy, "pullback_reclaim_window", 3)),
        pullback_ma20_touch_band_pct=float(getattr(strategy, "pullback_ma20_touch_band_pct", 0.01)),
        pullback_low_lookback=int(getattr(strategy, "pullback_low_lookback", 10)),
        pullback_low_band_pct=float(getattr(strategy, "pullback_low_band_pct", 0.02)),
        pullback_box_window=int(getattr(strategy, "pullback_box_window", 5)),
        pullback_box_range_pct_max=float(getattr(strategy, "pullback_box_range_pct_max", 0.08)),
        enable_residual_ranking=bool(getattr(strategy, "enable_residual_ranking", False)),
        residual_window=int(getattr(strategy, "residual_window", 60)),
        residual_benchmark_weight=residual_benchmark_weight,
        residual_industry_weight=residual_industry_weight,
        residual_weight_regime_mode=str(getattr(strategy, "residual_weight_regime_mode", "off") or "off").strip().lower(),
        residual_benchmark_weight_fallback=float(
            residual_benchmark_weight
            if residual_benchmark_weight_fallback is None or float(residual_benchmark_weight_fallback) < 0.0
            else residual_benchmark_weight_fallback
        ),
        residual_industry_weight_fallback=float(
            residual_industry_weight
            if residual_industry_weight_fallback is None or float(residual_industry_weight_fallback) < 0.0
            else residual_industry_weight_fallback
        ),
        ranking_mode=str(getattr(strategy, "ranking_mode", "none") or "none").strip().lower(),
        leadership_route_bucket_count=max(2, int(getattr(strategy, "leadership_route_bucket_count", 3) or 3)),
        breakout_quality_gate_min_score=float(getattr(strategy, "breakout_quality_gate_min_score", 0.55) or 0.55),
        breakout_quality_margin_cap_pct=float(getattr(strategy, "breakout_quality_margin_cap_pct", 0.08) or 0.08),
        breakout_quality_fade_cap_pct=float(getattr(strategy, "breakout_quality_fade_cap_pct", 0.035) or 0.035),
        breakout_quality_open_gap_cap_pct=float(getattr(strategy, "breakout_quality_open_gap_cap_pct", 0.04) or 0.04),
        residual_window_regime_mode=str(getattr(strategy, "residual_window_regime_mode", "off") or "off").strip().lower(),
        residual_window_fallback=int(getattr(strategy, "residual_window_fallback", getattr(strategy, "residual_window", 60)) or getattr(strategy, "residual_window", 60)),
        residual_window_regime_fast_ma=int(getattr(strategy, "residual_window_regime_fast_ma", 120) or 120),
        residual_window_regime_slow_ma=int(getattr(strategy, "residual_window_regime_slow_ma", 200) or 200),
        industry_relative_mode=str(getattr(strategy, "industry_relative_mode", "sector_proxy") or "sector_proxy").strip().lower(),
        industry_relative_regime_mode=str(getattr(strategy, "industry_relative_regime_mode", "off") or "off").strip().lower(),
        source_aware_residual_mode=str(getattr(strategy, "source_aware_residual_mode", "off") or "off").strip().lower(),
        residual_refine_mode=str(getattr(strategy, "residual_refine_mode", "off") or "off").strip().lower(),
        residual_refine_weight=float(getattr(strategy, "residual_refine_weight", 0.0) or 0.0),
        industry_second_stage_min_industry_score=float(getattr(strategy, "industry_second_stage_min_industry_score", 0.85) or 0.0),
        enable_sector_quality_ranking=bool(getattr(strategy, "enable_sector_quality_ranking", False)),
        sector_strength_window_short=int(getattr(strategy, "sector_strength_window_short", 20)),
        sector_strength_window_long=int(getattr(strategy, "sector_strength_window_long", 60)),
        volume_quality_window=int(getattr(strategy, "volume_quality_window", 20)),
        residual_weight=float(getattr(strategy, "residual_weight", 0.5)),
        sector_weight=float(getattr(strategy, "sector_weight", 0.3)),
        quality_weight=float(getattr(strategy, "quality_weight", 0.2)),
        enable_v2_trend_filter=bool(getattr(strategy, "enable_v2_trend_filter", True)),
        v2_trend_short_ma=int(getattr(strategy, "v2_trend_short_ma", 20)),
        v2_trend_long_ma=int(getattr(strategy, "v2_trend_long_ma", 60)),
        strength_ma=int(kwargs.get("strength_ma", 120)),
        base_order_value=float(kwargs.get("base_order_value", 0.0)),
        min_price=float(universe_filters.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0),
        min_list_days=int(universe_filters.get("min_list_days", 0) or 0),
        min_avg_turnover_20d=float(universe_filters.get("min_avg_turnover_20d", 0.0) or 0.0),
    )


def apply_breakout_provider_config(
    provider: Any,
    config: BreakoutProviderConfig,
    *,
    exit_cfg: ExitConfig,
) -> None:
    provider._config = config
    provider._ec = exit_cfg
    for name, value in asdict(config).items():
        if name == "min_hold_exempt_reasons":
            provider._min_hold_exempt_set = set(value)
            continue
        setattr(provider, f"_{name}", value)


def capture_breakout_runtime_state(provider: Any) -> BreakoutProviderRuntimeState:
    state = BreakoutProviderRuntimeState(
        mx=provider._mx,
        feats=provider._feats,
        bench_close=provider._bench_close,
        risk_on=provider._risk_on,
        strong_risk_on=provider._strong_risk_on,
        cand_idx=provider._cand_idx,
        sym_to_col=dict(provider._sym_to_col),
    )
    provider._runtime_state = state
    return state
