from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from backend.core.config.cn_a_governed_mainline import (
    CN_STOCK_ALPHA_CORE_BUDGET_SEMANTICS,
    CN_STOCK_ALPHA_CORE_LOCAL_BUDGET_CONTROLS,
    CN_STOCK_ALPHA_CORE_PHASE1_EXCLUDED_CAPABILITIES,
    CN_STOCK_TREND_ALPHA_CORE_SLEEVE_ID,
)
from backend.core.core.types import Side
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.portfolio.portfolio_runtime import build_rebalance_orders
from backend.core.stage_pipeline.contracts import ExecutionIntent, StageOutputs
from backend.core.stage_pipeline.adapters.lineage import record_scheduled_orders


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


def _normalize_pending_order_payload(raw_order: Any) -> dict[str, Any]:
    if isinstance(raw_order, dict):
        payload = dict(raw_order)
    else:
        payload = {
            "side": getattr(raw_order, "side"),
            "symbol": getattr(raw_order, "symbol"),
            "qty": getattr(raw_order, "qty"),
            "reason_code": getattr(raw_order, "reason_code", ""),
            "meta": getattr(raw_order, "meta", None),
        }
    return {
        "side": payload.get("side"),
        "symbol": _normalized_text(payload.get("symbol")),
        "qty": int(payload.get("qty", 0) or 0),
        "reason_code": str(payload.get("reason_code", "") or ""),
        "meta": dict(payload.get("meta") or {}),
    }


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
    asset_context = dict(getattr(runtime, "asset_context", {}) or {})
    asset_scope = str(asset_context.get("asset_scope") or "").strip().lower()
    if asset_scope:
        return asset_scope
    return "cn_a_equity"


def _stock_alpha_core_debug_context(runtime: Any) -> dict[str, Any]:
    if _resolve_runtime_asset_scope(runtime) != "cn_a_equity":
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


def _append_sleeve_budget_reject(
    *,
    day: Any,
    signal: Any,
    strength_ma: int,
    candidate_rows: list[dict[str, Any]] | None,
) -> None:
    if candidate_rows is None:
        return
    meta = _signal_meta(signal)
    candidate_rows.append(
        {
            "date": day.isoformat(),
            "symbol": _normalized_text(getattr(signal, "symbol", "")),
            "is_candidate": True,
            "strength": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
            "strength_ma": int(strength_ma),
            "selected": False,
            "selected_flag": False,
            "selected_rank": None,
            "reject_reason": "SLEEVE_BUDGET_EXCEEDED",
            "alpha_source": str(meta.get("alpha_source", meta.get("alpha_id", "")) or ""),
            "final_score": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
            "mf_score": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
            "sleeve_id": str(meta.get("sleeve_id", "") or ""),
        }
    )


def _apply_hard_sleeve_budget(
    runtime: Any,
    *,
    day: Any,
    controls: dict[str, Any],
    day_signals: Any,
    candidate_rows: list[dict[str, Any]] | None,
    debug_plan: dict[str, Any],
) -> tuple[list[Any], dict[str, int]]:
    buy_signals = list(day_signals.buy_signals or ())
    if str(getattr(runtime, "_portfolio_mode", "") or "").strip().lower() != "hard_sleeve_budget":
        return buy_signals, {}
    if not buy_signals:
        debug_plan["sleeve_budget_mode"] = "hard_sleeve_budget"
        debug_plan["sleeve_slot_caps"] = {}
        debug_plan["sleeve_available_slots"] = {}
        debug_plan["sleeve_candidate_counts"] = {}
        return buy_signals, {}

    sleeve_weights, market_state_weight_override_key = _resolve_sleeve_weights(runtime, day=day)
    after_sell_counts = _count_positions_after_sell_by_sleeve(runtime, sell_signals=list(day_signals.sell_signals or ()))
    active_sleeves = set(after_sell_counts)
    for signal in buy_signals:
        active_sleeves.add(_signal_sleeve_id(signal))
    caps = _allocate_sleeve_caps(
        total_slots=int(controls["effective_max_positions"]),
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
    strength_ma = int(getattr(runtime.request, "strength_ma", 120) or 120)
    for sleeve in sorted(grouped):
        ranked = sorted(grouped[sleeve], key=_signal_rank_key)
        allowed = int(available_slots.get(sleeve, 0))
        selected = ranked[:allowed] if allowed > 0 else []
        for chosen in selected:
            filtered_ids.add(id(chosen))
        selected_counts[sleeve] = int(len(selected))
        for rejected in ranked[allowed:]:
            reject_counts["SLEEVE_BUDGET_EXCEEDED"] = int(reject_counts.get("SLEEVE_BUDGET_EXCEEDED", 0)) + 1
            _append_sleeve_budget_reject(
                day=day,
                signal=rejected,
                strength_ma=strength_ma,
                candidate_rows=candidate_rows,
            )

    debug_plan["sleeve_budget_mode"] = "hard_sleeve_budget"
    debug_plan["same_symbol_policy"] = str(getattr(runtime.provider, "_same_symbol_policy", "") or "")
    debug_plan["market_state_weight_override_key"] = str(market_state_weight_override_key or "")
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
    filtered = [signal for signal in buy_signals if id(signal) in filtered_ids]
    debug_plan["after_sleeve_budget_count"] = int(len(filtered))
    return filtered, reject_counts


def _merge_deferred_sell_orders(next_day_orders: list[dict[str, Any]], deferred_sell_orders: list[Any]) -> tuple[list[dict[str, Any]], int]:
    if not deferred_sell_orders:
        return next_day_orders, 0
    merged: list[dict[str, Any]] = []
    sell_index_by_symbol: dict[str, int] = {}
    for order in list(next_day_orders or ()):
        normalized = _normalize_pending_order_payload(order)
        if normalized["side"] == Side.SELL:
            sell_index_by_symbol[normalized["symbol"]] = len(merged)
        merged.append(normalized)
    deferred_count = 0
    for raw_order in list(deferred_sell_orders or ()):
        normalized = _normalize_pending_order_payload(raw_order)
        if normalized["side"] != Side.SELL:
            continue
        deferred_count += 1
        idx = sell_index_by_symbol.get(normalized["symbol"])
        if idx is None:
            sell_index_by_symbol[normalized["symbol"]] = len(merged)
            merged.append(normalized)
            continue
        existing = merged[idx]
        existing["qty"] = max(int(existing.get("qty", 0) or 0), int(normalized.get("qty", 0) or 0))
        merged_meta = dict(existing.get("meta") or {})
        merged_meta.update(dict(normalized.get("meta") or {}))
        existing["meta"] = merged_meta
        if not str(existing.get("reason_code") or "").strip():
            existing["reason_code"] = str(normalized.get("reason_code") or "")
    merged.sort(key=lambda order: 0 if order["side"] == Side.SELL else 1)
    return merged, deferred_count


def _merge_runtime_reject_reason_counts(runtime: Any, reject_reason_counts: dict[str, Any] | None) -> None:
    if not isinstance(reject_reason_counts, dict) or not reject_reason_counts:
        return
    target = getattr(runtime, "order_reject_reason_counts", None)
    if not isinstance(target, dict):
        target = {}
        setattr(runtime, "order_reject_reason_counts", target)
    for reason, count in reject_reason_counts.items():
        key = str(reason or "").strip()
        if not key:
            continue
        target[key] = int(target.get(key, 0)) + int(count or 0)


def _retain_fast_mode_candidate_diagnostics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in list(rows or ()):
        reason = str((row or {}).get("reject_reason", "") or "").strip().upper()
        blocked = bool((row or {}).get("cash_blocked_flag", False))
        if blocked or reason == "SKIP_NO_CASH":
            kept.append(dict(row))
    return kept


def build_s7_order_stage_output(runtime: Any) -> StageOutputs:
    if runtime._current_day is None:
        raise RuntimeError("current day is not prepared")

    day = runtime._current_day["day"]
    controls = runtime._current_day["controls"]
    day_signals = runtime._current_day["day_signals"]
    next_open = dict(runtime._current_day["next_open"])
    nav = float(runtime._current_day["nav"])
    debug_plan: dict[str, Any] = _stock_alpha_core_debug_context(runtime)
    day_candidate_rows: list[dict[str, Any]] = []
    mf_gate_on_today = resolve_mf_gate_on_today(
        enable_multifactor_rank=bool(runtime.request.enable_multifactor_rank),
        mf_rank_gate_mode=str(runtime.request.mf_rank_gate_mode or "ALWAYS_ON"),
        risk_on_today=bool(controls["risk_on_today"]),
        strong_risk_on_today=bool(day_signals.strong_risk_on),
        market_state_today=str(controls.get("market_state") or ""),
    )
    atr_close_map: dict[str, tuple[float, float]] = {}
    provider_feats = getattr(runtime.provider, "_feats", None)
    provider_mx = getattr(runtime.provider, "_mx", None)
    provider_sym_to_col = getattr(runtime.provider, "_sym_to_col", {})
    if runtime._weight_mode == "inverse_vol" and provider_feats is not None and provider_mx is not None:
        row_idx = int(runtime._prepared_day_index or 0)
        for symbol, col_idx in dict(provider_sym_to_col or {}).items():
            atr_v = float(provider_feats.atr14[row_idx, col_idx])
            close_v = float(provider_mx.close[row_idx, col_idx])
            if not (np.isnan(atr_v) or np.isnan(close_v)):
                atr_close_map[str(symbol).lower()] = (atr_v, close_v)
    final_buy_signals, pre_reject_reason_counts = _apply_hard_sleeve_budget(
        runtime,
        day=day,
        controls=controls,
        day_signals=day_signals,
        candidate_rows=day_candidate_rows,
        debug_plan=debug_plan,
    )

    orders = build_rebalance_orders(
        positions=runtime.positions,
        cash_available=runtime.cash,
        nav_close=nav,
        max_positions=int(controls["effective_max_positions"]),
        lot_size=runtime.request.lot_size,
        sell_signals=list(day_signals.sell_signals),
        buy_signals=list(final_buy_signals),
        next_open=next_open,
        enable_strength_rank=bool(runtime.request.enable_strength_rank),
        strength_ma=int(runtime.request.strength_ma),
        strength_top_k_mode=str(runtime.request.strength_top_k_mode),
        strength_map=dict(day_signals.strength_map),
        enable_multifactor_rank=bool(runtime.request.enable_multifactor_rank),
        mf_topk=int(runtime.request.mf_topk),
        mf_concentrate_topn=int(runtime.request.mf_concentrate_topn),
        mf_concentrate_scale=float(runtime.request.mf_concentrate_scale),
        mf_gate_on_today=bool(mf_gate_on_today),
        mf_score_map=dict(day_signals.mf_score_map),
        overlay_mode=str(getattr(day_signals, "overlay_mode", "off") or "off"),
        overlay_gate_on_today=bool(getattr(day_signals, "overlay_gate_on_today", False)),
        overlay_score_map=dict(getattr(day_signals, "overlay_score_map", {}) or {}),
        overlay_observation_date=getattr(day_signals, "overlay_observation_date", None),
        overlay_score_source=str(getattr(day_signals, "overlay_score_source", "") or ""),
        momentum_top_pct=float(runtime.request.momentum_top_pct),
        decision_date=day,
        candidate_audit=day_candidate_rows,
        debug_plan=debug_plan,
        weight_mode=runtime._weight_mode,
        min_positions=runtime._min_positions_cfg,
        tilt_strength=float(getattr(runtime, "_tilt_strength", 0.0) or 0.0),
        tilt_top_n=int(getattr(runtime, "_tilt_top_n", 0) or 0),
        tilt_bottom_n=int(getattr(runtime, "_tilt_bottom_n", 0) or 0),
        atr_close_map=atr_close_map,
        min_trade_price=runtime._min_trade_price,
        decision_close_map={
            str(sig.symbol).lower(): float(getattr(runtime, "close_idx", {}).get((day, str(sig.symbol).lower()), 0.0) or 0.0)
            for sig in final_buy_signals
        },
        enable_entry_gap_guard=bool(getattr(getattr(runtime.request, "strategy", None), "enable_entry_gap_guard", False)),
        entry_gap_guard_pct=float(getattr(getattr(runtime.request, "strategy", None), "entry_gap_guard_pct", 0.0) or 0.0),
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
        strong_risk_on_today=bool(day_signals.strong_risk_on),
        rotation_replace_enabled=bool(getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_enabled", False)),
        rotation_replace_only_strong_risk_on=bool(
            getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_only_strong_risk_on", True)
        ),
        rotation_replace_max_swaps_per_day=int(
            getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_max_swaps_per_day", 1) or 1
        ),
        rotation_replace_candidate_top_n=int(
            getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_candidate_top_n", 3) or 3
        ),
        rotation_replace_min_score_gap=float(
            getattr(getattr(runtime, "_sizing_cfg", None), "rotation_replace_min_score_gap", 0.15) or 0.15
        ),
        rotation_min_hold_days=int(getattr(getattr(runtime.request, "strategy", None), "min_hold_days", 0) or 0),
    )
    merged_reject_reason_counts = dict(pre_reject_reason_counts or {})
    for reason, count in dict((debug_plan or {}).get("reject_reason_counts", {}) or {}).items():
        merged_reject_reason_counts[str(reason)] = int(merged_reject_reason_counts.get(str(reason), 0)) + int(count or 0)
    debug_plan["reject_reason_counts"] = merged_reject_reason_counts
    _merge_runtime_reject_reason_counts(runtime, merged_reject_reason_counts)
    if bool(runtime.request.fast_mode):
        runtime.candidate_rows.extend(_retain_fast_mode_candidate_diagnostics(day_candidate_rows))
    else:
        runtime.candidate_rows.extend(day_candidate_rows)

    runtime._apply_daily_decision_diagnostics(
        day_signals=day_signals,
        debug_plan=debug_plan,
    )
    next_day_orders = [
        {
            "side": order.side,
            "symbol": str(order.symbol).lower(),
            "qty": int(order.qty),
            "reason_code": str(order.reason_code),
            "meta": dict(order.meta or {}),
        }
        for order in orders
    ]
    next_day_orders = record_scheduled_orders(
        runtime,
        decision_date=day,
        scheduled_date=runtime._current_day.get("next_trading_day"),
        orders=next_day_orders,
    )
    next_day_orders, deferred_sell_count = _merge_deferred_sell_orders(
        next_day_orders,
        list(getattr(runtime, "deferred_sell_orders", []) or ()),
    )
    setattr(runtime, "deferred_sell_orders", [])
    execution_intent = ExecutionIntent(
        as_of_date=day,
        buy_candidates=tuple(str(sig.symbol).lower() for sig in final_buy_signals),
        sell_candidates=tuple(str(sig.symbol).lower() for sig in day_signals.sell_signals),
        hold_overrides=tuple(runtime._current_day["holding_symbols"]),
        risk_flags=tuple(
            flag
            for flag in (
                "RISK_ON" if bool(controls.get("risk_on_today")) else "RISK_OFF",
                "MF_GATE_ON" if bool(mf_gate_on_today) else "MF_GATE_OFF",
                "MFO_GATE_ON" if bool(getattr(day_signals, "overlay_gate_on_today", False)) else "MFO_GATE_OFF",
                "STRONG_RISK_ON" if bool(day_signals.strong_risk_on) else "",
            )
            if flag
        ),
        ranking_payload={
            "selected_symbols": list((debug_plan or {}).get("selected_symbols", []) or []),
            "reject_reason_counts": dict((debug_plan or {}).get("reject_reason_counts", {}) or {}),
            "effective_max_positions": int(controls["effective_max_positions"]),
        },
    )
    return StageOutputs(
        stage_key="S7",
        holding_symbols=runtime._current_day["holding_symbols"],
        buy_symbols=tuple(od["symbol"] for od in next_day_orders if od["side"] == Side.BUY),
        sell_symbols=tuple(od["symbol"] for od in next_day_orders if od["side"] == Side.SELL),
        payload={
            "next_day_orders": tuple(next_day_orders),
            "execution_intent": execution_intent.to_payload(),
        },
        reason_counts=dict((debug_plan or {}).get("reject_reason_counts", {}) or {}),
        summary_fragment={
            "mode": "bridge_order_planner",
            "portfolio_mode": str(getattr(runtime, "_portfolio_mode", "") or ""),
            "buy_orders_count": sum(1 for od in next_day_orders if od["side"] == Side.BUY),
            "sell_orders_count": sum(1 for od in next_day_orders if od["side"] == Side.SELL),
            "deferred_sell_orders_count": int(deferred_sell_count),
        },
    )
