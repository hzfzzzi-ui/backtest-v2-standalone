from __future__ import annotations

from typing import Any, Mapping

from backend.api.shared.json_utils import sanitize_json
from backend.core.config.etf_beta_contract import (
    build_etf_beta_formal_view,
    build_etf_beta_research_view,
    resolve_etf_beta_exposure_semantics as resolve_cn_etf_beta_exposure_semantics,
)


def _safe_float(value: Any, *, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return fallback
    if out != out:
        return fallback
    return out


def _safe_float_or_none(value: Any) -> float | None:
    out = _safe_float(value, fallback=float("nan"))
    if out != out:
        return None
    return out


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


def _resolve_etf_gap_breakdown(
    *,
    target_exposure: Any,
    deployment_pace: Any,
    actual_exposure: Any,
    execution_path: str,
) -> dict[str, Any]:
    target_value = _safe_float_or_none(target_exposure)
    if target_value is None or float(target_value) <= 0.0:
        return {
            "rebalance_timing_gap": 0.0,
            "rebalance_timing_reason_code": "",
            "execution_residual_gap": 0.0,
            "gap_primary_owner": "",
        }
    target_value = max(float(target_value), 0.0)
    pace_value = min(max(float(_safe_float_or_none(deployment_pace) or 0.0), 0.0), float(target_value))
    actual_value = max(float(_safe_float(actual_exposure, fallback=0.0) or 0.0), 0.0)
    policy_gap = max(float(target_value) - float(pace_value), 0.0)
    timing_gap = 0.0
    timing_reason_code = ""
    if str(execution_path or "").strip() == "hold_until_rebalance" and float(pace_value) > float(actual_value):
        timing_gap = max(float(pace_value) - float(actual_value), 0.0)
        if timing_gap > 0.0:
            timing_reason_code = "ETF_BETA_REBALANCE_TIMING_GAP"
    residual_gap = max(float(pace_value) - float(actual_value) - float(timing_gap), 0.0)
    if policy_gap > 1e-12:
        primary_owner = "pace_policy"
    elif timing_gap > 1e-12:
        primary_owner = "rebalance_timing"
    elif residual_gap > 1e-12:
        primary_owner = "execution_residual"
    else:
        primary_owner = ""
    return {
        "rebalance_timing_gap": float(timing_gap),
        "rebalance_timing_reason_code": timing_reason_code,
        "execution_residual_gap": float(residual_gap),
        "gap_primary_owner": primary_owner,
    }


def resolve_cn_etf_exposure_semantics(
    *,
    request: Any,
    nav: float,
    market_value: float,
    pos_values: list[tuple[str, float]],
    controls: Mapping[str, Any],
) -> dict[str, Any]:
    governed_contract = (
        dict(getattr(request, "governed_a_share", {}) or {})
        if isinstance(getattr(request, "governed_a_share", None), dict)
        else {}
    )
    etf_beta_contract = dict(governed_contract.get("etf_beta") or {})
    symbol_role_map = {
        _normalize_cn_etf_symbol_key(symbol): str(role).strip()
        for symbol, role in dict(etf_beta_contract.get("symbol_role_map") or {}).items()
        if _normalize_cn_etf_symbol_key(symbol) and str(role).strip()
    }
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
    actual_core_value = 0.0
    actual_satellite_value = 0.0
    actual_defense_value = 0.0
    for symbol, value in list(pos_values or ()):
        normalized = _normalize_cn_etf_symbol_key(symbol)
        value_float = _safe_float(value, fallback=float("nan"))
        if not normalized or value_float != value_float or value_float <= 0.0:
            continue
        role = symbol_role_map.get(normalized)
        if fallback_symbol and normalized == fallback_symbol:
            actual_fallback_value += float(value_float)
        elif normalized in risk_scope:
            actual_risk_value += float(value_float)
        else:
            actual_other_value += float(value_float)
        if role == "core_accumulator":
            actual_core_value += float(value_float)
        elif role == "tactical_satellite":
            actual_satellite_value += float(value_float)
        elif role == "limited_defense":
            actual_defense_value += float(value_float)
    actual_exposure = float(market_value / nav) if nav > 0.0 else 0.0
    actual_risk_exposure = float(actual_risk_value / nav) if nav > 0.0 else 0.0
    actual_fallback_exposure = float(actual_fallback_value / nav) if nav > 0.0 else 0.0
    actual_other_exposure = float(actual_other_value / nav) if nav > 0.0 else 0.0
    actual_core_exposure = float(actual_core_value / nav) if nav > 0.0 else 0.0
    actual_satellite_exposure = float(actual_satellite_value / nav) if nav > 0.0 else 0.0
    actual_defense_exposure = float(actual_defense_value / nav) if nav > 0.0 else 0.0
    etf_budget_roles_contract_version = ""
    etf_budget_roles_effective_state_5 = ""
    target_defense_budget = 0.0
    target_core_beta_budget = 0.0
    target_alpha_budget = 0.0
    actual_defense_budget = float(actual_defense_exposure)
    actual_core_beta_budget = float(actual_core_exposure)
    actual_alpha_budget = max(0.0, float(actual_exposure) - float(actual_defense_budget) - float(actual_core_beta_budget))
    defense_budget_gap = 0.0
    core_beta_budget_gap = 0.0
    alpha_budget_gap = 0.0
    governor_budget = {}
    raw_governor = controls.get("governor_budget")
    if isinstance(raw_governor, Mapping):
        governor_budget = dict(raw_governor)
    etf_budget_roles = dict(governor_budget.get("etf_budget_roles") or {})
    etf_budget_roles_target = dict(etf_budget_roles.get("target") or {})
    etf_budget_roles_actual = dict(etf_budget_roles.get("actual") or {})
    etf_budget_roles_deviation = dict(etf_budget_roles.get("deviation") or {})
    etf_budget_roles_contract_version = str(etf_budget_roles.get("contract_version") or "").strip()
    etf_budget_roles_effective_state_5 = str(etf_budget_roles.get("effective_state_5") or "").strip()
    target_defense_budget = _safe_float(etf_budget_roles_target.get("defense"), fallback=float("nan"))
    if target_defense_budget != target_defense_budget:
        target_defense_budget = _safe_float(exposure_semantics.get("limited_defense_cap"), fallback=0.0)
    target_core_beta_budget = _safe_float(etf_budget_roles_target.get("core_beta"), fallback=float("nan"))
    if target_core_beta_budget != target_core_beta_budget:
        target_core_beta_budget = max(0.0, _safe_float(target_exposure, fallback=0.0) - target_defense_budget)
    target_alpha_budget = _safe_float(etf_budget_roles_target.get("alpha"), fallback=float("nan"))
    if target_alpha_budget != target_alpha_budget:
        target_alpha_budget = max(0.0, _safe_float(etf_budget_roles_target.get("alpha"), fallback=0.0))
    actual_defense_budget = _safe_float(etf_budget_roles_actual.get("defense"), fallback=float("nan"))
    if actual_defense_budget != actual_defense_budget:
        actual_defense_budget = float(actual_defense_exposure)
    actual_core_beta_budget = _safe_float(etf_budget_roles_actual.get("core_beta"), fallback=float("nan"))
    if actual_core_beta_budget != actual_core_beta_budget:
        actual_core_beta_budget = float(actual_core_exposure)
    actual_alpha_budget = _safe_float(etf_budget_roles_actual.get("alpha"), fallback=float("nan"))
    if actual_alpha_budget != actual_alpha_budget:
        actual_alpha_budget = max(0.0, float(actual_exposure) - float(actual_defense_budget) - float(actual_core_beta_budget))
    defense_budget_gap = _safe_float(etf_budget_roles_deviation.get("defense_gap"), fallback=float("nan"))
    if defense_budget_gap != defense_budget_gap:
        defense_budget_gap = float(target_defense_budget - actual_defense_budget)
    core_beta_budget_gap = _safe_float(etf_budget_roles_deviation.get("core_beta_gap"), fallback=float("nan"))
    if core_beta_budget_gap != core_beta_budget_gap:
        core_beta_budget_gap = float(target_core_beta_budget - actual_core_beta_budget)
    alpha_budget_gap = _safe_float(etf_budget_roles_deviation.get("alpha_gap"), fallback=float("nan"))
    if alpha_budget_gap != alpha_budget_gap:
        alpha_budget_gap = float(target_alpha_budget - actual_alpha_budget)
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
        "actual_core_exposure": float(actual_core_exposure),
        "actual_satellite_exposure": float(actual_satellite_exposure),
        "actual_defense_exposure": float(actual_defense_exposure),
        "target_defense_budget": float(target_defense_budget),
        "target_core_beta_budget": float(target_core_beta_budget),
        "target_alpha_budget": float(target_alpha_budget),
        "actual_defense_budget": float(actual_defense_budget),
        "actual_core_beta_budget": float(actual_core_beta_budget),
        "actual_alpha_budget": float(actual_alpha_budget),
        "defense_budget_gap": float(defense_budget_gap),
        "core_beta_budget_gap": float(core_beta_budget_gap),
        "alpha_budget_gap": float(alpha_budget_gap),
        "strategic_floor_cap": _safe_float(exposure_semantics.get("strategic_floor_cap"), fallback=0.0),
        "tactical_overlay_cap": _safe_float(exposure_semantics.get("tactical_overlay_cap"), fallback=0.0),
        "limited_defense_cap": _safe_float(exposure_semantics.get("limited_defense_cap"), fallback=0.0),
        "deployment_pace": _safe_float(exposure_semantics.get("deployment_pace"), fallback=0.0),
        "hard_block_flags": list(exposure_semantics.get("hard_block_flags") or []),
        "deployability_gap": float(deployability_gap),
    }


def build_cn_etf_daily_diagnostics_updates(
    *,
    request: Any,
    daily_row: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    row_governor_payload: Mapping[str, Any],
    deploy_target_count: int,
) -> dict[str, Any]:
    governed_contract = (
        dict(getattr(request, "governed_a_share", {}) or {})
        if isinstance(getattr(request, "governed_a_share", None), dict)
        else {}
    )
    etf_beta_contract = dict(governed_contract.get("etf_beta") or {})
    total_exposure_cap = None
    raw_total_exposure_cap = row_governor_payload.get("total_exposure_cap")
    if raw_total_exposure_cap not in (None, ""):
        total_exposure_cap = _safe_float(raw_total_exposure_cap, fallback=float("nan"))
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
    actual_exposure = _safe_float(daily_row.get("etf_actual_exposure"), fallback=0.0)
    actual_risk_exposure = _safe_float(daily_row.get("etf_actual_risk_exposure"), fallback=0.0)
    actual_fallback_exposure = _safe_float(daily_row.get("etf_actual_fallback_exposure"), fallback=0.0)
    actual_other_exposure = _safe_float(daily_row.get("etf_actual_other_exposure"), fallback=0.0)
    actual_core_exposure = _safe_float(daily_row.get("etf_actual_core_exposure"), fallback=0.0)
    actual_satellite_exposure = _safe_float(daily_row.get("etf_actual_satellite_exposure"), fallback=0.0)
    actual_defense_exposure = _safe_float(daily_row.get("etf_actual_defense_exposure"), fallback=0.0)
    target_exposure = exposure_semantics.get("target_exposure")
    min_deployable_exposure = exposure_semantics.get("min_deployable_exposure")
    target_exposure_source = exposure_semantics.get("target_exposure_source")
    min_deployable_exposure_source = exposure_semantics.get("min_deployable_exposure_source")
    strategic_floor_cap = _safe_float_or_none(exposure_semantics.get("strategic_floor_cap"))
    tactical_overlay_cap = _safe_float_or_none(exposure_semantics.get("tactical_overlay_cap"))
    limited_defense_cap = _safe_float_or_none(exposure_semantics.get("limited_defense_cap"))
    deployment_pace = _safe_float_or_none(exposure_semantics.get("deployment_pace"))
    bull_partial_overlay_pace_ratio = _safe_float_or_none(diagnostics.get("etf_beta_bull_partial_overlay_pace_ratio"))
    if bull_partial_overlay_pace_ratio is None:
        bull_partial_overlay_pace_ratio = _safe_float_or_none(exposure_semantics.get("bull_partial_overlay_pace_ratio"))
    bull_pace_mode = str(diagnostics.get("etf_beta_bull_pace_mode") or exposure_semantics.get("bull_pace_mode") or "").strip()
    trans_up_contract_mode = str(
        diagnostics.get("etf_beta_trans_up_contract_mode") or exposure_semantics.get("trans_up_contract_mode") or ""
    ).strip()
    trans_up_single_seat_core_recovery = bool(
        diagnostics.get("etf_beta_trans_up_single_seat_core_recovery")
        if diagnostics.get("etf_beta_trans_up_single_seat_core_recovery") is not None
        else exposure_semantics.get("trans_up_single_seat_core_recovery", False)
    )
    hard_block_flags = [
        str(code).strip()
        for code in list(exposure_semantics.get("hard_block_flags") or ())
        if str(code).strip()
    ]
    deployability_gap = max(float(target_exposure or 0.0) - float(actual_exposure or 0.0), 0.0)
    execution_path = str(diagnostics.get("etf_beta_execution_path") or "").strip()
    trans_up_redeploy_active = bool(diagnostics.get("etf_beta_trans_up_redeploy_active", False))
    trans_up_redeploy_reason_code = str(diagnostics.get("etf_beta_trans_up_redeploy_reason_code") or "").strip()
    trans_up_redeploy_reject_reason = str(diagnostics.get("etf_beta_trans_up_redeploy_reject_reason") or "").strip()
    trans_up_redeploy_floor_gap = _safe_float_or_none(diagnostics.get("etf_beta_trans_up_redeploy_floor_gap"))
    trans_up_redeploy_edge_from_state = str(diagnostics.get("etf_beta_trans_up_redeploy_edge_from_state") or "").strip()
    weak_state_inter_redeploy_active = bool(
        diagnostics.get("etf_beta_weak_state_inter_rebalance_defense_redeploy_active", False)
    )
    weak_state_inter_redeploy_reason_code = str(
        diagnostics.get("etf_beta_weak_state_inter_rebalance_defense_redeploy_reason_code") or ""
    ).strip()
    weak_state_inter_redeploy_reject_reason = str(
        diagnostics.get("etf_beta_weak_state_inter_rebalance_defense_redeploy_reject_reason") or ""
    ).strip()
    weak_state_inter_redeploy_symbols = [
        str(item).strip().upper()
        for item in list(diagnostics.get("etf_beta_weak_state_inter_rebalance_defense_redeploy_symbols") or ())
        if str(item).strip()
    ]
    weak_state_inter_redeploy_current_symbols = [
        str(item).strip().upper()
        for item in list(diagnostics.get("etf_beta_weak_state_inter_rebalance_defense_current_symbols") or ())
        if str(item).strip()
    ]
    weak_state_inter_redeploy_posture_satisfied = bool(
        diagnostics.get("etf_beta_weak_state_inter_rebalance_defense_posture_satisfied", False)
    )
    state_edge_cash_release_active = bool(diagnostics.get("etf_beta_state_edge_cash_release_active", False))
    state_edge_cash_release_reason_code = str(diagnostics.get("etf_beta_state_edge_cash_release_reason_code") or "").strip()
    state_edge_cash_release_reject_reason = str(
        diagnostics.get("etf_beta_state_edge_cash_release_reject_reason") or ""
    ).strip()
    state_edge_cash_release_edge_from_state = str(
        diagnostics.get("etf_beta_state_edge_cash_release_edge_from_state") or ""
    ).strip()
    state_edge_cash_release_edge_to_state = str(
        diagnostics.get("etf_beta_state_edge_cash_release_edge_to_state") or ""
    ).strip()
    state_edge_cash_release_release_destination = str(
        diagnostics.get("etf_beta_state_edge_cash_release_release_destination") or ""
    ).strip()
    state_edge_cash_release_release_target_cash = _safe_float_or_none(
        diagnostics.get("etf_beta_state_edge_cash_release_release_target_cash")
    )
    state_edge_cash_release_release_cash = _safe_float_or_none(
        diagnostics.get("etf_beta_state_edge_cash_release_release_cash")
    )
    state_edge_cash_release_bounded_partial_release_ratio_cap = _safe_float_or_none(
        diagnostics.get("etf_beta_state_edge_cash_release_bounded_partial_release_ratio_cap")
    )
    state_edge_cash_release_symbols = [
        str(item).strip().upper()
        for item in list(diagnostics.get("etf_beta_state_edge_cash_release_symbols") or ())
        if str(item).strip()
    ]
    riskoff_account_budget_materialization_active = bool(
        diagnostics.get("etf_beta_riskoff_account_budget_materialization_active", False)
    )
    riskoff_account_budget_materialization_reason_code = str(
        diagnostics.get("etf_beta_riskoff_account_budget_materialization_reason_code") or ""
    ).strip()
    riskoff_account_budget_materialization_reject_reason = str(
        diagnostics.get("etf_beta_riskoff_account_budget_materialization_reject_reason") or ""
    ).strip()
    riskoff_account_budget_materialization_release_destination = str(
        diagnostics.get("etf_beta_riskoff_account_budget_materialization_release_destination") or ""
    ).strip()
    riskoff_account_budget_materialization_release_target_cash = _safe_float_or_none(
        diagnostics.get("etf_beta_riskoff_account_budget_materialization_release_target_cash")
    )
    riskoff_account_budget_materialization_release_cash = _safe_float_or_none(
        diagnostics.get("etf_beta_riskoff_account_budget_materialization_release_cash")
    )
    riskoff_account_budget_materialization_bounded_partial_release_ratio_cap = _safe_float_or_none(
        diagnostics.get("etf_beta_riskoff_account_budget_materialization_bounded_partial_release_ratio_cap")
    )
    riskoff_account_budget_materialization_symbols = [
        str(item).strip().upper()
        for item in list(diagnostics.get("etf_beta_riskoff_account_budget_materialization_symbols") or ())
        if str(item).strip()
    ]
    riskoff_account_budget_materialization_target_symbols = [
        str(item).strip().upper()
        for item in list(diagnostics.get("etf_beta_riskoff_account_budget_materialization_target_symbols") or ())
        if str(item).strip()
    ]
    account_transition_handoff_active = bool(
        diagnostics.get("etf_beta_account_transition_handoff_active", False)
    )
    account_transition_handoff_transition_kind = str(
        diagnostics.get("etf_beta_account_transition_handoff_transition_kind") or ""
    ).strip()
    account_transition_handoff_consumed = bool(
        diagnostics.get("etf_beta_account_transition_handoff_consumed", False)
    )
    account_transition_handoff_reason_code = str(
        diagnostics.get("etf_beta_account_transition_handoff_reason_code") or ""
    ).strip()
    account_transition_handoff_reject_reason = str(
        diagnostics.get("etf_beta_account_transition_handoff_reject_reason") or ""
    ).strip()
    account_transition_handoff_edge_from_state = str(
        diagnostics.get("etf_beta_account_transition_handoff_edge_from_state") or ""
    ).strip()
    account_transition_handoff_edge_to_state = str(
        diagnostics.get("etf_beta_account_transition_handoff_edge_to_state") or ""
    ).strip()
    account_transition_handoff_release_destination = str(
        diagnostics.get("etf_beta_account_transition_handoff_release_destination") or ""
    ).strip()
    account_transition_handoff_reference_paths = [
        str(item).strip()
        for item in list(diagnostics.get("etf_beta_account_transition_handoff_reference_paths") or ())
        if str(item).strip()
    ]
    account_transition_execution_owner = str(
        diagnostics.get("etf_beta_account_transition_execution_owner") or ""
    ).strip()
    account_transition_execution_status = str(
        diagnostics.get("etf_beta_account_transition_execution_status") or ""
    ).strip()
    account_transition_execution_reason_code = str(
        diagnostics.get("etf_beta_account_transition_execution_reason_code") or ""
    ).strip()
    account_transition_execution_reject_reason = str(
        diagnostics.get("etf_beta_account_transition_execution_reject_reason") or ""
    ).strip()
    account_transition_execution_reference_paths = [
        str(item).strip()
        for item in list(diagnostics.get("etf_beta_account_transition_execution_reference_paths") or ())
        if str(item).strip()
    ]
    pace_policy_gap = _safe_float_or_none(diagnostics.get("etf_beta_pace_policy_gap"))
    if pace_policy_gap is None:
        pace_policy_gap = _safe_float_or_none(exposure_semantics.get("pace_policy_gap"))
    pace_policy_reason_code = str(
        diagnostics.get("etf_beta_pace_policy_reason_code") or exposure_semantics.get("pace_policy_reason_code") or ""
    ).strip()
    gap_breakdown = _resolve_etf_gap_breakdown(
        target_exposure=target_exposure,
        deployment_pace=deployment_pace,
        actual_exposure=actual_exposure,
        execution_path=execution_path,
    )
    rebalance_timing_gap = _safe_float_or_none(gap_breakdown.get("rebalance_timing_gap"))
    rebalance_timing_reason_code = str(gap_breakdown.get("rebalance_timing_reason_code") or "").strip()
    execution_residual_gap = _safe_float_or_none(gap_breakdown.get("execution_residual_gap"))
    gap_primary_owner = str(gap_breakdown.get("gap_primary_owner") or "").strip()
    provider_formal_view = dict(diagnostics.get("etf_beta_formal_view") or {})
    provider_research_view = dict(diagnostics.get("etf_beta_research_view") or {})
    formal_view_source = provider_formal_view or exposure_semantics
    research_view_source = provider_research_view or exposure_semantics
    payload_contract_version = str(locals().get("etf_budget_roles_contract_version") or "")
    payload_effective_state_5 = str(locals().get("etf_budget_roles_effective_state_5") or "")
    payload_target_defense_budget = float(locals().get("target_defense_budget") or 0.0)
    payload_target_core_beta_budget = float(locals().get("target_core_beta_budget") or 0.0)
    payload_target_alpha_budget = float(locals().get("target_alpha_budget") or 0.0)
    payload_actual_defense_budget = float(locals().get("actual_defense_budget") or 0.0)
    payload_actual_core_beta_budget = float(locals().get("actual_core_beta_budget") or 0.0)
    payload_actual_alpha_budget = float(locals().get("actual_alpha_budget") or 0.0)
    payload_defense_budget_gap = float(locals().get("defense_budget_gap") or 0.0)
    payload_core_beta_budget_gap = float(locals().get("core_beta_budget_gap") or 0.0)
    payload_alpha_budget_gap = float(locals().get("alpha_budget_gap") or 0.0)
    etf_budget_roles_payload = sanitize_json(
        {
            "contract_version": payload_contract_version or "etf_defense_core_beta_budgets@1",
            "effective_state_5": payload_effective_state_5 or None,
            "target": {
                "defense": payload_target_defense_budget,
                "core_beta": payload_target_core_beta_budget,
                "alpha": payload_target_alpha_budget,
            },
            "actual": {
                "defense": payload_actual_defense_budget,
                "core_beta": payload_actual_core_beta_budget,
                "alpha": payload_actual_alpha_budget,
            },
            "deviation": {
                "defense_gap": payload_defense_budget_gap,
                "core_beta_gap": payload_core_beta_budget_gap,
                "alpha_gap": payload_alpha_budget_gap,
            },
        }
    )
    formal_view_payload = build_etf_beta_formal_view(
        formal_view_source,
        extra={
            "actual_exposure": float(actual_exposure or 0.0),
            "actual_risk_exposure": float(actual_risk_exposure or 0.0),
            "actual_fallback_exposure": float(actual_fallback_exposure or 0.0),
            "actual_other_exposure": float(actual_other_exposure or 0.0),
            "actual_core_exposure": float(actual_core_exposure or 0.0),
            "actual_satellite_exposure": float(actual_satellite_exposure or 0.0),
            "actual_defense_exposure": float(actual_defense_exposure or 0.0),
            "etf_budget_roles_contract_version": payload_contract_version or None,
            "etf_budget_roles_effective_state_5": payload_effective_state_5 or None,
            "etf_budget_roles": dict(etf_budget_roles_payload),
            "weak_state_inter_rebalance_defense_redeploy_active": bool(weak_state_inter_redeploy_active),
            "weak_state_inter_rebalance_defense_redeploy_reason_code": weak_state_inter_redeploy_reason_code or None,
            "weak_state_inter_rebalance_defense_redeploy_reject_reason": (
                weak_state_inter_redeploy_reject_reason or None
            ),
            "weak_state_inter_rebalance_defense_redeploy_symbols": list(weak_state_inter_redeploy_symbols),
            "weak_state_inter_rebalance_defense_current_symbols": list(weak_state_inter_redeploy_current_symbols),
            "weak_state_inter_rebalance_defense_posture_satisfied": bool(
                weak_state_inter_redeploy_posture_satisfied
            ),
            "state_edge_cash_release_active": bool(state_edge_cash_release_active),
            "state_edge_cash_release_reason_code": state_edge_cash_release_reason_code or None,
            "state_edge_cash_release_reject_reason": state_edge_cash_release_reject_reason or None,
            "state_edge_cash_release_edge_from_state": state_edge_cash_release_edge_from_state or None,
            "state_edge_cash_release_edge_to_state": state_edge_cash_release_edge_to_state or None,
            "state_edge_cash_release_release_destination": (
                state_edge_cash_release_release_destination or None
            ),
            "state_edge_cash_release_release_target_cash": state_edge_cash_release_release_target_cash,
            "state_edge_cash_release_release_cash": state_edge_cash_release_release_cash,
            "state_edge_cash_release_bounded_partial_release_ratio_cap": (
                state_edge_cash_release_bounded_partial_release_ratio_cap
            ),
            "state_edge_cash_release_symbols": list(state_edge_cash_release_symbols),
            "riskoff_account_budget_materialization": {
                "active": bool(riskoff_account_budget_materialization_active),
                "reason_code": riskoff_account_budget_materialization_reason_code or None,
                "reject_reason": riskoff_account_budget_materialization_reject_reason or None,
                "release_destination": riskoff_account_budget_materialization_release_destination or None,
                "release_target_cash": riskoff_account_budget_materialization_release_target_cash,
                "release_cash": riskoff_account_budget_materialization_release_cash,
                "bounded_partial_release_ratio_cap": (
                    riskoff_account_budget_materialization_bounded_partial_release_ratio_cap
                ),
                "symbols": list(riskoff_account_budget_materialization_symbols),
                "target_symbols": list(riskoff_account_budget_materialization_target_symbols),
            },
            "account_transition_handoff_consumption": {
                "active": bool(account_transition_handoff_active),
                "transition_kind": account_transition_handoff_transition_kind or None,
                "consumed": bool(account_transition_handoff_consumed),
                "reason_code": account_transition_handoff_reason_code or None,
                "reject_reason": account_transition_handoff_reject_reason or None,
                "edge_from_state": account_transition_handoff_edge_from_state or None,
                "edge_to_state": account_transition_handoff_edge_to_state or None,
                "release_destination": account_transition_handoff_release_destination or None,
                "reference_paths": list(account_transition_handoff_reference_paths),
            },
            "account_transition_execution": {
                "owner": account_transition_execution_owner or None,
                "status": account_transition_execution_status or None,
                "reason_code": account_transition_execution_reason_code or None,
                "reject_reason": account_transition_execution_reject_reason or None,
                "transition_kind": account_transition_handoff_transition_kind or None,
                "edge_from_state": account_transition_handoff_edge_from_state or None,
                "edge_to_state": account_transition_handoff_edge_to_state or None,
                "release_destination": account_transition_handoff_release_destination or None,
                "reference_paths": list(account_transition_execution_reference_paths),
            },
        },
    )
    research_view_payload = build_etf_beta_research_view(
        research_view_source,
        extra={
            "pace_policy_gap": pace_policy_gap,
            "pace_policy_reason_code": pace_policy_reason_code or None,
            "bull_partial_overlay_pace_ratio": bull_partial_overlay_pace_ratio,
            "bull_pace_mode": bull_pace_mode or None,
            "rebalance_timing_gap": rebalance_timing_gap,
            "rebalance_timing_reason_code": rebalance_timing_reason_code or None,
            "execution_residual_gap": execution_residual_gap,
            "gap_primary_owner": gap_primary_owner or None,
            "deployability_gap": float(deployability_gap or 0.0),
            "execution_path": execution_path or None,
            "trans_up_redeploy_active": bool(trans_up_redeploy_active),
            "trans_up_redeploy_reason_code": trans_up_redeploy_reason_code or None,
            "trans_up_redeploy_reject_reason": trans_up_redeploy_reject_reason or None,
            "trans_up_redeploy_floor_gap": trans_up_redeploy_floor_gap,
            "trans_up_redeploy_edge_from_state": trans_up_redeploy_edge_from_state or None,
            "actual_core_exposure": float(actual_core_exposure or 0.0),
            "actual_satellite_exposure": float(actual_satellite_exposure or 0.0),
            "actual_defense_exposure": float(actual_defense_exposure or 0.0),
            "etf_budget_roles_contract_version": payload_contract_version or None,
            "etf_budget_roles_effective_state_5": payload_effective_state_5 or None,
            "etf_budget_roles": dict(etf_budget_roles_payload),
            "weak_state_inter_rebalance_defense_redeploy_active": bool(weak_state_inter_redeploy_active),
            "weak_state_inter_rebalance_defense_redeploy_reason_code": weak_state_inter_redeploy_reason_code or None,
            "weak_state_inter_rebalance_defense_redeploy_reject_reason": (
                weak_state_inter_redeploy_reject_reason or None
            ),
            "weak_state_inter_rebalance_defense_redeploy_symbols": list(weak_state_inter_redeploy_symbols),
            "weak_state_inter_rebalance_defense_current_symbols": list(weak_state_inter_redeploy_current_symbols),
            "weak_state_inter_rebalance_defense_posture_satisfied": bool(
                weak_state_inter_redeploy_posture_satisfied
            ),
            "state_edge_cash_release_active": bool(state_edge_cash_release_active),
            "state_edge_cash_release_reason_code": state_edge_cash_release_reason_code or None,
            "state_edge_cash_release_reject_reason": state_edge_cash_release_reject_reason or None,
            "state_edge_cash_release_edge_from_state": state_edge_cash_release_edge_from_state or None,
            "state_edge_cash_release_edge_to_state": state_edge_cash_release_edge_to_state or None,
            "state_edge_cash_release_release_destination": (
                state_edge_cash_release_release_destination or None
            ),
            "state_edge_cash_release_release_target_cash": state_edge_cash_release_release_target_cash,
            "state_edge_cash_release_release_cash": state_edge_cash_release_release_cash,
            "state_edge_cash_release_bounded_partial_release_ratio_cap": (
                state_edge_cash_release_bounded_partial_release_ratio_cap
            ),
            "state_edge_cash_release_symbols": list(state_edge_cash_release_symbols),
            "riskoff_account_budget_materialization": {
                "active": bool(riskoff_account_budget_materialization_active),
                "reason_code": riskoff_account_budget_materialization_reason_code or None,
                "reject_reason": riskoff_account_budget_materialization_reject_reason or None,
                "release_destination": riskoff_account_budget_materialization_release_destination or None,
                "release_target_cash": riskoff_account_budget_materialization_release_target_cash,
                "release_cash": riskoff_account_budget_materialization_release_cash,
                "bounded_partial_release_ratio_cap": (
                    riskoff_account_budget_materialization_bounded_partial_release_ratio_cap
                ),
                "symbols": list(riskoff_account_budget_materialization_symbols),
                "target_symbols": list(riskoff_account_budget_materialization_target_symbols),
            },
            "account_transition_handoff_consumption": {
                "active": bool(account_transition_handoff_active),
                "transition_kind": account_transition_handoff_transition_kind or None,
                "consumed": bool(account_transition_handoff_consumed),
                "reason_code": account_transition_handoff_reason_code or None,
                "reject_reason": account_transition_handoff_reject_reason or None,
                "edge_from_state": account_transition_handoff_edge_from_state or None,
                "edge_to_state": account_transition_handoff_edge_to_state or None,
                "release_destination": account_transition_handoff_release_destination or None,
                "reference_paths": list(account_transition_handoff_reference_paths),
            },
            "account_transition_execution": {
                "owner": account_transition_execution_owner or None,
                "status": account_transition_execution_status or None,
                "reason_code": account_transition_execution_reason_code or None,
                "reject_reason": account_transition_execution_reject_reason or None,
                "transition_kind": account_transition_handoff_transition_kind or None,
                "edge_from_state": account_transition_handoff_edge_from_state or None,
                "edge_to_state": account_transition_handoff_edge_to_state or None,
                "release_destination": account_transition_handoff_release_destination or None,
                "reference_paths": list(account_transition_execution_reference_paths),
            },
        },
    )
    under_deploy_reason_codes = [
        str(code).strip()
        for code in list(diagnostics.get("etf_beta_under_deploy_reason_codes") or [])
        if str(code).strip()
    ]
    return {
        "daily_row_updates": {
            "etf_target_exposure": _safe_float_or_none(target_exposure),
            "etf_min_deployable_exposure": _safe_float_or_none(min_deployable_exposure),
            "etf_target_exposure_source": str(target_exposure_source or ""),
            "etf_min_deployable_exposure_source": str(min_deployable_exposure_source or ""),
            "etf_actual_exposure": float(actual_exposure or 0.0),
            "etf_actual_risk_exposure": float(actual_risk_exposure or 0.0),
            "etf_actual_fallback_exposure": float(actual_fallback_exposure or 0.0),
            "etf_actual_other_exposure": float(actual_other_exposure or 0.0),
            "etf_actual_core_exposure": float(actual_core_exposure or 0.0),
            "etf_actual_satellite_exposure": float(actual_satellite_exposure or 0.0),
            "etf_actual_defense_exposure": float(actual_defense_exposure or 0.0),
            "etf_target_defense_budget": payload_target_defense_budget,
            "etf_target_core_beta_budget": payload_target_core_beta_budget,
            "etf_target_alpha_budget": payload_target_alpha_budget,
            "etf_actual_defense_budget": payload_actual_defense_budget,
            "etf_actual_core_beta_budget": payload_actual_core_beta_budget,
            "etf_actual_alpha_budget": payload_actual_alpha_budget,
            "etf_defense_budget_gap": payload_defense_budget_gap,
            "etf_core_beta_budget_gap": payload_core_beta_budget_gap,
            "etf_alpha_budget_gap": payload_alpha_budget_gap,
        },
        "diagnostics_payload_updates": {
            "etf_beta_formal_view": dict(formal_view_payload),
            "etf_beta_research_view": dict(research_view_payload),
        },
        "etf_context": {
            "target_exposure": target_exposure,
            "min_deployable_exposure": min_deployable_exposure,
            "target_exposure_source": target_exposure_source,
            "min_deployable_exposure_source": min_deployable_exposure_source,
            "etf_budget_roles_contract_version": payload_contract_version or None,
            "etf_budget_roles_effective_state_5": payload_effective_state_5 or None,
            "etf_budget_roles": sanitize_json(
                {
                    "contract_version": payload_contract_version or "etf_defense_core_beta_budgets@1",
                    "effective_state_5": payload_effective_state_5 or None,
                    "target": {
                        "defense": payload_target_defense_budget,
                        "core_beta": payload_target_core_beta_budget,
                        "alpha": payload_target_alpha_budget,
                    },
                    "actual": {
                        "defense": payload_actual_defense_budget,
                        "core_beta": payload_actual_core_beta_budget,
                        "alpha": payload_actual_alpha_budget,
                    },
                    "deviation": {
                        "defense_gap": payload_defense_budget_gap,
                        "core_beta_gap": payload_core_beta_budget_gap,
                        "alpha_gap": payload_alpha_budget_gap,
                    },
                }
            ),
            "fallback_allowed": bool(exposure_semantics.get("fallback_allowed", False)),
            "strategic_floor_cap": strategic_floor_cap,
            "tactical_overlay_cap": tactical_overlay_cap,
            "limited_defense_cap": limited_defense_cap,
            "deployment_pace": deployment_pace,
            "pace_policy_gap": pace_policy_gap,
            "pace_policy_reason_code": pace_policy_reason_code,
            "rebalance_timing_gap": rebalance_timing_gap,
            "rebalance_timing_reason_code": rebalance_timing_reason_code,
            "execution_residual_gap": execution_residual_gap,
            "gap_primary_owner": gap_primary_owner,
            "trans_up_contract_mode": trans_up_contract_mode,
            "trans_up_single_seat_core_recovery": trans_up_single_seat_core_recovery,
            "hard_block_flags": hard_block_flags,
            "deployability_gap": float(deployability_gap or 0.0),
            "state_edge_cash_release": {
                "active": bool(state_edge_cash_release_active),
                "reason_code": state_edge_cash_release_reason_code or None,
                "reject_reason": state_edge_cash_release_reject_reason or None,
                "edge_from_state": state_edge_cash_release_edge_from_state or None,
                "edge_to_state": state_edge_cash_release_edge_to_state or None,
                "release_destination": state_edge_cash_release_release_destination or None,
                "release_target_cash": state_edge_cash_release_release_target_cash,
                "release_cash": state_edge_cash_release_release_cash,
                "bounded_partial_release_ratio_cap": state_edge_cash_release_bounded_partial_release_ratio_cap,
                "symbols": list(state_edge_cash_release_symbols),
            },
            "riskoff_account_budget_materialization": {
                "active": bool(riskoff_account_budget_materialization_active),
                "reason_code": riskoff_account_budget_materialization_reason_code or None,
                "reject_reason": riskoff_account_budget_materialization_reject_reason or None,
                "release_destination": riskoff_account_budget_materialization_release_destination or None,
                "release_target_cash": riskoff_account_budget_materialization_release_target_cash,
                "release_cash": riskoff_account_budget_materialization_release_cash,
                "bounded_partial_release_ratio_cap": (
                    riskoff_account_budget_materialization_bounded_partial_release_ratio_cap
                ),
                "symbols": list(riskoff_account_budget_materialization_symbols),
                "target_symbols": list(riskoff_account_budget_materialization_target_symbols),
            },
            "account_transition_handoff_consumption": {
                "active": bool(account_transition_handoff_active),
                "transition_kind": account_transition_handoff_transition_kind or None,
                "consumed": bool(account_transition_handoff_consumed),
                "reason_code": account_transition_handoff_reason_code or None,
                "reject_reason": account_transition_handoff_reject_reason or None,
                "edge_from_state": account_transition_handoff_edge_from_state or None,
                "edge_to_state": account_transition_handoff_edge_to_state or None,
                "release_destination": account_transition_handoff_release_destination or None,
                "reference_paths": list(account_transition_handoff_reference_paths),
            },
            "account_transition_execution": {
                "owner": account_transition_execution_owner or None,
                "status": account_transition_execution_status or None,
                "reason_code": account_transition_execution_reason_code or None,
                "reject_reason": account_transition_execution_reject_reason or None,
                "transition_kind": account_transition_handoff_transition_kind or None,
                "edge_from_state": account_transition_handoff_edge_from_state or None,
                "edge_to_state": account_transition_handoff_edge_to_state or None,
                "release_destination": account_transition_handoff_release_destination or None,
                "reference_paths": list(account_transition_execution_reference_paths),
            },
        },
        "under_deploy_reason_codes": under_deploy_reason_codes,
    }
