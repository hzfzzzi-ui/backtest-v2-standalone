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


def _empty_object_array() -> np.ndarray:
    return np.array([], dtype=object)


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
    enable_peak_giveback_ma20_exit: bool = False
    peak_giveback_ma20_min_peak_profit_pct: float = 0.20
    peak_giveback_ma20_min_giveback_pct: float = 0.25
    peak_giveback_ma20_min_hold_bars: int = 10
    peak_giveback_ma20_exit_pct: float = 0.5
    enable_mfe_mae_confirmation_exit: bool = False
    mfe_mae_confirmation_lookahead_bars: int = 3
    mfe_mae_confirmation_min_mfe_pct: float = 0.02
    mfe_mae_confirmation_max_mae_pct: float = -0.05
    mfe_mae_confirmation_exit_pct: float = 0.5
    mfe_mae_confirmation_scope: str = "all"
    mfe_mae_confirmation_action: str = "exit"
    mfe_mae_high_chase_min_core_flags: int = 2
    mfe_mae_high_chase_ret5_pct: float = 0.20
    mfe_mae_high_chase_ret10_pct: float = 0.30
    mfe_mae_high_chase_ret20_pct: float = 0.45
    mfe_mae_high_chase_ma20_extension_pct: float = 0.27
    mfe_mae_high_chase_ma60_extension_pct: float = 0.45
    mfe_mae_high_chase_atr_extension: float = 4.5
    mfe_mae_high_chase_breakout_margin_pct: float = 0.05
    mfe_mae_high_chase_open_gap_pct: float = 0.024
    mfe_mae_high_chase_fade_pct: float = 0.025
    mfe_mae_high_chase_breakout_quality_max: float = 0.46
    mfe_mae_high_chase_volume_price_quality_max: float = 0.08
    mfe_mae_watch_review_bars: int = 10
    mfe_mae_watch_review_min_mfe_pct: float = 0.02
    mfe_mae_watch_review_max_current_return_pct: float = 0.0
    mfe_mae_watch_review_max_mae_pct: float = -0.05
    mfe_mae_watch_deep_mae_immediate_pct: float = -0.08
    enable_mfe_mae_restore_candidate: bool = False
    mfe_mae_restore_candidate_scope: str = "high_chase"
    mfe_mae_restore_candidate_max_bars: int = 40
    mfe_mae_restore_candidate_target_basis: str = "original_target"
    mfe_mae_restore_candidate_clear_on_fill: bool = True
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
    bull_breakout_quality_veto_enabled: bool = False
    bull_breakout_quality_veto_min_residual_strength_score: float = 0.0
    bull_breakout_quality_veto_min_breakout_margin_score: float = 0.0
    bad_breakout_quality_veto_enabled: bool = False
    bad_breakout_quality_ret5_rank_min: float = 0.80
    bad_breakout_quality_r2_60_rank_max: float = 0.20
    trend_quality_soft_score_enabled: bool = False
    trend_quality_soft_score_weight: float = 0.30
    trend_quality_r2_60_weight: float = 0.45
    trend_quality_slope60_weight: float = 0.25
    trend_quality_ret60_vol_adj_weight: float = 0.15
    trend_quality_ret60_dd_adj_weight: float = 0.15
    risk_archetype_soft_deprioritize_enabled: bool = False
    risk_archetype_soft_deprioritize_quantile: float = 0.80
    risk_archetype_hot_crowded_penalty: float = 0.20
    risk_archetype_high_volatility_penalty: float = 0.15
    entry_risk_position_sizing_enabled: bool = False
    entry_risk_position_watch_scale: float = 0.80
    entry_risk_position_high_scale: float = 0.50
    entry_risk_position_extreme_scale: float = 1.0 / 3.0
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
    csi1000_new_min_circ_mv_yi: float = 0.0


@dataclass(slots=True)
class BreakoutProviderRuntimeState:
    mx: Any = None
    feats: Any = None
    bench_close: np.ndarray = field(default_factory=_empty_float_array)
    risk_on: np.ndarray = field(default_factory=_empty_bool_array)
    strong_risk_on: np.ndarray = field(default_factory=_empty_bool_array)
    cand_idx: Any = None
    sym_to_col: dict[str, int] = field(default_factory=dict)
    regime_engine: str = "ma200_legacy"
    formal_regime_features: Any = None
    required_feature_blocks_ready: np.ndarray = field(default_factory=_empty_bool_array)
    regime_confidence: np.ndarray = field(default_factory=_empty_float_array)
    regime_duration_bars: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int32))
    regime_transition_reason: np.ndarray = field(default_factory=lambda: np.array([], dtype=object))
    feature_availability: np.ndarray = field(default_factory=lambda: np.array([], dtype=object))
    fallback_active: np.ndarray = field(default_factory=_empty_bool_array)
    base_state_5: np.ndarray = field(default_factory=_empty_object_array)
    effective_state_5: np.ndarray = field(default_factory=_empty_object_array)
    coarse_state: np.ndarray = field(default_factory=_empty_object_array)
    effective_coarse_state: np.ndarray = field(default_factory=_empty_object_array)
    reason_codes: np.ndarray = field(default_factory=_empty_object_array)
    block_scores: np.ndarray = field(default_factory=_empty_object_array)
    subscores: np.ndarray = field(default_factory=_empty_object_array)
    manual_override: np.ndarray = field(default_factory=_empty_object_array)
    state_stability_metrics: np.ndarray = field(default_factory=_empty_object_array)
    regime_risk_budget_multiplier: np.ndarray = field(default_factory=_empty_float_array)
    defense_bias: np.ndarray = field(default_factory=_empty_float_array)


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
    bad_breakout_quality_ret5_rank_min = getattr(
        strategy,
        "bad_breakout_quality_ret5_rank_min",
        0.80,
    )
    bad_breakout_quality_r2_60_rank_max = getattr(
        strategy,
        "bad_breakout_quality_r2_60_rank_max",
        0.20,
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
        enable_peak_giveback_ma20_exit=bool(getattr(strategy, "enable_peak_giveback_ma20_exit", False)),
        peak_giveback_ma20_min_peak_profit_pct=float(
            getattr(strategy, "peak_giveback_ma20_min_peak_profit_pct", 0.20) or 0.20
        ),
        peak_giveback_ma20_min_giveback_pct=float(
            getattr(strategy, "peak_giveback_ma20_min_giveback_pct", 0.25) or 0.25
        ),
        peak_giveback_ma20_min_hold_bars=int(getattr(strategy, "peak_giveback_ma20_min_hold_bars", 10) or 10),
        peak_giveback_ma20_exit_pct=float(getattr(strategy, "peak_giveback_ma20_exit_pct", 0.5) or 0.5),
        enable_mfe_mae_confirmation_exit=bool(getattr(strategy, "enable_mfe_mae_confirmation_exit", False)),
        mfe_mae_confirmation_lookahead_bars=int(
            getattr(strategy, "mfe_mae_confirmation_lookahead_bars", 3) or 3
        ),
        mfe_mae_confirmation_min_mfe_pct=float(
            getattr(strategy, "mfe_mae_confirmation_min_mfe_pct", 0.02) or 0.02
        ),
        mfe_mae_confirmation_max_mae_pct=float(
            getattr(strategy, "mfe_mae_confirmation_max_mae_pct", -0.05)
        ),
        mfe_mae_confirmation_exit_pct=float(
            getattr(strategy, "mfe_mae_confirmation_exit_pct", 0.5) or 0.5
        ),
        mfe_mae_confirmation_scope=str(
            getattr(strategy, "mfe_mae_confirmation_scope", "all") or "all"
        ).strip().lower(),
        mfe_mae_confirmation_action=str(
            getattr(strategy, "mfe_mae_confirmation_action", "exit") or "exit"
        ).strip().lower(),
        mfe_mae_high_chase_min_core_flags=int(
            getattr(strategy, "mfe_mae_high_chase_min_core_flags", 2) or 2
        ),
        mfe_mae_high_chase_ret5_pct=float(
            getattr(strategy, "mfe_mae_high_chase_ret5_pct", 0.20) or 0.20
        ),
        mfe_mae_high_chase_ret10_pct=float(
            getattr(strategy, "mfe_mae_high_chase_ret10_pct", 0.30) or 0.30
        ),
        mfe_mae_high_chase_ret20_pct=float(
            getattr(strategy, "mfe_mae_high_chase_ret20_pct", 0.45) or 0.45
        ),
        mfe_mae_high_chase_ma20_extension_pct=float(
            getattr(strategy, "mfe_mae_high_chase_ma20_extension_pct", 0.27) or 0.27
        ),
        mfe_mae_high_chase_ma60_extension_pct=float(
            getattr(strategy, "mfe_mae_high_chase_ma60_extension_pct", 0.45) or 0.45
        ),
        mfe_mae_high_chase_atr_extension=float(
            getattr(strategy, "mfe_mae_high_chase_atr_extension", 4.5) or 4.5
        ),
        mfe_mae_high_chase_breakout_margin_pct=float(
            getattr(strategy, "mfe_mae_high_chase_breakout_margin_pct", 0.05) or 0.05
        ),
        mfe_mae_high_chase_open_gap_pct=float(
            getattr(strategy, "mfe_mae_high_chase_open_gap_pct", 0.024) or 0.024
        ),
        mfe_mae_high_chase_fade_pct=float(
            getattr(strategy, "mfe_mae_high_chase_fade_pct", 0.025) or 0.025
        ),
        mfe_mae_high_chase_breakout_quality_max=float(
            getattr(strategy, "mfe_mae_high_chase_breakout_quality_max", 0.46) or 0.46
        ),
        mfe_mae_high_chase_volume_price_quality_max=float(
            getattr(strategy, "mfe_mae_high_chase_volume_price_quality_max", 0.08) or 0.08
        ),
        mfe_mae_watch_review_bars=int(getattr(strategy, "mfe_mae_watch_review_bars", 10) or 10),
        mfe_mae_watch_review_min_mfe_pct=float(
            getattr(strategy, "mfe_mae_watch_review_min_mfe_pct", 0.02) or 0.02
        ),
        mfe_mae_watch_review_max_current_return_pct=float(
            getattr(strategy, "mfe_mae_watch_review_max_current_return_pct", 0.0)
        ),
        mfe_mae_watch_review_max_mae_pct=float(
            getattr(strategy, "mfe_mae_watch_review_max_mae_pct", -0.05)
        ),
        mfe_mae_watch_deep_mae_immediate_pct=float(
            getattr(strategy, "mfe_mae_watch_deep_mae_immediate_pct", -0.08)
        ),
        enable_mfe_mae_restore_candidate=bool(
            getattr(strategy, "enable_mfe_mae_restore_candidate", False)
        ),
        mfe_mae_restore_candidate_scope=str(
            getattr(strategy, "mfe_mae_restore_candidate_scope", "high_chase") or "high_chase"
        ).strip().lower(),
        mfe_mae_restore_candidate_max_bars=int(
            getattr(strategy, "mfe_mae_restore_candidate_max_bars", 40) or 40
        ),
        mfe_mae_restore_candidate_target_basis=str(
            getattr(strategy, "mfe_mae_restore_candidate_target_basis", "original_target") or "original_target"
        ).strip().lower(),
        mfe_mae_restore_candidate_clear_on_fill=bool(
            getattr(strategy, "mfe_mae_restore_candidate_clear_on_fill", True)
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
        bull_breakout_quality_veto_enabled=bool(getattr(strategy, "bull_breakout_quality_veto_enabled", False)),
        bull_breakout_quality_veto_min_residual_strength_score=float(
            getattr(strategy, "bull_breakout_quality_veto_min_residual_strength_score", 0.0) or 0.0
        ),
        bull_breakout_quality_veto_min_breakout_margin_score=float(
            getattr(strategy, "bull_breakout_quality_veto_min_breakout_margin_score", 0.0) or 0.0
        ),
        bad_breakout_quality_veto_enabled=bool(getattr(strategy, "bad_breakout_quality_veto_enabled", False)),
        bad_breakout_quality_ret5_rank_min=float(
            0.80 if bad_breakout_quality_ret5_rank_min is None else bad_breakout_quality_ret5_rank_min
        ),
        bad_breakout_quality_r2_60_rank_max=float(
            0.20 if bad_breakout_quality_r2_60_rank_max is None else bad_breakout_quality_r2_60_rank_max
        ),
        trend_quality_soft_score_enabled=bool(getattr(strategy, "trend_quality_soft_score_enabled", False)),
        trend_quality_soft_score_weight=float(getattr(strategy, "trend_quality_soft_score_weight", 0.30) or 0.0),
        trend_quality_r2_60_weight=float(getattr(strategy, "trend_quality_r2_60_weight", 0.45) or 0.0),
        trend_quality_slope60_weight=float(getattr(strategy, "trend_quality_slope60_weight", 0.25) or 0.0),
        trend_quality_ret60_vol_adj_weight=float(
            getattr(strategy, "trend_quality_ret60_vol_adj_weight", 0.15) or 0.0
        ),
        trend_quality_ret60_dd_adj_weight=float(
            getattr(strategy, "trend_quality_ret60_dd_adj_weight", 0.15) or 0.0
        ),
        risk_archetype_soft_deprioritize_enabled=bool(
            getattr(strategy, "risk_archetype_soft_deprioritize_enabled", False)
        ),
        risk_archetype_soft_deprioritize_quantile=float(
            getattr(strategy, "risk_archetype_soft_deprioritize_quantile", 0.80) or 0.80
        ),
        risk_archetype_hot_crowded_penalty=float(
            getattr(strategy, "risk_archetype_hot_crowded_penalty", 0.20) or 0.0
        ),
        risk_archetype_high_volatility_penalty=float(
            getattr(strategy, "risk_archetype_high_volatility_penalty", 0.15) or 0.0
        ),
        entry_risk_position_sizing_enabled=bool(
            getattr(strategy, "entry_risk_position_sizing_enabled", False)
        ),
        entry_risk_position_watch_scale=float(
            getattr(strategy, "entry_risk_position_watch_scale", 0.80) or 0.0
        ),
        entry_risk_position_high_scale=float(
            getattr(strategy, "entry_risk_position_high_scale", 0.50) or 0.0
        ),
        entry_risk_position_extreme_scale=float(
            getattr(strategy, "entry_risk_position_extreme_scale", 1.0 / 3.0) or 0.0
        ),
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
        csi1000_new_min_circ_mv_yi=float(universe_filters.get("csi1000_new_min_circ_mv_yi", 0.0) or 0.0),
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
        regime_engine=str(getattr(provider, "_regime_engine_name", "ma200_legacy") or "ma200_legacy"),
        formal_regime_features=getattr(provider, "_formal_regime_features", None),
        required_feature_blocks_ready=np.array(
            getattr(provider, "_required_feature_blocks_ready", np.array([], dtype=bool)),
            dtype=bool,
        ),
        regime_confidence=np.array(
            getattr(provider, "_regime_confidence_arr", np.array([], dtype=float)),
            dtype=float,
        ),
        regime_duration_bars=np.array(
            getattr(provider, "_regime_duration_bars_arr", np.array([], dtype=np.int32)),
            dtype=np.int32,
        ),
        regime_transition_reason=np.array(
            getattr(provider, "_regime_transition_reason_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        feature_availability=np.array(
            getattr(provider, "_feature_availability_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        fallback_active=np.array(
            getattr(provider, "_fallback_active_arr", np.array([], dtype=bool)),
            dtype=bool,
        ),
        base_state_5=np.array(
            getattr(provider, "_base_state_5_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        effective_state_5=np.array(
            getattr(provider, "_effective_state_5_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        coarse_state=np.array(
            getattr(provider, "_coarse_state_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        effective_coarse_state=np.array(
            getattr(provider, "_effective_coarse_state_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        reason_codes=np.array(
            getattr(provider, "_reason_codes_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        block_scores=np.array(
            getattr(provider, "_block_scores_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        subscores=np.array(
            getattr(provider, "_subscores_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        manual_override=np.array(
            getattr(provider, "_manual_override_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        state_stability_metrics=np.array(
            getattr(provider, "_state_stability_metrics_arr", np.array([], dtype=object)),
            dtype=object,
        ),
        regime_risk_budget_multiplier=np.array(
            getattr(provider, "_regime_risk_budget_multiplier_arr", np.array([], dtype=float)),
            dtype=float,
        ),
        defense_bias=np.array(
            getattr(provider, "_defense_bias_arr", np.array([], dtype=float)),
            dtype=float,
        ),
    )
    provider._runtime_state = state
    return state
