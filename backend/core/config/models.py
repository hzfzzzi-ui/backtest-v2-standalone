from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict


@dataclass(slots=True)
class DBConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str


@dataclass(slots=True)
class DBRuntimeConfig:
    statement_timeout_ms: int = 60000


@dataclass(slots=True)
class UniverseConfig:
    symbols: list[str]
    benchmark: str
    start: date
    end: date
    benchmark_compare_symbol: str = "000001.SH"
    allow_low_fidelity_history: bool = False


@dataclass(slots=True)
class DataSourceConfig:
    data_role: str = "v1"
    stocks_table: str = "pams_ohlcv_daily"
    v2_canonical_stocks_table: str = "pams_ohlcv_daily_v2"
    v2_runtime_stocks_table: str = "pams_ohlcv_daily_v2_runtime"
    v2_schema_mapping_table: str = "pams_ohlcv_daily_v2"
    index_table: str = "pit_index_daily"
    prefer_index_table: bool = True
    allow_cn_index_in_stocks_table: bool = False
    cn_index_filter_column: str = "market"
    cn_index_filter_value: str = "CN_INDEX"

    def resolved_data_role(self) -> str:
        role = str(self.data_role or "v1").strip().lower()
        if role not in {"v1", "v2_canonical", "v2_runtime"}:
            return "v1"
        return role

    def resolved_stocks_table(self) -> str:
        role = self.resolved_data_role()
        if role == "v2_canonical":
            return str(self.v2_canonical_stocks_table or self.stocks_table)
        if role == "v2_runtime":
            return str(self.v2_runtime_stocks_table or self.v2_canonical_stocks_table or self.stocks_table)
        return str(self.stocks_table)

    def resolved_stocks_mapping_table(self) -> str:
        role = self.resolved_data_role()
        if role in {"v2_canonical", "v2_runtime"}:
            return str(self.v2_schema_mapping_table or self.v2_canonical_stocks_table or self.stocks_table)
        return str(self.stocks_table)


@dataclass(slots=True)
class ExecutionConfig:
    engine_mode: str = "SLOW_AUDIT"
    profile: str = "basic"
    lot_size: int = 100
    tick_size: float = 0.01
    limit_pct_default: float = 0.10
    limit_pct_star: float = 0.05
    limit_pct_kcb_gem: float = 0.20
    liquidity_cap_pct: float = 0.10
    allow_liquidity_without_volume: bool = False
    t_plus_one: bool = True
    t_plus_one_cash: bool = False
    limit_price_epsilon_mode: str = "tick_or_default"
    limit_price_epsilon_default: float = 0.01
    dedup_same_day: bool = True
    block_buy_if_holding: bool = True
    allow_pyramiding: bool = False
    skip_if_no_cash: bool = True


@dataclass(slots=True)
class SizingConfig:
    mode: str = "fixed_qty"
    order_value: float = 10000.0
    reserve_cash_ratio: float = 0.02
    lot_size: int = 100
    # "OFF" keeps the historical sizing behavior.
    # "LOT100_MIN1LOT": dynamic order_value ensures at least 1 lot purchasable when cash allows.
    # "ODDLOT_1": research-only odd-lot mode.
    univote_lot_mode: str = "OFF"
    # Portfolio weight mode: "equal" (default) or "inverse_vol"
    weight_mode: str = "equal"
    # Minimum position count for sizing denominator (prevents over-concentration)
    min_positions: int = 10
    # Light rank-based tilt on top of equal sizing. Uses existing mf_rank ordering.
    tilt_strength: float = 0.0
    tilt_top_n: int = 3
    tilt_bottom_n: int = 2
    # Score-weighted sizing reuses current candidate score and normalizes scales
    # across planned selections so average exposure remains near baseline.
    score_weight_min_scale: float = 0.75
    score_weight_max_scale: float = 1.25
    # Candidate planner remains baseline-ranked unless explicitly enabled.
    candidate_plan_mode: str = "ranked"
    cash_aware_search_top_n: int = 12
    # Research-only optional rotation replace. Default off preserves baseline.
    rotation_replace_enabled: bool = False
    rotation_replace_only_strong_risk_on: bool = True
    rotation_replace_max_swaps_per_day: int = 1
    rotation_replace_candidate_top_n: int = 3
    rotation_replace_min_score_gap: float = 0.15


@dataclass(slots=True)
class CostConfig:
    commission_rate: float = 0.0003
    commission_min: float = 5.0
    stamp_tax_rate: float = 0.001
    slippage_bps: float = 2.0
    slippage_mode: str = "price_adjustment_only"


@dataclass(slots=True)
class DataScopeConfig:
    extend_prev_close: bool = True
    prev_close_missing_policy: str = "disable_limit_check"


@dataclass(slots=True)
class StrategyConfig:
    name: str = "sma_cross"
    fast: int = 5
    slow: int = 20
    order_size: int = 1000
    trend_ma: int = 200
    use_benchmark_regime: bool = False
    atr_n: int = 14
    atr_k: float = 2.5
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExitConfig:
    enable_take_profit: bool = False
    take_profit_mode: str = "pct"
    take_profit_pct: float = 0.10
    take_profit_atr_k: float = 3.0
    enable_fixed_stop_loss: bool = False
    fixed_stop_loss_pct: float = 0.05
    enable_atr_stop: bool = False
    atr_stop_k: float = 2.0
    enable_atr_trail: bool = False
    atr_trail_k: float = 3.0
    trailing_activate_profit_pct: float = 0.0
    segmented_trend_exit_mode: str = "off"
    segmented_mid_profit_pct: float = 0.0
    segmented_high_profit_pct: float = 0.0
    segmented_high_trail_k: float = 3.0
    enable_pre_profit_breakout_failure_exit: bool = False
    pre_profit_breakout_failure_max_bars: int = 0
    pre_profit_breakout_failure_atr_buffer_k: float = 0.0
    enable_profit_decay_exit: bool = False
    profit_decay_exit_profit_pct: float = 0.15
    profit_decay_exit_min_hold_bars: int = 10
    profit_decay_exit_residual_score_threshold: float = 0.35
    enable_ma20_exit: bool = False
    enable_low10_exit: bool = False


@dataclass(slots=True)
class RiskConfig:
    pass


@dataclass(slots=True)
class RiskBudgetConfig:
    enabled: bool = False
    # DD > dd_reduce_pct → scale max_positions by dd_reduce_scale
    dd_reduce_pct: float = 0.10
    dd_reduce_scale: float = 0.5
    atr_stop_k: float = 2.0


@dataclass(slots=True)
class MarketFilterConfig:
    enabled: bool = False
    long_ma_window: int = 200
    slope_window: int = 10
    slope_ma_period: int = 50
    bull_multiplier: float = 1.5
    light_multiplier: float = 0.6
    # Optional per-state multipliers. When None, fallback to the historical behavior.
    trans_down_multiplier: float | None = None
    trans_up_multiplier: float | None = None
    bear_multiplier: float | None = None
    freeze_trans_up_entries: bool = False
    ema_light_fast: int = 5
    ema_light_slow: int = 20


@dataclass(slots=True)
class BenchmarkRegimeConfig:
    enabled: bool = False
    fast_period: int = 20
    slow_period: int = 60
    slope_window: int = 5


@dataclass(slots=True)
class BreadthConfig:
    enabled: bool = False
    mode: str = "dynamic_maxpos"
    score_type: str = "B"
    mapping_mode: str = "smooth"
    min_positions: int = 3
    max_positions: int = 15
    step_high: float = 0.60
    step_mid: float = 0.45
    smooth_lo: float = 0.40
    smooth_range: float = 0.20
    ema_fast: int = 8
    ema_slow: int = 25
    gate_threshold: float = 0.45
    gate_quantile_window: int = 252
    gate_quantile_pct: float = 0.20
    gate_persist_days: int = 3
    size_scale_floor: float = 0.3


@dataclass(slots=True)
class RegimeEngineTrendBlockConfig:
    enabled: bool = True
    long_ma_window: int = 200
    slope_window: int = 20
    breakout_lookback: int = 20


@dataclass(slots=True)
class RegimeEngineRiskBlockConfig:
    enabled: bool = True
    realized_vol_window: int = 20
    atr_window: int = 14
    drawdown_window: int = 60


@dataclass(slots=True)
class RegimeEngineBreadthBlockConfig:
    enabled: bool = True
    universe: str = "benchmark_constituents"
    above_ma_short_window: int = 50
    above_ma_long_window: int = 200
    new_high_low_window: int = 20


@dataclass(slots=True)
class RegimeEngineParticipationBlockConfig:
    enabled: bool = True
    turnover_window: int = 20
    amount_window: int = 20
    use_turnover_rate: bool = True


@dataclass(slots=True)
class RegimeEnginePersistenceConfig:
    entry_confirm_bars: int = 3
    exit_confirm_bars: int = 2
    min_state_duration: int = 5
    confidence_floor: float = 0.55
    transition_cooldown: int = 3


@dataclass(slots=True)
class RegimeEngineFallbackConfig:
    on_feature_unavailable: str = "ma200_legacy"
    required_blocks: list[str] = field(default_factory=lambda: ["trend_block", "risk_block"])
    emit_feature_availability: bool = True


@dataclass(slots=True)
class WeeklyFiveStateRegimeConfig:
    benchmark: str = "000001.SH"
    ma_window: int = 120
    ma_slope_lookback: int = 20
    ret_short_window: int = 60
    ret_long_window: int = 120
    adx_window: int = 20
    weekly_rule: str = "W-FRI"
    upgrade_confirm_weeks: int = 2
    downgrade_confirm_weeks: int = 1
    turn_weak_budget: float = 0.15
    risk_budget_mode: str = "five_state"


@dataclass(slots=True)
class LegacyTurnWeakOverlayConfig:
    enabled: bool = False
    weekly_cfg: WeeklyFiveStateRegimeConfig = field(default_factory=WeeklyFiveStateRegimeConfig)


@dataclass(slots=True)
class RegimeEngineConfig:
    engine: str = "ma200_legacy"
    benchmark: str = ""
    trend_block: RegimeEngineTrendBlockConfig = field(default_factory=RegimeEngineTrendBlockConfig)
    risk_block: RegimeEngineRiskBlockConfig = field(default_factory=RegimeEngineRiskBlockConfig)
    breadth_block: RegimeEngineBreadthBlockConfig = field(default_factory=RegimeEngineBreadthBlockConfig)
    participation_block: RegimeEngineParticipationBlockConfig = field(default_factory=RegimeEngineParticipationBlockConfig)
    persistence: RegimeEnginePersistenceConfig = field(default_factory=RegimeEnginePersistenceConfig)
    fallback: RegimeEngineFallbackConfig = field(default_factory=RegimeEngineFallbackConfig)
    weekly_five_state: WeeklyFiveStateRegimeConfig = field(default_factory=WeeklyFiveStateRegimeConfig)
    legacy_turn_weak_overlay: LegacyTurnWeakOverlayConfig = field(default_factory=LegacyTurnWeakOverlayConfig)


@dataclass(slots=True)
class BacktestConfig:
    db: DBConfig
    db_runtime: DBRuntimeConfig
    universe: UniverseConfig
    data_source: DataSourceConfig
    schema_mapping: Dict[str, Dict[str, str]]
    data_scope: DataScopeConfig = field(default_factory=DataScopeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    exit: ExitConfig = field(default_factory=ExitConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    risk_budget: RiskBudgetConfig = field(default_factory=RiskBudgetConfig)
    regime_engine: RegimeEngineConfig = field(default_factory=RegimeEngineConfig)
    market_filter: MarketFilterConfig = field(default_factory=MarketFilterConfig)
    benchmark_regime: BenchmarkRegimeConfig = field(default_factory=BenchmarkRegimeConfig)
    breadth: BreadthConfig = field(default_factory=BreadthConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    initial_capital: float = 100000.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
