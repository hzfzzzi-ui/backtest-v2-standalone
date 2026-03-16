"""Result/materialization stage for the default vector runtime."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.core.portfolio.metrics import compute_backtest_metrics
from backend.core.portfolio.types import PortfolioBacktestResult


def finalize_default_runtime_result(
    *,
    simulation: Any,
    precompute_seconds: float,
    max_positions: int,
    enable_strength_rank: bool,
    strength_ma: int,
    collect_decision_diff: bool,
    debug_first_divergence: bool,
) -> PortfolioBacktestResult:
    daily_rows = simulation.daily_rows
    trade_rows = simulation.trade_rows
    candidate_rows = simulation.candidate_rows
    blocked_by_trend_count = simulation.blocked_by_trend_count
    total_buy_signals = simulation.total_buy_signals
    trend_slope_block_count = simulation.trend_slope_block_count
    trend_continuity_block_count = simulation.trend_continuity_block_count
    scan_all_symbols_count = simulation.scan_all_symbols_count
    cand_index_access_count = simulation.cand_index_access_count
    diag_reason_counts = simulation.diag_reason_counts
    exit_take_profit_count = simulation.exit_take_profit_count
    exit_fixed_stop_count = simulation.exit_fixed_stop_count
    exit_atr_stop_count = simulation.exit_atr_stop_count
    exit_atr_trail_count = simulation.exit_atr_trail_count
    exit_time_exit_count = simulation.exit_time_exit_count
    exit_signal_count = simulation.exit_signal_count
    exit_ma20_count = simulation.exit_ma20_count
    exit_low10_count = simulation.exit_low10_count
    debug_trace = simulation.debug_trace
    simulation_seconds = simulation.simulation_seconds

    io_t0 = time.perf_counter()
    daily_df = pd.DataFrame(daily_rows)
    trades_df = pd.DataFrame(trade_rows)
    candidates_df = pd.DataFrame(candidate_rows)
    io_write_seconds = float(time.perf_counter() - io_t0)

    metrics = compute_backtest_metrics(
        daily_df,
        trades_df,
        max_positions=max_positions,
        blocked_by_trend_count=blocked_by_trend_count,
        total_buy_signals=total_buy_signals,
        candidates_df=candidates_df,
        enable_strength_rank=bool(enable_strength_rank),
        strength_ma=int(strength_ma),
    )
    metrics["trend_slope_block_count"] = int(trend_slope_block_count)
    metrics["trend_continuity_block_count"] = int(trend_continuity_block_count)
    metrics["precompute_seconds"] = precompute_seconds
    metrics["simulation_seconds"] = simulation_seconds
    metrics["io_write_seconds"] = io_write_seconds
    metrics["scan_all_symbols_count"] = int(scan_all_symbols_count)
    metrics["cand_index_access_count"] = int(cand_index_access_count)
    metrics["notes"] = "preindex=true; held_only_sell=true; one_shot_write=true"
    metrics["candidate_diag_reason_counts"] = dict(diag_reason_counts)
    metrics["BLOCK_WEAK_TIER_DISABLED"] = int(diag_reason_counts.get("BLOCK_WEAK_TIER_DISABLED", 0) or 0)
    metrics["exit_take_profit_count"] = exit_take_profit_count
    metrics["exit_fixed_stop_count"] = exit_fixed_stop_count
    metrics["exit_atr_stop_count"] = exit_atr_stop_count
    metrics["exit_atr_trail_count"] = exit_atr_trail_count
    metrics["exit_time_exit_count"] = exit_time_exit_count
    metrics["exit_signal_count"] = exit_signal_count
    metrics["exit_ma20_count"] = exit_ma20_count
    metrics["exit_low10_count"] = exit_low10_count
    if collect_decision_diff:
        metrics["decision_diff_preview"] = []
    if debug_first_divergence:
        metrics["debug_trace"] = debug_trace
    return PortfolioBacktestResult(daily=daily_df, trades=trades_df, candidates=candidates_df, metrics=metrics)
