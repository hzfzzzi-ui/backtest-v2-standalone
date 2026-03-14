from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.core.portfolio.portfolio_builder import PortfolioBacktestResult, _compute_metrics


def _merge_count_map(target: dict[str, int], source: dict[str, Any] | None) -> dict[str, int]:
    for key, value in dict(source or {}).items():
        target[str(key)] = int(target.get(str(key), 0)) + int(value or 0)
    return target


def _build_multi_alpha_audit(runtime: Any) -> dict[str, Any] | None:
    rows = [dict(row) for row in list(getattr(runtime, "composition_audit_rows", []) or ())]
    if not rows:
        return None
    raw_counts: dict[str, int] = {}
    composed_counts: dict[str, int] = {}
    blocked_counts: dict[str, int] = {}
    conflict_counts: dict[str, int] = {}
    source_only_exit_count = 0
    global_risk_override_count = 0
    flagged_days: list[dict[str, Any]] = []
    for row in rows:
        _merge_count_map(raw_counts, row.get("raw_signal_counts_by_alpha"))
        _merge_count_map(composed_counts, row.get("composed_signal_counts_by_alpha"))
        _merge_count_map(blocked_counts, row.get("blocked_signal_counts_by_reason"))
        _merge_count_map(conflict_counts, row.get("conflict_resolution_counts"))
        source_only_exit_count += int(row.get("source_exit_count", 0) or 0)
        global_risk_override_count += int(row.get("global_risk_override_count", 0) or 0)
        if bool(row.get("flagged")):
            flagged_days.append(dict(row))
    return {
        "contract_version": "multi_alpha_audit@1",
        "summary": {
            "raw_signal_counts_by_alpha": dict(sorted(raw_counts.items())),
            "composed_signal_counts_by_alpha": dict(sorted(composed_counts.items())),
            "blocked_signal_counts_by_reason": dict(sorted(blocked_counts.items())),
            "conflict_resolution_counts": dict(sorted(conflict_counts.items())),
            "source_only_exit_count": int(source_only_exit_count),
            "global_risk_override_count": int(global_risk_override_count),
        },
        "flagged_days": flagged_days,
    }


def augment_metrics(runtime: Any, metrics: dict[str, Any]) -> None:
    candidate_diag_reason_counts = dict(getattr(runtime.provider, "diag_reason_counts", {}) or {})
    _merge_count_map(candidate_diag_reason_counts, getattr(runtime, "order_reject_reason_counts", {}) or {})
    metrics["candidate_diag_reason_counts"] = dict(sorted(candidate_diag_reason_counts.items()))
    metrics["blocked_by_trend_count"] = int(getattr(runtime.provider, "blocked_by_trend_count", 0) or 0)
    metrics["total_buy_signals"] = int(getattr(runtime.provider, "total_buy_signals", 0) or 0)
    metrics["min_hold_block_count"] = int(getattr(runtime.provider, "min_hold_block_count", 0) or 0)
    metrics["cooldown_block_count"] = int(getattr(runtime.provider, "cooldown_block_count", 0) or 0)
    multi_alpha_audit = _build_multi_alpha_audit(runtime)
    if isinstance(multi_alpha_audit, dict):
        summary = dict(multi_alpha_audit.get("summary") or {})
        metrics["source_only_exit_count"] = int(summary.get("source_only_exit_count", 0) or 0)
        metrics["global_risk_override_count"] = int(summary.get("global_risk_override_count", 0) or 0)
        audit_payload = dict(metrics.get("audit") or {})
        audit_payload.update(multi_alpha_audit)
        metrics["audit"] = audit_payload
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
        daily_df = pd.DataFrame(getattr(runtime, "daily_rows", []) or [])
        if not daily_df.empty:
            if "breadth_score" in daily_df.columns:
                breadth_score = pd.to_numeric(daily_df["breadth_score"], errors="coerce")
                metrics["breadth_score_mean"] = float(breadth_score.dropna().mean()) if breadth_score.notna().any() else 0.0
            else:
                metrics["breadth_score_mean"] = 0.0
            if "breadth_max_positions" in daily_df.columns:
                breadth_maxpos = pd.to_numeric(daily_df["breadth_max_positions"], errors="coerce")
                metrics["breadth_maxpos_mean"] = float(breadth_maxpos.dropna().mean()) if breadth_maxpos.notna().any() else 0.0
            else:
                metrics["breadth_maxpos_mean"] = 0.0
        else:
            metrics["breadth_score_mean"] = 0.0
            metrics["breadth_maxpos_mean"] = 0.0
        metrics["breadth_gate_block_count"] = 0
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
