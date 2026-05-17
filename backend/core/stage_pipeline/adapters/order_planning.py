from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from backend.core.core.types import Side
from backend.core.portfolio.execution_orders import build_execution_orders_from_candidate_plan
from backend.core.stage_pipeline.contracts import (
    ActionIntentAction,
    ActionIntentContract,
    ExecutionAuditContract,
    ExecutionAuditRecord,
    RiskOverrideContract,
    StageOutputs,
    SubsystemBudgetContract,
    TargetBookContract,
    TargetBookItem,
)
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


def _safe_int(value: Any, *, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return int(fallback)


def _signal_meta(signal: Any) -> dict[str, Any]:
    return dict(getattr(signal, "meta", {}) or {})


def _owner_system_from_meta(meta: Mapping[str, Any] | None = None, *, fallback: str = "") -> str:
    payload = dict(meta or {})
    return str(
        payload.get("owner_system")
        or payload.get("sleeve_id")
        or payload.get("alpha_id")
        or fallback
        or "unassigned"
    ).strip()


def _make_source_intent_id(*, decision_date: Any, owner_system: str, action_index: int, symbol: str, side: str) -> str:
    day_text = getattr(decision_date, "isoformat", lambda: str(decision_date or ""))()
    normalized_owner = "".join(ch if ch.isalnum() else "_" for ch in str(owner_system or "unassigned")).strip("_") or "unassigned"
    normalized_symbol = "".join(ch if ch.isalnum() else "_" for ch in str(symbol or "")).strip("_") or "unknown"
    normalized_side = str(side or "").strip().upper() or "UNKNOWN"
    return f"intent_{day_text}_{normalized_owner}_{int(action_index):03d}_{normalized_symbol}_{normalized_side}"


def _coerce_weight_fraction(*, amount: float, nav_close: float, budget_value: float) -> float:
    if float(nav_close) <= 0.0 or float(budget_value) <= 0.0:
        return 0.0
    requested_weight = max(float(amount), 0.0) / float(nav_close)
    return float(max(0.0, min(1.0, requested_weight / float(budget_value))))


def _normalize_formal_reason_codes(meta: Mapping[str, Any], *, fallback: str) -> tuple[str, ...]:
    raw = meta.get("formal_reason_codes")
    if isinstance(raw, (list, tuple)):
        codes = tuple(str(code).strip() for code in raw if str(code).strip())
        if codes:
            return codes
    text = str(fallback or "").strip()
    return (text,) if text else ()


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


def _build_subsystem_budget_contracts(
    *,
    day: Any,
    controls: Mapping[str, Any],
    candidate_boundary_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    governor_budget = dict(controls.get("governor_budget") or {})
    reason_codes = tuple(str(code).strip() for code in list(governor_budget.get("budget_reason_codes") or ()) if str(code).strip())
    hard_block_flags = tuple(str(code).strip() for code in list(governor_budget.get("hard_block_flags") or ()) if str(code).strip())
    contracts: list[dict[str, Any]] = []

    owner_system_slot_caps = {
        str(key).strip(): int(value or 0)
        for key, value in dict(candidate_boundary_payload.get("owner_system_slot_caps") or {}).items()
        if str(key).strip()
    }
    owner_system_available_slots = {
        str(key).strip(): int(value or 0)
        for key, value in dict(candidate_boundary_payload.get("owner_system_available_slots") or {}).items()
        if str(key).strip()
    }
    total_slot_caps = sum(max(int(value or 0), 0) for value in owner_system_slot_caps.values())
    hard_max_positions = max(
        1,
        _safe_int(
            governor_budget.get("hard_max_positions"),
            fallback=_safe_int(controls.get("effective_max_positions"), fallback=1),
        ),
    )

    if owner_system_slot_caps:
        for owner_system in sorted(owner_system_slot_caps):
            slot_cap = max(int(owner_system_slot_caps.get(owner_system, 0) or 0), 0)
            available_slots = max(int(owner_system_available_slots.get(owner_system, 0) or 0), 0)
            budget_value = 0.0
            if total_slot_caps > 0:
                budget_value = min(float(slot_cap) / float(total_slot_caps), 1.0)
            elif hard_max_positions > 0:
                budget_value = min(float(slot_cap) / float(hard_max_positions), 1.0)
            contracts.append(
                SubsystemBudgetContract(
                    as_of_date=day,
                    owner_system=owner_system,
                    budget_value=float(max(budget_value, 0.0)),
                    budget_unit="weight",
                    budget_basis="portfolio_relative",
                    deployment_pace=str(governor_budget.get("deployment_pace") or "normal"),
                    allow_new_risk=available_slots > 0 and int(controls.get("effective_max_positions", 0) or 0) > 0,
                    force_reduce_only=int(controls.get("effective_max_positions", 0) or 0) <= 0,
                    hard_block_flags=hard_block_flags,
                    reason_codes=reason_codes,
                    notes={
                        "slot_cap": int(slot_cap),
                        "available_slots": int(available_slots),
                        "shared_boundary_role": "formal_runtime_budget",
                    },
                ).to_payload()
            )
        return contracts

    sleeve_budgets = dict(governor_budget.get("sleeve_budgets") or {})
    for owner_system, payload in sorted(sleeve_budgets.items()):
        sleeve_payload = dict(payload or {})
        target_exposure = sleeve_payload.get("target_exposure")
        budget_share = sleeve_payload.get("budget_share")
        total_exposure_cap = governor_budget.get("total_exposure_cap")
        budget_value = _safe_float(
            target_exposure
            if target_exposure not in (None, "")
            else (total_exposure_cap if total_exposure_cap not in (None, "") else budget_share),
            fallback=0.0,
        )
        contracts.append(
            SubsystemBudgetContract(
                as_of_date=day,
                owner_system=str(owner_system).strip(),
                budget_value=float(max(0.0, min(1.0, budget_value))),
                budget_unit="weight",
                budget_basis="portfolio_relative",
                strategic_floor_cap=governor_budget.get("strategic_floor_cap"),
                tactical_overlay_cap=governor_budget.get("tactical_overlay_cap"),
                deployment_pace=str(governor_budget.get("deployment_pace") or "normal"),
                allow_new_risk=int(sleeve_payload.get("available_slots", 0) or 0) > 0 and int(controls.get("effective_max_positions", 0) or 0) > 0,
                force_reduce_only=int(controls.get("effective_max_positions", 0) or 0) <= 0,
                hard_block_flags=hard_block_flags,
                reason_codes=reason_codes,
                notes={
                    "slot_cap": int(sleeve_payload.get("slot_cap", 0) or 0),
                    "available_slots": int(sleeve_payload.get("available_slots", 0) or 0),
                    "shared_boundary_role": "formal_runtime_budget",
                },
            ).to_payload()
        )
    return contracts


def _build_risk_override_contracts(
    *,
    day: Any,
    controls: Mapping[str, Any],
    sell_signals: list[Any],
) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    portfolio_reason_codes: list[str] = []
    if int(controls.get("effective_max_positions", 0) or 0) <= 0:
        portfolio_reason_codes.append("NO_DEPLOYABLE_SLOTS")
    if not bool(controls.get("benchmark_regime_on", True)):
        portfolio_reason_codes.append("BENCHMARK_REGIME_OFF")
    if str(controls.get("trade_mode", "") or "").strip().upper() == "NO_TRADE":
        portfolio_reason_codes.append("TRADE_MODE_NO_TRADE")
    if portfolio_reason_codes:
        overrides.append(
            RiskOverrideContract(
                as_of_date=day,
                override_owner="global_portfolio_governor",
                scope="portfolio",
                action="REDUCE_ONLY",
                reason_codes=tuple(dict.fromkeys(portfolio_reason_codes)),
                notes={"origin": "governor_snapshot"},
            ).to_payload()
        )

    seen_symbols: set[str] = set()
    for signal in list(sell_signals or ()):
        meta = _signal_meta(signal)
        if str(meta.get("exit_owner", "") or "").strip() != "global_risk_override":
            continue
        symbol = _normalized_text(getattr(signal, "symbol", ""))
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        overrides.append(
            RiskOverrideContract(
                as_of_date=day,
                override_owner="global_portfolio_governor",
                scope="symbol",
                action="FORCE_EXIT",
                target_symbol=symbol,
                reason_codes=_normalize_formal_reason_codes(meta, fallback=str(getattr(signal, "reason_code", "") or "")),
                notes={"origin": "sell_signal_override"},
            ).to_payload()
        )
    return overrides


def _build_action_intent_contracts(
    *,
    day: Any,
    planned_items: list[dict[str, Any]],
    sell_signals: list[Any],
    subsystem_budgets: list[dict[str, Any]],
    holdings: Mapping[str, int],
    nav_close: float,
) -> list[dict[str, Any]]:
    budgets_by_owner = {
        str(item.get("owner_system") or "").strip(): float(item.get("budget_value") or 0.0)
        for item in list(subsystem_budgets or ())
        if str(item.get("owner_system") or "").strip()
    }
    grouped_actions: dict[str, list[ActionIntentAction]] = {}
    next_action_index: dict[str, int] = {}

    def _append_action(owner_system: str, **kwargs: Any) -> None:
        owner = str(owner_system or "").strip() or "unassigned"
        action_index = int(next_action_index.get(owner, 1))
        action = ActionIntentAction(
            action_index=action_index,
            source_intent_id=_make_source_intent_id(
                decision_date=day,
                owner_system=owner,
                action_index=action_index,
                symbol=str(kwargs.get("symbol") or ""),
                side=str(kwargs.get("side") or ""),
            ),
            **kwargs,
        )
        grouped_actions.setdefault(owner, []).append(action)
        next_action_index[owner] = action_index + 1

    for priority, item in enumerate(list(planned_items or ()), start=1):
        signal = item.get("signal")
        meta = _signal_meta(signal)
        owner_system = _owner_system_from_meta(meta)
        budget_value = float(budgets_by_owner.get(owner_system, 0.0) or 0.0)
        requested_amount = _safe_float(
            item.get("target_amount_scaled", item.get("candidate_cost", 0.0)),
            fallback=0.0,
        )
        _append_action(
            owner_system,
            symbol=_normalized_text(item.get("symbol")),
            side="BUY",
            priority=priority,
            reason_codes=_normalize_formal_reason_codes(meta, fallback=str(getattr(signal, "reason_code", "") or "")),
            suggested_size_value=_coerce_weight_fraction(
                amount=requested_amount,
                nav_close=float(nav_close),
                budget_value=float(budget_value),
            ),
            suggested_size_unit="weight",
            suggested_size_basis="subsystem_budget_relative",
            notes={
                "signal_strength": _safe_float(meta.get("compose_score", meta.get("raw_score")), fallback=0.0),
                "budget_value": float(budget_value),
                "shared_boundary_role": "formal_action_intent",
            },
        )

    for signal in list(sell_signals or ()):
        meta = _signal_meta(signal)
        if str(meta.get("exit_owner", "") or "").strip() == "global_risk_override":
            continue
        symbol = _normalized_text(getattr(signal, "symbol", ""))
        held_qty = max(int(dict(holdings or {}).get(symbol, 0) or 0), 0)
        if held_qty <= 0:
            continue
        owner_system = _owner_system_from_meta(
            meta,
            fallback=str(meta.get("entry_sleeve_id") or meta.get("entry_alpha_id") or ""),
        )
        requested_qty = int(getattr(signal, "qty", 0) or 0)
        _append_action(
            owner_system,
            symbol=symbol,
            side="SELL",
            priority=1,
            reason_codes=_normalize_formal_reason_codes(meta, fallback=str(getattr(signal, "reason_code", "") or "")),
            suggested_size_value=(
                1.0
                if requested_qty <= 0
                else float(max(0.0, min(1.0, float(requested_qty) / float(held_qty))))
            ),
            suggested_size_unit="ratio",
            suggested_size_basis="sellable_qty_relative",
            notes={
                "sellable_qty": int(held_qty),
                "shared_boundary_role": "formal_action_intent",
            },
        )

    contracts: list[dict[str, Any]] = []
    for owner_system in sorted(grouped_actions):
        actions = tuple(sorted(grouped_actions.get(owner_system, []), key=lambda item: (int(item.priority), int(item.action_index))))
        contracts.append(
            ActionIntentContract(
                as_of_date=day,
                owner_system=owner_system,
                actions=actions,
            ).to_payload()
        )
    return contracts


def _build_execution_audit_contract(
    *,
    day: Any,
    action_intents: list[dict[str, Any]],
    next_day_orders: list[dict[str, Any]],
    debug_plan: Mapping[str, Any],
    risk_overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    accepted_orders = {
        (
            str((dict(order.get("meta") or {})).get("owner_system") or "").strip(),
            _normalized_text(order.get("symbol")),
            str(order.get("side") or "").strip().upper(),
        ): dict(order)
        for order in list(next_day_orders or ())
    }
    reject_by_symbol = {
        _normalized_text(item.get("symbol")): str(item.get("reject_reason") or "").strip()
        for item in list((dict(debug_plan or {}).get("annotated_items") or ()))
        if _normalized_text(item.get("symbol"))
    }
    source_only_rejected_sells = {
        (
            str(item.get("owner_system") or "").strip(),
            _normalized_text(item.get("symbol")),
            "SELL",
        ): dict(item)
        for item in list((dict(debug_plan or {}).get("source_only_rejected_sells") or ()))
    }
    reduce_only_active = any(
        str(item.get("scope") or "") == "portfolio" and str(item.get("action") or "") == "REDUCE_ONLY"
        for item in list(risk_overrides or ())
    )
    records: list[ExecutionAuditRecord] = []

    for contract in list(action_intents or ()):
        owner_system = str(contract.get("owner_system") or "").strip()
        for action in list(contract.get("actions") or ()):
            action_index = _safe_int(action.get("action_index"), fallback=0)
            symbol = _normalized_text(action.get("symbol"))
            side = str(action.get("side") or "").strip().upper()
            requested_size_value = _safe_float(action.get("suggested_size_value"), fallback=0.0)
            requested_size_unit = str(action.get("suggested_size_unit") or "").strip().lower()
            requested_size_basis = str(action.get("suggested_size_basis") or "").strip().lower()
            order_key = (owner_system, symbol, side)
            accepted = accepted_orders.get(order_key)
            source_only_reject = source_only_rejected_sells.get(order_key)
            if accepted is not None:
                records.append(
                    ExecutionAuditRecord(
                        action_index=action_index,
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="accepted",
                        reason_codes=tuple(str(code).strip() for code in list(action.get("reason_codes") or ()) if str(code).strip()),
                        final_qty=int(accepted.get("qty", 0) or 0),
                        notes={"shared_boundary_role": "formal_execution_audit"},
                    )
                )
                continue
            if source_only_reject is not None:
                records.append(
                    ExecutionAuditRecord(
                        action_index=action_index,
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="rejected",
                        reason_codes=("SOURCE_ONLY_SELL_MISMATCH",),
                        final_qty=0,
                        notes={
                            "shared_boundary_role": "formal_execution_audit",
                            "holding_entry_alpha_id": str(source_only_reject.get("holding_entry_alpha_id") or ""),
                            "holding_entry_sleeve_id": str(source_only_reject.get("holding_entry_sleeve_id") or ""),
                        },
                    )
                )
                continue
            if side == "BUY" and reduce_only_active:
                records.append(
                    ExecutionAuditRecord(
                        action_index=action_index,
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="blocked",
                        reason_codes=("REDUCE_ONLY_BLOCKED",),
                        blocked_by_override=True,
                        final_qty=0,
                        notes={"shared_boundary_role": "formal_execution_audit"},
                    )
                )
                continue
            reject_reason = reject_by_symbol.get(symbol)
            if reject_reason:
                records.append(
                    ExecutionAuditRecord(
                        action_index=action_index,
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="rejected",
                        reason_codes=(str(reject_reason),),
                        final_qty=0,
                        notes={"shared_boundary_role": "formal_execution_audit"},
                    )
                )

    return ExecutionAuditContract(
        as_of_date=day,
        records=tuple(sorted(records, key=lambda item: (int(item.action_index), item.symbol, item.outcome))),
    ).to_payload()


def _build_target_book_contract(
    *,
    day: Any,
    next_trading_day: Any,
    next_day_orders: list[dict[str, Any]],
    controls: Mapping[str, Any],
    next_open: Mapping[str, Any] | None = None,
    nav_close: float = 0.0,
    default_owner_system: str = "",
) -> dict[str, Any]:
    target_items_by_symbol: dict[str, TargetBookItem] = {}
    for priority, order in enumerate(list(next_day_orders or ()), start=1):
        symbol = _normalized_text(order.get("symbol"))
        if not symbol:
            continue
        meta = dict(order.get("meta") or {})
        owner_system = str(
            meta.get("owner_system")
            or meta.get("sleeve_id")
            or meta.get("alpha_id")
            or default_owner_system
            or "unassigned"
        ).strip()
        reason_codes = _normalize_formal_reason_codes(meta, fallback=str(order.get("reason_code") or ""))
        target_weight = 0.0
        if order.get("side") == Side.BUY:
            raw_target_weight = meta.get("target_weight")
            target_weight = _safe_float(raw_target_weight, fallback=float("nan"))
            if target_weight != target_weight:
                px = _safe_float((dict(next_open or {})).get(symbol), fallback=0.0)
                qty = max(0, int(order.get("qty", 0) or 0))
                target_weight = (
                    (float(qty) * float(px) / float(nav_close))
                    if float(nav_close) > 0.0 and float(px) > 0.0 and int(qty) > 0
                    else 0.0
                )
        target_items_by_symbol[symbol] = TargetBookItem(
            symbol=symbol,
            target_weight=float(max(target_weight, 0.0)),
            owner_system=owner_system,
            reason_codes=reason_codes,
            priority=priority,
        )
    target_book = TargetBookContract(
        decision_date=day,
        execution_date=next_trading_day,
        execution_timing="next_open",
        portfolio_constraints={
            "max_total_positions": int(controls.get("effective_max_positions", 0) or 0),
            "allow_new_positions": int(controls.get("effective_max_positions", 0) or 0) > 0,
            "force_reduce_only": int(controls.get("effective_max_positions", 0) or 0) <= 0,
        },
        targets=tuple(target_items_by_symbol[symbol] for symbol in sorted(target_items_by_symbol)),
        blocking_result={
            "hard_blocked": int(controls.get("effective_max_positions", 0) or 0) <= 0,
            "reason_codes": [str(code).strip() for code in list(controls.get("reason_codes") or ()) if str(code).strip()],
        },
        notes={
            "state_5": str(controls.get("effective_state_5") or controls.get("market_state_5") or "").strip(),
        },
    )
    return target_book.to_payload()


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


def _build_execution_kernel_payload(
    *,
    candidate_rows: list[dict[str, Any]],
    debug_plan: Mapping[str, Any],
) -> dict[str, Any]:
    reject_reason_counts = dict(
        (dict(debug_plan or {}).get("execution_kernel_reject_reason_counts")
         or dict(debug_plan or {}).get("reject_reason_counts")
         or {})
    )
    return {
        "contract_version": "execution_kernel_v1",
        "candidate_rows": tuple(dict(row) for row in list(candidate_rows or ())),
        "reject_reason_counts": {
            str(reason).strip(): int(count or 0)
            for reason, count in reject_reason_counts.items()
            if str(reason).strip()
        },
        "debug_plan": dict(debug_plan or {}),
    }


def _resolve_owner_system(meta: Mapping[str, Any] | None, *, fallback: str = "") -> str:
    payload = dict(meta or {})
    return str(
        payload.get("owner_system")
        or payload.get("sleeve_id")
        or payload.get("alpha_id")
        or fallback
        or "unassigned"
    ).strip()


def _build_subsystem_budget_payloads(
    *,
    day: Any,
    controls: Mapping[str, Any],
    debug_plan: Mapping[str, Any],
    candidate_boundary_payload: Mapping[str, Any],
    fallback_owner_system: str,
) -> list[dict[str, Any]]:
    governor_budget = dict(controls.get("governor_budget") or {})
    raw_budget = dict(governor_budget.get("raw_sleeve_budget") or {})
    raw_slot_caps = {
        str(owner).strip(): int(value or 0)
        for owner, value in dict(raw_budget.get("slot_caps") or {}).items()
        if str(owner).strip()
    }
    raw_available_slots = {
        str(owner).strip(): int(value or 0)
        for owner, value in dict(raw_budget.get("available_slots") or {}).items()
        if str(owner).strip()
    }
    raw_positions_after_sell = {
        str(owner).strip(): int(value or 0)
        for owner, value in dict(raw_budget.get("positions_after_sell") or {}).items()
        if str(owner).strip()
    }
    raw_candidate_counts = {
        str(owner).strip(): int(value or 0)
        for owner, value in dict(raw_budget.get("candidate_counts") or {}).items()
        if str(owner).strip()
    }
    raw_selected_counts = {
        str(owner).strip(): int(value or 0)
        for owner, value in dict(raw_budget.get("selected_counts") or {}).items()
        if str(owner).strip()
    }
    if not raw_slot_caps:
        raw_slot_caps = {
            str(owner).strip(): int(value or 0)
            for owner, value in dict(candidate_boundary_payload.get("owner_system_slot_caps") or {}).items()
            if str(owner).strip()
        }
        raw_available_slots = {
            str(owner).strip(): int(value or 0)
            for owner, value in dict(candidate_boundary_payload.get("owner_system_available_slots") or {}).items()
            if str(owner).strip()
        }
        selected_candidates = list(candidate_boundary_payload.get("selected_candidates") or ())
        selected_counts: dict[str, int] = {}
        for item in selected_candidates:
            owner = str(dict(item or {}).get("owner_system") or "").strip()
            if not owner:
                continue
            selected_counts[owner] = int(selected_counts.get(owner, 0)) + 1
        raw_selected_counts = dict(selected_counts)
    total_slot_caps = sum(max(0, value) for value in raw_slot_caps.values())
    if total_slot_caps <= 0:
        owner_system = str(
            governor_budget.get("budget_consumer_sleeve_id")
            or fallback_owner_system
            or "unassigned"
        ).strip()
        return [
            SubsystemBudgetContract(
                as_of_date=day,
                owner_system=owner_system,
                budget_value=float(_safe_float(governor_budget.get("total_exposure_cap"), fallback=1.0)),
                strategic_floor_cap=_safe_float(governor_budget.get("strategic_floor_cap"), fallback=float("nan")),
                tactical_overlay_cap=_safe_float(governor_budget.get("tactical_overlay_cap"), fallback=float("nan")),
                deployment_pace=str(governor_budget.get("deployment_pace") or "normal"),
                allow_new_risk=int(controls.get("effective_max_positions", 0) or 0) > 0,
                force_reduce_only=int(controls.get("effective_max_positions", 0) or 0) <= 0,
                hard_block_flags=tuple(str(code) for code in list(governor_budget.get("hard_block_flags") or ()) if str(code)),
                reason_codes=tuple(str(code) for code in list(governor_budget.get("budget_reason_codes") or ()) if str(code)),
                notes={
                    "source": "governor_budget_snapshot",
                    "effective_max_positions": int(controls.get("effective_max_positions", 0) or 0),
                    "system_budget_owner": str(debug_plan.get("system_budget_owner") or ""),
                },
            ).to_payload()
        ]

    payloads: list[dict[str, Any]] = []
    for owner_system in sorted(raw_slot_caps):
        budget_value = float(max(0, raw_slot_caps.get(owner_system, 0))) / float(max(total_slot_caps, 1))
        payloads.append(
            SubsystemBudgetContract(
                as_of_date=day,
                owner_system=owner_system,
                budget_value=min(max(budget_value, 0.0), 1.0),
                strategic_floor_cap=_safe_float(governor_budget.get("strategic_floor_cap"), fallback=float("nan")),
                tactical_overlay_cap=_safe_float(governor_budget.get("tactical_overlay_cap"), fallback=float("nan")),
                deployment_pace=str(governor_budget.get("deployment_pace") or "normal"),
                allow_new_risk=int(controls.get("effective_max_positions", 0) or 0) > 0,
                force_reduce_only=int(controls.get("effective_max_positions", 0) or 0) <= 0,
                hard_block_flags=tuple(str(code) for code in list(governor_budget.get("hard_block_flags") or ()) if str(code)),
                reason_codes=tuple(str(code) for code in list(governor_budget.get("budget_reason_codes") or ()) if str(code)),
                notes={
                    "source": "governor_raw_sleeve_budget",
                    "slot_cap": int(raw_slot_caps.get(owner_system, 0) or 0),
                    "available_slots": int(raw_available_slots.get(owner_system, 0) or 0),
                    "positions_after_sell": int(raw_positions_after_sell.get(owner_system, 0) or 0),
                    "candidate_count": int(raw_candidate_counts.get(owner_system, 0) or 0),
                    "selected_count": int(raw_selected_counts.get(owner_system, 0) or 0),
                },
            ).to_payload()
        )
    return payloads


def _build_risk_override_payloads(
    *,
    day: Any,
    controls: Mapping[str, Any],
    sell_signals: list[Any],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    effective_max_positions = int(controls.get("effective_max_positions", 0) or 0)
    if effective_max_positions <= 0:
        payloads.append(
            RiskOverrideContract(
                as_of_date=day,
                override_owner="global_portfolio_governor",
                scope="portfolio",
                action="REDUCE_ONLY",
                reason_codes=tuple(str(code) for code in list(controls.get("reason_codes") or ()) if str(code)),
                notes={"source": "day_controls", "effective_max_positions": effective_max_positions},
            ).to_payload()
        )
    force_exit_symbols: set[str] = set()
    for signal in list(sell_signals or ()):
        meta = _signal_meta(signal)
        if str(meta.get("exit_owner", "") or "").strip() != "global_risk_override":
            continue
        symbol = _normalized_text(getattr(signal, "symbol", ""))
        if not symbol or symbol in force_exit_symbols:
            continue
        force_exit_symbols.add(symbol)
        payloads.append(
            RiskOverrideContract(
                as_of_date=day,
                override_owner="global_portfolio_governor",
                scope="symbol",
                action="FORCE_EXIT",
                target_symbol=symbol,
                reason_codes=_normalize_formal_reason_codes(meta, fallback=str(getattr(signal, "reason_code", "") or "")),
                notes={"source": "sell_signal_override"},
            ).to_payload()
        )
    payloads.sort(
        key=lambda item: (
            0 if str(item.get("scope") or "") == "portfolio" else 1,
            0 if str(item.get("action") or "") == "FORCE_EXIT" else 1,
            str(item.get("target_symbol") or ""),
        )
    )
    return payloads


def _build_action_intent_payloads(
    *,
    day: Any,
    planned_items: list[dict[str, Any]],
    sell_signals: list[Any],
    positions: Mapping[str, Any],
    nav_close: float,
    subsystem_budgets: list[dict[str, Any]],
    default_owner_system: str,
) -> list[dict[str, Any]]:
    budget_by_owner = {
        str(item.get("owner_system") or "").strip(): float(item.get("budget_value") or 0.0)
        for item in list(subsystem_budgets or ())
        if str(item.get("owner_system") or "").strip()
    }
    owner_specs: dict[str, list[dict[str, Any]]] = {}
    owner_action_index: dict[str, int] = {}
    pending_entries: dict[tuple[str, str], dict[str, Any]] = {}
    spec_sort_order = 0

    def _next_index(owner_system: str) -> int:
        owner_action_index[owner_system] = int(owner_action_index.get(owner_system, 0)) + 1
        return int(owner_action_index[owner_system])

    def _merge_reason_codes(*parts: Any) -> tuple[str, ...]:
        merged: list[str] = []
        for part in parts:
            for code in list(part or ()):
                text = str(code).strip()
                if text and text not in merged:
                    merged.append(text)
        return tuple(merged)

    def _append_spec(owner_system: str, spec: dict[str, Any]) -> None:
        nonlocal spec_sort_order
        spec_sort_order += 1
        payload = dict(spec or {})
        payload["_sort_order"] = int(spec_sort_order)
        owner_specs.setdefault(owner_system, []).append(payload)

    for signal in list(sell_signals or ()):
        meta = _signal_meta(signal)
        if str(meta.get("exit_owner", "") or "").strip() == "global_risk_override":
            continue
        owner_system = _resolve_owner_system(meta, fallback=default_owner_system)
        symbol = _normalized_text(getattr(signal, "symbol", ""))
        entry = pending_entries.setdefault((owner_system, symbol), {"buy": None, "sell": None})
        current = dict(entry.get("sell") or {})
        entry["sell"] = {
            "priority": min(_safe_int(current.get("priority"), fallback=1), 1) if current else 1,
            "reason_codes": _merge_reason_codes(
                current.get("reason_codes"),
                _normalize_formal_reason_codes(meta, fallback=str(getattr(signal, "reason_code", "") or "")),
            ),
            "qty": max(_safe_int(current.get("qty"), fallback=0), _safe_int(getattr(signal, "qty", 0), fallback=0)),
            "held": max(
                _safe_int(current.get("held"), fallback=0),
                max(0, _safe_int(dict(positions or {}).get(symbol, 0), fallback=0)),
            ),
            "notes": {
                "source": "sell_signal",
                "sellable_qty": max(0, _safe_int(dict(positions or {}).get(symbol, 0), fallback=0)),
            },
        }

    for priority, item in enumerate(list(planned_items or ()), start=1):
        signal = item.get("signal")
        meta = _signal_meta(signal)
        owner_system = _resolve_owner_system(meta, fallback=default_owner_system)
        symbol = _normalized_text(item.get("symbol"))
        entry = pending_entries.setdefault((owner_system, symbol), {"buy": None, "sell": None})
        current = dict(entry.get("buy") or {})
        price = _safe_float(item.get("price", current.get("price", 0.0)), fallback=0.0)
        entry["buy"] = {
            "priority": min(_safe_int(current.get("priority"), fallback=priority), int(priority)) if current else int(priority),
            "reason_codes": _merge_reason_codes(
                current.get("reason_codes"),
                _normalize_formal_reason_codes(meta, fallback=str(getattr(signal, "reason_code", "") or "")),
            ),
            "target_amount_scaled": _safe_float(current.get("target_amount_scaled"), fallback=0.0) + _safe_float(item.get("target_amount_scaled"), fallback=0.0),
            "price": float(price),
            "notes": {
                "source": "candidate_plan",
                "target_amount_scaled": _safe_float(item.get("target_amount_scaled"), fallback=0.0),
                "candidate_price": float(price),
            },
        }

    for (owner_system, symbol), entry in pending_entries.items():
        sell_payload = dict(entry.get("sell") or {})
        buy_payload = dict(entry.get("buy") or {})
        if sell_payload and buy_payload:
            budget_value = float(budget_by_owner.get(owner_system, 1.0) or 1.0)
            target_amount_scaled = _safe_float(buy_payload.get("target_amount_scaled"), fallback=0.0)
            price = _safe_float(buy_payload.get("price"), fallback=0.0)
            held = max(_safe_int(sell_payload.get("held"), fallback=0), 0)
            if held <= 0 or price <= 0.0:
                buy_size = 0.0
                if float(nav_close) > 0.0 and budget_value > 0.0:
                    buy_size = min(max(float(target_amount_scaled) / float(nav_close) / float(budget_value), 0.0), 1.0)
                notes = dict(buy_payload.get("notes") or {})
                notes.update({"netted_from_dual_side": True, "dual_side_fallback": "price_or_holding_missing"})
                _append_spec(
                    owner_system,
                    {
                        "priority": int(_safe_int(buy_payload.get("priority"), fallback=1)),
                        "symbol": symbol,
                        "side": "BUY",
                        "reason_codes": _merge_reason_codes(sell_payload.get("reason_codes"), buy_payload.get("reason_codes")),
                        "suggested_size_value": float(buy_size),
                        "suggested_size_unit": "weight",
                        "suggested_size_basis": "subsystem_budget_relative",
                        "notes": notes,
                    },
                )
                continue
            held_amount = float(held) * float(price)
            delta_amount = float(target_amount_scaled) - float(held_amount)
            if abs(delta_amount) <= 1e-9:
                continue
            if delta_amount > 0.0:
                buy_size = 0.0
                if float(nav_close) > 0.0 and budget_value > 0.0:
                    buy_size = min(max(float(delta_amount) / float(nav_close) / float(budget_value), 0.0), 1.0)
                notes = dict(buy_payload.get("notes") or {})
                notes.update(
                    {
                        "netted_from_dual_side": True,
                        "dual_side_sell_qty": int(_safe_int(sell_payload.get("qty"), fallback=0)),
                        "dual_side_held_qty": int(held),
                    }
                )
                _append_spec(
                    owner_system,
                    {
                        "priority": int(_safe_int(buy_payload.get("priority"), fallback=1)),
                        "symbol": symbol,
                        "side": "BUY",
                        "reason_codes": _merge_reason_codes(sell_payload.get("reason_codes"), buy_payload.get("reason_codes")),
                        "suggested_size_value": float(buy_size),
                        "suggested_size_unit": "weight",
                        "suggested_size_basis": "subsystem_budget_relative",
                        "notes": notes,
                    },
                )
                continue
            sell_ratio = min(max(abs(float(delta_amount)) / float(held_amount), 0.0), 1.0)
            notes = dict(sell_payload.get("notes") or {})
            notes.update(
                {
                    "netted_from_dual_side": True,
                    "dual_side_target_amount_scaled": float(target_amount_scaled),
                    "dual_side_candidate_price": float(price),
                }
            )
            _append_spec(
                owner_system,
                {
                    "priority": int(_safe_int(sell_payload.get("priority"), fallback=1)),
                    "symbol": symbol,
                    "side": "SELL",
                    "reason_codes": _merge_reason_codes(sell_payload.get("reason_codes"), buy_payload.get("reason_codes")),
                    "suggested_size_value": float(sell_ratio),
                    "suggested_size_unit": "ratio",
                    "suggested_size_basis": "sellable_qty_relative",
                    "notes": notes,
                },
            )
            continue
        if sell_payload:
            held = max(_safe_int(sell_payload.get("held"), fallback=0), 0)
            qty = _safe_int(sell_payload.get("qty"), fallback=0)
            sell_ratio = 1.0 if held <= 0 or qty <= 0 else min(max(float(qty) / float(max(held, 1)), 0.0), 1.0)
            _append_spec(
                owner_system,
                {
                    "priority": int(_safe_int(sell_payload.get("priority"), fallback=1)),
                    "symbol": symbol,
                    "side": "SELL",
                    "reason_codes": tuple(sell_payload.get("reason_codes") or ()),
                    "suggested_size_value": float(sell_ratio),
                    "suggested_size_unit": "ratio",
                    "suggested_size_basis": "sellable_qty_relative",
                    "notes": dict(sell_payload.get("notes") or {}),
                },
            )
        if buy_payload:
            budget_value = float(budget_by_owner.get(owner_system, 1.0) or 1.0)
            target_amount_scaled = _safe_float(buy_payload.get("target_amount_scaled"), fallback=0.0)
            buy_size = 0.0
            if float(nav_close) > 0.0 and budget_value > 0.0:
                buy_size = min(max(float(target_amount_scaled) / float(nav_close) / float(budget_value), 0.0), 1.0)
            _append_spec(
                owner_system,
                {
                    "priority": int(_safe_int(buy_payload.get("priority"), fallback=1)),
                    "symbol": symbol,
                    "side": "BUY",
                    "reason_codes": tuple(buy_payload.get("reason_codes") or ()),
                    "suggested_size_value": float(buy_size),
                    "suggested_size_unit": "weight",
                    "suggested_size_basis": "subsystem_budget_relative",
                    "notes": dict(buy_payload.get("notes") or {}),
                },
            )

    payloads: list[dict[str, Any]] = []
    for owner_system in sorted(owner_specs):
        actions: list[ActionIntentAction] = []
        for spec in sorted(
            owner_specs[owner_system],
            key=lambda item: (int(item.get("priority", 1) or 1), int(item.get("_sort_order", 0) or 0)),
        ):
            action_index = _next_index(owner_system)
            symbol = _normalized_text(spec.get("symbol"))
            side = str(spec.get("side") or "").strip().upper()
            actions.append(
                ActionIntentAction(
                    action_index=action_index,
                    symbol=symbol,
                    side=side,
                    priority=int(spec.get("priority", 1) or 1),
                    reason_codes=tuple(spec.get("reason_codes") or ()),
                    suggested_size_value=float(spec.get("suggested_size_value", 0.0) or 0.0),
                    suggested_size_unit=str(spec.get("suggested_size_unit") or ""),
                    suggested_size_basis=str(spec.get("suggested_size_basis") or ""),
                    source_intent_id=_make_source_intent_id(
                        decision_date=day,
                        owner_system=owner_system,
                        action_index=action_index,
                        symbol=symbol,
                        side=side,
                    ),
                    notes=dict(spec.get("notes") or {}),
                )
            )
        actions = sorted(actions, key=lambda item: (int(item.priority), int(item.action_index)))
        payloads.append(
            ActionIntentContract(
                as_of_date=day,
                owner_system=owner_system,
                actions=tuple(actions),
            ).to_payload()
        )
    return payloads


def _build_execution_audit_payload(
    *,
    day: Any,
    action_intents: list[dict[str, Any]],
    next_day_orders: list[dict[str, Any]],
    planned_items: list[dict[str, Any]],
    debug_plan: Mapping[str, Any],
    risk_overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    order_lookup = {
        (str(order.get("side") or "").strip().upper(), _normalized_text(order.get("symbol"))): dict(order)
        for order in list(next_day_orders or ())
    }
    planned_item_by_symbol = {
        _normalized_text(item.get("symbol")): dict(item)
        for item in list(planned_items or ())
        if _normalized_text(item.get("symbol"))
    }
    annotated_item_by_symbol = {
        _normalized_text(item.get("symbol")): dict(item)
        for item in list((dict(debug_plan or {}).get("annotated_items") or ()))
        if _normalized_text(item.get("symbol"))
    }
    source_only_rejected_sells = {
        (
            str(item.get("owner_system") or "").strip(),
            _normalized_text(item.get("symbol")),
            "SELL",
        ): dict(item)
        for item in list((dict(debug_plan or {}).get("source_only_rejected_sells") or ()))
    }
    reduce_only_active = any(
        str(item.get("scope") or "").strip() == "portfolio"
        and str(item.get("action") or "").strip() == "REDUCE_ONLY"
        for item in list(risk_overrides or ())
    )
    records: list[ExecutionAuditRecord] = []
    for contract_payload in list(action_intents or ()):
        owner_system = str(contract_payload.get("owner_system") or "").strip()
        for action_payload in list(contract_payload.get("actions") or ()):
            side = str(action_payload.get("side") or "").strip().upper()
            symbol = _normalized_text(action_payload.get("symbol"))
            order = order_lookup.get((side, symbol))
            source_only_reject = source_only_rejected_sells.get((owner_system, symbol, side))
            requested_size_value = float(action_payload.get("suggested_size_value", 0.0) or 0.0)
            requested_size_unit = str(action_payload.get("suggested_size_unit") or "").strip().lower()
            requested_size_basis = str(action_payload.get("suggested_size_basis") or "").strip().lower()
            reject_reason = str(annotated_item_by_symbol.get(symbol, {}).get("reject_reason") or planned_item_by_symbol.get(symbol, {}).get("reject_reason") or "").strip()
            if source_only_reject is not None:
                records.append(
                    ExecutionAuditRecord(
                        action_index=int(action_payload.get("action_index", 0) or 0),
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="rejected",
                        reason_codes=("SOURCE_ONLY_SELL_MISMATCH",),
                        final_qty=0,
                        notes={
                            "shared_boundary_role": "formal_execution_audit",
                            "holding_entry_alpha_id": str(source_only_reject.get("holding_entry_alpha_id") or ""),
                            "holding_entry_sleeve_id": str(source_only_reject.get("holding_entry_sleeve_id") or ""),
                        },
                    )
                )
                continue
            if side == "BUY" and reduce_only_active:
                records.append(
                    ExecutionAuditRecord(
                        action_index=int(action_payload.get("action_index", 0) or 0),
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="blocked",
                        reason_codes=("REDUCE_ONLY_BLOCKED",),
                        blocked_by_override=True,
                        final_qty=0,
                        notes={"shared_boundary_role": "formal_execution_audit"},
                    )
                )
                continue
            if side == "SELL":
                if order:
                    records.append(
                        ExecutionAuditRecord(
                            action_index=int(action_payload.get("action_index", 0) or 0),
                            owner_system=owner_system,
                            symbol=symbol,
                            side=side,
                            requested_size_value=requested_size_value,
                            requested_size_unit=requested_size_unit,
                            requested_size_basis=requested_size_basis,
                            outcome="accepted",
                            reason_codes=tuple(str(code) for code in list(action_payload.get("reason_codes") or ()) if str(code)),
                            final_qty=int(order.get("qty", 0) or 0),
                        )
                    )
                else:
                    records.append(
                        ExecutionAuditRecord(
                            action_index=int(action_payload.get("action_index", 0) or 0),
                            owner_system=owner_system,
                            symbol=symbol,
                            side=side,
                            requested_size_value=requested_size_value,
                            requested_size_unit=requested_size_unit,
                            requested_size_basis=requested_size_basis,
                            outcome="rejected",
                            reason_codes=((reject_reason or "NOT_SCHEDULED"),),
                            final_qty=0,
                            notes={"shared_boundary_role": "formal_execution_audit"},
                        )
                    )
                continue
            if order:
                records.append(
                    ExecutionAuditRecord(
                        action_index=int(action_payload.get("action_index", 0) or 0),
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="accepted",
                        reason_codes=tuple(str(code) for code in list(action_payload.get("reason_codes") or ()) if str(code)),
                        rounded_to_lot=reject_reason == "SKIP_QTY_ZERO",
                        final_qty=int(order.get("qty", 0) or 0),
                        notes={"shared_boundary_role": "formal_execution_audit"},
                    )
                )
            else:
                records.append(
                    ExecutionAuditRecord(
                        action_index=int(action_payload.get("action_index", 0) or 0),
                        owner_system=owner_system,
                        symbol=symbol,
                        side=side,
                        requested_size_value=requested_size_value,
                        requested_size_unit=requested_size_unit,
                        requested_size_basis=requested_size_basis,
                        outcome="rejected",
                        reason_codes=(reject_reason or "NOT_SCHEDULED",),
                        rounded_to_lot=reject_reason == "SKIP_QTY_ZERO",
                        final_qty=0,
                        notes={"shared_boundary_role": "formal_execution_audit"},
                    )
                )
    records.sort(key=lambda item: (int(item.action_index), item.symbol, item.outcome))
    return ExecutionAuditContract(
        as_of_date=day,
        records=tuple(records),
    ).to_payload()


def build_s7_order_stage_output(runtime: Any) -> StageOutputs:
    if runtime._current_day is None:
        raise RuntimeError("current day is not prepared")

    day = runtime._current_day["day"]
    controls = runtime._current_day["controls"]
    day_signals = runtime._current_day["day_signals"]
    nav = float(runtime._current_day["nav"])
    candidate_boundary = dict(runtime._current_day.get("candidate_boundary") or {})
    if not candidate_boundary:
        raise RuntimeError("candidate_boundary must be prepared before order_planning")
    candidate_plan = dict(runtime._current_day.get("candidate_plan") or {})
    if not candidate_plan:
        raise RuntimeError("candidate_plan must be prepared before order_planning")
    candidate_boundary_payload = dict(candidate_boundary.get("payload") or {})
    candidate_plan_payload = dict(candidate_plan.get("payload") or {})
    next_open = dict(runtime._current_day["next_open"])
    boundary_debug_plan = dict(candidate_boundary.get("debug_plan") or {})
    plan_debug_plan = dict(candidate_plan.get("debug_plan") or {})
    execution_debug_plan: dict[str, Any] = {}
    execution_candidate_rows: list[dict[str, Any]] = []
    planned_items = list(candidate_plan.get("planned_items") or [])
    execution_base_order_value = float(
        getattr(getattr(runtime, "request", None), "base_order_value", 0.0) or 0.0
    )
    final_buy_signals = [
        item.get("signal")
        for item in planned_items
        if item.get("signal") is not None
    ]
    planned_rotation_sell_signals = list(candidate_plan.get("planned_rotation_sell_signals") or [])
    atr_close_map: dict[str, tuple[float, float]] = {}
    provider_feats = getattr(runtime.provider, "_feats", None)
    provider_mx = getattr(runtime.provider, "_mx", None)
    provider_sym_to_col = getattr(runtime.provider, "_sym_to_col", {})
    if getattr(runtime, "_weight_mode", "") == "inverse_vol" and provider_feats is not None and provider_mx is not None:
        row_idx = int(runtime._prepared_day_index or 0)
        for symbol, col_idx in dict(provider_sym_to_col or {}).items():
            atr_v = float(provider_feats.atr14[row_idx, col_idx])
            close_v = float(provider_mx.close[row_idx, col_idx])
            if not (np.isnan(atr_v) or np.isnan(close_v)):
                atr_close_map[str(symbol).lower()] = (atr_v, close_v)

    orders = build_execution_orders_from_candidate_plan(
        positions=runtime.positions,
        cash_available=runtime.cash,
        nav_close=nav,
        max_positions=int(controls["effective_max_positions"]),
        lot_size=runtime.request.lot_size,
        sell_signals=[*list(day_signals.sell_signals), *planned_rotation_sell_signals],
        planned_items=planned_items,
        next_open=next_open,
        strength_ma=int(runtime.request.strength_ma),
        decision_date=day,
        candidate_audit=execution_candidate_rows,
        debug_plan=execution_debug_plan,
        overlay_mode=str(getattr(day_signals, "overlay_mode", "off") or "off"),
        overlay_gate_on_today=bool(getattr(day_signals, "overlay_gate_on_today", False)),
        overlay_observation_date=getattr(day_signals, "overlay_observation_date", None),
        overlay_score_source=str(getattr(day_signals, "overlay_score_source", "") or ""),
        slip_bps=float(getattr(runtime, "_slip_bps", 0.0) or 0.0),
        comm_rate=float(getattr(runtime, "_comm_rate", 0.0) or 0.0),
        comm_min=float(getattr(runtime, "_comm_min", 0.0) or 0.0),
        stamp_rate=float(getattr(runtime, "_stamp_rate", 0.0) or 0.0),
        base_order_value=float(execution_base_order_value),
        weight_mode=str(getattr(runtime, "_weight_mode", "equal") or "equal"),
        min_positions=int(getattr(runtime, "_min_positions_cfg", 0) or 0),
        atr_close_map=atr_close_map,
        holding_sources=getattr(runtime, "holding_sources", {}),
    )
    execution_reject_reason_counts = dict(
        (execution_debug_plan.get("execution_kernel_reject_reason_counts")
         or execution_debug_plan.get("reject_reason_counts")
         or {})
    )
    execution_kernel_payload = _build_execution_kernel_payload(
        candidate_rows=execution_candidate_rows,
        debug_plan=execution_debug_plan,
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
    target_book = _build_target_book_contract(
        day=day,
        next_trading_day=runtime._current_day.get("next_trading_day"),
        next_day_orders=next_day_orders,
        controls=controls,
        next_open=runtime._current_day.get("next_open"),
        nav_close=float(nav),
        default_owner_system=str(
            plan_debug_plan.get("system_sleeve_id")
            or boundary_debug_plan.get("system_sleeve_id")
            or ""
        ),
    )
    default_owner_system = str(
        plan_debug_plan.get("system_sleeve_id")
        or boundary_debug_plan.get("system_sleeve_id")
        or ""
    )
    subsystem_budgets = _build_subsystem_budget_payloads(
        day=day,
        controls=controls,
        debug_plan={**boundary_debug_plan, **plan_debug_plan, **execution_debug_plan},
        candidate_boundary_payload=candidate_boundary_payload,
        fallback_owner_system=default_owner_system,
    )
    action_intents = _build_action_intent_payloads(
        day=day,
        planned_items=planned_items,
        sell_signals=[*list(day_signals.sell_signals), *planned_rotation_sell_signals],
        positions=runtime.positions,
        nav_close=float(nav),
        subsystem_budgets=subsystem_budgets,
        default_owner_system=default_owner_system,
    )
    risk_overrides = _build_risk_override_payloads(
        day=day,
        controls=controls,
        sell_signals=list(day_signals.sell_signals),
    )
    execution_audit = _build_execution_audit_payload(
        day=day,
        action_intents=action_intents,
        next_day_orders=next_day_orders,
        planned_items=planned_items,
        debug_plan=execution_debug_plan,
        risk_overrides=risk_overrides,
    )
    return StageOutputs(
        stage_key="S7",
        holding_symbols=runtime._current_day["holding_symbols"],
        buy_symbols=tuple(od["symbol"] for od in next_day_orders if od["side"] == Side.BUY),
        sell_symbols=tuple(od["symbol"] for od in next_day_orders if od["side"] == Side.SELL),
        payload={
            "next_day_orders": tuple(next_day_orders),
            "formal_execution_boundary": {
                "subsystem_budgets": tuple(subsystem_budgets),
                "action_intents": tuple(action_intents),
                "risk_overrides": tuple(risk_overrides),
                "target_book": target_book,
                "execution_audit": execution_audit,
            },
            "compat_contracts": {
                "candidate_boundary": candidate_boundary_payload,
                "candidate_plan": candidate_plan_payload,
                "execution_kernel": execution_kernel_payload,
            },
            "candidate_boundary": candidate_boundary_payload,
            "candidate_plan": candidate_plan_payload,
            "execution_kernel": execution_kernel_payload,
            "subsystem_budgets": tuple(subsystem_budgets),
            "action_intents": tuple(action_intents),
            "risk_overrides": tuple(risk_overrides),
            "target_book": target_book,
            "execution_audit": execution_audit,
        },
        reason_counts=execution_reject_reason_counts,
        summary_fragment={
            "mode": "bridge_order_planner",
            "portfolio_mode": str(getattr(runtime, "_portfolio_mode", "") or ""),
            "buy_orders_count": sum(1 for od in next_day_orders if od["side"] == Side.BUY),
            "sell_orders_count": sum(1 for od in next_day_orders if od["side"] == Side.SELL),
            "deferred_sell_orders_count": int(deferred_sell_count),
            "candidate_boundary_mode": str(candidate_boundary_payload.get("boundary_mode") or ""),
            "candidate_plan_mode": str(candidate_plan_payload.get("plan_mode") or ""),
            "formal_action_intent_count": int(len(action_intents)),
            "formal_risk_override_count": int(len(risk_overrides)),
            "target_book_count": int(len(list(target_book.get("targets") or ()))),
        },
    )
