from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd

from backend.core.audit.experiment_audit import build_accounting_integrity_audit
from backend.core.portfolio.metrics import compute_backtest_metrics
from backend.core.portfolio.types import PortfolioBacktestResult
from backend.core.stage_pipeline.adapters.lineage import (
    build_execution_lineage_audit,
    finalize_execution_lineage,
)

_compute_metrics = compute_backtest_metrics


def _merge_count_map(target: dict[str, int], source: dict[str, Any] | None) -> dict[str, int]:
    for key, value in dict(source or {}).items():
        target[str(key)] = int(target.get(str(key), 0)) + int(value or 0)
    return target


def _parse_governor_budget(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return dict(parsed) if isinstance(parsed, dict) else None


def _build_governor_budget_audit(runtime: Any) -> dict[str, Any] | None:
    rows = [dict(row) for row in list(getattr(runtime, "daily_rows", []) or ())]
    if not rows:
        return None
    request = getattr(runtime, "request", None)
    asset_context = dict(getattr(request, "asset_context", {}) or {})
    asset_scope = str(asset_context.get("asset_scope") or "").strip().lower()
    reason_counts: dict[str, int] = {}
    drawdown_state_counts: dict[str, int] = {}
    recovery_state_counts: dict[str, int] = {}
    cooldown_state_counts: dict[str, int] = {}
    reduced_budget_days = 0
    defense_floor_active_days = 0
    sleeve_budget_reject_days = 0
    flagged_days: list[dict[str, Any]] = []
    latest_payload: dict[str, Any] | None = None
    for row in rows:
        payload = _parse_governor_budget(row.get("governor_budget_json"))
        if not isinstance(payload, dict) or not payload:
            continue
        latest_payload = payload
        _merge_count_map(reason_counts, {code: 1 for code in list(payload.get("budget_reason_codes") or ())})
        drawdown_state = str(payload.get("drawdown_state") or "").strip()
        recovery_state = str(payload.get("recovery_state") or "").strip()
        cooldown_state = str(payload.get("cooldown_state") or "").strip()
        if drawdown_state:
            drawdown_state_counts[drawdown_state] = int(drawdown_state_counts.get(drawdown_state, 0)) + 1
        if recovery_state:
            recovery_state_counts[recovery_state] = int(recovery_state_counts.get(recovery_state, 0)) + 1
        if cooldown_state:
            cooldown_state_counts[cooldown_state] = int(cooldown_state_counts.get(cooldown_state, 0)) + 1
        total_risk_budget = payload.get("total_risk_budget")
        if total_risk_budget is not None:
            try:
                if float(total_risk_budget) < 0.999:
                    reduced_budget_days += 1
            except Exception:
                pass
        defense_floor = payload.get("defense_floor")
        try:
            if defense_floor is not None and float(defense_floor) > 0.0:
                defense_floor_active_days += 1
        except Exception:
            pass
        reject_count = int(payload.get("sleeve_budget_reject_count", 0) or 0)
        if reject_count > 0:
            sleeve_budget_reject_days += 1
        if reject_count > 0 or bool(payload.get("budget_reason_codes")):
            flagged_days.append(
                {
                    "date": str(row.get("date") or ""),
                    "drawdown_state": drawdown_state,
                    "recovery_state": recovery_state,
                    "cooldown_state": cooldown_state,
                    "budget_reason_codes": list(payload.get("budget_reason_codes") or ()),
                    "sleeve_budget_reject_count": reject_count,
                    "budget_diagnostics": dict(payload.get("budget_diagnostics") or {}),
                }
            )
    if latest_payload is None:
        return None
    try:
        current_multiplier = (
            None
            if latest_payload.get("risk_budget_multiplier") is None
            else float(latest_payload.get("risk_budget_multiplier"))
        )
    except Exception:
        current_multiplier = None
    if current_multiplier is None:
        try:
            fallback_multiplier = (
                None
                if latest_payload.get("total_risk_budget") is None
                else float(latest_payload.get("total_risk_budget"))
            )
        except Exception:
            fallback_multiplier = None
        if fallback_multiplier is not None:
            latest_payload = dict(latest_payload)
            latest_payload["risk_budget_multiplier"] = fallback_multiplier
    if asset_scope == "cn_etf":
        latest_payload = dict(latest_payload)
        latest_payload["asset_scope"] = "cn_etf"
        latest_payload["budget_consumer_sleeve_id"] = "cn_etf_beta"
        latest_payload["budget_consumer_system_role"] = "market_beta_sleeve"
        latest_payload["budget_semantics"] = "consume_governor_sleeve_budget"
        latest_payload["phase1_boundary_excludes"] = []
        latest_payload["local_budget_controls"] = []
        sleeve_budgets = dict(latest_payload.get("sleeve_budgets") or {})
        etf_sleeve_payload = dict(sleeve_budgets.get("cn_etf_beta") or {})
        if not etf_sleeve_payload:
            stock_like_payload = next(
                (
                    dict(payload)
                    for key, payload in sleeve_budgets.items()
                    if str(key).strip() == "cn_stock_trend_alpha_core" and isinstance(payload, dict)
                ),
                {},
            )
            etf_sleeve_payload = stock_like_payload
        if not etf_sleeve_payload:
            etf_sleeve_payload = {
                "slot_cap": latest_payload.get("effective_max_positions"),
                "available_slots": latest_payload.get("effective_max_positions"),
                "positions_after_sell": 0,
                "candidate_count": 0,
                "selected_count": 0,
                "budget_share": 1.0,
                "raw_sleeve_ids": [],
            }
        etf_sleeve_payload["system_role"] = "market_beta_sleeve"
        etf_sleeve_payload["budget_source"] = str(latest_payload.get("budget_owner") or "global_portfolio_governor")
        etf_sleeve_payload["phase1_boundary_excludes"] = []
        etf_sleeve_payload["local_budget_controls"] = []
        latest_payload["sleeve_budgets"] = {"cn_etf_beta": etf_sleeve_payload}
    return {
        "contract_version": str(latest_payload.get("contract_version") or "cn_a_governor_budget@1"),
        "summary": {
            "budget_reason_counts": dict(sorted(reason_counts.items())),
            "drawdown_state_counts": dict(sorted(drawdown_state_counts.items())),
            "recovery_state_counts": dict(sorted(recovery_state_counts.items())),
            "cooldown_state_counts": dict(sorted(cooldown_state_counts.items())),
            "reduced_budget_days": int(reduced_budget_days),
            "defense_floor_active_days": int(defense_floor_active_days),
            "sleeve_budget_reject_days": int(sleeve_budget_reject_days),
        },
        "latest": latest_payload,
        "flagged_days": flagged_days,
    }


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
    planning_reject_reason_counts = dict(getattr(runtime, "order_reject_reason_counts", {}) or {})
    fill_reject_reason_counts = dict(getattr(runtime, "fill_reject_reason_counts", {}) or {})
    _merge_count_map(candidate_diag_reason_counts, planning_reject_reason_counts)
    metrics["candidate_diag_reason_counts"] = dict(sorted(candidate_diag_reason_counts.items()))
    metrics["planning_reject_reason_counts"] = dict(sorted(planning_reject_reason_counts.items()))
    metrics["fill_reject_reason_counts"] = dict(sorted(fill_reject_reason_counts.items()))
    metrics["planning_cash_skip_count"] = int(
        int(planning_reject_reason_counts.get("SKIP_NO_CASH", 0) or 0)
        + int(planning_reject_reason_counts.get("SKIP_CASH_INSUFFICIENT", 0) or 0)
    )
    metrics["fill_cash_reject_count"] = int(fill_reject_reason_counts.get("INSUFFICIENT_CASH", 0) or 0)
    metrics["blocked_by_trend_count"] = int(getattr(runtime.provider, "blocked_by_trend_count", 0) or 0)
    metrics["total_buy_signals"] = int(getattr(runtime.provider, "total_buy_signals", 0) or 0)
    metrics["min_hold_block_count"] = int(getattr(runtime.provider, "min_hold_block_count", 0) or 0)
    metrics["cooldown_block_count"] = int(getattr(runtime.provider, "cooldown_block_count", 0) or 0)
    metrics["bull_breakout_quality_veto_block_count"] = int(
        getattr(runtime.provider, "bull_breakout_quality_veto_block_count", 0) or 0
    )
    metrics["bull_breakout_quality_veto_residual_block_count"] = int(
        getattr(runtime.provider, "bull_breakout_quality_veto_residual_block_count", 0) or 0
    )
    metrics["bull_breakout_quality_veto_margin_block_count"] = int(
        getattr(runtime.provider, "bull_breakout_quality_veto_margin_block_count", 0) or 0
    )
    accounting_integrity = build_accounting_integrity_audit(
        initial_cash=getattr(runtime.request, "initial_cash", None),
        daily_snapshots=getattr(runtime, "accounting_audit_rows", ()),
    )
    execution_lineage_rows = finalize_execution_lineage(runtime)
    execution_lineage = build_execution_lineage_audit(
        execution_lineage_rows,
        planning_reject_reason_counts=planning_reject_reason_counts,
        fill_reject_reason_counts=fill_reject_reason_counts,
    )
    audit_payload = dict(metrics.get("audit") or {})
    audit_payload["accounting_integrity"] = accounting_integrity
    audit_payload["execution_lineage"] = execution_lineage
    metrics["audit"] = audit_payload
    metrics["execution_lineage_ledger"] = execution_lineage_rows
    multi_alpha_audit = _build_multi_alpha_audit(runtime)
    if isinstance(multi_alpha_audit, dict):
        summary = dict(multi_alpha_audit.get("summary") or {})
        metrics["source_only_exit_count"] = int(summary.get("source_only_exit_count", 0) or 0)
        metrics["global_risk_override_count"] = int(summary.get("global_risk_override_count", 0) or 0)
        audit_payload = dict(metrics.get("audit") or {})
        audit_payload.update(multi_alpha_audit)
        metrics["audit"] = audit_payload
    governor_budget_audit = _build_governor_budget_audit(runtime)
    if isinstance(governor_budget_audit, dict):
        summary = dict(governor_budget_audit.get("summary") or {})
        metrics["risk_budget_active_days"] = int(summary.get("reduced_budget_days", 0) or 0)
        audit_payload = dict(metrics.get("audit") or {})
        audit_payload["governor_budget"] = governor_budget_audit
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
        if not daily_df.empty and "regime_confidence" in daily_df.columns:
            regime_conf = pd.to_numeric(daily_df["regime_confidence"], errors="coerce")
            confidence_floor = float(
                getattr(
                    getattr(getattr(runtime, "request", None), "regime_engine_cfg", None),
                    "persistence",
                    None,
                ).confidence_floor
            ) if getattr(getattr(getattr(runtime, "request", None), "regime_engine_cfg", None), "persistence", None) is not None else 0.55
            metrics["regime_confidence_mean"] = float(regime_conf.dropna().mean()) if regime_conf.notna().any() else 0.0
            metrics["regime_low_confidence_days"] = int((regime_conf < confidence_floor).sum()) if regime_conf.notna().any() else 0
            metrics["regime_low_confidence_ratio"] = float((regime_conf < confidence_floor).mean()) if regime_conf.notna().any() else 0.0
        if not daily_df.empty and "market_state" in daily_df.columns:
            state_series = daily_df["market_state"].fillna("").astype(str)
            metrics["regime_switch_count"] = int((state_series != state_series.shift(1)).sum() - (1 if len(state_series) > 0 else 0))
        if not daily_df.empty and "regime_transition_reason" in daily_df.columns:
            reason_counts = (
                daily_df["regime_transition_reason"]
                .fillna("")
                .astype(str)
                .loc[lambda s: s.str.len() > 0]
                .value_counts()
                .to_dict()
            )
            metrics["regime_transition_reason_counts"] = {str(key): int(value) for key, value in reason_counts.items()}
        if not daily_df.empty and "feature_availability_json" in daily_df.columns:
            feature_unavailable_days = 0
            for raw in daily_df["feature_availability_json"].fillna("").astype(str):
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                if not bool(payload.get("required_blocks_ready", True)) or bool(payload.get("fallback_active", False)):
                    feature_unavailable_days += 1
            metrics["regime_feature_unavailable_days"] = int(feature_unavailable_days)
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
    cash_events_df = pd.DataFrame(getattr(runtime, "dividend_event_rows", []) or [])
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
    metrics["notes"] = "stage_pipeline_bridge=true"
    augment_metrics(runtime, metrics)
    return PortfolioBacktestResult(
        daily=daily_df,
        trades=trades_df,
        candidates=candidates_df,
        metrics=metrics,
        cash_events=cash_events_df,
    )
