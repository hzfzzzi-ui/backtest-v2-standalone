from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

import numpy as np

from backend.core.algorithms.topk import stable_topk
from backend.core.config.cn_a_governed_mainline import (
    CN_ETF_BETA_BUDGET_SEMANTICS,
    CN_ETF_BETA_SLEEVE_ID,
    CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS,
    CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS,
    CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES,
    CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID,
)
def _normalized_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _safe_float(value: Any, *, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(fallback)
    if np.isnan(out):
        return float(fallback)
    return float(out)


def _signal_meta(signal: Any) -> dict[str, Any]:
    return dict(getattr(signal, "meta", {}) or {})


def _normalize_formal_reason_codes(meta: Mapping[str, Any], *, fallback: str) -> tuple[str, ...]:
    raw = meta.get("formal_reason_codes")
    if isinstance(raw, (list, tuple)):
        codes = tuple(str(code).strip() for code in raw if str(code).strip())
        if codes:
            return codes
    text = str(fallback or "").strip()
    return (text,) if text else ()


def _signal_owner_system(signal: Any) -> str:
    meta = _signal_meta(signal)
    return str(
        meta.get("owner_system")
        or meta.get("sleeve_id")
        or meta.get("alpha_id")
        or "unassigned"
    ).strip()


def _signal_sleeve_id(signal: Any) -> str:
    return _normalized_text(_signal_meta(signal).get("sleeve_id")) or "unassigned"


def _signal_rank_key(signal: Any) -> tuple[float, str, str, str]:
    meta = _signal_meta(signal)
    return (
        -_safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
        _normalized_text(meta.get("alpha_id")),
        str(getattr(signal, "reason_code", "") or ""),
        _normalized_text(getattr(signal, "symbol", "")),
    )


def _market_state_bucket_name(value: Any) -> str:
    state = str(value or "").strip().upper()
    if state in {"BULL", "TRANS_UP"}:
        return "RISK_ON"
    if state in {"BEAR", "TRANS_DOWN"}:
        return "RISK_OFF"
    return ""


def _resolve_market_state_for_day(runtime: Any, day: Any) -> str:
    provider = getattr(runtime, "provider", None)
    market_state_map = dict(getattr(provider, "_market_state_name_map", {}) or {})
    state = str(market_state_map.get(day, "") or "").strip().upper()
    if state:
        return state
    current_day = dict(getattr(runtime, "_current_day", {}) or {})
    day_signals = current_day.get("day_signals")
    diagnostics = dict(getattr(day_signals, "diagnostics", {}) or {})
    return str(diagnostics.get("market_state", "") or "").strip().upper()


def _resolve_runtime_asset_scope(runtime: Any) -> str:
    request = getattr(runtime, "request", None)
    asset_scope = str(getattr(request, "asset_scope", "") or "").strip().lower()
    if asset_scope:
        return asset_scope
    request_asset_context = getattr(request, "asset_context", None)
    if isinstance(request_asset_context, dict):
        asset_scope = str(request_asset_context.get("asset_scope") or "").strip().lower()
        if asset_scope:
            return asset_scope
    asset_context = dict(getattr(runtime, "asset_context", {}) or {})
    asset_scope = str(asset_context.get("asset_scope") or "").strip().lower()
    if asset_scope:
        return asset_scope
    data_bundle = getattr(request, "data_bundle", None)
    universe_meta = getattr(data_bundle, "universe_meta", None)
    if isinstance(universe_meta, dict):
        asset_scope = str(universe_meta.get("asset_scope") or "").strip().lower()
        if asset_scope:
            return asset_scope
    provider = getattr(runtime, "provider", None)
    if provider is not None and hasattr(provider, "_etf_beta_slot_cap_arr"):
        return "cn_etf"
    return "cn_a_equity"


def system_sleeve_debug_context(runtime: Any) -> dict[str, Any]:
    asset_scope = _resolve_runtime_asset_scope(runtime)
    if asset_scope == "cn_etf":
        return {
            "system_sleeve_id": CN_ETF_BETA_SLEEVE_ID,
            "system_sleeve_role": "market_beta_sleeve",
            "system_budget_owner": "global_portfolio_governor",
            "system_budget_semantics": CN_ETF_BETA_BUDGET_SEMANTICS,
            "system_sleeve_strategy_semantics": "weekly_relative_strength_beta",
            "system_sleeve_local_budget_controls": [],
            "system_sleeve_phase1_excluded_capabilities": [],
        }
    if asset_scope != "cn_a_equity":
        return {}
    return {
        "system_sleeve_id": CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID,
        "system_sleeve_role": "stock_alpha_sleeve",
        "system_budget_owner": "global_portfolio_governor",
        "system_budget_semantics": CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS,
        "system_sleeve_strategy_semantics": "trend_breakout_residual",
        "system_sleeve_local_budget_controls": list(CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS),
        "system_sleeve_phase1_excluded_capabilities": list(CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES),
    }


def _resolve_sleeve_weights(runtime: Any, *, day: Any | None = None) -> tuple[dict[str, float], str]:
    provider = getattr(runtime, "provider", None)
    multi_alpha = dict(getattr(provider, "_multi_alpha", {}) or {})
    composition = dict(multi_alpha.get("signal_composition") or {})
    module_specs = dict(getattr(provider, "_module_specs", {}) or {})
    weights: dict[str, float] = {}
    for item in list(composition.get("modules") or ()):
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue
        name = _normalized_text(item.get("name"))
        sleeve_id = ""
        spec = module_specs.get(name)
        if spec is not None:
            sleeve_id = _normalized_text(getattr(spec, "sleeve_id", ""))
        sleeve_id = sleeve_id or _normalized_text(item.get("sleeve_id"))
        if not sleeve_id:
            continue
        weight = _safe_float(item.get("weight"), fallback=0.0)
        if weight <= 0:
            continue
        weights[sleeve_id] = float(weights.get(sleeve_id, 0.0)) + float(weight)
    state_used = ""
    overrides_raw = composition.get("market_state_weight_overrides")
    if isinstance(overrides_raw, dict) and day is not None:
        market_state = _resolve_market_state_for_day(runtime, day)
        state_bucket = _market_state_bucket_name(market_state)
        override_payload = None
        for key in (market_state, state_bucket, "DEFAULT"):
            text = str(key or "").strip().upper()
            if not text:
                continue
            candidate = overrides_raw.get(text)
            if isinstance(candidate, dict):
                override_payload = candidate
                state_used = text
                break
        if isinstance(override_payload, dict):
            for sleeve_key, raw_weight in override_payload.items():
                sleeve_id = _normalized_text(sleeve_key)
                if not sleeve_id:
                    continue
                weight = _safe_float(raw_weight, fallback=-1.0)
                if weight < 0.0:
                    continue
                weights[sleeve_id] = float(weight)
    return weights, state_used


def _allocate_sleeve_caps(
    *,
    total_slots: int,
    active_sleeves: set[str],
    sleeve_weights: dict[str, float],
) -> dict[str, int]:
    sleeves = sorted(str(sleeve) for sleeve in active_sleeves if str(sleeve).strip())
    total_slots = max(0, int(total_slots))
    if total_slots <= 0 or not sleeves:
        return {sleeve: 0 for sleeve in sleeves}
    positive_weights = {
        sleeve: float(sleeve_weights.get(sleeve, 0.0))
        for sleeve in sleeves
        if float(sleeve_weights.get(sleeve, 0.0)) > 0
    }
    if not positive_weights:
        positive_weights = {sleeve: 1.0 for sleeve in sleeves}
    weight_total = float(sum(positive_weights.values()) or 0.0)
    raw_caps: dict[str, float] = {
        sleeve: (float(positive_weights.get(sleeve, 0.0)) / weight_total) * float(total_slots)
        for sleeve in sleeves
    }
    caps = {sleeve: int(raw_caps.get(sleeve, 0.0)) for sleeve in sleeves}
    assigned = int(sum(caps.values()))
    remainder = max(0, total_slots - assigned)
    ranking = sorted(
        sleeves,
        key=lambda sleeve: (
            -(raw_caps.get(sleeve, 0.0) - int(raw_caps.get(sleeve, 0.0))),
            -float(positive_weights.get(sleeve, 0.0)),
            sleeve,
        ),
    )
    for sleeve in ranking[:remainder]:
        caps[sleeve] = int(caps.get(sleeve, 0)) + 1
    return caps


def _count_positions_after_sell_by_sleeve(runtime: Any, *, sell_signals: list[Any]) -> dict[str, int]:
    future_positions = {str(symbol).lower(): int(qty) for symbol, qty in dict(runtime.positions or {}).items() if int(qty) > 0}
    for signal in list(sell_signals or ()):
        symbol = _normalized_text(getattr(signal, "symbol", ""))
        held = int(future_positions.get(symbol, 0))
        if held <= 0:
            continue
        qty = held if int(getattr(signal, "qty", 0) or 0) <= 0 else min(held, int(getattr(signal, "qty", 0) or 0))
        remain = held - qty
        if remain > 0:
            future_positions[symbol] = remain
        else:
            future_positions.pop(symbol, None)
    counts: dict[str, int] = defaultdict(int)
    for symbol, qty in future_positions.items():
        if int(qty) <= 0:
            continue
        holding_source = dict(getattr(runtime, "holding_sources", {}).get(symbol) or {})
        sleeve_id = _normalized_text(holding_source.get("entry_sleeve_id")) or "unassigned"
        counts[sleeve_id] = int(counts.get(sleeve_id, 0)) + 1
    return dict(counts)


def _build_candidate_reject_row(
    *,
    day: Any,
    signal: Any,
    reject_reason: str,
    selected: bool = False,
    selected_rank: int | None = None,
) -> dict[str, Any]:
    meta = _signal_meta(signal)
    return {
        "date": day.isoformat(),
        "symbol": _normalized_text(getattr(signal, "symbol", "")),
        "is_candidate": True,
        "strength": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
        "strength_ma": int(meta.get("strength_ma", 120) or 120),
        "selected": bool(selected),
        "selected_flag": bool(selected),
        "selected_rank": selected_rank,
        "reject_reason": str(reject_reason or ""),
        "alpha_source": str(meta.get("alpha_source", meta.get("alpha_id", "")) or ""),
        "final_score": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
        "mf_score": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
        "sleeve_id": str(meta.get("sleeve_id", "") or ""),
        "owner_system": str(meta.get("owner_system", meta.get("sleeve_id", "")) or ""),
        "decision_layer": "candidate_boundary",
    }


def _candidate_boundary_item_payload(
    *,
    signal: Any,
    priority: int,
) -> dict[str, Any]:
    meta = _signal_meta(signal)
    return {
        "symbol": str(getattr(signal, "symbol", "")).lower(),
        "owner_system": _signal_owner_system(signal),
        "score": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
        "reason_codes": list(
            _normalize_formal_reason_codes(meta, fallback=str(getattr(signal, "reason_code", "") or ""))
        ),
        "priority": int(priority),
    }


def _build_candidate_boundary_payload(
    *,
    day: Any,
    boundary_mode: str,
    selected_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    owner_system_slot_caps: Mapping[str, int] | None = None,
    owner_system_available_slots: Mapping[str, int] | None = None,
    owner_system_candidate_counts: Mapping[str, int] | None = None,
    owner_system_selected_counts: Mapping[str, int] | None = None,
    reject_reason_counts: Mapping[str, int] | None = None,
    notes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": "candidate_boundary_v1",
        "decision_date": day.isoformat() if hasattr(day, "isoformat") else str(day or ""),
        "boundary_mode": str(boundary_mode or "").strip(),
        "selected_candidates": [dict(item) for item in list(selected_candidates or ())],
        "owner_system_slot_caps": {
            str(key): int(value or 0) for key, value in dict(owner_system_slot_caps or {}).items()
        },
        "owner_system_available_slots": {
            str(key): int(value or 0) for key, value in dict(owner_system_available_slots or {}).items()
        },
        "owner_system_candidate_counts": {
            str(key): int(value or 0) for key, value in dict(owner_system_candidate_counts or {}).items()
        },
        "owner_system_selected_counts": {
            str(key): int(value or 0) for key, value in dict(owner_system_selected_counts or {}).items()
        },
        "reject_reason_counts": {
            str(key): int(value or 0) for key, value in dict(reject_reason_counts or {}).items()
        },
        "notes": dict(notes or {}),
    }


def build_candidate_boundary_result(
    runtime: Any,
    *,
    day: Any,
    controls: Mapping[str, Any],
    day_signals: Any,
) -> dict[str, Any]:
    buy_signals = list(day_signals.buy_signals or ())
    debug_plan = dict(system_sleeve_debug_context(runtime))
    boundary_mode = str(getattr(runtime, "_portfolio_mode", "") or "").strip().lower()
    if not buy_signals:
        payload = _build_candidate_boundary_payload(
            day=day,
            boundary_mode=boundary_mode or "passthrough",
            selected_candidates=(),
            reject_reason_counts={},
            notes={
                "empty_candidates": True,
                "execution_boundary_role": "internal_only",
            },
        )
        debug_plan["candidate_boundary_mode"] = boundary_mode or "passthrough"
        debug_plan["candidate_boundary_selected_symbols"] = []
        debug_plan["candidate_boundary_reject_count"] = 0
        return {
            "buy_signals": [],
            "candidate_rows": [],
            "reject_reason_counts": {},
            "debug_plan": debug_plan,
            "payload": payload,
        }

    if boundary_mode != "hard_sleeve_budget":
        owner_system_candidate_counts: dict[str, int] = defaultdict(int)
        for sig in buy_signals:
            owner_system_candidate_counts[_signal_sleeve_id(sig)] += 1
        selected_candidates = tuple(
            _candidate_boundary_item_payload(
                signal=sig,
                priority=priority,
            )
            for priority, sig in enumerate(buy_signals, start=1)
        )
        payload = _build_candidate_boundary_payload(
            day=day,
            boundary_mode=boundary_mode or "passthrough",
            selected_candidates=selected_candidates,
            owner_system_candidate_counts=dict(sorted(owner_system_candidate_counts.items())),
            owner_system_selected_counts=dict(sorted(owner_system_candidate_counts.items())),
            reject_reason_counts={},
            notes={
                "passthrough": True,
                "execution_boundary_role": "internal_only",
            },
        )
        debug_plan["candidate_boundary_mode"] = boundary_mode or "passthrough"
        debug_plan["candidate_boundary_selected_symbols"] = [str(sig.symbol).lower() for sig in buy_signals]
        debug_plan["candidate_boundary_reject_count"] = 0
        return {
            "buy_signals": buy_signals,
            "candidate_rows": [],
            "reject_reason_counts": {},
            "debug_plan": debug_plan,
            "payload": payload,
        }

    sleeve_weights, market_state_weight_override_key = _resolve_sleeve_weights(runtime, day=day)
    after_sell_counts = _count_positions_after_sell_by_sleeve(runtime, sell_signals=list(day_signals.sell_signals or ()))
    active_sleeves = set(after_sell_counts)
    for signal in buy_signals:
        active_sleeves.add(_signal_sleeve_id(signal))
    caps = _allocate_sleeve_caps(
        total_slots=int(controls.get("effective_max_positions", 0) or 0),
        active_sleeves=active_sleeves,
        sleeve_weights=sleeve_weights,
    )
    available_slots = {
        sleeve: max(0, int(caps.get(sleeve, 0)) - int(after_sell_counts.get(sleeve, 0)))
        for sleeve in caps
    }
    grouped: dict[str, list[Any]] = defaultdict(list)
    for signal in buy_signals:
        grouped[_signal_sleeve_id(signal)].append(signal)

    filtered_ids: set[int] = set()
    reject_counts: dict[str, int] = {}
    selected_counts: dict[str, int] = {}
    candidate_rows: list[dict[str, Any]] = []
    selected_signals: list[Any] = []
    for sleeve in sorted(grouped):
        allowed = int(available_slots.get(sleeve, 0))
        sleeve_signals = list(grouped[sleeve])
        selected = stable_topk(sleeve_signals, allowed, key=_signal_rank_key) if allowed > 0 else []
        selected_ids = {id(signal) for signal in selected}
        for chosen in selected:
            filtered_ids.add(id(chosen))
            selected_signals.append(chosen)
        selected_counts[sleeve] = int(len(selected))
        for rejected in sleeve_signals:
            if id(rejected) in selected_ids:
                continue
            reject_counts["SLEEVE_BUDGET_EXCEEDED"] = int(reject_counts.get("SLEEVE_BUDGET_EXCEEDED", 0)) + 1
            candidate_rows.append(
                _build_candidate_reject_row(
                    day=day,
                    signal=rejected,
                    reject_reason="SLEEVE_BUDGET_EXCEEDED",
                    selected=False,
                    selected_rank=None,
                )
            )

    filtered = [signal for signal in buy_signals if id(signal) in filtered_ids]
    payload = _build_candidate_boundary_payload(
        day=day,
        boundary_mode="hard_sleeve_budget",
        selected_candidates=tuple(
            _candidate_boundary_item_payload(
                signal=sig,
                priority=priority,
            )
            for priority, sig in enumerate(filtered, start=1)
        ),
        owner_system_slot_caps=caps,
        owner_system_available_slots=available_slots,
        owner_system_candidate_counts={sleeve: int(len(signals)) for sleeve, signals in grouped.items()},
        owner_system_selected_counts=selected_counts,
        reject_reason_counts=reject_counts,
        notes={
            "same_symbol_policy": str(getattr(runtime.provider, "_same_symbol_policy", "") or ""),
            "market_state_weight_override_key": str(market_state_weight_override_key or ""),
            "system_sleeve_id": str(debug_plan.get("system_sleeve_id") or ""),
            "execution_boundary_role": "internal_only",
        },
    )
    debug_plan["candidate_boundary_mode"] = "hard_sleeve_budget"
    debug_plan["candidate_boundary_selected_symbols"] = [str(sig.symbol).lower() for sig in filtered]
    debug_plan["candidate_boundary_reject_count"] = int(reject_counts.get("SLEEVE_BUDGET_EXCEEDED", 0))
    debug_plan["same_symbol_policy"] = str(getattr(runtime.provider, "_same_symbol_policy", "") or "")
    debug_plan["market_state_weight_override_key"] = str(market_state_weight_override_key or "")
    debug_plan["sleeve_budget_mode"] = "hard_sleeve_budget"
    debug_plan["sleeve_weights_effective"] = dict(sorted((str(k), float(v)) for k, v in sleeve_weights.items()))
    debug_plan["sleeve_slot_caps"] = dict(sorted(caps.items()))
    debug_plan["sleeve_available_slots"] = dict(sorted(available_slots.items()))
    debug_plan["sleeve_positions_after_sell"] = dict(sorted(after_sell_counts.items()))
    debug_plan["sleeve_candidate_counts"] = {sleeve: int(len(signals)) for sleeve, signals in sorted(grouped.items())}
    debug_plan["sleeve_selected_counts"] = dict(sorted(selected_counts.items()))
    debug_plan["sleeve_budget_reject_count"] = int(reject_counts.get("SLEEVE_BUDGET_EXCEEDED", 0))
    if debug_plan.get("system_sleeve_id"):
        debug_plan["system_sleeve_raw_ids"] = sorted(grouped.keys())
        debug_plan["system_sleeve_consumes_governor_budget"] = True
    return {
        "buy_signals": filtered,
        "candidate_rows": candidate_rows,
        "reject_reason_counts": reject_counts,
        "debug_plan": debug_plan,
        "payload": payload,
    }
