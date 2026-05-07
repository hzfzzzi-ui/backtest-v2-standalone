from __future__ import annotations

from typing import Any, Mapping

from backend.core.portfolio.candidate_plan import build_candidate_plan
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.stage_pipeline.adapters.candidate_boundary import _normalize_formal_reason_codes, _safe_float, _signal_meta, _signal_owner_system


def _candidate_plan_item_payload(
    *,
    item: Mapping[str, Any],
    priority: int,
) -> dict[str, Any]:
    signal = item.get("signal")
    meta = _signal_meta(signal)
    return {
        "symbol": str(item.get("symbol", "")).lower(),
        "owner_system": _signal_owner_system(signal),
        "score": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
        "reason_codes": list(
            _normalize_formal_reason_codes(
                meta,
                fallback=str(getattr(signal, "reason_code", "") or ""),
            )
        ),
        "priority": int(priority),
    }


def _build_candidate_plan_payload(
    *,
    day: Any,
    plan_mode: str,
    planned_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    planned_rotation_sell_symbols: list[str] | tuple[str, ...],
    reject_reason_counts: Mapping[str, int] | None = None,
    notes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": "candidate_plan_v1",
        "decision_date": day.isoformat() if hasattr(day, "isoformat") else str(day or ""),
        "plan_mode": str(plan_mode or "").strip(),
        "planned_candidates": [dict(candidate) for candidate in list(planned_candidates or ())],
        "planned_rotation_sell_symbols": [str(symbol).lower() for symbol in list(planned_rotation_sell_symbols or ())],
        "reject_reason_counts": {
            str(key): int(value or 0) for key, value in dict(reject_reason_counts or {}).items()
        },
        "notes": dict(notes or {}),
    }


def build_candidate_plan_result(
    runtime: Any,
    *,
    day: Any,
    controls: Mapping[str, Any],
    day_signals: Any,
    candidate_boundary: Mapping[str, Any],
    next_open: Mapping[str, float],
    nav: float,
) -> dict[str, Any]:
    market_state_today = str(
        controls.get("effective_state_5")
        or controls.get("market_state_5")
        or controls.get("market_state")
        or ""
    )
    mf_gate_on_today = resolve_mf_gate_on_today(
        enable_multifactor_rank=bool(getattr(getattr(runtime, "request", None), "enable_multifactor_rank", False)),
        mf_rank_gate_mode=str(getattr(getattr(runtime, "request", None), "mf_rank_gate_mode", "ALWAYS_ON") or "ALWAYS_ON"),
        risk_on_today=bool(controls.get("risk_on_today", False)),
        strong_risk_on_today=bool(getattr(day_signals, "strong_risk_on", False)),
        market_state_today=market_state_today,
    )
    plan = build_candidate_plan(
        positions=dict(getattr(runtime, "positions", {}) or {}),
        cash_available=float(getattr(runtime, "cash", 0.0) or 0.0),
        nav_close=float(nav),
        max_positions=int(controls.get("effective_max_positions", 0) or 0),
        lot_size=int(getattr(getattr(runtime, "request", None), "lot_size", 100) or 100),
        sell_signals=list(day_signals.sell_signals or ()),
        buy_signals=list(candidate_boundary.get("buy_signals") or day_signals.buy_signals or ()),
        next_open=dict(next_open or {}),
        enable_strength_rank=bool(getattr(getattr(runtime, "request", None), "enable_strength_rank", False)),
        strength_ma=int(getattr(getattr(runtime, "request", None), "strength_ma", 120) or 120),
        strength_map=dict(getattr(day_signals, "strength_map", {}) or {}),
        enable_multifactor_rank=bool(getattr(getattr(runtime, "request", None), "enable_multifactor_rank", False)),
        mf_topk=int(getattr(getattr(runtime, "request", None), "mf_topk", 10) or 10),
        mf_concentrate_topn=int(getattr(getattr(runtime, "request", None), "mf_concentrate_topn", 3) or 3),
        mf_concentrate_scale=float(getattr(getattr(runtime, "request", None), "mf_concentrate_scale", 1.5) or 1.5),
        mf_gate_on_today=bool(mf_gate_on_today),
        mf_score_map=dict(getattr(day_signals, "mf_score_map", {}) or {}),
        overlay_mode=str(getattr(day_signals, "overlay_mode", "off") or "off"),
        overlay_gate_on_today=bool(getattr(day_signals, "overlay_gate_on_today", False)),
        overlay_score_map=dict(getattr(day_signals, "overlay_score_map", {}) or {}),
        overlay_band_limit=int(getattr(day_signals, "overlay_band_limit", 0) or 0),
        overlay_observation_date=getattr(day_signals, "overlay_observation_date", None),
        overlay_score_source=str(getattr(day_signals, "overlay_score_source", "") or ""),
        momentum_top_pct=float(getattr(getattr(runtime, "request", None), "momentum_top_pct", 0.0) or 0.0),
        decision_date=day,
        base_order_value=float(getattr(getattr(runtime, "request", None), "base_order_value", 0.0) or 0.0),
        weight_mode=str(getattr(runtime, "_weight_mode", "equal") or "equal"),
        min_positions=int(getattr(runtime, "_min_positions_cfg", 0) or 0),
        tilt_strength=float(getattr(runtime, "_tilt_strength", 0.0) or 0.0),
        tilt_top_n=int(getattr(runtime, "_tilt_top_n", 0) or 0),
        tilt_bottom_n=int(getattr(runtime, "_tilt_bottom_n", 0) or 0),
        atr_close_map=dict(getattr(runtime, "_candidate_plan_atr_close_map", {}) or {}),
        min_trade_price=float(getattr(runtime, "_min_trade_price", 0.0) or 0.0),
        decision_close_map={
            str(sig.symbol).lower(): float(getattr(runtime, "close_idx", {}).get((day, str(sig.symbol).lower()), 0.0) or 0.0)
            for sig in list(candidate_boundary.get("buy_signals") or day_signals.buy_signals or ())
        },
        enable_entry_gap_guard=bool(getattr(getattr(getattr(runtime, "request", None), "strategy", None), "enable_entry_gap_guard", False)),
        entry_gap_guard_pct=float(getattr(getattr(getattr(runtime, "request", None), "strategy", None), "entry_gap_guard_pct", 0.0) or 0.0),
        score_weight_min_scale=float(getattr(getattr(runtime, "_sizing_cfg", None), "score_weight_min_scale", 0.75) or 0.75),
        score_weight_max_scale=float(getattr(getattr(runtime, "_sizing_cfg", None), "score_weight_max_scale", 1.25) or 1.25),
        candidate_plan_mode=str(getattr(getattr(runtime, "_sizing_cfg", None), "candidate_plan_mode", "ranked") or "ranked"),
        cash_aware_search_top_n=int(getattr(getattr(runtime, "_sizing_cfg", None), "cash_aware_search_top_n", 12) or 12),
        holding_entry_dates={
            str(symbol).lower(): (
                source.entry_date if hasattr(source, "entry_date") else dict(source or {}).get("entry_date")
            )
            for symbol, source in dict(getattr(runtime, "holding_sources", {}) or {}).items()
        },
        market_state_today=market_state_today,
        strong_risk_on_today=bool(getattr(day_signals, "strong_risk_on", False)),
        rotation_replace_enabled=bool(getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_enabled", False)),
        rotation_replace_only_strong_risk_on=bool(getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_only_strong_risk_on", True)),
        rotation_replace_max_swaps_per_day=int(getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_max_swaps_per_day", 1) or 1),
        rotation_replace_candidate_top_n=int(getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_candidate_top_n", 3) or 3),
        rotation_replace_min_score_gap=float(getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_min_score_gap", 0.15) or 0.15),
        rotation_min_hold_days=int(getattr(getattr(getattr(runtime, "request", None), "strategy", None), "min_hold_days", 0) or 0),
    )
    planned_items = list(plan.get("planned_items") or [])
    payload = _build_candidate_plan_payload(
        day=day,
        plan_mode=str(plan.get("plan_mode") or ""),
        planned_candidates=tuple(
            _candidate_plan_item_payload(
                item=item,
                priority=priority,
            )
            for priority, item in enumerate(planned_items, start=1)
        ),
        planned_rotation_sell_symbols=tuple(str(sym).lower() for sym in list(plan.get("planned_rotation_sell_symbols") or ())),
        reject_reason_counts=dict(plan.get("reject_reason_counts") or {}),
        notes={
            "candidate_boundary_mode": str((dict(candidate_boundary.get("payload") or {})).get("boundary_mode") or ""),
            "planned_rotation_sell_count": int(len(list(plan.get("planned_rotation_sell_signals") or ()))),
            "execution_boundary_role": "internal_only",
        },
    )
    return {
        "planned_items": planned_items,
        "buy_signals": list(plan.get("planned_buy_signals") or ()),
        "planned_rotation_sell_signals": list(plan.get("planned_rotation_sell_signals") or ()),
        "candidate_rows": list(plan.get("candidate_rows") or ()),
        "reject_reason_counts": dict(plan.get("reject_reason_counts") or {}),
        "rotation_pair_meta_by_symbol": dict(plan.get("rotation_pair_meta_by_symbol") or {}),
        "debug_plan": dict(plan.get("debug_plan") or {}),
        "payload": payload,
    }
