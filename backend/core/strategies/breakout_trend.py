from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from backend.core.core.models import Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class BreakoutTrendStrategy(Strategy):
    breakout_window: int = 20
    enable_dual_breakout: bool = False
    breakout_window_short: int = 20
    breakout_window_long: int = 55
    dual_breakout_mode: str = "or"
    dual_breakout_gate_ma_window: int = 120
    dual_breakout_gate_slope_lookback: int = 10
    breakout_entry_buffer_pct: float = 0.0
    # Entry quality controls
    # none | close_strength | volume_confirm | volume_ratio_confirm | volatility_confirm
    entry_confirm_mode: str = "none"
    # none | t1_confirm | t2_confirm | pullback_confirm
    entry_delay_mode: str = "none"
    enable_entry_gap_guard: bool = False
    entry_gap_guard_pct: float = 0.04
    enable_entry_above_slow_ma: bool = False
    enable_entry_slow_ma_slope: bool = False
    entry_slope_lookback: int = 5
    # Portfolio mode: equal_10 | equal_8 | equal_6 | profit_release
    portfolio_mode: str = "equal_10"
    order_size: int = 1000
    # Universe 过滤
    min_price: float = 0.0
    # 市场环境
    regime_ma: int = 60
    # V2 个股趋势过滤
    enable_v2_trend_filter: bool = True
    v2_trend_short_ma: int = 20
    v2_trend_long_ma: int = 60
    # ATR 退出
    enable_atr_stop: bool = True
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
    # 止盈 / 固定止损
    enable_take_profit: bool = False
    take_profit_mode: str = "pct"
    take_profit_pct: float = 0.10
    take_profit_atr_k: float = 3.0
    enable_fixed_stop_loss: bool = False
    fixed_stop_loss_pct: float = 0.05
    # 时间退出
    max_hold_days: int = 0
    # 持仓约束 / 再入场约束
    min_hold_days: int = 0
    cooldown_days: int = 0
    min_hold_exempt_reasons: list[str] = field(default_factory=lambda: ["ATR_STOP_LOSS", "FIXED_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT"])
    # 趋势退出
    enable_ma20_exit: bool = False
    enable_low10_exit: bool = False
    risk_off_exit_mode: str = "risk_on_off"
    risk_off_exit_partial_pct: float = 1.0
    risk_off_exit_partial_mode: str = "all_states"
    risk_off_exit_partial_only_if_profitable: bool = False
    risk_off_exit_trans_down_max_positions: int = 0
    risk_off_exit_trans_down_min_residual_score: float = 0.0
    # Regime 退出
    enable_risk_off_exit: bool = False
    # 动量排名选股
    momentum_top_pct: float = 0.0
    # 行业趋势门控
    enable_sector_gate: bool = False
    sector_rank_window: int = 60
    sector_top_pct: float = 0.30
    # Multi-alpha candidate expansion
    enable_pullback_candidates: bool = False
    pullback_variant_mode: str = "pb_reclaim_ma20"
    pullback_touch_lookback: int = 12
    pullback_reclaim_window: int = 3
    pullback_ma20_touch_band_pct: float = 0.01
    pullback_low_lookback: int = 10
    pullback_low_band_pct: float = 0.02
    pullback_box_window: int = 5
    pullback_box_range_pct_max: float = 0.08
    # Unified ranking
    enable_residual_ranking: bool = False
    residual_window: int = 60
    residual_benchmark_weight: float = 0.5
    residual_industry_weight: float = 0.5
    industry_relative_mode: str = "sector_proxy"
    industry_relative_regime_mode: str = "off"
    residual_weight_regime_mode: str = "off"
    residual_benchmark_weight_fallback: float = -1.0
    residual_industry_weight_fallback: float = -1.0
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

    def __post_init__(self) -> None:
        Strategy.__init__(self)

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, object]) -> list[Signal]:
        # Breakout 策略的信号生成由 BreakoutTrendProvider 矩阵引擎处理
        # 此方法仅作为 Strategy 接口的兼容实现
        return []
