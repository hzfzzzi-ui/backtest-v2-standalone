from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SEMANTIC_CONFIG_SCHEMA_VERSION = "2026-03-20"
_SUPPORTED_MULTI_ALPHA_MODULES = frozenset({"breakout_55", "rsi_reversal", "moneyflow_monthly"})
_SUPPORTED_MULTI_ALPHA_COMPOSE_MODES = frozenset({"REGIME_ROUTE"})
_SUPPORTED_MULTI_ALPHA_SAME_SYMBOL_POLICIES = frozenset({"PREFER_HIGHER_SCORE"})
_SUPPORTED_MULTI_ALPHA_HOLDING_OWNERSHIP = frozenset({"SOURCE_ONLY"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UniverseFiltersConfig(StrictModel):
    exclude_st: bool | None = None
    exclude_delisted: bool | None = None
    exclude_suspended: bool | None = None
    exclude_star_market: bool | None = None
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
    bull_breakout_quality_veto_enabled: bool | None = None
    bull_breakout_quality_veto_min_residual_strength_score: float | None = None
    bull_breakout_quality_veto_min_breakout_margin_score: float | None = None
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
    market_state_weight_overrides: dict[str, dict[str, float]] | None = None
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
    long_ma_window: int | None = None
    slope_ma_period: int | None = None
    slope_window: int | None = None
    bull_multiplier: float | None = None
    light_multiplier: float | None = None
    trans_down_multiplier: float | None = None
    trans_up_multiplier: float | None = None
    bear_multiplier: float | None = None
    freeze_trans_up_entries: bool | None = None
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


class RegimeEngineTrendBlockConfig(StrictModel):
    enabled: bool | None = None
    long_ma_window: int | None = None
    slope_window: int | None = None
    breakout_lookback: int | None = None


class RegimeEngineRiskBlockConfig(StrictModel):
    enabled: bool | None = None
    realized_vol_window: int | None = None
    atr_window: int | None = None
    drawdown_window: int | None = None


class RegimeEngineBreadthBlockConfig(StrictModel):
    enabled: bool | None = None
    universe: Literal["benchmark_constituents", "strategy_universe"] | None = None
    above_ma_short_window: int | None = None
    above_ma_long_window: int | None = None
    new_high_low_window: int | None = None


class RegimeEngineParticipationBlockConfig(StrictModel):
    enabled: bool | None = None
    turnover_window: int | None = None
    amount_window: int | None = None
    use_turnover_rate: bool | None = None


class RegimeEnginePersistenceConfig(StrictModel):
    entry_confirm_bars: int | None = None
    exit_confirm_bars: int | None = None
    min_state_duration: int | None = None
    confidence_floor: float | None = None
    transition_cooldown: int | None = None


class RegimeEngineFallbackConfig(StrictModel):
    on_feature_unavailable: Literal["ma200_legacy", "disabled"] | None = None
    required_blocks: list[
        Literal["trend_block", "risk_block", "breadth_block", "participation_block"]
    ] | None = None
    emit_feature_availability: bool | None = None


class WeeklyFiveStateRegimeConfig(StrictModel):
    benchmark: str | None = None
    ma_window: int | None = None
    ma_slope_lookback: int | None = None
    ret_short_window: int | None = None
    ret_long_window: int | None = None
    adx_window: int | None = None
    weekly_rule: str | None = None
    upgrade_confirm_weeks: int | None = None
    downgrade_confirm_weeks: int | None = None
    turn_weak_budget: float | None = None
    risk_budget_mode: Literal["five_state", "three_state", "asymmetric_budget"] | None = None


class LegacyTurnWeakOverlayConfig(StrictModel):
    enabled: bool | None = None
    weekly_cfg: WeeklyFiveStateRegimeConfig | None = None


class RegimeEngineConfig(StrictModel):
    engine: Literal["ma200_legacy", "market_regime_framework", "weekly_five_state"] | None = None
    benchmark: str | None = None
    trend_block: RegimeEngineTrendBlockConfig | None = None
    risk_block: RegimeEngineRiskBlockConfig | None = None
    breadth_block: RegimeEngineBreadthBlockConfig | None = None
    participation_block: RegimeEngineParticipationBlockConfig | None = None
    persistence: RegimeEnginePersistenceConfig | None = None
    fallback: RegimeEngineFallbackConfig | None = None
    weekly_five_state: WeeklyFiveStateRegimeConfig | None = None
    legacy_turn_weak_overlay: LegacyTurnWeakOverlayConfig | None = None


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


class DataSourceSemanticConfig(StrictModel):
    data_role: str | None = None


class FrontendSemanticConfig(StrictModel):
    asset_scope: str | None = None
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
    data_source: DataSourceSemanticConfig | None = None
    regime_engine: RegimeEngineConfig | None = None
    exit_priority: list[str] | None = None


