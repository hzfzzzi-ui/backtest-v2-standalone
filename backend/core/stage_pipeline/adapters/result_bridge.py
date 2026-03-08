from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.core.portfolio.portfolio_builder import PortfolioBacktestResult, _compute_metrics


def augment_metrics(runtime: Any, metrics: dict[str, Any]) -> None:
    metrics["candidate_diag_reason_counts"] = dict(getattr(runtime.provider, "diag_reason_counts", {}) or {})
    metrics["blocked_by_trend_count"] = int(getattr(runtime.provider, "blocked_by_trend_count", 0) or 0)
    metrics["total_buy_signals"] = int(getattr(runtime.provider, "total_buy_signals", 0) or 0)
    metrics["min_hold_block_count"] = int(getattr(runtime.provider, "min_hold_block_count", 0) or 0)
    metrics["cooldown_block_count"] = int(getattr(runtime.provider, "cooldown_block_count", 0) or 0)
    if runtime.route_id == "provider_breakout_runtime":
        diag = dict(getattr(runtime.provider, "diag_reason_counts", {}) or {})
        metrics["exit_atr_stop_count"] = int(diag.get("ATR_STOP_LOSS", 0))
        metrics["exit_atr_trail_count"] = int(diag.get("ATR_TRAIL_EXIT", 0))
        metrics["exit_take_profit_count"] = int(diag.get("TAKE_PROFIT", 0))
        metrics["exit_fixed_stop_count"] = int(diag.get("FIXED_STOP_LOSS", 0))
        metrics["exit_time_exit_count"] = int(diag.get("TIME_EXIT", 0))
        metrics["exit_signal_count"] = 0
        metrics["exit_ma20_count"] = int(diag.get("TREND_EXIT_MA20", 0))
        metrics["exit_low10_count"] = int(diag.get("TREND_EXIT_LOW10", 0))
        metrics["market_filter_bull_days"] = int(runtime.market_filter_bull_days)
        metrics["market_filter_bear_days"] = int(runtime.market_filter_bear_days)
        metrics["market_state_trans_down_days"] = int(runtime.market_state_trans_down_days)
        metrics["market_state_trans_up_days"] = int(runtime.market_state_trans_up_days)
        metrics["trade_mode_main_days"] = int(runtime.trade_mode_main_days)
        metrics["trade_mode_light_days"] = int(runtime.trade_mode_light_days)
        metrics["trade_mode_notrade_days"] = int(runtime.trade_mode_notrade_days)
        return
    for field_name in (
        "atr_stop_exit_count",
        "atr_trail_exit_count",
        "atr_trail_update_count",
        "take_profit_exit_count",
        "fixed_stop_loss_exit_count",
        "regime_trend_days",
        "regime_mr_days",
        "mr_rsi_oversold_buy_count",
        "mr_rsi_overbought_sell_count",
        "mr_stop_loss_count",
        "mr_time_exit_count",
        "trend_slope_block_count",
        "trend_continuity_block_count",
        "entry_above_slow_ma_block_count",
        "entry_slope_block_count",
        "market_state_bull_days",
        "market_state_bear_days",
        "market_state_trans_down_days",
        "market_state_trans_up_days",
        "trade_mode_main_days",
        "trade_mode_light_days",
        "trade_mode_notrade_days",
    ):
        if hasattr(runtime.provider, field_name):
            metrics[field_name] = getattr(runtime.provider, field_name)


def build_portfolio_backtest_result(runtime: Any) -> PortfolioBacktestResult:
    daily_df = pd.DataFrame(runtime.daily_rows)
    trades_df = pd.DataFrame(runtime.trade_rows)
    candidates_df = pd.DataFrame(runtime.candidate_rows)
    metrics = _compute_metrics(
        daily_df,
        trades_df,
        max_positions=runtime.request.max_positions,
        blocked_by_trend_count=int(getattr(runtime.provider, "blocked_by_trend_count", 0) or 0),
        total_buy_signals=int(getattr(runtime.provider, "total_buy_signals", 0) or 0),
        candidates_df=candidates_df,
        enable_strength_rank=bool(runtime.request.enable_strength_rank),
        strength_ma=int(runtime.request.strength_ma),
    )
    metrics["simulation_seconds"] = float(time.perf_counter() - runtime._simulation_t0)
    metrics["precompute_seconds"] = float(getattr(runtime.provider, "precompute_seconds", 0.0) or 0.0)
    metrics["notes"] = "stage_pipeline_legacy_adapter=true"
    augment_metrics(runtime, metrics)
    return PortfolioBacktestResult(
        daily=daily_df,
        trades=trades_df,
        candidates=candidates_df,
        metrics=metrics,
    )
