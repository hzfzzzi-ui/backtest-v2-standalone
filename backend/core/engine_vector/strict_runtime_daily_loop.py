"""Daily simulation loop for the default vector runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.core.config.models import CostConfig

@dataclass(slots=True)
class DefaultRuntimeSimulationStage:
    daily_rows: list[dict[str, Any]]
    trade_rows: list[dict[str, Any]]
    candidate_rows: list[dict[str, Any]]
    blocked_by_trend_count: int
    total_buy_signals: int
    trend_slope_block_count: int
    trend_continuity_block_count: int
    scan_all_symbols_count: int
    cand_index_access_count: int
    diag_reason_counts: dict[str, int]
    exit_take_profit_count: int
    exit_fixed_stop_count: int
    exit_atr_stop_count: int
    exit_atr_trail_count: int
    exit_time_exit_count: int
    exit_signal_count: int
    exit_ma20_count: int
    exit_low10_count: int
    debug_trace: dict[str, Any]
    simulation_seconds: float

def run_default_runtime_daily_loop(
    *,
    strategy: Any,
    trading_days: list[date],
    initial_cash: float,
    max_positions: int,
    lot_size: int,
    enable_strength_rank: bool,
    strength_ma: int,
    strength_top_k_mode: str,
    fast_mode: bool,
    debug_first_divergence: bool,
    enable_multifactor_rank: bool,
    mf_topk: int,
    mf_concentrate_topn: int,
    mf_concentrate_scale: float,
    mf_rank_gate_mode: str,
    momentum_top_pct: float,
    cost_cfg: CostConfig | None,
    params: dict[str, Any],
    inputs: Any,
    benchmark_state: Any,
    signal_state: Any,
) -> DefaultRuntimeSimulationStage:
    # The daily loop emits raw execution observations only. Final funnel and
    # route-specific diagnostic semantics are owned by downstream artifact
    # builders.
    mx = inputs.mx
    feats = inputs.feats
    strength = inputs.strength
    bench_close = benchmark_state.bench_close
    risk_on = benchmark_state.risk_on
    strong_risk_on = benchmark_state.strong_risk_on
    sig_m = signal_state.sig_m
    cand_idx = signal_state.cand_idx
    open_idx = signal_state.open_idx
    close_idx = signal_state.close_idx
    sym_to_col = signal_state.sym_to_col

    _min_trade_price = float(params["min_trade_price"])
    enable_dd_breaker = bool(params["enable_dd_breaker"])
    dd_reduce_pct = float(params["dd_reduce_pct"])
    dd_reduce_scale = float(params["dd_reduce_scale"])
    weight_mode = str(params["weight_mode"])
    min_positions = int(params["min_positions"])
    tilt_strength = float(params["tilt_strength"])
    tilt_top_n = int(params["tilt_top_n"])
    tilt_bottom_n = int(params["tilt_bottom_n"])
    score_weight_min_scale = float(params["score_weight_min_scale"])
    score_weight_max_scale = float(params["score_weight_max_scale"])
    candidate_plan_mode = str(params["candidate_plan_mode"])
    cash_aware_search_top_n = int(params["cash_aware_search_top_n"])
    rotation_replace_enabled = bool(params["rotation_replace_enabled"])
    rotation_replace_only_strong_risk_on = bool(params["rotation_replace_only_strong_risk_on"])
    rotation_replace_max_swaps_per_day = int(params["rotation_replace_max_swaps_per_day"])
    rotation_replace_candidate_top_n = int(params["rotation_replace_candidate_top_n"])
    rotation_replace_min_score_gap = float(params["rotation_replace_min_score_gap"])
    enable_trend_filter = bool(params["enable_trend_filter"])
    enable_trend_tier = bool(params["enable_trend_tier"])
    enable_trend_accel = bool(params["enable_trend_accel"])
    weak_trend_order_scale = float(params["weak_trend_order_scale"])
    strong_trend_order_scale = float(params["strong_trend_order_scale"])
    enable_trend_break_exit = bool(params["enable_trend_break_exit"])
    trend_break_confirm_days = int(params["trend_break_confirm_days"])
    trend_break_confirm_gap_pct = float(params["trend_break_confirm_gap_pct"])
    trend_break_use_benchmark_regime = bool(params["trend_break_use_benchmark_regime"])
    enable_atr_stop = bool(params["enable_atr_stop"])
    enable_atr_trail = bool(params["enable_atr_trail"])
    atr_stop_k = float(params["atr_stop_k"])
    atr_trail_k = float(params["atr_trail_k"])
    trailing_activate_profit_pct = float(params["trailing_activate_profit_pct"])
    enable_take_profit = bool(params["enable_take_profit"])
    take_profit_mode = str(params["take_profit_mode"])
    take_profit_pct = float(params["take_profit_pct"])
    take_profit_atr_k = float(params["take_profit_atr_k"])
    enable_fixed_stop_loss = bool(params["enable_fixed_stop_loss"])
    fixed_stop_loss_pct = float(params["fixed_stop_loss_pct"])
    max_hold_days = int(params["max_hold_days"])
    enable_ma20_exit = bool(params["enable_ma20_exit"])
    enable_low10_exit = bool(params["enable_low10_exit"])
    order_size = int(params["order_size"])


    return DefaultRuntimeSimulationStage(
        daily_rows=daily_rows,
        trade_rows=trade_rows,
        candidate_rows=candidate_rows,
        blocked_by_trend_count=int(blocked_by_trend_count),
        total_buy_signals=int(total_buy_signals),
        trend_slope_block_count=int(trend_slope_block_count),
        trend_continuity_block_count=int(trend_continuity_block_count),
        scan_all_symbols_count=int(scan_all_symbols_count),
        cand_index_access_count=int(cand_index_access_count),
        diag_reason_counts=dict(diag_reason_counts),
        exit_take_profit_count=int(exit_take_profit_count),
        exit_fixed_stop_count=int(exit_fixed_stop_count),
        exit_atr_stop_count=int(exit_atr_stop_count),
        exit_atr_trail_count=int(exit_atr_trail_count),
        exit_time_exit_count=int(exit_time_exit_count),
        exit_signal_count=int(exit_signal_count),
        exit_ma20_count=int(exit_ma20_count),
        exit_low10_count=int(exit_low10_count),
        debug_trace=debug_trace,
        simulation_seconds=float(simulation_seconds),
    )
