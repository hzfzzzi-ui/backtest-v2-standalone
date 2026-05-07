from __future__ import annotations

import math
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.core.config.cn_a_governed_mainline import canonical_state_5

_STATE_BUDGET_MAP: dict[str, dict[str, float]] = {
    "BULL": {"defense": 0.0, "core_beta": 0.5, "alpha": 0.5},
    "TRANS_UP": {"defense": 0.0, "core_beta": 0.5, "alpha": 0.5},
    "TRANS_DOWN": {"defense": 0.4, "core_beta": 0.4, "alpha": 0.2},
    "RISK_OFF": {"defense": 0.7, "core_beta": 0.3, "alpha": 0.0},
}
_RISK_ON_STATES = {"BULL", "TRANS_UP"}
_DEFENSIVE_STATES = {"TRANS_DOWN", "RISK_OFF"}
_WEAK_STATES = {"TRANS_DOWN", "RISK_OFF"}
_STATE_EDGE_RELEASE_FROM_STATES = {"BULL", "TRANS_UP"}
_STATE_EDGE_RELEASE_TO_STATES = {"TRANS_DOWN", "RISK_OFF"}
_STATE_EDGE_RELEASE_RATIO_CAP = 0.02
_RISK_OFF_LEFT_SIDE_DEFENSE_ASSETS = ("511010.SH",)
_RISK_OFF_LEFT_SIDE_CORE_BETA_ASSETS = ("510300.SH",)
_DEFENSE_ESTABLISH_RESEARCH_VARIANTS: dict[str, dict[str, Any]] = {
    "all_defensive": {
        "edge_to_states": ["TRANS_DOWN", "RISK_OFF"],
        "top_up_existing_defense": True,
    },
    "riskoff_only": {
        "edge_to_states": ["RISK_OFF"],
        "top_up_existing_defense": True,
    },
    "riskoff_only_no_topup": {
        "edge_to_states": ["RISK_OFF"],
        "top_up_existing_defense": False,
    },
}
_ACTIVE_DEFENSE_ESTABLISH_RESEARCH_VARIANT = "riskoff_only"
_TOLERANCE = 1e-6


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return 0.0
    return out if out == out and out not in (float("inf"), float("-inf")) else 0.0


def _optional_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return float(out) if math.isfinite(out) else None


def _state_budget(state: Any) -> dict[str, float]:
    normalized = canonical_state_5(str(state or "").strip()) or "TRANS_UP"
    return dict(_STATE_BUDGET_MAP.get(normalized) or _STATE_BUDGET_MAP["TRANS_UP"])


def _resolve_defense_establish_research_variant() -> dict[str, Any]:
    variant_id = str(_ACTIVE_DEFENSE_ESTABLISH_RESEARCH_VARIANT or "").strip() or "all_defensive"
    payload = dict(_DEFENSE_ESTABLISH_RESEARCH_VARIANTS.get(variant_id) or {})
    edge_to_states = [
        canonical_state_5(str(item).strip())
        for item in list(payload.get("edge_to_states") or [])
        if canonical_state_5(str(item).strip())
    ]
    return sanitize_json(
        {
            "variant_id": variant_id,
            "edge_to_states": edge_to_states,
            "top_up_existing_defense": bool(payload.get("top_up_existing_defense", True)),
        }
    )


def build_account_state_transition_policy() -> dict[str, Any]:
    return sanitize_json(
        {
            "contract_version": "account_layer_state_transition_policy@1",
            "state_source": "account_layer_state_machine",
            "resolution_mode": "component_evidence_priority_map",
            "transition_families": {
                "risk_on_to_risk_on": {
                    "carry_rules": {
                        "mode": "carry_risk_budgets",
                        "allowed_roles": ["core_beta", "alpha"],
                    },
                    "de_risk_rules": {
                        "mode": "steady_state_reweight",
                        "priority_roles": [],
                    },
                    "cash_release_rules": {
                        "mode": "none",
                        "destination": None,
                    },
                    "budget_handoff_rules": {
                        "mode": "steady_state_budget_map",
                    },
                },
                "risk_on_to_defensive": {
                    "carry_rules": {
                        "mode": "bounded_defensive_carry",
                        "allowed_roles": ["defense", "core_beta"],
                    },
                    "de_risk_rules": {
                        "mode": "bounded_partial_de_risk",
                        "priority_roles": ["alpha", "core_beta"],
                    },
                    "cash_release_rules": {
                        "mode": "bounded_partial_release",
                        "destination": "defense",
                    },
                    "budget_handoff_rules": {
                        "mode": "shift_to_defensive_budget",
                    },
                },
                "defensive_to_defensive": {
                    "carry_rules": {
                        "mode": "defensive_carry_forward",
                        "allowed_roles": ["defense", "core_beta"],
                    },
                    "de_risk_rules": {
                        "mode": "defensive_rebalance",
                        "priority_roles": ["core_beta"],
                    },
                    "cash_release_rules": {
                        "mode": "rebalance_within_defensive",
                        "destination": "defense",
                    },
                    "budget_handoff_rules": {
                        "mode": "defensive_budget_roll",
                    },
                },
                "defensive_to_recovery": {
                    "carry_rules": {
                        "mode": "recovery_carry_forward",
                        "allowed_roles": ["defense", "core_beta"],
                    },
                    "de_risk_rules": {
                        "mode": "none",
                        "priority_roles": [],
                    },
                    "cash_release_rules": {
                        "mode": "reuse_existing_cash",
                        "destination": "core_beta",
                    },
                    "budget_handoff_rules": {
                        "mode": "rebuild_risk_budgets",
                    },
                },
            },
        }
    )


def _classify_state_transition(previous_state: Any, effective_state: Any) -> str:
    prev_state = canonical_state_5(str(previous_state or "").strip()) or None
    next_state = canonical_state_5(str(effective_state or "").strip()) or None
    if next_state in _DEFENSIVE_STATES:
        if prev_state in _DEFENSIVE_STATES:
            return "defensive_to_defensive"
        return "risk_on_to_defensive"
    if prev_state in _DEFENSIVE_STATES:
        return "defensive_to_recovery"
    return "risk_on_to_risk_on"


def resolve_account_state_from_evidence(
    *,
    stock_state_5: Any,
    etf_state_5: Any,
    previous_account_state_5: Any | None = None,
) -> dict[str, Any]:
    stock_state = canonical_state_5(str(stock_state_5 or "").strip()) or None
    etf_state = canonical_state_5(str(etf_state_5 or "").strip()) or None
    previous_state = canonical_state_5(str(previous_account_state_5 or "").strip()) or None
    evidence_states = [state for state in (stock_state, etf_state) if state]
    effective_state = next(
        (
            candidate
            for candidate in ("RISK_OFF", "TRANS_DOWN", "TRANS_UP", "BULL")
            if candidate in evidence_states
        ),
        None,
    )
    effective_state = effective_state or previous_state or "TRANS_UP"
    transition_kind = _classify_state_transition(previous_state, effective_state)
    return sanitize_json(
        {
            "contract_version": "account_layer_state_resolution@1",
            "state_source": "account_layer_state_machine",
            "resolution_mode": "component_evidence_priority_map",
            "previous_account_state_5": previous_state,
            "effective_state_5": effective_state,
            "component_evidence": {
                "stock_state_5": stock_state,
                "etf_state_5": etf_state,
            },
            "transition_kind": transition_kind,
        }
    )


def build_account_state_transition_runtime(
    *,
    previous_state_5: Any | None,
    effective_state_5: Any | None,
) -> dict[str, Any]:
    previous_state = canonical_state_5(str(previous_state_5 or "").strip()) or None
    effective_state = canonical_state_5(str(effective_state_5 or "").strip()) or None
    transition_kind = _classify_state_transition(previous_state, effective_state)
    policy = build_account_state_transition_policy()
    rules = dict((policy.get("transition_families") or {}).get(transition_kind) or {})
    return sanitize_json(
        {
            "contract_version": "account_layer_state_transition_runtime@1",
            "state_source": "account_layer_state_machine",
            "previous_state_5": previous_state,
            "effective_state_5": effective_state,
            "transition_kind": transition_kind,
            "transition_active": bool(previous_state and effective_state and previous_state != effective_state),
            "carry_rules": dict(rules.get("carry_rules") or {}),
            "de_risk_rules": dict(rules.get("de_risk_rules") or {}),
            "cash_release_rules": dict(rules.get("cash_release_rules") or {}),
            "budget_handoff_rules": dict(rules.get("budget_handoff_rules") or {}),
        }
    )


def build_account_transition_action_handoff(
    *,
    previous_state_5: Any | None,
    effective_state_5: Any | None,
) -> dict[str, Any]:
    transition_runtime = build_account_state_transition_runtime(
        previous_state_5=previous_state_5,
        effective_state_5=effective_state_5,
    )
    transition_kind = str(transition_runtime.get("transition_kind") or "").strip()
    carry_rules = dict(transition_runtime.get("carry_rules") or {})
    de_risk_rules = dict(transition_runtime.get("de_risk_rules") or {})
    cash_release_rules = dict(transition_runtime.get("cash_release_rules") or {})
    budget_handoff_rules = dict(transition_runtime.get("budget_handoff_rules") or {})
    implemented_for_execution = transition_kind == "risk_on_to_defensive"
    if cash_release_rules.get("mode") == "bounded_partial_release":
        cash_release_rules = {
            **cash_release_rules,
            "bounded_partial_release_ratio_cap": _STATE_EDGE_RELEASE_RATIO_CAP,
        }
    return sanitize_json(
        {
            "contract_version": "account_transition_action_handoff@1",
            "state_source": "account_layer_state_machine",
            "previous_state_5": transition_runtime.get("previous_state_5"),
            "effective_state_5": transition_runtime.get("effective_state_5"),
            "transition_kind": transition_kind,
            "transition_active": bool(transition_runtime.get("transition_active")),
            "execution_priority": "account_layer_transition_contract",
            "consumption_mode": "priority_execution" if implemented_for_execution else "reference_only",
            "implemented_for_execution": implemented_for_execution,
            "reference_only": not implemented_for_execution,
            "carry_action": carry_rules,
            "de_risk_action": de_risk_rules,
            "cash_release_action": cash_release_rules,
            "budget_handoff_action": budget_handoff_rules,
            "diagnostics_reference_paths": [
                "state_edge_cash_release",
                "riskoff_cash_drip_topup",
                "riskoff_account_budget_materialization",
                "weak_state_inter_rebalance_defense_redeploy",
            ],
        }
    )


def _build_transition_family_implementation_status() -> dict[str, dict[str, Any]]:
    return sanitize_json(
        {
            "risk_on_to_risk_on": {
                "contract_ready": True,
                "execution_ready": False,
                "owner_mode": "shared_account_execution_runtime",
                "status": "contract_ready_reference_only",
            },
            "risk_on_to_defensive": {
                "contract_ready": True,
                "execution_ready": True,
                "owner_mode": "shared_account_execution_runtime",
                "status": "execution_ready",
            },
            "defensive_to_defensive": {
                "contract_ready": True,
                "execution_ready": False,
                "owner_mode": "shared_account_execution_runtime",
                "status": "contract_ready_reference_only",
            },
            "defensive_to_recovery": {
                "contract_ready": True,
                "execution_ready": False,
                "owner_mode": "shared_account_execution_runtime",
                "status": "contract_ready_reference_only",
            },
        }
    )


def build_shared_account_transition_execution_runtime(
    *,
    state_transition_runtime: dict[str, Any] | None,
    transition_action_handoff: dict[str, Any] | None,
) -> dict[str, Any]:
    runtime = dict(state_transition_runtime or {})
    handoff = dict(transition_action_handoff or {})
    transition_kind = str(runtime.get("transition_kind") or handoff.get("transition_kind") or "").strip()
    family_status = _build_transition_family_implementation_status()
    active = bool(runtime.get("transition_active") or handoff.get("transition_active"))
    family_payload = dict(family_status.get(transition_kind) or {})
    execution_ready = bool(family_payload.get("execution_ready"))
    if not active:
        status = "inactive"
        reason_code = "ACCOUNT_LAYER_SHARED_TRANSITION_EXECUTION_INACTIVE"
        reject_reason = None
    elif execution_ready:
        status = "owned"
        reason_code = "ACCOUNT_LAYER_SHARED_TRANSITION_EXECUTION_OWNED"
        reject_reason = None
    else:
        status = "reference_only"
        reason_code = "ACCOUNT_LAYER_SHARED_TRANSITION_EXECUTION_NOT_IMPLEMENTED"
        reject_reason = "ACCOUNT_LAYER_SHARED_TRANSITION_EXECUTION_FAMILY_NOT_IMPLEMENTED"
    return sanitize_json(
        {
            "contract_version": "shared_account_transition_execution_runtime@1",
            "owner": "shared_account_execution_runtime",
            "state_source": "account_layer_state_machine",
            "transition_kind": transition_kind or None,
            "active": active,
            "status": status,
            "reason_code": reason_code,
            "reject_reason": reject_reason,
            "reference_only": status != "owned",
            "execution_path": "shared_account_transition_execution_runtime" if status == "owned" else None,
            "family_implementation_status": family_status,
            "implemented_for_execution": execution_ready,
            "reference_paths": list(handoff.get("diagnostics_reference_paths") or []),
        }
    )


def _riskoff_left_side_accumulation_policy(*, effective_state: Any | None = None) -> dict[str, Any]:
    normalized_state = (
        canonical_state_5(str(effective_state or "").strip())
        if effective_state is not None
        else None
    )
    target_budget = _state_budget("RISK_OFF")
    return sanitize_json(
        {
            "contract_version": "riskoff_account_left_side_accumulation_budget@1",
            "enabled": True,
            "active": normalized_state == "RISK_OFF",
            "scoped_state_5": "RISK_OFF",
            "budget_semantics": "defense_first_left_side_accumulation",
            "defense_assets": list(_RISK_OFF_LEFT_SIDE_DEFENSE_ASSETS),
            "core_beta_assets": list(_RISK_OFF_LEFT_SIDE_CORE_BETA_ASSETS),
            "defense_weight": round(_safe_float(target_budget.get("defense")), 6),
            "core_beta_weight": round(_safe_float(target_budget.get("core_beta")), 6),
            "alpha_weight": round(_safe_float(target_budget.get("alpha")), 6),
            "fixed_core_beta_accumulation_symbol": "510300.SH",
            "execution_constraint_change": False,
            "total_exposure_change": False,
        }
    )


def resolve_stock_etf_budget_for_state(
    state: Any,
    *,
    fallback_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    fallback = sanitize_json(
        {
            "cn_stock_trend_alpha_core": _safe_float((fallback_weights or {}).get("cn_stock_trend_alpha_core")) or 0.5,
            "cn_etf_beta": _safe_float((fallback_weights or {}).get("cn_etf_beta")) or 0.5,
        }
    )
    state_text = canonical_state_5(str(state or "").strip()) or ""
    if not state_text:
        return sanitize_json(
            {
                "effective_state_5": None,
                "weights": fallback,
                "source": "fixed_weight_50_50_fallback",
                "fallback_applied": True,
            }
        )
    budget = _state_budget(state_text)
    role_budgets = {
        "defense": round(_safe_float(budget.get("defense")), 6),
        "core_beta": round(_safe_float(budget.get("core_beta")), 6),
        "alpha": round(_safe_float(budget.get("alpha")), 6),
    }
    weights = {
        "cn_stock_trend_alpha_core": float(role_budgets["alpha"]),
        "cn_etf_beta": round(float(role_budgets["defense"]) + float(role_budgets["core_beta"]), 6),
    }
    return sanitize_json(
        {
            "effective_state_5": state_text,
            "weights": weights,
            "budget_roles": role_budgets,
            "source": "account_state_budget_map",
            "fallback_applied": False,
        }
    )


def build_account_budget_control(
    *,
    enabled: bool,
    fallback_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    state_budget_map = {}
    state_budget_role_map = {}
    for state in _STATE_BUDGET_MAP:
        resolved = resolve_stock_etf_budget_for_state(state, fallback_weights=fallback_weights)
        state_budget_map[state] = dict(resolved.get("weights") or {})
        state_budget_role_map[state] = dict(resolved.get("budget_roles") or {})
    fallback = sanitize_json(
        {
            "cn_stock_trend_alpha_core": _safe_float((fallback_weights or {}).get("cn_stock_trend_alpha_core")) or 0.5,
            "cn_etf_beta": _safe_float((fallback_weights or {}).get("cn_etf_beta")) or 0.5,
        }
    )
    return sanitize_json(
        {
            "contract_version": "account_budget_control@1",
            "enabled": bool(enabled),
            "budget_owner": "account_allocator",
            "budget_basis": "share_of_total_nav",
            "source_mode": "account_state_budget_map",
            "state_source": "account_layer_state_machine",
            "fallback_mode": "fixed_weight_50_50",
            "state_transition_policy": build_account_state_transition_policy(),
            "transition_action_handoff_contract": {
                "contract_version": "account_transition_action_handoff@1",
                "state_source": "account_layer_state_machine",
                "consumption_scope": "execution_layer",
                "transition_families": [
                    "risk_on_to_risk_on",
                    "risk_on_to_defensive",
                    "defensive_to_defensive",
                    "defensive_to_recovery",
                ],
            },
            "state_edge_cash_release_policy": {
                "contract_version": "account_state_edge_cash_release_policy@1",
                "enabled": True,
                "reference_only": True,
                "edge_from_states": sorted(_STATE_EDGE_RELEASE_FROM_STATES),
                "edge_to_states": sorted(_STATE_EDGE_RELEASE_TO_STATES),
                "release_destination_by_state": {
                    "TRANS_DOWN": "defense",
                    "RISK_OFF": "accumulation",
                },
                "bounded_partial_release_ratio_cap": _STATE_EDGE_RELEASE_RATIO_CAP,
            },
            "riskoff_left_side_accumulation_policy": _riskoff_left_side_accumulation_policy(),
            "state_budget_map": state_budget_map,
            "state_budget_role_map": state_budget_role_map,
            "fallback_weights": fallback,
        }
    )


def _actual_budget_snapshot(combo_governed_snapshot: dict[str, Any]) -> dict[str, Any]:
    sleeve_budgets = (
        dict(combo_governed_snapshot.get("sleeve_budgets") or {})
        if isinstance(combo_governed_snapshot.get("sleeve_budgets"), dict)
        else {}
    )
    stock_payload = (
        dict(sleeve_budgets.get("cn_stock_trend_alpha_core") or {})
        if isinstance(sleeve_budgets.get("cn_stock_trend_alpha_core"), dict)
        else {}
    )
    etf_payload = (
        dict(sleeve_budgets.get("cn_etf_beta") or {})
        if isinstance(sleeve_budgets.get("cn_etf_beta"), dict)
        else {}
    )

    alpha = max(0.0, _safe_float(stock_payload.get("actual_exposure")))
    etf_total = max(0.0, _safe_float(etf_payload.get("actual_exposure")))
    etf_risk = max(0.0, min(etf_total, _safe_float(etf_payload.get("actual_risk_exposure"))))
    explicit_defense = _optional_float(etf_payload.get("actual_defense_exposure"))
    if explicit_defense is not None:
        defense = max(0.0, min(etf_total, float(explicit_defense)))
        core_beta = max(0.0, min(etf_total, etf_risk) - defense)
        derivation = "stock_actual_exposure + etf_actual_role_exposures"
    else:
        defense = max(0.0, etf_total - etf_risk)
        core_beta = max(0.0, min(etf_total, etf_risk))
        derivation = "stock_actual_exposure + etf_actual_risk_split_proxy"
    total_deployed = max(0.0, alpha + defense + core_beta)
    unallocated_cash = max(0.0, 1.0 - total_deployed)

    return sanitize_json(
        {
            "defense": defense,
            "core_beta": core_beta,
            "alpha": alpha,
            "total_deployed": total_deployed,
            "unallocated_cash": unallocated_cash,
            "derivation": derivation,
        }
    )


def _deviation_payload(
    *,
    effective_state: str,
    suggested: dict[str, float],
    actual: dict[str, Any],
) -> dict[str, Any]:
    defense_gap = round(_safe_float(suggested.get("defense")) - _safe_float(actual.get("defense")), 6)
    core_gap = round(_safe_float(suggested.get("core_beta")) - _safe_float(actual.get("core_beta")), 6)
    alpha_gap = round(_safe_float(suggested.get("alpha")) - _safe_float(actual.get("alpha")), 6)
    derivation = str(actual.get("derivation") or "").strip().lower()
    if "proxy" in derivation:
        reasons: list[str] = ["ACTUAL_BUDGETS_USE_PROXY_SPLIT"]
    else:
        reasons = ["ACTUAL_BUDGETS_USE_COMPONENT_ROLE_EXPOSURES"]

    if defense_gap > _TOLERANCE:
        reasons.append("DEFENSE_UNDER_SUGGESTED")
    elif defense_gap < -_TOLERANCE:
        reasons.append("DEFENSE_OVER_SUGGESTED")

    if core_gap > _TOLERANCE:
        reasons.append("CORE_BETA_UNDER_SUGGESTED")
    elif core_gap < -_TOLERANCE:
        reasons.append("CORE_BETA_OVER_SUGGESTED")

    if alpha_gap > _TOLERANCE:
        reasons.append("ALPHA_UNDER_SUGGESTED")
    elif alpha_gap < -_TOLERANCE:
        reasons.append("ALPHA_OVER_SUGGESTED")

    if _safe_float(actual.get("unallocated_cash")) > 0.05:
        reasons.append("UNALLOCATED_CASH_PRESENT")

    if effective_state in _WEAK_STATES and alpha_gap < -_TOLERANCE:
        reasons.append("WEAK_STATE_ALPHA_NOT_RELEASED")

    return sanitize_json(
        {
            "defense_gap": defense_gap,
            "core_beta_gap": core_gap,
            "alpha_gap": alpha_gap,
            "reason_codes": reasons,
        }
    )


def _cash_release_suggestion(
    *,
    effective_state: str,
    suggested: dict[str, float],
    actual: dict[str, Any],
) -> dict[str, Any]:
    if effective_state not in _WEAK_STATES:
        return sanitize_json(
            {
                "active": False,
                "release_destination": None,
                "source_role": None,
                "target_role": None,
                "suggested_release": 0.0,
                "reason_codes": ["STATE_DOES_NOT_REQUIRE_CASH_RELEASE"],
            }
        )

    release_destination = "defense" if effective_state == "TRANS_DOWN" else "accumulation"
    defense_need = max(0.0, _safe_float(suggested.get("defense")) - _safe_float(actual.get("defense")))
    alpha_excess = max(0.0, _safe_float(actual.get("alpha")) - _safe_float(suggested.get("alpha")))
    core_excess = max(0.0, _safe_float(actual.get("core_beta")) - _safe_float(suggested.get("core_beta")))
    total_deployed = max(0.0, _safe_float(actual.get("total_deployed")))
    bounded_partial_release_cap = min(total_deployed * _STATE_EDGE_RELEASE_RATIO_CAP, max(defense_need, alpha_excess, core_excess))

    source_role = None
    source_excess = 0.0
    if alpha_excess > _TOLERANCE:
        source_role = "alpha"
        source_excess = alpha_excess
    elif core_excess > _TOLERANCE:
        source_role = "core_beta"
        source_excess = core_excess

    suggested_release = min(defense_need, source_excess, bounded_partial_release_cap) if source_role else 0.0
    reason_codes: list[str] = []
    if defense_need <= _TOLERANCE:
        reason_codes.append("DEFENSE_TARGET_ALREADY_SATISFIED")
    elif not source_role:
        reason_codes.append("NO_OVER_BUDGET_SOURCE_ROLE")
    else:
        reason_codes.append(f"RELEASE_FROM_{source_role.upper()}_TO_{release_destination.upper()}")
        if bounded_partial_release_cap + _TOLERANCE < min(defense_need, source_excess):
            reason_codes.append("STATE_EDGE_BOUNDED_PARTIAL_RELEASE_CAP_APPLIED")

    return sanitize_json(
        {
            "active": suggested_release > _TOLERANCE,
            "release_destination": release_destination if source_role else None,
            "source_role": source_role,
            "target_role": release_destination if source_role else None,
            "bounded_partial_release_ratio_cap": _STATE_EDGE_RELEASE_RATIO_CAP,
            "suggested_release": round(suggested_release, 6),
            "reason_codes": reason_codes,
        }
    )


def build_account_budget_runtime_reference(
    *,
    combo_regime: dict[str, Any],
    combo_governed_snapshot: dict[str, Any],
    account_state_resolution: dict[str, Any] | None = None,
    state_transition_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state_resolution = dict(account_state_resolution or {})
    transition_runtime = dict(state_transition_runtime or {})
    effective_state = (
        canonical_state_5(str(state_resolution.get("effective_state_5") or "").strip())
        or canonical_state_5(str(combo_regime.get("effective_state") or "").strip())
        or "TRANS_UP"
    )
    suggested_budgets = _state_budget(effective_state)
    actual_budgets = _actual_budget_snapshot(combo_governed_snapshot)
    deviation = _deviation_payload(
        effective_state=effective_state,
        suggested=suggested_budgets,
        actual=actual_budgets,
    )
    cash_release = _cash_release_suggestion(
        effective_state=effective_state,
        suggested=suggested_budgets,
        actual=actual_budgets,
    )
    transition_action_handoff = build_account_transition_action_handoff(
        previous_state_5=state_resolution.get("previous_account_state_5"),
        effective_state_5=effective_state,
    )
    return sanitize_json(
        {
            "contract_version": "account_budget_runtime_reference@1",
            "mode": "reference_only",
            "non_takeover": True,
            "budget_basis": "share_of_total_nav",
            "state_source": str(state_resolution.get("state_source") or "account_layer_state_machine"),
            "effective_state_5": effective_state,
            "state_resolution": sanitize_json(
                {
                    **state_resolution,
                    "effective_state_5": effective_state,
                }
            ),
            "state_transition_runtime": sanitize_json(
                {
                    **transition_runtime,
                    "effective_state_5": effective_state,
                }
            ),
            "transition_action_handoff": transition_action_handoff,
            "suggested_budgets": suggested_budgets,
            "etf_budget_roles": sanitize_json(
                {
                    "contract_version": "etf_defense_core_beta_budgets@1",
                    "effective_state_5": effective_state,
                    "target": {
                        "defense": round(_safe_float(suggested_budgets.get("defense")), 6),
                        "core_beta": round(_safe_float(suggested_budgets.get("core_beta")), 6),
                        "alpha": round(_safe_float(suggested_budgets.get("alpha")), 6),
                    },
                    "actual": {
                        "defense": round(_safe_float(actual_budgets.get("defense")), 6),
                        "core_beta": round(_safe_float(actual_budgets.get("core_beta")), 6),
                        "alpha": round(_safe_float(actual_budgets.get("alpha")), 6),
                    },
                    "deviation": {
                        "defense_gap": round(_safe_float(deviation.get("defense_gap")), 6),
                        "core_beta_gap": round(_safe_float(deviation.get("core_beta_gap")), 6),
                        "alpha_gap": round(_safe_float(deviation.get("alpha_gap")), 6),
                    },
                }
            ),
            "riskoff_left_side_accumulation_budget": _riskoff_left_side_accumulation_policy(
                effective_state=effective_state
            ),
            "actual_budgets": actual_budgets,
            "deviation": deviation,
            "suggested_cash_release": cash_release,
            "state_edge_cash_release": sanitize_json(
                {
                    "contract_version": "account_state_edge_cash_release_reference@1",
                    "active": bool(cash_release.get("active")),
                    "effective_state_5": effective_state,
                    "release_destination": cash_release.get("release_destination"),
                    "bounded_partial_release_ratio_cap": _STATE_EDGE_RELEASE_RATIO_CAP,
                    "suggested_release": cash_release.get("suggested_release"),
                    "reason_codes": list(cash_release.get("reason_codes") or []),
                }
            ),
        }
    )


def build_shared_transition_execution_policy_config(
    *,
    account_budget_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    control = dict(account_budget_control or {})
    riskoff_policy = dict(control.get("riskoff_left_side_accumulation_policy") or {})
    defense_assets = [
        str(item).strip().upper()
        for item in list(riskoff_policy.get("defense_assets") or ["511010.SH"])
        if str(item).strip()
    ]
    core_beta_assets = [
        str(item).strip().upper()
        for item in list(riskoff_policy.get("core_beta_assets") or ["510300.SH"])
        if str(item).strip()
    ]
    defense_symbol = defense_assets[0] if defense_assets else "511010.SH"
    core_beta_symbol = core_beta_assets[0] if core_beta_assets else "510300.SH"
    defense_establish_variant = _resolve_defense_establish_research_variant()
    return sanitize_json(
        {
            "contract_version": "shared_account_transition_execution_policy@1",
            "enabled": True,
            "owner": "shared_account_execution_runtime",
            "diagnostics_reference_paths": [
                "state_edge_cash_release",
                "riskoff_cash_drip_topup",
                "riskoff_account_budget_materialization",
                "weak_state_inter_rebalance_defense_redeploy",
            ],
            "transition_families": {
                "risk_on_to_defensive": {
                    "enabled": True,
                    "action_mode": "sell_first_defense_cash_release",
                    "release_ratio_cap": 0.2,
                    "minimum_defense_lots": 1,
                    "defense_symbol": defense_symbol,
                    "core_beta_symbol": core_beta_symbol,
                    "defense_establish_enabled": True,
                    "defense_establish_mode": "buy_after_sell_same_edge",
                    "defense_establish_variant_id": defense_establish_variant.get("variant_id"),
                    "defense_establish_edge_to_states": list(
                        defense_establish_variant.get("edge_to_states") or []
                    ),
                    "defense_establish_top_up_existing_defense": bool(
                        defense_establish_variant.get("top_up_existing_defense")
                    ),
                },
                "risk_on_to_risk_on": {"enabled": False},
                "defensive_to_defensive": {"enabled": False},
                "defensive_to_recovery": {"enabled": False},
            },
        }
    )


def build_account_allocator_runtime(
    *,
    account_budget_control: dict[str, Any],
    account_budget_runtime_reference: dict[str, Any],
    combo_reference: dict[str, Any] | None = None,
    riskoff_budget_execution_materialization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    control = dict(account_budget_control or {})
    shadow = dict(account_budget_runtime_reference or {})
    etf_budget_roles = dict(shadow.get("etf_budget_roles") or {})
    riskoff_left_side_accumulation_budget = dict(
        shadow.get("riskoff_left_side_accumulation_budget")
        or control.get("riskoff_left_side_accumulation_policy")
        or {}
    )
    riskoff_budget_execution_materialization_payload = dict(
        riskoff_budget_execution_materialization or {}
    )
    transition_action_handoff = dict(shadow.get("transition_action_handoff") or {})
    transition_execution = build_shared_account_transition_execution_runtime(
        state_transition_runtime=shadow.get("state_transition_runtime") or {},
        transition_action_handoff=transition_action_handoff,
    )
    if not riskoff_budget_execution_materialization_payload:
        riskoff_budget_execution_materialization_payload = sanitize_json(
            {
                "contract_version": "riskoff_account_budget_execution_materialization@1",
                "active": False,
                "budget_established": bool(riskoff_left_side_accumulation_budget.get("active")),
                "execution_activated": False,
                "execution_rejected": False,
                "execution_path": None,
                "materialization_mode": "bounded_partial_de_risk_release",
                "materialization_order": ["defense", "core_beta"],
                "release_destination": None,
                "release_target_cash": 0.0,
                "release_cash": 0.0,
                "bounded_partial_release_ratio_cap": 0.02,
                "reason_code": None,
                "reject_reason": None,
                "target_symbols": [],
                "release_symbols": [],
            }
        )
    budget_roles = {
        "target": {
            "defense": round(_safe_float(((etf_budget_roles.get("target") or {}).get("defense"))), 6),
            "core_beta": round(_safe_float(((etf_budget_roles.get("target") or {}).get("core_beta"))), 6),
            "alpha": round(_safe_float(((etf_budget_roles.get("target") or {}).get("alpha"))), 6),
        },
        "actual": {
            "defense": round(_safe_float(((etf_budget_roles.get("actual") or {}).get("defense"))), 6),
            "core_beta": round(_safe_float(((etf_budget_roles.get("actual") or {}).get("core_beta"))), 6),
            "alpha": round(_safe_float(((etf_budget_roles.get("actual") or {}).get("alpha"))), 6),
        },
        "deviation": {
            "defense_gap": round(_safe_float(((etf_budget_roles.get("deviation") or {}).get("defense_gap"))), 6),
            "core_beta_gap": round(_safe_float(((etf_budget_roles.get("deviation") or {}).get("core_beta_gap"))), 6),
            "alpha_gap": round(_safe_float(((etf_budget_roles.get("deviation") or {}).get("alpha_gap"))), 6),
        },
        "reason_codes": list(((shadow.get("deviation") or {}).get("reason_codes")) or []),
    }
    return sanitize_json(
        {
            "contract_version": "account_allocator_runtime@1",
            "runtime_truth_source": "account_allocator",
            "budget_owner": str(control.get("budget_owner") or "account_allocator"),
            "budget_basis": str(control.get("budget_basis") or "share_of_total_nav"),
            "source_mode": str(control.get("source_mode") or "account_state_budget_map"),
            "state_source": str(
                shadow.get("state_source")
                or control.get("state_source")
                or "account_layer_state_machine"
            ),
            "effective_state_5": shadow.get("effective_state_5"),
            "state_budget_map": dict(control.get("state_budget_map") or {}),
            "state_budget_role_map": dict(control.get("state_budget_role_map") or {}),
            "state_transition_policy": dict(control.get("state_transition_policy") or {}),
            "state_resolution": dict(shadow.get("state_resolution") or {}),
            "state_transition_runtime": dict(shadow.get("state_transition_runtime") or {}),
            "transition_action_handoff": transition_action_handoff,
            "transition_execution": transition_execution,
            "transition_execution_owner": str(transition_execution.get("owner") or "shared_account_execution_runtime"),
            "transition_execution_status": str(transition_execution.get("status") or "reference_only"),
            "transition_execution_reason_code": transition_execution.get("reason_code"),
            "transition_execution_reject_reason": transition_execution.get("reject_reason"),
            "transition_execution_reference_paths": list(transition_execution.get("reference_paths") or []),
            "state_edge_cash_release_policy": dict(control.get("state_edge_cash_release_policy") or {}),
            "riskoff_left_side_accumulation_budget": riskoff_left_side_accumulation_budget,
            "riskoff_budget_execution_materialization": riskoff_budget_execution_materialization_payload,
            "budget_roles": budget_roles,
            "sleeves_consume_budgets": True,
            "reference_combo": sanitize_json(
                {
                    **dict(combo_reference or {}),
                    "reference_only": True,
                    "narrative_role": "reference_zone",
                }
            ),
        }
    )
