from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from backend.core.engine_vector.signal_provider import DaySignals
from backend.core.portfolio.portfolio_builder import calc_buy_slots, compute_nav_snapshot


@dataclass(frozen=True, slots=True)
class DailySnapshot:
    nav: float
    market_value: float
    controls: dict[str, Any]


def build_daily_row(
    runtime: Any,
    *,
    day: date,
    nav: float,
    daily_ret: float,
    drawdown: float,
    gross_exposure: float,
    turnover_pct: float,
    top5: list[dict[str, Any]],
    controls: Mapping[str, Any],
) -> dict[str, Any]:
    row = {
        "date": day.isoformat(),
        "nav": nav,
        "cash": runtime.cash,
        "positions_count": len(runtime.positions),
        "positions_count_end_of_day": len(runtime.positions),
        "daily_return": daily_ret,
        "drawdown": drawdown,
        "gross_exposure": gross_exposure,
        "turnover_pct": turnover_pct,
        "top5_positions_json": json.dumps(top5, ensure_ascii=False),
        "candidates_count": 0,
        "selected_count": 0,
        "top5_selected_strength_json": "[]",
        "top5_rejected_strength_json": "[]",
        "buy_slots_before_buy": 0,
        "buy_slots_after_sell": 0,
        "raw_buy_signal_count": 0,
        "raw_alpha_signal_count": 0,
        "composed_buy_signal_count": 0,
        "composed_sell_signal_count": 0,
        "buy_candidate_count": 0,
        "after_held_filter_count": 0,
        "after_slot_filter_count": 0,
        "after_cash_lot_count": 0,
        "positions_before_sell": 0,
        "sells_executed_count": 0,
        "positions_after_sell": 0,
        "buy_slots_calculated": 0,
        "candidates_after_held_filter_count": 0,
        "sorting_triggered": False,
        "mean_order_value_scale": 0.0,
        "weak_trend_buy_rate": 0.0,
        "strong_trend_buy_rate": 0.0,
        "mf_rank_triggered": 0,
        "mf_rank_applied": 0,
        "mf_candidates_when_triggered": 0,
        "mf_topk_reject_count": 0,
        "mf_concentrated_selected_count": 0,
        "mf_gate_on": 0,
        "strong_risk_on": 0,
        "mf_rank_suppressed_by_strong_gate": 0,
        "same_symbol_conflict_count": 0,
        "sleeve_budget_reject_count": 0,
        "source_only_exit_count": 0,
        "global_risk_override_count": 0,
        "trend_slope_block_count": 0,
        "trend_continuity_block_count": 0,
        "base_trend_on_rate": 0.0,
        "quality_trend_on_rate": 0.0,
        "effective_max_positions": int(controls["effective_max_positions"]),
        "breadth_score": controls.get("breadth_score"),
        "breadth_max_positions": int(controls.get("breadth_max_positions", controls["effective_max_positions"])),
        "dd_state": str(controls["dd_state"]),
    }
    if runtime.route_id == "provider_breakout_runtime":
        row["market_state"] = str(controls["market_state"])
        row["trade_mode"] = str(controls["trade_mode"])
        row["benchmark_regime_on"] = bool(controls["benchmark_regime_on"])
    return row


def prepare_daily_snapshot(runtime: Any, *, day_index: int, day: date) -> DailySnapshot:
    nav, market_value, pos_values = compute_nav_snapshot(
        cash=runtime.cash,
        positions=runtime.positions,
        close_idx=runtime.close_idx,
        day=day,
    )
    runtime.peak_nav = max(runtime.peak_nav, nav)
    daily_ret = (nav / runtime.prev_nav - 1.0) if runtime.prev_nav > 0 else 0.0
    drawdown = (nav / runtime.peak_nav - 1.0) if runtime.peak_nav > 0 else 0.0
    controls = runtime._compute_day_controls(day_index, day, drawdown)
    gross_exposure = (market_value / nav) if nav > 0 else 0.0
    turnover_pct = (runtime._traded_value_today / runtime.prev_nav) if runtime.prev_nav > 0 else 0.0
    top5 = [
        {"symbol": symbol, "value": round(value, 2)}
        for symbol, value in sorted(pos_values, key=lambda item: item[1], reverse=True)[:5]
    ]
    runtime.daily_rows.append(
        build_daily_row(
            runtime,
            day=day,
            nav=nav,
            daily_ret=daily_ret,
            drawdown=drawdown,
            gross_exposure=gross_exposure,
            turnover_pct=turnover_pct,
            top5=top5,
            controls=controls,
        )
    )
    runtime.prev_nav = nav
    return DailySnapshot(
        nav=float(nav),
        market_value=float(market_value),
        controls=dict(controls),
    )


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _safe_float(value: Any, *, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(fallback)
    if out != out:
        return float(fallback)
    return float(out)


def _signal_snapshot(signal: Any) -> dict[str, Any]:
    meta = dict(getattr(signal, "meta", {}) or {})
    return {
        "symbol": _normalized_text(getattr(signal, "symbol", "")),
        "side": str(getattr(signal, "side", "") or ""),
        "reason_code": str(getattr(signal, "reason_code", "") or ""),
        "alpha_id": str(meta.get("alpha_id", "") or ""),
        "sleeve_id": str(meta.get("sleeve_id", "") or ""),
        "raw_score": _safe_float(meta.get("raw_score"), fallback=0.0),
        "compose_score": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
        "conflict_resolution": str(meta.get("conflict_resolution", "") or ""),
        "exit_owner": str(meta.get("exit_owner", "") or ""),
        "enabled_by_policy": bool(meta.get("enabled_by_policy", True)),
    }


def _count_signals_by_alpha(signals: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for signal in list(signals or ()):
        alpha_id = str(dict(getattr(signal, "meta", {}) or {}).get("alpha_id", "") or "").strip() or "unknown"
        counts[alpha_id] = int(counts.get(alpha_id, 0)) + 1
    return counts


def _merge_count_maps(target: dict[str, int], source: Mapping[str, Any] | None) -> dict[str, int]:
    for key, value in dict(source or {}).items():
        target[str(key)] = int(target.get(str(key), 0)) + int(value or 0)
    return target


def apply_daily_decision_diagnostics(runtime: Any, *, day_signals: DaySignals, debug_plan: Mapping[str, Any]) -> None:
    if not runtime.daily_rows or runtime._current_day is None:
        return
    daily_row = runtime.daily_rows[-1]
    sell_symbols = {str(sig.symbol).lower() for sig in day_signals.sell_signals}
    positions_after_sell = int(
        sum(1 for symbol, qty in runtime.positions.items() if int(qty) > 0 and str(symbol).lower() not in sell_symbols)
    )
    buy_slots = int(calc_buy_slots(int(runtime._current_day["controls"]["effective_max_positions"]), int(positions_after_sell)))
    daily_row["positions_before_sell"] = int(sum(1 for qty in runtime.positions.values() if int(qty) > 0))
    daily_row["positions_after_sell"] = int(positions_after_sell)
    daily_row["buy_slots_before_buy"] = int(buy_slots)
    daily_row["buy_slots_after_sell"] = int(buy_slots)
    daily_row["buy_slots_calculated"] = int(buy_slots)
    daily_row["sells_executed_count"] = int(len(day_signals.sell_signals))
    daily_row["candidates_count"] = int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
    daily_row["selected_count"] = int(len((debug_plan or {}).get("selected_symbols", []) or []))
    daily_row["buy_candidate_count"] = int(len(day_signals.buy_signals))
    daily_row["after_held_filter_count"] = int(len(day_signals.buy_signals))
    daily_row["raw_buy_signal_count"] = int(day_signals.diagnostics.get("raw_buy_signal_count", len(day_signals.buy_signals)) or 0)
    daily_row["raw_alpha_signal_count"] = int(day_signals.diagnostics.get("raw_alpha_signal_count", len(day_signals.raw_alpha_signals)) or 0)
    daily_row["composed_buy_signal_count"] = int(day_signals.diagnostics.get("composed_buy_signal_count", len(day_signals.composed_buy_signals)) or 0)
    daily_row["composed_sell_signal_count"] = int(day_signals.diagnostics.get("composed_sell_signal_count", len(day_signals.composed_sell_signals)) or 0)
    daily_row["after_slot_filter_count"] = int((debug_plan or {}).get("after_sleeve_budget_count", len(day_signals.buy_signals)) or 0)
    daily_row["after_cash_lot_count"] = int(len((debug_plan or {}).get("selected_symbols", []) or []))
    daily_row["candidates_after_held_filter_count"] = int(daily_row["after_held_filter_count"])
    daily_row["sorting_triggered"] = bool(
        int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
        > int((debug_plan or {}).get("buy_slots", 0) or 0)
    )
    daily_row["mf_rank_triggered"] = 1 if bool((debug_plan or {}).get("mf_rank_triggered", False)) else 0
    daily_row["mf_rank_applied"] = 1 if bool((debug_plan or {}).get("mf_rank_applied", False)) else 0
    daily_row["mf_candidates_when_triggered"] = int((debug_plan or {}).get("mf_candidates_when_triggered", 0) or 0)
    daily_row["mf_topk_reject_count"] = int((debug_plan or {}).get("mf_topk_reject_count", 0) or 0)
    daily_row["mf_concentrated_selected_count"] = int((debug_plan or {}).get("mf_concentrated_selected_count", 0) or 0)
    daily_row["mf_gate_on"] = 1 if bool((debug_plan or {}).get("mf_gate_on", False)) else 0
    daily_row["strong_risk_on"] = 1 if bool(getattr(day_signals, "strong_risk_on", False)) else 0
    cands_now = int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
    slots_now = int((debug_plan or {}).get("buy_slots", 0) or 0)
    enable_multifactor_rank = bool(
        getattr(getattr(runtime, "request", None), "enable_multifactor_rank", day_signals.diagnostics.get("enable_multifactor_rank", False))
    )
    daily_row["mf_rank_suppressed_by_strong_gate"] = (
        1
        if bool(cands_now > slots_now)
        and bool(enable_multifactor_rank)
        and not bool((debug_plan or {}).get("mf_gate_on", False))
        else 0
    )
    daily_row["same_symbol_conflict_count"] = int(day_signals.diagnostics.get("conflict_resolution_count", 0) or 0)
    daily_row["sleeve_budget_reject_count"] = int((debug_plan or {}).get("sleeve_budget_reject_count", 0) or 0)
    daily_row["source_only_exit_count"] = int(
        sum(1 for signal in day_signals.sell_signals if str((getattr(signal, "meta", {}) or {}).get("exit_owner", "") or "") == "source_only")
    )
    daily_row["global_risk_override_count"] = int(
        sum(1 for signal in day_signals.sell_signals if str((getattr(signal, "meta", {}) or {}).get("exit_owner", "") or "") == "global_risk_override")
    )
    if not bool(day_signals.diagnostics.get("composition_enabled", False)):
        return

    raw_counts = _count_signals_by_alpha(day_signals.raw_alpha_signals)
    composed_buy_counts = _count_signals_by_alpha(day_signals.composed_buy_signals)
    composed_sell_counts = _count_signals_by_alpha(day_signals.composed_sell_signals)
    composed_counts: dict[str, int] = {}
    _merge_count_maps(composed_counts, composed_buy_counts)
    _merge_count_maps(composed_counts, composed_sell_counts)
    blocked_counts: dict[str, int] = {}
    suppressed = int(day_signals.diagnostics.get("suppressed_raw_alpha_signal_count", 0) or 0)
    if suppressed > 0:
        blocked_counts["DISABLED_BY_REGIME"] = int(suppressed)
    conflicts = int(day_signals.diagnostics.get("conflict_resolution_count", 0) or 0)
    if conflicts > 0:
        blocked_counts["SAME_SYMBOL_CONFLICT"] = int(conflicts)
    sleeve_rejects = int((debug_plan or {}).get("sleeve_budget_reject_count", 0) or 0)
    if sleeve_rejects > 0:
        blocked_counts["SLEEVE_BUDGET_EXCEEDED"] = int(sleeve_rejects)
    conflict_resolution = str((debug_plan or {}).get("same_symbol_policy") or day_signals.diagnostics.get("same_symbol_policy") or "prefer_higher_score")
    conflict_counts = {conflict_resolution: conflicts} if conflicts > 0 else {}
    audit_row = {
        "date": str(daily_row["date"]),
        "regime_tag": str(day_signals.diagnostics.get("regime_tag", "") or ""),
        "raw_alpha_signals": [_signal_snapshot(signal) for signal in day_signals.raw_alpha_signals],
        "composed_buy_signals": [_signal_snapshot(signal) for signal in day_signals.composed_buy_signals],
        "composed_sell_signals": [_signal_snapshot(signal) for signal in day_signals.composed_sell_signals],
        "raw_signal_counts_by_alpha": raw_counts,
        "composed_signal_counts_by_alpha": composed_counts,
        "blocked_signal_counts_by_reason": blocked_counts,
        "conflict_resolution_counts": conflict_counts,
        "same_symbol_conflicts": int(conflicts),
        "source_exit_count": int(daily_row["source_only_exit_count"]),
        "global_risk_override_count": int(daily_row["global_risk_override_count"]),
        "sleeve_budget": {
            "mode": str((debug_plan or {}).get("sleeve_budget_mode", "") or ""),
            "slot_caps": dict((debug_plan or {}).get("sleeve_slot_caps", {}) or {}),
            "available_slots": dict((debug_plan or {}).get("sleeve_available_slots", {}) or {}),
            "positions_after_sell": dict((debug_plan or {}).get("sleeve_positions_after_sell", {}) or {}),
            "candidate_counts": dict((debug_plan or {}).get("sleeve_candidate_counts", {}) or {}),
            "selected_counts": dict((debug_plan or {}).get("sleeve_selected_counts", {}) or {}),
        },
    }
    audit_row["flagged"] = bool(
        any(
        (
            bool(blocked_counts),
            int(audit_row["source_exit_count"]) > 0,
            int(audit_row["global_risk_override_count"]) > 0,
        )
    ))
    getattr(runtime, "composition_audit_rows", []).append(audit_row)
