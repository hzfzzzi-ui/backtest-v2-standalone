from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from backend.core.config.cn_a_governed_mainline import (
    build_governor_budget_snapshot,
    merge_governor_budget_snapshot,
)
from backend.core.config.etf_beta_contract import resolve_etf_beta_exposure_semantics as resolve_cn_etf_beta_exposure_semantics
from backend.core.engine_vector.signal_provider import DaySignals
from backend.core.portfolio.nav_snapshot import compute_nav_snapshot
from backend.core.portfolio.sizing import calc_buy_slots
from backend.core.stage_pipeline.adapters.day_controls import _resolve_runtime_asset_scope
from backend.core.stage_pipeline.contracts import AccountingSnapshot, RuntimeDiagnosticsInput
from backend.core.stage_pipeline.adapters.fill_accounting import capture_accounting_snapshot


@dataclass(frozen=True, slots=True)
class DailySnapshot:
    nav: float
    market_value: float
    controls: dict[str, Any]
    accounting_snapshot: AccountingSnapshot


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
    etf_exposure_semantics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_asset_scope = _resolve_runtime_asset_scope(runtime)
    governor_budget = controls.get("governor_budget")
    if not isinstance(governor_budget, dict):
        governor_budget = build_governor_budget_snapshot(
            asset_scope=runtime_asset_scope,
            hard_max_positions=getattr(getattr(runtime, "request", None), "max_positions", controls["effective_max_positions"]),
            effective_max_positions=controls["effective_max_positions"],
            risk_budget_multiplier=controls.get("risk_budget_multiplier"),
            drawdown=drawdown,
            drawdown_state=controls.get("dd_state"),
            regime_transition_reason=controls.get("regime_transition_reason"),
            base_state_5=controls.get("base_state_5") or controls.get("market_state_5"),
            effective_state_5=controls.get("effective_state_5") or controls.get("market_state_5"),
            coarse_state=controls.get("coarse_state"),
            effective_coarse_state=controls.get("effective_coarse_state"),
            reason_codes=controls.get("reason_codes"),
            defense_bias=controls.get("defense_bias"),
            manual_override=controls.get("manual_override"),
            breadth_max_positions=controls.get("breadth_max_positions"),
            positions_after_sell=len(runtime.positions),
        )
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
        "diagnostics_input_json": "",
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
        "moneyflow_overlay_enabled": 0,
        "moneyflow_overlay_mode": "off",
        "moneyflow_overlay_gate_on": 0,
        "moneyflow_overlay_observation_date": "",
        "moneyflow_overlay_score_source": "",
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
        "regime_engine": str(controls.get("regime_engine", "") or ""),
        "regime_confidence": controls.get("regime_confidence"),
        "regime_duration_bars": controls.get("regime_duration_bars"),
        "regime_transition_reason": str(controls.get("regime_transition_reason", "") or ""),
        "feature_availability_json": json.dumps(controls.get("feature_availability") or {}, ensure_ascii=False),
        "market_state_5": str(controls.get("market_state_5", "") or ""),
        "base_state_5": str(controls.get("base_state_5", controls.get("market_state_5", "")) or ""),
        "effective_state_5": str(controls.get("effective_state_5", controls.get("market_state_5", "")) or ""),
        "coarse_state": str(controls.get("coarse_state", "") or ""),
        "effective_coarse_state": str(controls.get("effective_coarse_state", "") or ""),
        "market_state_score": controls.get("market_state_score"),
        "market_state_raw": str(controls.get("market_state_raw", "") or ""),
        "market_state_smoothed": str(controls.get("market_state_smoothed", "") or ""),
        "risk_budget_multiplier": controls.get("risk_budget_multiplier"),
        "reason_codes_json": json.dumps(list(controls.get("reason_codes") or []), ensure_ascii=False),
        "block_scores_json": json.dumps(_jsonable(controls.get("block_scores") or {}), ensure_ascii=False),
        "subscores_json": json.dumps(_jsonable(controls.get("subscores") or {}), ensure_ascii=False),
        "manual_override_json": json.dumps(_jsonable(controls.get("manual_override") or {}), ensure_ascii=False),
        "state_stability_metrics_json": json.dumps(_jsonable(controls.get("state_stability_metrics") or {}), ensure_ascii=False),
        "defense_bias": controls.get("defense_bias"),
        "weekly_observation_flag": bool(controls.get("weekly_observation_flag", False)),
        "etf_target_exposure": (etf_exposure_semantics or {}).get("target_exposure"),
        "etf_min_deployable_exposure": (etf_exposure_semantics or {}).get("min_deployable_exposure"),
        "etf_target_exposure_source": str((etf_exposure_semantics or {}).get("target_exposure_source") or ""),
        "etf_min_deployable_exposure_source": str((etf_exposure_semantics or {}).get("min_deployable_exposure_source") or ""),
        "etf_actual_exposure": (etf_exposure_semantics or {}).get("actual_exposure"),
        "etf_actual_risk_exposure": (etf_exposure_semantics or {}).get("actual_risk_exposure"),
        "etf_actual_fallback_exposure": (etf_exposure_semantics or {}).get("actual_fallback_exposure"),
        "etf_actual_other_exposure": (etf_exposure_semantics or {}).get("actual_other_exposure"),
        "etf_deployability_gap": (etf_exposure_semantics or {}).get("deployability_gap"),
        "governor_budget_json": json.dumps(governor_budget, ensure_ascii=False),
    }
    if getattr(runtime, "route_id", "") == "provider_breakout_runtime":
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
        hfq_close_idx=getattr(runtime, "hfq_close_idx", None),
        position_entry_adj=getattr(runtime, "position_entry_adj", None),
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
    etf_exposure_semantics = _resolve_cn_etf_exposure_semantics(
        runtime,
        nav=nav,
        market_value=market_value,
        pos_values=pos_values,
        controls=controls,
    )
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
            etf_exposure_semantics=etf_exposure_semantics,
        )
    )
    runtime.prev_nav = nav
    accounting_snapshot = getattr(runtime, "_last_accounting_snapshot", None)
    daily_marks = {
        "day": day.isoformat(),
        "nav": float(nav),
        "market_value": float(market_value),
    }
    if isinstance(accounting_snapshot, AccountingSnapshot):
        accounting_snapshot = AccountingSnapshot(
            cash=accounting_snapshot.cash,
            positions=accounting_snapshot.positions,
            filled_orders=accounting_snapshot.filled_orders,
            trade_rows=accounting_snapshot.trade_rows,
            daily_marks={**dict(accounting_snapshot.daily_marks), **daily_marks},
            counters=accounting_snapshot.counters,
        )
    else:
        accounting_snapshot = capture_accounting_snapshot(
            runtime,
            trade_rows=getattr(runtime, "_last_trade_rows_today", ()),
            daily_marks=daily_marks,
        )
    return DailySnapshot(
        nav=float(nav),
        market_value=float(market_value),
        controls=dict(controls),
        accounting_snapshot=accounting_snapshot,
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


def _safe_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        out = int(value)
    except Exception:
        try:
            out = int(float(value))
        except Exception:
            return None
    return int(out)


def _normalize_cn_etf_symbol_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "." in text:
        code, venue = text.split(".", 1)
        code = code.strip()
        venue = venue.strip().lower()
        if code and venue in {"sh", "sse"}:
            return f"sh{code}"
        if code and venue in {"sz", "szse"}:
            return f"sz{code}"
    if len(text) > 2 and text[:2] in {"sh", "sz"}:
        return text
    return text


def _resolve_cn_etf_exposure_semantics(
    runtime: Any,
    *,
    nav: float,
    market_value: float,
    pos_values: list[tuple[str, float]],
    controls: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_asset_scope = _resolve_runtime_asset_scope(runtime)
    if runtime_asset_scope != "cn_etf":
        return {}
    request = getattr(runtime, "request", None)
    governed_contract = (
        dict(getattr(request, "governed_a_share", {}) or {})
        if isinstance(getattr(request, "governed_a_share", None), dict)
        else {}
    )
    etf_beta_contract = dict(governed_contract.get("etf_beta") or {})
    if not etf_beta_contract:
        return {}
    fallback_symbol = _normalize_cn_etf_symbol_key(etf_beta_contract.get("fallback_symbol"))
    risk_scope = {
        _normalize_cn_etf_symbol_key(symbol)
        for symbol in list(etf_beta_contract.get("core_beta_symbols") or ())
        + list(etf_beta_contract.get("limited_defense_candidates") or ())
        if _normalize_cn_etf_symbol_key(symbol)
    }
    actual_risk_value = 0.0
    actual_fallback_value = 0.0
    actual_other_value = 0.0
    for symbol, value in list(pos_values or ()):
        normalized = _normalize_cn_etf_symbol_key(symbol)
        value_float = _safe_float(value)
        if not normalized or value_float is None or value_float <= 0.0:
            continue
        if fallback_symbol and normalized == fallback_symbol:
            actual_fallback_value += float(value_float)
        elif normalized in risk_scope:
            actual_risk_value += float(value_float)
        else:
            actual_other_value += float(value_float)
    actual_exposure = float(market_value / nav) if nav > 0.0 else 0.0
    actual_risk_exposure = float(actual_risk_value / nav) if nav > 0.0 else 0.0
    actual_fallback_exposure = float(actual_fallback_value / nav) if nav > 0.0 else 0.0
    actual_other_exposure = float(actual_other_value / nav) if nav > 0.0 else 0.0
    governor_budget = {}
    raw_governor = controls.get("governor_budget")
    if isinstance(raw_governor, Mapping):
        governor_budget = dict(raw_governor)
    sleeve_budget = dict((governor_budget.get("sleeve_budgets") or {}).get("cn_etf_beta") or {})
    target_selected_count = sleeve_budget.get("target_selected_count")
    slot_cap = sleeve_budget.get("slot_cap")
    if target_selected_count in (None, "", 0):
        target_selected_count = controls.get("buy_slots_before_buy") or controls.get("buy_slots_after_sell")
    exposure_semantics = resolve_cn_etf_beta_exposure_semantics(
        etf_beta_contract=etf_beta_contract,
        effective_state_5=controls.get("effective_state_5") or controls.get("market_state_5"),
        total_exposure_cap=governor_budget.get("total_exposure_cap"),
        slot_cap=slot_cap,
        target_selected_count=target_selected_count,
        sleeve_budget_snapshot=sleeve_budget,
    )
    target_exposure = _safe_float(exposure_semantics.get("target_exposure"), fallback=0.0)
    deployability_gap = max(float(target_exposure or 0.0) - float(actual_exposure), 0.0)
    return {
        "target_exposure": target_exposure,
        "target_exposure_source": str(exposure_semantics.get("target_exposure_source") or ""),
        "min_deployable_exposure": _safe_float(exposure_semantics.get("min_deployable_exposure"), fallback=0.0),
        "min_deployable_exposure_source": str(exposure_semantics.get("min_deployable_exposure_source") or ""),
        "target_selected_count": int(exposure_semantics.get("target_selected_count") or 0),
        "fallback_allowed": bool(exposure_semantics.get("fallback_allowed", False)),
        "actual_exposure": float(actual_exposure),
        "actual_risk_exposure": float(actual_risk_exposure),
        "actual_fallback_exposure": float(actual_fallback_exposure),
        "actual_other_exposure": float(actual_other_exposure),
        "deployability_gap": float(deployability_gap),
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value:
            return None
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(raw) for key, raw in dict(value).items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in list(value)]
    return str(value)


def _governor_budget_payload_from_row(daily_row: Mapping[str, Any]) -> dict[str, Any]:
    raw = daily_row.get("governor_budget_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _json_array_or_empty(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return list(raw)
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        return []
    return list(parsed) if isinstance(parsed, list) else []


def _json_object_or_empty(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


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


def _build_runtime_diagnostics_input(
    runtime: Any,
    *,
    day_signals: DaySignals,
    debug_plan: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    positions_before_sell: int,
    positions_after_sell: int,
    buy_slots: int,
    candidates_count: int,
    selected_count: int,
    raw_buy_candidate_count: int,
    raw_after_held_filter_count: int,
    raw_after_slot_filter_count: int | None,
    raw_after_cash_lot_count: int | None,
) -> RuntimeDiagnosticsInput:
    return RuntimeDiagnosticsInput(
        route_id=str(getattr(runtime, "route_id", "") or ""),
        candidates_count=int(candidates_count),
        selected_count=int(selected_count),
        positions_before_sell=int(positions_before_sell),
        positions_after_sell=int(positions_after_sell),
        buy_slots=int(buy_slots),
        raw_buy_signal_count=int(diagnostics.get("raw_buy_signal_count", 0) or 0),
        raw_alpha_signal_count=int(diagnostics.get("raw_alpha_signal_count", len(day_signals.raw_alpha_signals)) or 0),
        composed_buy_signal_count=int(diagnostics.get("composed_buy_signal_count", len(day_signals.composed_buy_signals)) or 0),
        composed_sell_signal_count=int(diagnostics.get("composed_sell_signal_count", len(day_signals.composed_sell_signals)) or 0),
        raw_buy_candidate_count=int(raw_buy_candidate_count),
        raw_after_held_filter_count=int(raw_after_held_filter_count),
        raw_after_slot_filter_count=raw_after_slot_filter_count,
        raw_after_cash_lot_count=raw_after_cash_lot_count,
        benchmark_regime_on=bool(runtime.daily_rows[-1].get("benchmark_regime_on")),
        strong_risk_on=bool(getattr(day_signals, "strong_risk_on", False)),
        diagnostics=_jsonable(diagnostics),
        debug_plan=_jsonable(debug_plan),
    )


def apply_daily_decision_diagnostics(runtime: Any, *, day_signals: DaySignals, debug_plan: Mapping[str, Any]) -> None:
    if not runtime.daily_rows or runtime._current_day is None:
        return
    daily_row = runtime.daily_rows[-1]
    sell_symbols = {str(sig.symbol).lower() for sig in day_signals.sell_signals}
    positions_before_sell = int(sum(1 for qty in runtime.positions.values() if int(qty) > 0))
    positions_after_sell = int(
        sum(1 for symbol, qty in runtime.positions.items() if int(qty) > 0 and str(symbol).lower() not in sell_symbols)
    )
    buy_slots = int(calc_buy_slots(int(runtime._current_day["controls"]["effective_max_positions"]), int(positions_after_sell)))
    daily_row["positions_before_sell"] = int(positions_before_sell)
    daily_row["positions_after_sell"] = int(positions_after_sell)
    daily_row["buy_slots_before_buy"] = int(buy_slots)
    daily_row["buy_slots_after_sell"] = int(buy_slots)
    daily_row["buy_slots_calculated"] = int(buy_slots)
    diagnostics = dict(getattr(day_signals, "diagnostics", {}) or {})
    plan = dict(debug_plan or {})
    selected_symbols = list(plan.get("selected_symbols", []) or [])

    selected_count = _safe_int_or_none(plan.get("selected_count"))
    if selected_count is None:
        selected_count = int(len(selected_symbols))

    after_slot_filter_count = _safe_int_or_none(plan.get("after_slot_filter_count"))
    if after_slot_filter_count is None:
        after_slot_filter_count = _safe_int_or_none(plan.get("after_sleeve_budget_count"))

    after_cash_lot_count = _safe_int_or_none(plan.get("after_cash_lot_count"))

    raw_buy_candidate_count = _safe_int_or_none(diagnostics.get("buy_candidate_count"))
    raw_after_held_filter_count = _safe_int_or_none(diagnostics.get("after_held_filter_count"))
    if raw_buy_candidate_count is None:
        raw_buy_candidate_count = int(raw_after_held_filter_count or 0)
    if raw_after_held_filter_count is None:
        raw_after_held_filter_count = int(raw_buy_candidate_count or 0)
    candidates_count = int(plan.get("buy_candidates_count", 0) or 0)
    raw_after_slot_filter_count = after_slot_filter_count
    raw_after_cash_lot_count = after_cash_lot_count
    buy_candidate_count = int(raw_buy_candidate_count or 0)
    after_held_filter_count = int(raw_after_held_filter_count or 0)
    after_slot_filter_count = int(raw_after_slot_filter_count or 0)
    after_cash_lot_count = int(selected_count if raw_after_cash_lot_count is None else raw_after_cash_lot_count)

    daily_row["sells_executed_count"] = int(len(day_signals.sell_signals))
    daily_row["candidates_count"] = int(candidates_count)
    daily_row["selected_count"] = int(selected_count)
    daily_row["buy_candidate_count"] = int(buy_candidate_count)
    daily_row["after_held_filter_count"] = int(after_held_filter_count)
    daily_row["raw_buy_signal_count"] = int(diagnostics.get("raw_buy_signal_count", 0) or 0)
    daily_row["raw_alpha_signal_count"] = int(diagnostics.get("raw_alpha_signal_count", len(day_signals.raw_alpha_signals)) or 0)
    daily_row["composed_buy_signal_count"] = int(diagnostics.get("composed_buy_signal_count", len(day_signals.composed_buy_signals)) or 0)
    daily_row["composed_sell_signal_count"] = int(diagnostics.get("composed_sell_signal_count", len(day_signals.composed_sell_signals)) or 0)
    daily_row["after_slot_filter_count"] = int(after_slot_filter_count)
    daily_row["after_cash_lot_count"] = int(after_cash_lot_count)
    daily_row["candidates_after_held_filter_count"] = int(after_held_filter_count)
    daily_row["sorting_triggered"] = bool(
        int(plan.get("buy_candidates_count", 0) or 0)
        > int(plan.get("buy_slots", 0) or 0)
    )
    daily_row["mf_rank_triggered"] = 1 if bool(plan.get("mf_rank_triggered", False)) else 0
    daily_row["mf_rank_applied"] = 1 if bool(plan.get("mf_rank_applied", False)) else 0
    daily_row["mf_candidates_when_triggered"] = int(plan.get("mf_candidates_when_triggered", 0) or 0)
    daily_row["mf_topk_reject_count"] = int(plan.get("mf_topk_reject_count", 0) or 0)
    daily_row["mf_concentrated_selected_count"] = int(plan.get("mf_concentrated_selected_count", 0) or 0)
    daily_row["mf_gate_on"] = 1 if bool(plan.get("mf_gate_on", False)) else 0
    daily_row["moneyflow_overlay_enabled"] = 1 if bool(plan.get("moneyflow_overlay_enabled", False)) else 0
    daily_row["moneyflow_overlay_mode"] = str(plan.get("moneyflow_overlay_mode", diagnostics.get("moneyflow_overlay_mode", "off")) or "off")
    daily_row["moneyflow_overlay_gate_on"] = 1 if bool(plan.get("moneyflow_overlay_gate_on", diagnostics.get("moneyflow_overlay_gate_on", False))) else 0
    daily_row["moneyflow_overlay_observation_date"] = str(
        plan.get("moneyflow_overlay_observation_date", diagnostics.get("moneyflow_overlay_observation_date", "")) or ""
    )
    daily_row["moneyflow_overlay_score_source"] = str(
        plan.get("moneyflow_overlay_score_source", diagnostics.get("moneyflow_overlay_score_source", "")) or ""
    )
    daily_row["strong_risk_on"] = 1 if bool(getattr(day_signals, "strong_risk_on", False)) else 0
    cands_now = int(plan.get("buy_candidates_count", 0) or 0)
    slots_now = int(plan.get("buy_slots", 0) or 0)
    enable_multifactor_rank = bool(
        getattr(getattr(runtime, "request", None), "enable_multifactor_rank", diagnostics.get("enable_multifactor_rank", False))
    )
    daily_row["mf_rank_suppressed_by_strong_gate"] = (
        1
        if bool(cands_now > slots_now)
        and bool(enable_multifactor_rank)
        and not bool(plan.get("mf_gate_on", False))
        else 0
    )
    daily_row["same_symbol_conflict_count"] = int(diagnostics.get("conflict_resolution_count", 0) or 0)
    daily_row["sleeve_budget_reject_count"] = int(plan.get("sleeve_budget_reject_count", 0) or 0)
    daily_row["source_only_exit_count"] = int(
        sum(1 for signal in day_signals.sell_signals if str((getattr(signal, "meta", {}) or {}).get("exit_owner", "") or "") == "source_only")
    )
    daily_row["global_risk_override_count"] = int(
        sum(1 for signal in day_signals.sell_signals if str((getattr(signal, "meta", {}) or {}).get("exit_owner", "") or "") == "global_risk_override")
    )
    daily_row["diagnostics_input_json"] = _build_runtime_diagnostics_input(
        runtime,
        day_signals=day_signals,
        debug_plan=plan,
        diagnostics=diagnostics,
        positions_before_sell=positions_before_sell,
        positions_after_sell=positions_after_sell,
        buy_slots=buy_slots,
        candidates_count=candidates_count,
        selected_count=int(selected_count),
        raw_buy_candidate_count=int(raw_buy_candidate_count or 0),
        raw_after_held_filter_count=int(raw_after_held_filter_count or 0),
        raw_after_slot_filter_count=raw_after_slot_filter_count,
        raw_after_cash_lot_count=raw_after_cash_lot_count,
    ).to_json()
    runtime_asset_scope = _resolve_runtime_asset_scope(runtime)
    etf_target_selected_count = (
        _safe_int_or_none(diagnostics.get("etf_beta_selected_cap"))
        if runtime_asset_scope == "cn_etf"
        else None
    )
    if runtime_asset_scope == "cn_etf" and etf_target_selected_count is None:
        etf_target_selected_count = int(buy_slots)
    hard_max_positions = (
        getattr(getattr(runtime, "request", None), "max_positions", None)
        or daily_row.get("effective_max_positions")
        or (((getattr(runtime, "_current_day", None) or {}).get("controls") or {}).get("effective_max_positions"))
        or 0
    )
    target_exposure = None
    min_deployable_exposure = None
    target_exposure_source = None
    min_deployable_exposure_source = None
    fallback_allowed = None
    under_deploy_reason_codes: list[str] = []
    actual_exposure = _safe_float(daily_row.get("etf_actual_exposure"), fallback=0.0)
    actual_risk_exposure = _safe_float(daily_row.get("etf_actual_risk_exposure"), fallback=0.0)
    actual_fallback_exposure = _safe_float(daily_row.get("etf_actual_fallback_exposure"), fallback=0.0)
    actual_other_exposure = _safe_float(daily_row.get("etf_actual_other_exposure"), fallback=0.0)
    deployability_gap = _safe_float(daily_row.get("etf_deployability_gap"), fallback=0.0)
    row_governor_payload = _governor_budget_payload_from_row(daily_row)
    if runtime_asset_scope == "cn_etf":
        request = getattr(runtime, "request", None)
        governed_contract = (
            dict(getattr(request, "governed_a_share", {}) or {})
            if isinstance(getattr(request, "governed_a_share", None), dict)
            else {}
        )
        etf_beta_contract = dict(governed_contract.get("etf_beta") or {})
        deploy_target_count = max(int(etf_target_selected_count or 0), 0)
        total_exposure_cap = None
        raw_total_exposure_cap = row_governor_payload.get("total_exposure_cap")
        if raw_total_exposure_cap not in (None, ""):
            total_exposure_cap = _safe_float(raw_total_exposure_cap, fallback=float("nan"))
            if total_exposure_cap != total_exposure_cap:
                total_exposure_cap = None
        if total_exposure_cap is None:
            raw_total_risk_budget = row_governor_payload.get("total_risk_budget")
            if raw_total_risk_budget not in (None, ""):
                total_exposure_cap = _safe_float(raw_total_risk_budget, fallback=float("nan"))
                if total_exposure_cap != total_exposure_cap:
                    total_exposure_cap = None
        if total_exposure_cap is None:
            total_exposure_cap = 1.0
        exposure_semantics = resolve_cn_etf_beta_exposure_semantics(
            etf_beta_contract=etf_beta_contract,
            effective_state_5=daily_row.get("effective_state_5") or daily_row.get("market_state_5"),
            total_exposure_cap=total_exposure_cap,
            slot_cap=deploy_target_count,
            target_selected_count=deploy_target_count,
            sleeve_budget_snapshot=dict((row_governor_payload.get("sleeve_budgets") or {}).get("cn_etf_beta") or {}),
        )
        target_exposure = exposure_semantics.get("target_exposure")
        min_deployable_exposure = exposure_semantics.get("min_deployable_exposure")
        target_exposure_source = exposure_semantics.get("target_exposure_source")
        min_deployable_exposure_source = exposure_semantics.get("min_deployable_exposure_source")
        fallback_allowed = bool(exposure_semantics.get("fallback_allowed", False))
        deployability_gap = max(float(target_exposure or 0.0) - float(actual_exposure or 0.0), 0.0)
    governor_budget = merge_governor_budget_snapshot(
        row_governor_payload,
        asset_scope=runtime_asset_scope,
        hard_max_positions=hard_max_positions,
        effective_max_positions=(
            daily_row.get("effective_max_positions")
            or (((getattr(runtime, "_current_day", None) or {}).get("controls") or {}).get("effective_max_positions"))
            or 0
        ),
        risk_budget_multiplier=daily_row.get("risk_budget_multiplier"),
        drawdown=daily_row.get("drawdown"),
        drawdown_state=daily_row.get("dd_state"),
        regime_transition_reason=daily_row.get("regime_transition_reason"),
        base_state_5=daily_row.get("base_state_5") or daily_row.get("market_state_5"),
        effective_state_5=daily_row.get("effective_state_5") or daily_row.get("market_state_5"),
        coarse_state=daily_row.get("coarse_state"),
        effective_coarse_state=daily_row.get("effective_coarse_state"),
        reason_codes=_json_array_or_empty(daily_row.get("reason_codes_json")),
        defense_bias=daily_row.get("defense_bias"),
        manual_override=_json_object_or_empty(daily_row.get("manual_override_json")),
        breadth_max_positions=daily_row.get("breadth_max_positions"),
        positions_after_sell=positions_after_sell,
        sleeve_budget_mode=plan.get("sleeve_budget_mode"),
        raw_sleeve_slot_caps=dict(plan.get("sleeve_slot_caps", {}) or {}),
        raw_sleeve_available_slots=dict(plan.get("sleeve_available_slots", {}) or {}),
        raw_sleeve_positions_after_sell=dict(plan.get("sleeve_positions_after_sell", {}) or {}),
        raw_sleeve_candidate_counts=dict(plan.get("sleeve_candidate_counts", {}) or {}),
        raw_sleeve_selected_counts=dict(plan.get("sleeve_selected_counts", {}) or {}),
        sleeve_budget_reject_count=daily_row["sleeve_budget_reject_count"],
        target_exposure=target_exposure,
        min_deployable_exposure=min_deployable_exposure,
        target_exposure_source=target_exposure_source,
        min_deployable_exposure_source=min_deployable_exposure_source,
        fallback_allowed=fallback_allowed,
        actual_exposure=actual_exposure,
        actual_risk_exposure=actual_risk_exposure,
        actual_fallback_exposure=actual_fallback_exposure,
        actual_other_exposure=actual_other_exposure,
        deployability_gap=deployability_gap,
    )
    budget_reason_codes = list(governor_budget.get("budget_reason_codes") or [])
    deploy_target_count = int(etf_target_selected_count if runtime_asset_scope == "cn_etf" and etf_target_selected_count is not None else buy_slots)
    if int(selected_count) < int(deploy_target_count):
        budget_reason_codes.append("BUY_SLOT_UNUSED")
        if int(candidates_count) < int(deploy_target_count):
            budget_reason_codes.append("CANDIDATES_BELOW_BUDGET")
        if int(after_cash_lot_count) < int(after_slot_filter_count):
            budget_reason_codes.append("CASH_LOT_CONSTRAINT")
        if int(selected_count) <= 0:
            budget_reason_codes.append("NO_SELECTED_ORDERS")
    if runtime_asset_scope == "cn_etf":
        under_deploy_reason_codes.extend(
            [
                str(code).strip()
                for code in list(diagnostics.get("etf_beta_under_deploy_reason_codes") or [])
                if str(code).strip()
            ]
        )
        if int(selected_count) < int(deploy_target_count):
            under_deploy_reason_codes.extend(
                [
                    code
                    for code in [
                        "BUY_SLOT_UNUSED",
                        "CANDIDATES_BELOW_BUDGET" if int(candidates_count) < int(deploy_target_count) else "",
                        "CASH_LOT_CONSTRAINT" if int(after_cash_lot_count) < int(after_slot_filter_count) else "",
                        "NO_SELECTED_ORDERS" if int(selected_count) <= 0 else "",
                    ]
                    if code
                ]
            )
    governor_budget["budget_reason_codes"] = sorted({str(code) for code in budget_reason_codes if str(code).strip()})
    governor_budget["budget_diagnostics"] = {
        "buy_slots": int(buy_slots),
        "deploy_target_count": int(deploy_target_count),
        "selected_count": int(selected_count),
        "candidates_count": int(candidates_count),
        "after_slot_filter_count": int(after_slot_filter_count),
        "after_cash_lot_count": int(after_cash_lot_count),
        "deployment_gap": max(int(deploy_target_count) - int(selected_count), 0),
    }
    if runtime_asset_scope == "cn_etf":
        governor_budget["target_exposure"] = target_exposure
        governor_budget["min_deployable_exposure"] = min_deployable_exposure
        governor_budget["target_exposure_source"] = target_exposure_source
        governor_budget["min_deployable_exposure_source"] = min_deployable_exposure_source
        governor_budget["fallback_allowed"] = bool(fallback_allowed)
        governor_budget["under_deploy_reason_codes"] = sorted({str(code) for code in under_deploy_reason_codes if str(code).strip()})
        governor_budget["actual_exposure"] = float(actual_exposure or 0.0)
        governor_budget["actual_risk_exposure"] = float(actual_risk_exposure or 0.0)
        governor_budget["actual_fallback_exposure"] = float(actual_fallback_exposure or 0.0)
        governor_budget["actual_other_exposure"] = float(actual_other_exposure or 0.0)
        governor_budget["deployability_gap"] = float(deployability_gap or 0.0)
        sleeve_budgets = dict(governor_budget.get("sleeve_budgets") or {})
        etf_sleeve = dict(sleeve_budgets.get("cn_etf_beta") or {})
        etf_sleeve["target_exposure"] = target_exposure
        etf_sleeve["min_deployable_exposure"] = min_deployable_exposure
        etf_sleeve["target_exposure_source"] = target_exposure_source
        etf_sleeve["min_deployable_exposure_source"] = min_deployable_exposure_source
        etf_sleeve["fallback_allowed"] = bool(fallback_allowed)
        etf_sleeve["under_deploy_reason_codes"] = sorted({str(code) for code in under_deploy_reason_codes if str(code).strip()})
        etf_sleeve["target_selected_count"] = int(deploy_target_count)
        etf_sleeve["actual_exposure"] = float(actual_exposure or 0.0)
        etf_sleeve["actual_risk_exposure"] = float(actual_risk_exposure or 0.0)
        etf_sleeve["actual_fallback_exposure"] = float(actual_fallback_exposure or 0.0)
        etf_sleeve["actual_other_exposure"] = float(actual_other_exposure or 0.0)
        etf_sleeve["deployability_gap"] = float(deployability_gap or 0.0)
        sleeve_budgets["cn_etf_beta"] = etf_sleeve
        governor_budget["sleeve_budgets"] = sleeve_budgets
    daily_row["governor_budget_json"] = json.dumps(governor_budget, ensure_ascii=False)
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
