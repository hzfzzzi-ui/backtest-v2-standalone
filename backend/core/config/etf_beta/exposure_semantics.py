from __future__ import annotations

from typing import Any

from .common import (
    _bull_pace_mode,
    _controlled_accumulation_mode_from_layering_policy,
    _deployment_pace_for_state,
    _derive_layering_semantics,
    _is_formal_stabilizer_role,
    _is_standalone_mainline_role,
    _normalize_choice,
    _normalize_controlled_accumulation_mode,
    _normalize_reason_list,
    _normalize_state_bool_map,
    _normalize_state_float_map,
    _normalize_state_int_map,
    _normalize_state_symbol_float_map,
    _normalize_state_symbol_list_map,
    _normalize_symbol_float_map,
    _normalize_symbol_list,
    _normalize_text,
    _pace_policy_mode,
    _pace_policy_reason_code,
    _resolve_phase1_defense_template,
    _resolve_phase1_equity_template,
    _resolve_phase1_bucket_split,
    _safe_float,
    _safe_int,
    _safe_notional_exposure,
    _trans_up_contract_mode,
    canonical_state_5,
)
from .defaults import (
    CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
    CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE,
    CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
    CN_ETF_BETA_LAYERING_POLICY,
    CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE,
    CN_ETF_BETA_LOCAL_POLICY_MODE,
    CN_ETF_BETA_POLICY_SCOPE,
    CN_ETF_BETA_STRATEGY_ROLE,
    CN_ETF_PHASE1_EQUITY_TILT_LIMITS,
)
from .normalization import normalize_etf_beta_contract


def _weighted_subtotal(weights: dict[str, float], symbols: list[str]) -> float:
    symbol_scope = {str(symbol).strip().upper() for symbol in list(symbols or []) if str(symbol).strip()}
    return float(sum(float(weight) for symbol, weight in dict(weights or {}).items() if str(symbol).strip().upper() in symbol_scope))


def _allocate_bucket(*, budget: float, weights: dict[str, float], symbols: list[str]) -> dict[str, float]:
    if float(budget) <= 1e-12:
        return {}
    symbol_scope = [str(symbol).strip().upper() for symbol in list(symbols or []) if str(symbol).strip()]
    scoped_weights = {
        symbol: float(weight)
        for symbol, weight in dict(weights or {}).items()
        if str(symbol).strip().upper() in set(symbol_scope) and float(weight) > 0.0
    }
    total = float(sum(scoped_weights.values()))
    if total <= 1e-12:
        return {}
    return {symbol: float(budget) * float(weight) / total for symbol, weight in scoped_weights.items()}


def _pick_target_exposure(
    *,
    etf_beta: dict[str, Any],
    effective_state_5: str,
    total_exposure_cap: Any,
    sleeve_budget_snapshot: dict[str, Any],
) -> tuple[float | None, str | None, list[str]]:
    target_exposure_map = _normalize_state_float_map(etf_beta.get("target_exposure_by_state_5"))
    if effective_state_5 and effective_state_5 in target_exposure_map:
        return float(target_exposure_map[effective_state_5]), f"state_map::{effective_state_5}", []

    fixed_target = _safe_notional_exposure(etf_beta.get("target_exposure"))
    if fixed_target is not None:
        return float(fixed_target), "fixed", []

    reasons: list[str] = []
    budget_target = _safe_float(sleeve_budget_snapshot.get("target_exposure"))
    if budget_target is not None:
        if 0.0 <= float(budget_target) <= 1.0 + 1e-12:
            return float(max(0.0, min(float(budget_target), 1.0))), "governor_sleeve_budget", reasons
        reasons.append("GOVERNOR_TARGET_EXPOSURE_OUT_OF_RANGE")

    cap_target = _safe_float(total_exposure_cap)
    if cap_target is None:
        cap_target = _safe_float(sleeve_budget_snapshot.get("total_exposure_cap"))
    if cap_target is not None:
        if 0.0 <= float(cap_target) <= 1.0 + 1e-12:
            return float(max(0.0, min(float(cap_target), 1.0))), "governor_total_exposure_cap", reasons
        reasons.append("GOVERNOR_TOTAL_EXPOSURE_CAP_OUT_OF_RANGE")

    return 0.0, "governor_zero_default", reasons


def _pick_target_selected_count(
    *,
    etf_beta: dict[str, Any],
    effective_state_5: str,
    slot_cap: Any,
    target_selected_count: Any,
    sleeve_budget_snapshot: dict[str, Any],
    trans_up_single_seat_core_recovery: bool,
) -> tuple[int, str | None]:
    if trans_up_single_seat_core_recovery:
        return 1, "trans_up_single_seat_core_recovery"

    target_selected_count_map = _normalize_state_int_map(etf_beta.get("target_selected_count_by_state_5"))
    if effective_state_5 and effective_state_5 in target_selected_count_map:
        value = int(target_selected_count_map[effective_state_5])
        if value > 0:
            return value, f"state_map::{effective_state_5}"

    for value, source in (
        (target_selected_count, "input"),
        (sleeve_budget_snapshot.get("target_selected_count"), "budget_snapshot"),
        (slot_cap, "slot_cap"),
        (etf_beta.get("max_selected_symbols"), "max_selected_symbols"),
    ):
        normalized = _safe_int(value, default=0)
        if normalized > 0:
            return int(normalized), source
    return 1, "fallback_default"


def _pick_min_deployable_exposure(
    *,
    etf_beta: dict[str, Any],
    effective_state_5: str,
    target_exposure: float | None,
    target_selected_count: int,
    sleeve_budget_snapshot: dict[str, Any],
) -> tuple[float | None, str | None]:
    min_deployable_map = _normalize_state_float_map(etf_beta.get("min_deployable_exposure_by_state_5"))
    if effective_state_5 and effective_state_5 in min_deployable_map:
        return float(min_deployable_map[effective_state_5]), f"state_map::{effective_state_5}"

    fixed_value = _safe_notional_exposure(etf_beta.get("min_deployable_exposure"))
    if fixed_value is not None:
        return float(fixed_value), "fixed"

    budget_value = _safe_notional_exposure(sleeve_budget_snapshot.get("min_deployable_exposure"))
    if budget_value is not None:
        return float(budget_value), "budget_snapshot"

    if _is_formal_stabilizer_role(etf_beta.get("strategy_role"), etf_beta.get("local_policy_mode")):
        return 0.0, "phase1_allocation_engine"

    if target_exposure is not None and target_selected_count > 0:
        return float(target_exposure) / float(target_selected_count), "derived_from_target"
    return None, None


def _pick_fallback_allowed(
    *,
    etf_beta: dict[str, Any],
    effective_state_5: str,
    sleeve_budget_snapshot: dict[str, Any],
) -> tuple[bool, str | None]:
    fallback_allowed_map = _normalize_state_bool_map(etf_beta.get("fallback_allowed_by_state_5"))
    if effective_state_5 and effective_state_5 in fallback_allowed_map:
        return bool(fallback_allowed_map[effective_state_5]), f"state_map::{effective_state_5}"
    if etf_beta.get("fallback_allowed") is not None:
        return bool(etf_beta.get("fallback_allowed")), "fixed"
    if sleeve_budget_snapshot.get("fallback_allowed") is not None:
        return bool(sleeve_budget_snapshot.get("fallback_allowed")), "budget_snapshot"
    fallback_mode_text = _normalize_text(etf_beta.get("fallback_mode")).lower()
    return bool(fallback_mode_text and fallback_mode_text != "none"), "fallback_mode_default"


def _resolve_weak_state_defense_policy(
    *,
    etf_beta: dict[str, Any],
    effective_state_5: str,
    limited_defense_symbols: list[str],
) -> dict[str, Any]:
    raw_policy = dict(etf_beta.get("weak_state_defense_policy") or {})
    enabled = bool(raw_policy.get("enabled", False))
    active = bool(enabled and effective_state_5 in {"TRANS_DOWN", "RISK_OFF"})
    candidate_map = _normalize_state_symbol_list_map(raw_policy.get("defense_candidate_symbols_by_state_5"))
    target_weight_map = _normalize_state_symbol_float_map(raw_policy.get("target_weights_by_state_5"))
    min_seat_map = _normalize_state_int_map(raw_policy.get("minimum_defense_seats_by_state_5"))
    allow_core_beta_map = _normalize_state_bool_map(raw_policy.get("allow_core_beta_by_state_5"))
    candidate_symbols = list(candidate_map.get(effective_state_5) or [])
    if not candidate_symbols:
        candidate_symbols = [str(symbol).strip().upper() for symbol in list(limited_defense_symbols or []) if str(symbol).strip()]
    unavailable_reason_codes: list[str] = []
    if active and not candidate_symbols:
        unavailable_reason_codes.append("ETF_BETA_WEAK_STATE_NO_DEFENSE_CANDIDATES")
    active_target_weights = dict(target_weight_map.get(effective_state_5) or {})
    if active and not active_target_weights:
        unavailable_reason_codes.append("ETF_BETA_WEAK_STATE_NO_TARGET_WEIGHTS")
    return {
        "policy_id": _normalize_text(raw_policy.get("policy_id")) or None,
        "active": active,
        "candidate_symbols": candidate_symbols,
        "target_weights_by_state_5": target_weight_map,
        "active_target_weights": active_target_weights,
        "min_seats": max(0, int(min_seat_map.get(effective_state_5, 0))) if active else 0,
        "allow_core_beta": bool(allow_core_beta_map.get(effective_state_5, False)) if active else False,
        "unavailable_reason_codes": unavailable_reason_codes,
    }


def resolve_etf_beta_exposure_semantics(
    *,
    etf_beta_contract: dict[str, Any] | None,
    effective_state_5: Any = None,
    total_exposure_cap: Any = None,
    slot_cap: Any = None,
    target_selected_count: Any = None,
    sleeve_budget_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    etf_beta = normalize_etf_beta_contract(etf_beta_contract or {})
    sleeve_budget = dict(sleeve_budget_snapshot or {})
    state_5 = canonical_state_5(effective_state_5 or sleeve_budget.get("effective_state_5") or "TRANS_UP")

    strategy_role = _normalize_choice(
        etf_beta.get("strategy_role"),
        default=CN_ETF_BETA_STRATEGY_ROLE,
        allowed={"auxiliary_beta_sleeve", "governed_broad_based_standalone_mainline", "phase1_allocation_engine", "strategic_beta_stabilizer"},
    )
    local_policy_mode = _normalize_choice(
        etf_beta.get("local_policy_mode"),
        default=CN_ETF_BETA_LOCAL_POLICY_MODE,
        allowed={"legacy_beta_selection", "broad_based_rotation_mainline", "phase1_bucket_allocation"},
    )
    governor_boundary_mode = _normalize_choice(
        etf_beta.get("governor_boundary_mode"),
        default=CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        allowed={"consume_governor_sleeve_budget", "consume_governor_state_and_budget"},
    )
    exposure_policy_family = _normalize_choice(
        etf_beta.get("exposure_policy_family"),
        default=CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
        allowed={"default", "broad_based_governed_v1", "broad_based_standalone_mainline_v1", "phase1_governed_allocation_v1"},
    )
    policy_scope = _normalize_choice(
        etf_beta.get("policy_scope"),
        default=CN_ETF_BETA_POLICY_SCOPE,
        allowed={"general", "broad_based_only"},
    )
    broad_based_only = bool(etf_beta.get("broad_based_only")) if etf_beta.get("broad_based_only") is not None else policy_scope == "broad_based_only"
    layering_policy = _normalize_choice(
        etf_beta.get("layering_policy"),
        default=CN_ETF_BETA_LAYERING_POLICY,
        allowed={"none", "light_accumulate", "light_trans_down_accumulate"},
    )
    controlled_accumulation_mode = _normalize_controlled_accumulation_mode(etf_beta.get("controlled_accumulation_mode"))
    if not _normalize_text(etf_beta.get("controlled_accumulation_mode")):
        controlled_accumulation_mode = _controlled_accumulation_mode_from_layering_policy(layering_policy)

    formal_stabilizer_active = _is_formal_stabilizer_role(strategy_role, local_policy_mode)
    standalone_mainline_active = _is_standalone_mainline_role(
        strategy_role,
        local_policy_mode=local_policy_mode,
        exposure_policy_family=exposure_policy_family,
    )
    boundary_policy_mode = _normalize_text(etf_beta.get("boundary_policy_mode")) or (
        CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE if formal_stabilizer_active else CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE
    )
    trans_up_contract_mode = _trans_up_contract_mode(effective_state_5=state_5, formal_stabilizer_active=formal_stabilizer_active)
    trans_up_single_seat_core_recovery = trans_up_contract_mode == "single_seat_core_recovery"

    governor_budget_reason_codes = _normalize_reason_list(sleeve_budget.get("budget_reason_codes") or [])
    requested_budget, target_exposure_source, budget_reason_codes = _pick_target_exposure(
        etf_beta=etf_beta,
        effective_state_5=state_5,
        total_exposure_cap=total_exposure_cap,
        sleeve_budget_snapshot=sleeve_budget,
    )
    governor_budget_reason_codes = _normalize_reason_list(list(governor_budget_reason_codes) + list(budget_reason_codes))

    governor_hard_block_reason_codes: list[str] = []
    if sleeve_budget.get("allow_new_risk") is False:
        governor_hard_block_reason_codes.append("GOVERNOR_ALLOW_NEW_RISK_FALSE")
    governor_hard_blocked = bool(governor_hard_block_reason_codes)

    requested_budget_value = float(requested_budget or 0.0)
    applied_budget = 0.0 if governor_hard_blocked else requested_budget_value
    target_exposure = requested_budget_value if requested_budget is not None else None

    selected_count, target_selected_count_source = _pick_target_selected_count(
        etf_beta=etf_beta,
        effective_state_5=state_5,
        slot_cap=slot_cap,
        target_selected_count=target_selected_count,
        sleeve_budget_snapshot=sleeve_budget,
        trans_up_single_seat_core_recovery=trans_up_single_seat_core_recovery,
    )
    if governor_hard_blocked:
        selected_count = 0
        target_selected_count_source = "governor_hard_block"

    min_deployable_exposure, min_deployable_exposure_source = _pick_min_deployable_exposure(
        etf_beta=etf_beta,
        effective_state_5=state_5,
        target_exposure=target_exposure,
        target_selected_count=max(selected_count, 1),
        sleeve_budget_snapshot=sleeve_budget,
    )
    fallback_allowed, fallback_allowed_source = _pick_fallback_allowed(
        etf_beta=etf_beta,
        effective_state_5=state_5,
        sleeve_budget_snapshot=sleeve_budget,
    )

    equity_core_bucket_map = _normalize_state_float_map(etf_beta.get("equity_core_bucket_by_state_5"))
    defense_tilt_bucket_map = _normalize_state_float_map(etf_beta.get("defense_tilt_bucket_by_state_5"))
    cash_buffer_bucket_map = _normalize_state_float_map(etf_beta.get("cash_buffer_bucket_by_state_5"))
    equity_core_bucket = float(equity_core_bucket_map.get(state_5, 0.0))
    defense_tilt_bucket = float(defense_tilt_bucket_map.get(state_5, 0.0))
    cash_buffer_bucket = float(cash_buffer_bucket_map.get(state_5, 0.0))

    core_accumulator_symbols = _normalize_symbol_list(etf_beta.get("core_accumulator_symbols"))
    tactical_satellite_symbols = _normalize_symbol_list(etf_beta.get("tactical_satellite_symbols"))
    limited_defense_symbols = _normalize_symbol_list(etf_beta.get("limited_defense_candidates"))
    symbol_role_map = {
        str(symbol).strip().upper(): str(role).strip()
        for symbol, role in dict(etf_beta.get("symbol_role_map") or {}).items()
        if str(symbol).strip() and str(role).strip()
    }

    equity_core_template_weights = _resolve_phase1_equity_template(
        etf_beta.get("equity_core_template_weights"),
        effective_state_5=state_5,
        tilt_limits=dict(etf_beta.get("equity_core_tilt_limits") or {}),
    )
    equity_core_tilt_limits = _normalize_symbol_float_map(etf_beta.get("equity_core_tilt_limits")) or dict(CN_ETF_PHASE1_EQUITY_TILT_LIMITS)
    defense_asset_weights = _resolve_phase1_defense_template(etf_beta.get("defense_asset_weights"))
    weak_state_defense_policy = _resolve_weak_state_defense_policy(
        etf_beta=etf_beta,
        effective_state_5=state_5,
        limited_defense_symbols=limited_defense_symbols,
    )
    weak_state_defense_policy_id = str(weak_state_defense_policy.get("policy_id") or "").strip() or None
    weak_state_defense_policy_active = bool(weak_state_defense_policy.get("active", False))
    weak_state_defense_candidate_symbols = [
        str(symbol).strip().upper()
        for symbol in list(weak_state_defense_policy.get("candidate_symbols") or [])
        if str(symbol).strip()
    ]
    weak_state_target_weights_by_state_5 = {
        state_5: dict(symbol_weights)
        for state_5, symbol_weights in dict(weak_state_defense_policy.get("target_weights_by_state_5") or {}).items()
    }
    weak_state_active_target_weights = {
        str(symbol).strip().upper(): float(weight)
        for symbol, weight in dict(weak_state_defense_policy.get("active_target_weights") or {}).items()
        if str(symbol).strip() and float(weight) > 0.0
    }
    weak_state_defense_allow_core_beta = bool(weak_state_defense_policy.get("allow_core_beta", False))
    weak_state_defense_unavailable_reason_codes = [
        str(code).strip()
        for code in list(weak_state_defense_policy.get("unavailable_reason_codes") or [])
        if str(code).strip()
    ]

    core_weight_share = _weighted_subtotal(equity_core_template_weights, core_accumulator_symbols)
    satellite_weight_share = _weighted_subtotal(equity_core_template_weights, tactical_satellite_symbols)
    strategic_floor_cap = float(applied_budget) * float(equity_core_bucket) * float(core_weight_share)
    tactical_overlay_cap = (
        float(applied_budget) * float(equity_core_bucket) * float(satellite_weight_share)
        if state_5 in {"BULL", "TRANS_UP"} and (state_5 == "BULL" or standalone_mainline_active) and not governor_hard_blocked
        else 0.0
    )
    limited_defense_cap = float(applied_budget) * float(defense_tilt_bucket)
    cash_weight = float(applied_budget) * float(cash_buffer_bucket)
    defense_weight = float(limited_defense_cap)
    if trans_up_single_seat_core_recovery:
        limited_defense_cap = 0.0
        defense_weight = 0.0

    bull_partial_overlay_pace_ratio = _safe_float(etf_beta.get("bull_partial_overlay_pace_ratio")) if state_5 == "BULL" and tactical_overlay_cap > 1e-12 else None
    bull_pace_mode = _bull_pace_mode(
        effective_state_5=state_5,
        tactical_overlay_cap=tactical_overlay_cap,
        bull_partial_overlay_pace_ratio=float(bull_partial_overlay_pace_ratio or 0.0),
        hard_blocked=governor_hard_blocked,
    )
    deployment_pace = _deployment_pace_for_state(
        effective_state_5=state_5,
        strategic_floor_cap=strategic_floor_cap,
        tactical_overlay_cap=tactical_overlay_cap,
        bull_partial_overlay_pace_ratio=float(bull_partial_overlay_pace_ratio or 0.0),
        target_exposure=float(target_exposure or 0.0),
        min_deployable_exposure=float(min_deployable_exposure or 0.0),
        standalone_mainline_active=standalone_mainline_active,
        hard_blocked=governor_hard_blocked,
    )
    pace_policy_gap = max(0.0, float(target_exposure or 0.0) - float(deployment_pace))
    pace_policy_mode = _pace_policy_mode(
        effective_state_5=state_5,
        target_exposure=float(target_exposure or 0.0),
        deployment_pace=float(deployment_pace),
        bull_pace_mode=bull_pace_mode,
    ) if target_exposure is not None else None
    pace_policy_reason_code = _pace_policy_reason_code(
        effective_state_5=state_5,
        target_exposure=float(target_exposure or 0.0),
        deployment_pace=float(deployment_pace),
        bull_pace_mode=bull_pace_mode,
    ) if target_exposure is not None else None

    layering_band, layering_active, layering_reason_codes = _derive_layering_semantics(
        exposure_policy_family=exposure_policy_family,
        layering_policy=layering_policy,
        effective_state_5=state_5,
        target_exposure=target_exposure,
    )

    local_boundary_reason_codes: list[str] = []
    if governor_hard_blocked:
        local_boundary_state = "GOVERNOR_HARD_BLOCK"
        local_boundary_reason_codes.extend(governor_hard_block_reason_codes)
    elif state_5 in {"TRANS_DOWN", "RISK_OFF"}:
        local_boundary_state = "REDUCED_ALLOCATION"
        if formal_stabilizer_active:
            local_boundary_reason_codes.append("PHASE1_DOCUMENT_REDUCED_ALLOCATION")
        else:
            local_boundary_reason_codes.append(f"{state_5}_REDUCED_ALLOCATION")
    else:
        local_boundary_state = "ACTIVE"
    if trans_up_single_seat_core_recovery:
        local_boundary_reason_codes.append("TRANS_UP_SINGLE_SEAT_CORE_RECOVERY")
    local_boundary_reason_codes = _normalize_reason_list(local_boundary_reason_codes)

    targets: dict[str, float] = {}
    targets.update(_allocate_bucket(budget=strategic_floor_cap, weights=equity_core_template_weights, symbols=core_accumulator_symbols))
    if tactical_overlay_cap > 1e-12:
        for symbol, value in _allocate_bucket(budget=tactical_overlay_cap, weights=equity_core_template_weights, symbols=tactical_satellite_symbols).items():
            targets[symbol] = float(targets.get(symbol, 0.0)) + float(value)
    if limited_defense_cap > 1e-12:
        for symbol, value in _allocate_bucket(budget=limited_defense_cap, weights=defense_asset_weights, symbols=limited_defense_symbols).items():
            targets[symbol] = float(targets.get(symbol, 0.0)) + float(value)

    if trans_up_single_seat_core_recovery:
        targets = {symbol: value for symbol, value in targets.items() if symbol_role_map.get(symbol) == "core_accumulator"}
    elif state_5 in {"TRANS_DOWN", "RISK_OFF"}:
        targets = {symbol: value for symbol, value in targets.items() if symbol_role_map.get(symbol) != "tactical_satellite"}

    weak_state_defense_deployability_floor_applied = False
    if weak_state_defense_policy_active and not governor_hard_blocked and float(target_exposure or 0.0) > 1e-12:
        if weak_state_active_target_weights:
            weak_state_defense_symbols = [
                symbol
                for symbol in weak_state_active_target_weights
                if symbol not in set(core_accumulator_symbols)
            ]
            strategic_floor_cap = float(target_exposure or 0.0) * _weighted_subtotal(
                weak_state_active_target_weights,
                core_accumulator_symbols,
            )
            tactical_overlay_cap = 0.0
            limited_defense_cap = float(target_exposure or 0.0) * _weighted_subtotal(
                weak_state_active_target_weights,
                weak_state_defense_symbols,
            )
            defense_weight = float(limited_defense_cap)
            targets = {
                symbol: float(target_exposure or 0.0) * float(weight)
                for symbol, weight in weak_state_active_target_weights.items()
                if float(weight) > 1e-12
            }
            cash_weight = max(0.0, float(applied_budget) - float(sum(targets.values())))
        elif state_5 == "RISK_OFF":
            if weak_state_defense_candidate_symbols:
                strategic_floor_cap = 0.0
                tactical_overlay_cap = 0.0
                limited_defense_cap = float(target_exposure or 0.0)
                defense_weight = float(limited_defense_cap)
                cash_weight = 0.0
                targets = _allocate_bucket(
                    budget=float(target_exposure or 0.0),
                    weights=defense_asset_weights,
                    symbols=weak_state_defense_candidate_symbols,
                )
        elif state_5 == "TRANS_DOWN":
            allowed_symbols = set(core_accumulator_symbols)
            if weak_state_defense_candidate_symbols:
                allowed_symbols.update(weak_state_defense_candidate_symbols)
            elif not weak_state_defense_allow_core_beta:
                targets = {}
            targets = {
                symbol: value
                for symbol, value in targets.items()
                if symbol in allowed_symbols
            }

    positive_target_symbols = [
        symbol
        for symbol, value in targets.items()
        if str(symbol).strip() and float(value) > 1e-12
    ]
    if (
        weak_state_defense_policy_active
        and float(target_exposure or 0.0) > 1e-12
        and positive_target_symbols
    ):
        desired_selected_count = max(
            int(selected_count),
            int(weak_state_defense_policy.get("min_seats") or 0),
            len(positive_target_symbols),
        )
        weak_state_defense_deployability_floor_applied = desired_selected_count > int(selected_count)
        if desired_selected_count > int(selected_count):
            selected_count = int(desired_selected_count)
            target_selected_count_source = f"weak_state_defense_policy::{state_5}"

    if target_selected_count_source in {"fallback_default", "max_selected_symbols"} and not trans_up_single_seat_core_recovery:
        selected_count = max(selected_count, len([symbol for symbol, value in targets.items() if float(value) > 1e-12]))

    reason_codes = ["PHASE1_ALLOCATION_ENGINE::THREE_BUCKET", "STRATEGIC_BETA_STABILIZER::THREE_BUCKET", f"STATE_5::{state_5}"]
    if pace_policy_reason_code:
        reason_codes.append(pace_policy_reason_code)
    if governor_hard_blocked:
        reason_codes.extend(governor_hard_block_reason_codes)
    if weak_state_defense_policy_active:
        reason_codes.append("ETF_BETA_WEAK_STATE_DEFENSE_POLICY_ACTIVE")
        if weak_state_defense_allow_core_beta:
            reason_codes.append("ETF_BETA_WEAK_STATE_ALLOW_CORE_BETA")
        if weak_state_defense_deployability_floor_applied:
            reason_codes.append("ETF_BETA_WEAK_STATE_DEFENSE_SEAT_FLOOR_ACTIVE")
    reason_codes.extend(list(weak_state_defense_unavailable_reason_codes))
    minimum_defense_exposure_floor = float(limited_defense_cap) if state_5 in {"TRANS_DOWN", "RISK_OFF"} else 0.0

    return {
        "effective_state_5": state_5,
        "strategy_role": strategy_role,
        "governor_boundary_mode": governor_boundary_mode,
        "local_policy_mode": local_policy_mode,
        "boundary_policy_mode": boundary_policy_mode,
        "exposure_policy_family": exposure_policy_family,
        "policy_scope": policy_scope,
        "broad_based_only": broad_based_only,
        "layering_policy": layering_policy,
        "controlled_accumulation_mode": controlled_accumulation_mode,
        "layering_band": layering_band,
        "layering_active": layering_active,
        "layering_reason_codes": list(layering_reason_codes),
        "requested_budget": float(requested_budget_value),
        "applied_budget": float(applied_budget),
        "target_exposure": target_exposure,
        "target_exposure_source": target_exposure_source,
        "min_deployable_exposure": min_deployable_exposure,
        "min_deployable_exposure_source": min_deployable_exposure_source,
        "target_selected_count": int(selected_count),
        "target_selected_count_source": target_selected_count_source,
        "fallback_allowed": bool(fallback_allowed),
        "fallback_allowed_source": fallback_allowed_source,
        "weak_state_defense_policy_id": weak_state_defense_policy_id,
        "weak_state_defense_policy_active": weak_state_defense_policy_active,
        "weak_state_defense_candidate_symbols": list(weak_state_defense_candidate_symbols),
        "weak_state_defense_allow_core_beta": weak_state_defense_allow_core_beta,
        "weak_state_target_weights_by_state_5": weak_state_target_weights_by_state_5,
        "weak_state_active_target_weights": weak_state_active_target_weights,
        "weak_state_defense_deployability_floor_applied": weak_state_defense_deployability_floor_applied,
        "weak_state_defense_unavailable_reason_codes": list(weak_state_defense_unavailable_reason_codes),
        "target_exposure_by_state_5": _normalize_state_float_map(etf_beta.get("target_exposure_by_state_5")),
        "min_deployable_exposure_by_state_5": _normalize_state_float_map(etf_beta.get("min_deployable_exposure_by_state_5")),
        "target_selected_count_by_state_5": _normalize_state_int_map(etf_beta.get("target_selected_count_by_state_5")),
        "fallback_allowed_by_state_5": _normalize_state_bool_map(etf_beta.get("fallback_allowed_by_state_5")),
        "equity_core_bucket": equity_core_bucket,
        "defense_tilt_bucket": defense_tilt_bucket,
        "cash_buffer_bucket": cash_buffer_bucket,
        "equity_core_bucket_by_state_5": equity_core_bucket_map,
        "defense_tilt_bucket_by_state_5": defense_tilt_bucket_map,
        "cash_buffer_bucket_by_state_5": cash_buffer_bucket_map,
        "equity_core_template_weights": equity_core_template_weights,
        "equity_core_tilt_limits": equity_core_tilt_limits,
        "defense_asset_weights": defense_asset_weights,
        "cash_weight": cash_weight,
        "defense_weight": defense_weight,
        "targets": targets,
        "strategic_floor_cap": float(strategic_floor_cap),
        "tactical_overlay_cap": float(tactical_overlay_cap),
        "limited_defense_cap": float(limited_defense_cap),
        "minimum_defense_exposure_floor": float(minimum_defense_exposure_floor),
        "deployment_pace": float(deployment_pace),
        "bull_partial_overlay_pace_ratio": bull_partial_overlay_pace_ratio,
        "bull_pace_mode": bull_pace_mode,
        "pace_policy_gap": float(pace_policy_gap),
        "pace_policy_reason_code": pace_policy_reason_code,
        "pace_policy_mode": pace_policy_mode,
        "hard_block_flags": list(governor_hard_block_reason_codes),
        "governor_hard_blocked": governor_hard_blocked,
        "governor_hard_block_reason_codes": list(governor_hard_block_reason_codes),
        "governor_budget_reason_codes": list(governor_budget_reason_codes),
        "local_boundary_state": local_boundary_state,
        "local_boundary_reason_codes": local_boundary_reason_codes,
        "core_accumulator_symbols": list(core_accumulator_symbols),
        "tactical_satellite_symbols": list(tactical_satellite_symbols),
        "limited_defense_symbols": list(limited_defense_symbols),
        "symbol_role_map": symbol_role_map,
        "trans_up_contract_mode": trans_up_contract_mode,
        "trans_up_single_seat_core_recovery": trans_up_single_seat_core_recovery,
        "reason_codes": _normalize_reason_list(reason_codes),
    }


__all__ = ["resolve_etf_beta_exposure_semantics"]
