from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from ._utils import _hash_json, sanitize_json


SEMANTIC_CONFIG_SCHEMA_VERSION = "2026-03-11"
_SUPPORTED_MULTI_ALPHA_MODULES = frozenset({"breakout_55", "rsi_reversal"})
_SUPPORTED_MULTI_ALPHA_COMPOSE_MODES = frozenset({"REGIME_ROUTE"})
_SUPPORTED_MULTI_ALPHA_SAME_SYMBOL_POLICIES = frozenset({"PREFER_HIGHER_SCORE"})
_SUPPORTED_MULTI_ALPHA_HOLDING_OWNERSHIP = frozenset({"SOURCE_ONLY"})


class StrictModel(BaseModel):
    class Config:
        extra = "forbid"


class UniverseFiltersConfig(StrictModel):
    exclude_st: bool | None = None
    exclude_delisted: bool | None = None
    exclude_suspended: bool | None = None
    min_list_days: int | None = None
    min_avg_turnover_20d: float | None = None
    min_avg_turnover_rate_20d: float | None = None
    turnover_rate_field: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    atr_pct_range: str | None = None
    limit_rule: str | None = None


class UniverseConfig(StrictModel):
    start: str | None = None
    end: str | None = None
    benchmark: str | None = None
    symbols: list[str] | None = None
    limit: int | None = None
    price_adj: str | None = None
    membership_mode: str | None = None
    allow_low_fidelity_history: bool | None = None
    filters: UniverseFiltersConfig | None = None


class RegimeFilterConfig(StrictModel):
    enabled: bool | None = None
    regime_threshold: float | None = None
    alpha_m: float | None = None
    alpha_sec: float | None = None
    alpha_i: float | None = None


class RegimeDetectionConfig(StrictModel):
    enabled: bool | None = None
    regime_ma: int | None = None
    regime_filter: RegimeFilterConfig | None = None


class TrendSignalConfig(StrictModel):
    strategy: str | None = None
    fast_ma: int | None = None
    slow_ma: int | None = None
    entry_buffer_pct: float | None = None


class MeanReversionConfig(StrictModel):
    strategy: str | None = None
    rsi_period: int | None = None
    rsi_buy_threshold: float | None = None
    rsi_sell_threshold: float | None = None
    mr_max_hold_days: int | None = None
    mr_stop_loss_pct: float | None = None


class MaSignalConfig(StrictModel):
    fast_ma: int | None = None
    slow_ma: int | None = None
    entry_buffer_pct: float | None = None


class BreakoutSignalConfig(StrictModel):
    breakout_window: int | None = None
    enable_dual_breakout: bool | None = None
    breakout_window_short: int | None = None
    breakout_window_long: int | None = None
    dual_breakout_mode: str | None = None
    dual_breakout_gate_ma_window: int | None = None
    dual_breakout_gate_slope_lookback: int | None = None
    breakout_entry_buffer_pct: float | None = None
    entry_confirm_mode: str | None = None
    entry_delay_mode: str | None = None
    entry_gap_guard_enabled: bool | None = None
    entry_gap_guard_pct: float | None = None
    enable_pullback_candidates: bool | None = None
    pullback_variant_mode: str | None = None
    pullback_touch_lookback: int | None = None
    pullback_reclaim_window: int | None = None
    pullback_ma20_touch_band_pct: float | None = None
    pullback_low_lookback: int | None = None
    pullback_low_band_pct: float | None = None
    pullback_box_window: int | None = None
    pullback_box_range_pct_max: float | None = None


class EntryFilterConfig(StrictModel):
    enable_entry_above_slow_ma: bool | None = None
    enable_entry_slow_ma_slope: bool | None = None
    entry_slope_lookback: int | None = None


class RankingConfig(StrictModel):
    momentum_top_pct: float | None = None
    score_source_mode: str | None = None
    residual_window: int | None = None
    leadership_route_bucket_count: int | None = None
    residual_benchmark_weight: float | None = None
    residual_industry_weight: float | None = None
    industry_relative_mode: str | None = None
    industry_relative_regime_mode: str | None = None
    residual_weight_regime_mode: str | None = None
    residual_benchmark_weight_fallback: float | None = None
    residual_industry_weight_fallback: float | None = None
    breakout_quality_gate_min_score: float | None = None
    breakout_quality_margin_cap_pct: float | None = None
    breakout_quality_fade_cap_pct: float | None = None
    breakout_quality_open_gap_cap_pct: float | None = None
    residual_window_regime_mode: str | None = None
    residual_window_fallback: int | None = None
    residual_window_regime_fast_ma: int | None = None
    residual_window_regime_slow_ma: int | None = None
    source_aware_residual_mode: str | None = None
    residual_refine_mode: str | None = None
    residual_refine_weight: float | None = None
    industry_second_stage_min_industry_score: float | None = None
    residual_weight: float | None = None
    sector_weight: float | None = None
    quality_weight: float | None = None
    enable_strength_rank: bool | None = None
    strength_ma: int | None = None
    strength_top_k_mode: str | None = None
    enable_multifactor_rank: bool | None = None
    mf_topk: int | None = None
    mf_concentrate_scale: float | None = None
    mf_rank_gate_mode: str | None = None


class SignalGenerationModuleConfig(StrictModel):
    name: str
    enabled: bool | None = None
    alpha_id: str | None = None
    family: str | None = None
    params: dict[str, Any] | None = None


class SignalGenerationConfig(StrictModel):
    enabled: bool | None = None
    strategy: str | None = None
    modules: list[SignalGenerationModuleConfig] | None = None
    regime_detection: RegimeDetectionConfig | None = None
    trend: TrendSignalConfig | None = None
    mr: MeanReversionConfig | None = None
    sma: MaSignalConfig | None = None
    ema: MaSignalConfig | None = None
    breakout: BreakoutSignalConfig | None = None
    entry_filter: EntryFilterConfig | None = None
    ranking: RankingConfig | None = None


class BenchmarkRegimeConfig(StrictModel):
    enabled: bool | None = None
    fast_period: int | None = None
    slow_period: int | None = None
    slope_window: int | None = None


class StockTrendFilterConfig(StrictModel):
    enabled: bool | None = None
    short_ma: int | None = None
    long_ma: int | None = None


class SectorGateConfig(StrictModel):
    enabled: bool | None = None
    rank_window: int | None = None
    top_pct: float | None = None


class SignalCompositionModuleConfig(StrictModel):
    name: str
    enabled: bool | None = None
    role: str | None = None
    weight: float | None = None
    priority: int | None = None


class SignalCompositionConfig(StrictModel):
    enabled: bool | None = None
    compose_mode: str | None = None
    modules: list[SignalCompositionModuleConfig] | None = None
    regime_matrix: dict[str, list[str]] | None = None
    same_symbol_policy: str | None = None
    holding_ownership: str | None = None
    score_threshold: float | None = None


class AtrStopConfig(StrictModel):
    enabled: bool | None = None
    k: float | None = None


class TrailingExitConfig(StrictModel):
    enabled: bool | None = None
    k: float | None = None
    activate_profit_pct: float | None = None
    segmented_trend_exit_mode: str | None = None
    segmented_mid_profit_pct: float | None = None
    segmented_high_profit_pct: float | None = None
    segmented_high_trail_k: float | None = None
    pre_profit_breakout_failure_enabled: bool | None = None
    pre_profit_breakout_failure_max_bars: int | None = None
    pre_profit_breakout_failure_atr_buffer_k: float | None = None
    profit_decay_exit_enabled: bool | None = None
    profit_decay_exit_profit_pct: float | None = None
    profit_decay_exit_min_hold_bars: int | None = None
    profit_decay_exit_residual_score_threshold: float | None = None


class TimeExitConfig(StrictModel):
    enabled: bool | None = None
    n_days: int | None = None


class HoldConstraintConfig(StrictModel):
    min_hold_days: int | None = None
    cooldown_days: int | None = None


class TakeProfitConfig(StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    pct: float | None = None
    atr_k: float | None = None


class FixedStopConfig(StrictModel):
    enabled: bool | None = None
    pct: float | None = None


class ToggleConfig(StrictModel):
    enabled: bool | None = None


class RiskOffExitConfig(StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    partial_pct: float | None = None
    partial_mode: str | None = None
    partial_only_if_profitable: bool | None = None
    trans_down_max_positions: int | None = None
    trans_down_min_residual_score: float | None = None


class ExitRulesConfig(StrictModel):
    enabled: bool | None = None
    signal_reverse: bool | None = None
    atr_stop: AtrStopConfig | None = None
    trailing: TrailingExitConfig | None = None
    time_exit: TimeExitConfig | None = None
    hold_constraint: HoldConstraintConfig | None = None
    take_profit: TakeProfitConfig | None = None
    fixed_stop: FixedStopConfig | None = None
    ma20_exit: ToggleConfig | None = None
    low10_exit: ToggleConfig | None = None
    risk_off_exit: RiskOffExitConfig | None = None


class UniverseFilterConfig(StrictModel):
    min_price: float | None = None


class RiskBudgetConfig(StrictModel):
    enabled: bool | None = None
    dd_reduce_pct: float | None = None
    dd_reduce_scale: float | None = None
    atr_stop_k: float | None = None
    base_portfolio_risk: float | None = None
    min_active_ratio: float | None = None
    dd_scale_10: float | None = None
    dd_scale_15: float | None = None
    dd_fixed_20: float | None = None
    dd_stop_pct: float | None = None
    dd_stop_cooldown_days: int | None = None
    dd_stop_protect_days: int | None = None


class MarketFilterConfig(StrictModel):
    enabled: bool | None = None
    slope_ma_period: int | None = None
    slope_window: int | None = None
    bull_multiplier: float | None = None
    light_multiplier: float | None = None
    trans_down_multiplier: float | None = None
    trans_up_multiplier: float | None = None
    bear_multiplier: float | None = None
    ema_light_fast: int | None = None
    ema_light_slow: int | None = None


class BreadthConfig(StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    score_type: str | None = None
    mapping_mode: str | None = None
    min_positions: int | None = None
    max_positions: int | None = None
    step_high: float | None = None
    step_mid: float | None = None
    smooth_lo: float | None = None
    smooth_range: float | None = None
    ema_fast: int | None = None
    ema_slow: int | None = None
    gate_threshold: float | None = None
    gate_quantile_window: int | None = None
    gate_quantile_pct: float | None = None
    gate_persist_days: int | None = None
    size_scale_floor: float | None = None


class CostModelConfig(StrictModel):
    commission: str | None = None
    stamp_tax: str | None = None
    slippage: str | None = None
    matching: str | None = None


class PositionRiskConfig(StrictModel):
    enabled: bool | None = None
    max_positions: int | None = None
    single_stock_cap: float | None = None
    industry_cap: float | None = None
    lot: int | None = None
    cash_shortage_policy: str | None = None
    portfolio_mode: str | None = None
    risk_budget: RiskBudgetConfig | None = None
    market_filter: MarketFilterConfig | None = None
    breadth: BreadthConfig | None = None
    cost_model: CostModelConfig | None = None


class SizingConfig(StrictModel):
    weight_mode: str | None = None
    min_positions: int | None = None
    tilt_strength: float | None = None
    tilt_top_n: int | None = None
    tilt_bottom_n: int | None = None
    score_weight_min_scale: float | None = None
    score_weight_max_scale: float | None = None
    candidate_plan_mode: str | None = None
    cash_aware_search_top_n: int | None = None
    rotation_replace_enabled: bool | None = None
    rotation_replace_only_strong_risk_on: bool | None = None
    rotation_replace_max_swaps_per_day: int | None = None
    rotation_replace_candidate_top_n: int | None = None
    rotation_replace_min_score_gap: float | None = None


class FlowScriptConfig(StrictModel):
    script_id: str | None = None
    description: str | None = None
    recommended_preset: str | None = None


class FrontendSemanticConfig(StrictModel):
    mode: str | None = None
    initial_capital: float | None = None
    strategy_pack: str | None = None
    universe_mode: str | None = None
    industries: list[str] | None = None
    universe: UniverseConfig | None = None
    signal_generation: SignalGenerationConfig | None = None
    benchmark_regime: BenchmarkRegimeConfig | None = None
    stock_trend_filter: StockTrendFilterConfig | None = None
    sector_gate: SectorGateConfig | None = None
    signal_composition: SignalCompositionConfig | None = None
    exit_rules: ExitRulesConfig | None = None
    universe_filter: UniverseFilterConfig | None = None
    position_risk: PositionRiskConfig | None = None
    sizing: SizingConfig | None = None
    flow_script: FlowScriptConfig | None = None
    exit_priority: list[str] | None = None


def _build_error(path: str, message: str) -> dict[str, str]:
    return {"path": path, "message": message}


def _normalized_strategy(raw: dict[str, Any]) -> str:
    signal_generation = raw.get("signal_generation") if isinstance(raw.get("signal_generation"), dict) else {}
    candidates = [
        signal_generation.get("strategy"),
        raw.get("strategy_pack"),
    ]
    for value in candidates:
        text = str(value or "").strip().upper()
        if text:
            return text
    return ""


def _normalized_option(value: Any) -> str:
    return str(value or "").strip().upper()


def _validate_semantic_logic(raw: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    signal_generation = raw.get("signal_generation") if isinstance(raw.get("signal_generation"), dict) else {}
    signal_composition = raw.get("signal_composition") if isinstance(raw.get("signal_composition"), dict) else {}
    ranking = signal_generation.get("ranking") if isinstance(signal_generation.get("ranking"), dict) else {}
    exit_rules = raw.get("exit_rules") if isinstance(raw.get("exit_rules"), dict) else {}
    risk_off_exit = exit_rules.get("risk_off_exit") if isinstance(exit_rules.get("risk_off_exit"), dict) else {}
    sizing = raw.get("sizing") if isinstance(raw.get("sizing"), dict) else {}
    strategy = _normalized_strategy(raw)

    if strategy and not signal_generation:
        errors.append(_build_error("signal_generation", "required when strategy_pack or signal_generation.strategy is set"))
        return errors

    if strategy == "BREAKOUT_TREND" and not isinstance(signal_generation.get("breakout"), dict):
        errors.append(_build_error("signal_generation.breakout", "required for BREAKOUT_TREND"))
    if strategy == "SMA_CROSS" and not isinstance(signal_generation.get("sma"), dict):
        errors.append(_build_error("signal_generation.sma", "required for SMA_CROSS"))
    if strategy == "EMA_CROSS" and not isinstance(signal_generation.get("ema"), dict):
        errors.append(_build_error("signal_generation.ema", "required for EMA_CROSS"))
    if strategy == "REGIME_ROUTER":
        if not isinstance(signal_generation.get("regime_detection"), dict):
            errors.append(_build_error("signal_generation.regime_detection", "required for REGIME_ROUTER"))
        if not isinstance(signal_generation.get("trend"), dict):
            errors.append(_build_error("signal_generation.trend", "required for REGIME_ROUTER"))
        if not isinstance(signal_generation.get("mr"), dict):
            errors.append(_build_error("signal_generation.mr", "required for REGIME_ROUTER"))
    breakout = signal_generation.get("breakout") if isinstance(signal_generation.get("breakout"), dict) else {}
    if breakout.get("entry_gap_guard_pct") is not None:
        try:
            entry_gap_guard_pct = float(breakout.get("entry_gap_guard_pct"))
        except Exception:
            entry_gap_guard_pct = 0.0
        if entry_gap_guard_pct <= 0.0:
            errors.append(
                _build_error(
                    "signal_generation.breakout.entry_gap_guard_pct",
                    "entry_gap_guard_pct must be > 0",
                )
            )

    ranking_mode = _normalized_option(ranking.get("score_source_mode"))
    if ranking_mode and ranking_mode not in {
        "NONE",
        "RESIDUAL_ONLY",
        "RESIDUAL_QUALITY",
        "SECTOR_QUALITY",
        "PROVIDER_FINAL",
        "QUALITY_THEN_RESIDUAL",
        "LEADERSHIP_THEN_RESIDUAL",
    }:
        errors.append(
            _build_error(
                "signal_generation.ranking.score_source_mode",
                f"unsupported ranking score_source_mode: {ranking_mode}",
            )
        )
    if ranking.get("breakout_quality_gate_min_score") is not None:
        try:
            gate_min_score = float(ranking.get("breakout_quality_gate_min_score"))
        except Exception:
            gate_min_score = -1.0
        if not (0.0 <= gate_min_score <= 1.0):
            errors.append(
                _build_error(
                    "signal_generation.ranking.breakout_quality_gate_min_score",
                    "breakout_quality_gate_min_score must be within [0, 1]",
                )
            )
    for cap_key in (
        "breakout_quality_margin_cap_pct",
        "breakout_quality_fade_cap_pct",
        "breakout_quality_open_gap_cap_pct",
    ):
        if ranking.get(cap_key) is None:
            continue
        try:
            cap_value = float(ranking.get(cap_key))
        except Exception:
            cap_value = -1.0
        if cap_value <= 0.0:
            errors.append(
                _build_error(
                    f"signal_generation.ranking.{cap_key}",
                    f"{cap_key} must be > 0",
                )
            )
    if ranking.get("residual_window") is not None:
        try:
            residual_window = int(ranking.get("residual_window"))
        except Exception:
            residual_window = 0
        if residual_window < 2:
            errors.append(
                _build_error(
                    "signal_generation.ranking.residual_window",
                    "residual_window must be >= 2",
                )
            )
    if ranking.get("leadership_route_bucket_count") is not None:
        try:
            leadership_route_bucket_count = int(ranking.get("leadership_route_bucket_count"))
        except Exception:
            leadership_route_bucket_count = 0
        if leadership_route_bucket_count < 2:
            errors.append(
                _build_error(
                    "signal_generation.ranking.leadership_route_bucket_count",
                    "leadership_route_bucket_count must be >= 2",
                )
            )
    residual_window_regime_mode = _normalized_option(ranking.get("residual_window_regime_mode"))
    if residual_window_regime_mode and residual_window_regime_mode not in {"OFF", "STRONG_RISK_ON"}:
        errors.append(
            _build_error(
                "signal_generation.ranking.residual_window_regime_mode",
                f"unsupported residual_window_regime_mode: {residual_window_regime_mode}",
            )
        )
    residual_weight_regime_mode = _normalized_option(ranking.get("residual_weight_regime_mode"))
    if residual_weight_regime_mode and residual_weight_regime_mode not in {"OFF", "STRONG_RISK_ON"}:
        errors.append(
            _build_error(
                "signal_generation.ranking.residual_weight_regime_mode",
                f"unsupported residual_weight_regime_mode: {residual_weight_regime_mode}",
            )
        )
    if ranking.get("residual_window_fallback") is not None:
        try:
            residual_window_fallback = int(ranking.get("residual_window_fallback"))
        except Exception:
            residual_window_fallback = 0
        if residual_window_fallback < 2:
            errors.append(
                _build_error(
                    "signal_generation.ranking.residual_window_fallback",
                    "residual_window_fallback must be >= 2",
                )
            )
    regime_fast_ma = None
    regime_slow_ma = None
    if ranking.get("residual_window_regime_fast_ma") is not None:
        try:
            regime_fast_ma = int(ranking.get("residual_window_regime_fast_ma"))
        except Exception:
            regime_fast_ma = 0
        if regime_fast_ma < 2:
            errors.append(
                _build_error(
                    "signal_generation.ranking.residual_window_regime_fast_ma",
                    "residual_window_regime_fast_ma must be >= 2",
                )
            )
    if ranking.get("residual_window_regime_slow_ma") is not None:
        try:
            regime_slow_ma = int(ranking.get("residual_window_regime_slow_ma"))
        except Exception:
            regime_slow_ma = 0
        if regime_slow_ma < 2:
            errors.append(
                _build_error(
                    "signal_generation.ranking.residual_window_regime_slow_ma",
                    "residual_window_regime_slow_ma must be >= 2",
                )
            )
    if regime_fast_ma is not None and regime_slow_ma is not None and regime_fast_ma >= regime_slow_ma:
        errors.append(
            _build_error(
                "signal_generation.ranking.residual_window_regime_fast_ma",
                "residual_window_regime_fast_ma must be < residual_window_regime_slow_ma",
            )
        )
    for weight_key in (
        "residual_benchmark_weight",
        "residual_industry_weight",
        "residual_benchmark_weight_fallback",
        "residual_industry_weight_fallback",
        "residual_weight",
        "sector_weight",
        "quality_weight",
    ):
        weight_value = ranking.get(weight_key)
        if weight_value is None:
            continue
        try:
            parsed_weight = float(weight_value)
        except Exception:
            parsed_weight = -1.0
        if parsed_weight < 0.0:
            errors.append(
                _build_error(
                    f"signal_generation.ranking.{weight_key}",
                    f"{weight_key} must be >= 0",
                )
            )
    split_bench_weight = ranking.get("residual_benchmark_weight")
    split_industry_weight = ranking.get("residual_industry_weight")
    if split_bench_weight is not None and split_industry_weight is not None:
        try:
            split_bench_weight_f = float(split_bench_weight)
            split_industry_weight_f = float(split_industry_weight)
        except Exception:
            split_bench_weight_f = -1.0
            split_industry_weight_f = -1.0
        if split_bench_weight_f >= 0.0 and split_industry_weight_f >= 0.0:
            if split_bench_weight_f + split_industry_weight_f <= 1e-12:
                errors.append(
                    _build_error(
                        "signal_generation.ranking.residual_benchmark_weight",
                        "residual_benchmark_weight + residual_industry_weight must be > 0",
                )
            )
    industry_relative_mode = _normalized_option(ranking.get("industry_relative_mode"))
    if industry_relative_mode and industry_relative_mode not in {"SECTOR_PROXY", "INDUSTRY_RANK_PCT", "INDUSTRY_EXCESS_MEDIAN"}:
        errors.append(
            _build_error(
                "signal_generation.ranking.industry_relative_mode",
                f"unsupported industry_relative_mode: {industry_relative_mode}",
            )
        )
    industry_relative_regime_mode = _normalized_option(ranking.get("industry_relative_regime_mode"))
    if industry_relative_regime_mode and industry_relative_regime_mode not in {"OFF", "STRONG_RISK_ON"}:
        errors.append(
            _build_error(
                "signal_generation.ranking.industry_relative_regime_mode",
                f"unsupported industry_relative_regime_mode: {industry_relative_regime_mode}",
            )
        )
    split_bench_weight_fallback = ranking.get("residual_benchmark_weight_fallback")
    split_industry_weight_fallback = ranking.get("residual_industry_weight_fallback")
    if (split_bench_weight_fallback is None) != (split_industry_weight_fallback is None):
        errors.append(
            _build_error(
                "signal_generation.ranking.residual_benchmark_weight_fallback",
                "residual_benchmark_weight_fallback and residual_industry_weight_fallback must be provided together",
            )
        )
    if split_bench_weight_fallback is not None and split_industry_weight_fallback is not None:
        try:
            split_bench_weight_fallback_f = float(split_bench_weight_fallback)
            split_industry_weight_fallback_f = float(split_industry_weight_fallback)
        except Exception:
            split_bench_weight_fallback_f = -1.0
            split_industry_weight_fallback_f = -1.0
        if split_bench_weight_fallback_f >= 0.0 and split_industry_weight_fallback_f >= 0.0:
            if split_bench_weight_fallback_f + split_industry_weight_fallback_f <= 1e-12:
                errors.append(
                    _build_error(
                        "signal_generation.ranking.residual_benchmark_weight_fallback",
                        "residual_benchmark_weight_fallback + residual_industry_weight_fallback must be > 0",
                    )
                )
    ranking_gate_mode = _normalized_option(ranking.get("mf_rank_gate_mode"))
    if ranking_gate_mode and ranking_gate_mode not in {
        "ALWAYS_ON",
        "ONLY_RISK_ON",
        "RISK_ON_ONLY",
        "STRONG_RISK_ON",
        "ONLY_STRONG_RISK_ON",
        "BULL_ONLY",
        "TRANS_UP_OR_BULL",
    }:
        errors.append(
            _build_error(
                "signal_generation.ranking.mf_rank_gate_mode",
                f"unsupported ranking mf_rank_gate_mode: {ranking_gate_mode}",
            )
        )

    source_aware_mode = _normalized_option(ranking.get("source_aware_residual_mode"))
    if source_aware_mode and source_aware_mode not in {"OFF", "PULLBACK_ONLY", "PULLBACK_ONLY_RANK"}:
        errors.append(
            _build_error(
                "signal_generation.ranking.source_aware_residual_mode",
                f"unsupported source_aware_residual_mode: {source_aware_mode}",
            )
        )
    residual_refine_mode = _normalized_option(ranking.get("residual_refine_mode"))
    if residual_refine_mode and residual_refine_mode not in {
        "OFF",
        "BREAKOUT_MARGIN",
        "CONDITIONAL_TIEBREAK",
        "INDUSTRY_SECOND_STAGE",
        "INDUSTRY_SECOND_STAGE_TIEBREAK",
    }:
        errors.append(
            _build_error(
                "signal_generation.ranking.residual_refine_mode",
                f"unsupported residual_refine_mode: {residual_refine_mode}",
            )
        )
    if ranking.get("residual_refine_weight") is not None:
        try:
            residual_refine_weight = float(ranking.get("residual_refine_weight"))
        except Exception:
            residual_refine_weight = -1.0
        if not (0.0 <= residual_refine_weight <= 1.0):
            errors.append(
                _build_error(
                    "signal_generation.ranking.residual_refine_weight",
                    "residual_refine_weight must be within [0, 1]",
                )
            )
    if ranking.get("industry_second_stage_min_industry_score") is not None:
        try:
            min_industry_score = float(ranking.get("industry_second_stage_min_industry_score"))
        except Exception:
            min_industry_score = -1.0
        if not (0.0 <= min_industry_score <= 1.0):
            errors.append(
                _build_error(
                    "signal_generation.ranking.industry_second_stage_min_industry_score",
                    "industry_second_stage_min_industry_score must be within [0, 1]",
                )
            )

    weight_mode = _normalized_option(sizing.get("weight_mode"))
    if weight_mode and weight_mode not in {"EQUAL", "INVERSE_VOL", "MF_RANK_TILT", "SCORE_WEIGHTED"}:
        errors.append(
            _build_error(
                "sizing.weight_mode",
                f"unsupported sizing weight_mode: {weight_mode}",
            )
        )
    if sizing.get("tilt_strength") is not None:
        try:
            tilt_strength = float(sizing.get("tilt_strength"))
        except Exception:
            tilt_strength = -1.0
        if not (0.0 <= tilt_strength < 1.0):
            errors.append(
                _build_error(
                    "sizing.tilt_strength",
                    "tilt_strength must be within [0, 1)",
                )
            )
    score_weight_min_scale: float | None = None
    score_weight_max_scale: float | None = None
    if sizing.get("score_weight_min_scale") is not None or weight_mode == "SCORE_WEIGHTED":
        try:
            score_weight_min_scale = float(sizing.get("score_weight_min_scale", 0.75))
        except Exception:
            score_weight_min_scale = -1.0
        if score_weight_min_scale <= 0.0:
            errors.append(
                _build_error(
                    "sizing.score_weight_min_scale",
                    "score_weight_min_scale must be > 0",
                )
            )
    if sizing.get("score_weight_max_scale") is not None or weight_mode == "SCORE_WEIGHTED":
        try:
            score_weight_max_scale = float(sizing.get("score_weight_max_scale", 1.25))
        except Exception:
            score_weight_max_scale = -1.0
        if score_weight_max_scale <= 0.0:
            errors.append(
                _build_error(
                    "sizing.score_weight_max_scale",
                    "score_weight_max_scale must be > 0",
                )
            )
    if (
        score_weight_min_scale is not None
        and score_weight_max_scale is not None
        and score_weight_min_scale > 0.0
        and score_weight_max_scale > 0.0
        and score_weight_min_scale > score_weight_max_scale
    ):
        errors.append(
            _build_error(
                "sizing.score_weight_max_scale",
                "score_weight_max_scale must be >= score_weight_min_scale",
            )
        )
    candidate_plan_mode = _normalized_option(sizing.get("candidate_plan_mode"))
    if candidate_plan_mode and candidate_plan_mode not in {"RANKED", "CASH_AWARE"}:
        errors.append(
            _build_error(
                "sizing.candidate_plan_mode",
                f"unsupported sizing candidate_plan_mode: {candidate_plan_mode}",
            )
        )
    if sizing.get("cash_aware_search_top_n") is not None or candidate_plan_mode == "CASH_AWARE":
        try:
            cash_aware_search_top_n = int(sizing.get("cash_aware_search_top_n", 12))
        except Exception:
            cash_aware_search_top_n = 0
        if cash_aware_search_top_n <= 0:
            errors.append(
                _build_error(
                    "sizing.cash_aware_search_top_n",
                    "cash_aware_search_top_n must be > 0",
                )
            )
    if sizing.get("rotation_replace_max_swaps_per_day") is not None:
        try:
            rotation_replace_max_swaps_per_day = int(sizing.get("rotation_replace_max_swaps_per_day"))
        except Exception:
            rotation_replace_max_swaps_per_day = 0
        if rotation_replace_max_swaps_per_day <= 0:
            errors.append(
                _build_error(
                    "sizing.rotation_replace_max_swaps_per_day",
                    "rotation_replace_max_swaps_per_day must be >= 1",
                )
            )
    if sizing.get("rotation_replace_candidate_top_n") is not None:
        try:
            rotation_replace_candidate_top_n = int(sizing.get("rotation_replace_candidate_top_n"))
        except Exception:
            rotation_replace_candidate_top_n = 0
        if rotation_replace_candidate_top_n <= 0:
            errors.append(
                _build_error(
                    "sizing.rotation_replace_candidate_top_n",
                    "rotation_replace_candidate_top_n must be >= 1",
                )
            )
    if sizing.get("rotation_replace_min_score_gap") is not None:
        try:
            rotation_replace_min_score_gap = float(sizing.get("rotation_replace_min_score_gap"))
        except Exception:
            rotation_replace_min_score_gap = -1.0
        if rotation_replace_min_score_gap < 0.0:
            errors.append(
                _build_error(
                    "sizing.rotation_replace_min_score_gap",
                    "rotation_replace_min_score_gap must be >= 0",
                )
            )
    if sizing.get("tilt_top_n") is not None:
        try:
            tilt_top_n = int(sizing.get("tilt_top_n"))
        except Exception:
            tilt_top_n = 0
        if tilt_top_n <= 0:
            errors.append(
                _build_error(
                    "sizing.tilt_top_n",
                    "tilt_top_n must be >= 1",
                )
            )
    if sizing.get("tilt_bottom_n") is not None:
        try:
            tilt_bottom_n = int(sizing.get("tilt_bottom_n"))
        except Exception:
            tilt_bottom_n = -1
        if tilt_bottom_n < 0:
            errors.append(
                _build_error(
                    "sizing.tilt_bottom_n",
                    "tilt_bottom_n must be >= 0",
                )
            )

    if risk_off_exit.get("partial_pct") is not None:
        try:
            partial_pct = float(risk_off_exit.get("partial_pct"))
        except Exception:
            partial_pct = -1.0
        if not (0.0 < partial_pct <= 1.0):
            errors.append(
                _build_error(
                    "exit_rules.risk_off_exit.partial_pct",
                    "partial_pct must be within (0, 1]",
                )
            )
    risk_off_mode = _normalized_option(risk_off_exit.get("mode"))
    if risk_off_mode and risk_off_mode not in {
        "RISK_ON_OFF",
        "BEAR_ONLY",
        "TRANS_DOWN_OR_BEAR",
        "TRANS_DOWN_FREEZE_BEAR_EXIT",
        "TRANS_DOWN_TOPK_BEAR_EXIT",
        "TRANS_DOWN_RESIDUAL_FLOOR_BEAR_EXIT",
        "TRANS_DOWN_RESIDUAL_PROFIT_FLOOR_BEAR_EXIT",
        "TRANS_DOWN_RESIDUAL_MA20_FLOOR_BEAR_EXIT",
    }:
        errors.append(
            _build_error(
                "exit_rules.risk_off_exit.mode",
                f"unsupported risk_off_exit mode: {risk_off_mode}",
            )
        )
    if risk_off_exit.get("trans_down_max_positions") is not None:
        try:
            trans_down_max_positions = int(risk_off_exit.get("trans_down_max_positions"))
        except Exception:
            trans_down_max_positions = 0
        if trans_down_max_positions <= 0:
            errors.append(
                _build_error(
                    "exit_rules.risk_off_exit.trans_down_max_positions",
                    "trans_down_max_positions must be >= 1",
                )
            )
    if risk_off_exit.get("trans_down_min_residual_score") is not None:
        try:
            trans_down_min_residual_score = float(risk_off_exit.get("trans_down_min_residual_score"))
        except Exception:
            trans_down_min_residual_score = -1.0
        if not (0.0 <= trans_down_min_residual_score <= 1.0):
            errors.append(
                _build_error(
                    "exit_rules.risk_off_exit.trans_down_min_residual_score",
                    "trans_down_min_residual_score must be within [0, 1]",
                )
            )
    partial_mode = _normalized_option(risk_off_exit.get("partial_mode"))
    if partial_mode and partial_mode not in {"ALL_STATES", "TRANS_DOWN_ONLY", "FIRST_TRANS_DOWN_THEN_FULL"}:
        errors.append(
            _build_error(
                "exit_rules.risk_off_exit.partial_mode",
                f"unsupported risk_off_exit partial_mode: {partial_mode}",
            )
        )

    trailing = exit_rules.get("trailing") if isinstance(exit_rules.get("trailing"), dict) else {}
    segmented_exit_mode = _normalized_option(trailing.get("segmented_trend_exit_mode"))
    if segmented_exit_mode and segmented_exit_mode not in {"OFF", "MA20", "LOW10", "CHANDELIER"}:
        errors.append(
            _build_error(
                "exit_rules.trailing.segmented_trend_exit_mode",
                f"unsupported segmented_trend_exit_mode: {segmented_exit_mode}",
            )
        )
    if trailing.get("pre_profit_breakout_failure_max_bars") is not None:
        try:
            pre_profit_breakout_failure_max_bars = int(trailing.get("pre_profit_breakout_failure_max_bars"))
        except Exception:
            pre_profit_breakout_failure_max_bars = 0
        if pre_profit_breakout_failure_max_bars <= 0:
            errors.append(
                _build_error(
                    "exit_rules.trailing.pre_profit_breakout_failure_max_bars",
                    "pre_profit_breakout_failure_max_bars must be >= 1",
                )
            )
    if trailing.get("pre_profit_breakout_failure_atr_buffer_k") is not None:
        try:
            pre_profit_breakout_failure_atr_buffer_k = float(trailing.get("pre_profit_breakout_failure_atr_buffer_k"))
        except Exception:
            pre_profit_breakout_failure_atr_buffer_k = -1.0
        if pre_profit_breakout_failure_atr_buffer_k < 0.0:
            errors.append(
                _build_error(
                    "exit_rules.trailing.pre_profit_breakout_failure_atr_buffer_k",
                    "pre_profit_breakout_failure_atr_buffer_k must be >= 0",
                )
            )
    if trailing.get("profit_decay_exit_profit_pct") is not None:
        try:
            profit_decay_exit_profit_pct = float(trailing.get("profit_decay_exit_profit_pct"))
        except Exception:
            profit_decay_exit_profit_pct = 0.0
        if profit_decay_exit_profit_pct <= 0.0:
            errors.append(
                _build_error(
                    "exit_rules.trailing.profit_decay_exit_profit_pct",
                    "profit_decay_exit_profit_pct must be > 0",
                )
            )
    if trailing.get("profit_decay_exit_min_hold_bars") is not None:
        try:
            profit_decay_exit_min_hold_bars = int(trailing.get("profit_decay_exit_min_hold_bars"))
        except Exception:
            profit_decay_exit_min_hold_bars = 0
        if profit_decay_exit_min_hold_bars <= 0:
            errors.append(
                _build_error(
                    "exit_rules.trailing.profit_decay_exit_min_hold_bars",
                    "profit_decay_exit_min_hold_bars must be >= 1",
                )
            )
    if trailing.get("profit_decay_exit_residual_score_threshold") is not None:
        try:
            profit_decay_exit_residual_score_threshold = float(trailing.get("profit_decay_exit_residual_score_threshold"))
        except Exception:
            profit_decay_exit_residual_score_threshold = -1.0
        if not (0.0 <= profit_decay_exit_residual_score_threshold <= 1.0):
            errors.append(
                _build_error(
                    "exit_rules.trailing.profit_decay_exit_residual_score_threshold",
                    "profit_decay_exit_residual_score_threshold must be within [0, 1]",
                )
            )

    modules = signal_generation.get("modules") if isinstance(signal_generation.get("modules"), list) else []
    if modules:
        seen_names: set[str] = set()
        for idx, module in enumerate(modules):
            module_name = str((module or {}).get("name") or "").strip().lower()
            path = f"signal_generation.modules[{idx}].name"
            if not module_name:
                errors.append(_build_error(path, "module name is required"))
                continue
            if module_name not in _SUPPORTED_MULTI_ALPHA_MODULES:
                errors.append(_build_error(path, f"unsupported multi-alpha module: {module_name}"))
                continue
            if module_name in seen_names:
                errors.append(_build_error(path, f"duplicate multi-alpha module: {module_name}"))
                continue
            seen_names.add(module_name)

        if not signal_composition:
            errors.append(_build_error("signal_composition", "required when signal_generation.modules is set"))
            return errors

        compose_mode = _normalized_option(signal_composition.get("compose_mode"))
        if not compose_mode:
            errors.append(_build_error("signal_composition.compose_mode", "required when signal_generation.modules is set"))
        elif compose_mode not in _SUPPORTED_MULTI_ALPHA_COMPOSE_MODES:
            errors.append(
                _build_error(
                    "signal_composition.compose_mode",
                    f"unsupported multi-alpha compose_mode: {compose_mode}",
                )
            )

        same_symbol_policy = _normalized_option(signal_composition.get("same_symbol_policy"))
        if same_symbol_policy and same_symbol_policy not in _SUPPORTED_MULTI_ALPHA_SAME_SYMBOL_POLICIES:
            errors.append(
                _build_error(
                    "signal_composition.same_symbol_policy",
                    f"unsupported same_symbol_policy: {same_symbol_policy}",
                )
            )

        holding_ownership = _normalized_option(signal_composition.get("holding_ownership"))
        if holding_ownership and holding_ownership not in _SUPPORTED_MULTI_ALPHA_HOLDING_OWNERSHIP:
            errors.append(
                _build_error(
                    "signal_composition.holding_ownership",
                    f"unsupported holding_ownership: {holding_ownership}",
                )
            )

        composition_modules = (
            signal_composition.get("modules") if isinstance(signal_composition.get("modules"), list) else []
        )
        for idx, module in enumerate(composition_modules):
            module_name = str((module or {}).get("name") or "").strip().lower()
            path = f"signal_composition.modules[{idx}].name"
            if not module_name:
                errors.append(_build_error(path, "module name is required"))
                continue
            if module_name not in seen_names:
                errors.append(_build_error(path, f"module not declared in signal_generation.modules: {module_name}"))

    return errors


def validate_semantic_config_json(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        model = FrontendSemanticConfig.parse_obj(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"invalid config_json: {exc}") from exc
    normalized = jsonable_dict(model)
    logic_errors = _validate_semantic_logic(normalized)
    if logic_errors:
        raise HTTPException(status_code=400, detail={"message": "invalid config_json", "errors": logic_errors})
    return normalized


def compile_semantic_config_json(
    raw: dict[str, Any],
    *,
    compiled_plan_payload: dict[str, Any] | None = None,
    config_source: str = "config_json",
) -> dict[str, Any]:
    input_config = sanitize_json(dict(raw or {}))
    resolved_input = validate_semantic_config_json(input_config)
    config_hash = _hash_json(input_config)
    provenance = {
        "schema_version": SEMANTIC_CONFIG_SCHEMA_VERSION,
        "config_source": str(config_source or "config_json"),
        "config_hash": config_hash,
    }
    return {
        "input_config": sanitize_json(dict(input_config)),
        "resolved_config": sanitize_json(
            {
                **provenance,
                "config_json": dict(resolved_input),
            }
        ),
        "compiled_plan": sanitize_json(
            {
                **provenance,
                **dict(compiled_plan_payload or {}),
            }
        ),
        "config_hash": config_hash,
        "schema_version": SEMANTIC_CONFIG_SCHEMA_VERSION,
        "config_source": str(config_source or "config_json"),
    }


def jsonable_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)
