from __future__ import annotations

import json
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json

from .common import (
    _collect_formal_scope_violations,
    _normalize_choice,
    _normalize_optional_choice,
    _normalize_reason_list,
    _normalize_symbol_list,
    _normalize_symbol_map,
    _normalize_symbol_pairs,
    _normalize_text,
    _safe_float,
    _safe_int,
    build_etf_beta_formal_view,
    build_etf_beta_research_view,
)
from .defaults import (
    CN_ETF_BETA_ALLOCATION_ENGINE_MODE,
    CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
    CN_ETF_BETA_BUCKET_POLICY_PROFILE,
    CN_ETF_BETA_CANDIDATE_POOL_PROFILE,
    CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
    CN_ETF_BETA_FALLBACK_MODE,
    CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
    CN_ETF_BETA_LAYERING_POLICY,
    CN_ETF_BETA_LOCAL_POLICY_MODE,
    CN_ETF_BETA_POLICY_SCOPE,
    CN_ETF_BETA_REBALANCE_FREQUENCY,
    CN_ETF_BETA_RULE_FAMILY,
    CN_ETF_BETA_RS_FAST_WEIGHT,
    CN_ETF_BETA_RS_FAST_WINDOW,
    CN_ETF_BETA_RS_MID_WEIGHT,
    CN_ETF_BETA_RS_MID_WINDOW,
    CN_ETF_BETA_RS_SLOW_WEIGHT,
    CN_ETF_BETA_RS_SLOW_WINDOW,
    CN_ETF_BETA_SLEEVE_ID,
    CN_ETF_BETA_STRATEGY_ROLE,
    CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
    CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
    CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
    CN_ETF_BETA_VOL_TARGET_WINDOW,
    CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
    CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS,
    CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS,
    CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES,
    CN_ETF_FORMAL_PHASE1_POOL_VERSION,
    _FORMAL_GOVERNOR_BOUNDARY_ALLOWED,
    _FORMAL_PHASE1_SYMBOL_SCOPE,
    _FORMAL_SIGNAL_SEMANTICS_ALLOWED,
)
from .exposure_semantics import resolve_etf_beta_exposure_semantics
from .normalization import normalize_etf_beta_contract


def _normalize_symbol_reason_map(values: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not isinstance(values, dict):
        return out
    for raw_symbol, raw_codes in values.items():
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        codes = [str(code).strip() for code in list(raw_codes or ()) if str(code).strip()]
        out[symbol] = codes
    return out


def _extract_out_of_scope_symbols(evidence: dict[str, Any]) -> list[str]:
    symbols: list[str] = []
    for key, value in dict(evidence or {}).items():
        if not key.endswith("_excluded_symbols") and not key.endswith("_extra_scope_symbols"):
            continue
        for item in list(value or ()):
            symbol = str(item or "").strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
    return symbols


def _summary_source_alias(value: Any) -> Any:
    text = str(value or "").strip()
    if text == "governor_sleeve_budget":
        return "budget_snapshot"
    return value


def _is_formal_phase1_stabilizer(strategy_role: Any, local_policy_mode: Any) -> bool:
    role = str(strategy_role or "").strip()
    local_mode = str(local_policy_mode or "").strip()
    return role in {"phase1_allocation_engine", "strategic_beta_stabilizer"} and local_mode == "phase1_bucket_allocation"


def classify_etf_formal_alignment(
    *,
    input_etfs: Any,
    core_beta_symbols: Any,
    limited_defense_candidates: Any,
    fallback_mode: Any,
    fallback_symbol: Any,
    strategy_role: Any,
    governor_boundary_mode: Any,
    local_policy_mode: Any,
    source_entry_type: Any,
    research_rule_family: Any,
    absolute_filter_profile: Any,
    candidate_pool_profile: Any,
    selection_chain_profile: Any,
    controlled_accumulation_mode: Any,
    template_target_formal_symbols: Any,
    template_proxy_map: Any,
    proxy_replacement_mode: Any,
    formal_replacement_pairs: Any,
    core_slot_symbols: Any,
    growth_slot_symbols: Any,
    growth_seat_symbol: Any,
    runtime_selection_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    evidence: dict[str, Any] = {
        "reference_doc": CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
        "formal_etf_pool_version": CN_ETF_FORMAL_PHASE1_POOL_VERSION,
        "formal_phase1_core_symbols": list(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS),
        "formal_phase1_limited_defense_candidates": list(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES),
        "formal_phase1_excluded_symbols": list(CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS),
    }
    allowed_symbols = set(_FORMAL_PHASE1_SYMBOL_SCOPE)
    excluded_symbols = set(CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS)

    _collect_formal_scope_violations(
        input_etfs,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="input_etfs",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        core_beta_symbols,
        allowed=set(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS),
        excluded=excluded_symbols,
        field_name="core_beta_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        limited_defense_candidates,
        allowed=set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES),
        excluded=excluded_symbols,
        field_name="limited_defense_candidates",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        [fallback_symbol] if _normalize_text(fallback_symbol) else [],
        allowed=set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES),
        excluded=excluded_symbols,
        field_name="fallback_symbol",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        template_target_formal_symbols,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="template_target_formal_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        core_slot_symbols,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="core_slot_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        growth_slot_symbols,
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="growth_slot_symbols",
        reasons=reasons,
        evidence=evidence,
    )
    _collect_formal_scope_violations(
        [growth_seat_symbol] if _normalize_text(growth_seat_symbol) else [],
        allowed=allowed_symbols,
        excluded=excluded_symbols,
        field_name="growth_seat_symbol",
        reasons=reasons,
        evidence=evidence,
    )

    fallback_mode_text = _normalize_choice(
        fallback_mode,
        default=CN_ETF_BETA_FALLBACK_MODE,
        allowed={"none", "cash", "single_symbol"},
    )
    if fallback_mode_text == "single_symbol":
        reasons.append("LIMITED_DEFENSE_SCOPE_OUT_OF_SCOPE::single_symbol_fallback")
        evidence["uses_single_symbol_fallback"] = True

    for field_name, allowed_values in _FORMAL_GOVERNOR_BOUNDARY_ALLOWED.items():
        raw_value = {
            "governor_boundary_mode": governor_boundary_mode,
            "source_entry_type": source_entry_type,
        }.get(field_name)
        text = _normalize_text(raw_value)
        if text and text not in allowed_values:
            reasons.append(f"GOVERNOR_BOUNDARY_OUT_OF_SCOPE::{field_name}::{text}")
            evidence.setdefault("governor_boundary_out_of_scope", {})[field_name] = text

    for field_name, allowed_values in _FORMAL_SIGNAL_SEMANTICS_ALLOWED.items():
        raw_value = {
            "research_rule_family": research_rule_family,
            "strategy_role": strategy_role,
            "local_policy_mode": local_policy_mode,
        }.get(field_name)
        text = _normalize_text(raw_value)
        if text and text not in allowed_values:
            reasons.append(f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::{field_name}::{text}")
            evidence.setdefault("signal_semantics_out_of_scope", {})[field_name] = text

    controlled_accumulation_mode_text = _normalize_text(controlled_accumulation_mode).lower()
    if controlled_accumulation_mode_text and controlled_accumulation_mode_text != "none":
        reasons.append(
            f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::controlled_accumulation_mode::{_normalize_text(controlled_accumulation_mode)}"
        )
        evidence["controlled_accumulation_mode"] = _normalize_text(controlled_accumulation_mode)

    if absolute_filter_profile:
        reasons.append(f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::absolute_filter_profile::{_normalize_text(absolute_filter_profile)}")
    if candidate_pool_profile:
        reasons.append(f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::candidate_pool_profile::{_normalize_text(candidate_pool_profile)}")
    if selection_chain_profile:
        reasons.append(f"SIGNAL_SEMANTICS_OUT_OF_SCOPE::selection_chain_profile::{_normalize_text(selection_chain_profile)}")

    if _normalize_symbol_map(template_proxy_map):
        reasons.append("OUTPUT_CONTRACT_OUT_OF_SCOPE::template_proxy_map")
        evidence["template_proxy_map_keys"] = sorted(_normalize_symbol_map(template_proxy_map).keys())
    if _normalize_text(proxy_replacement_mode) and _normalize_text(proxy_replacement_mode).lower() != "none":
        reasons.append(f"OUTPUT_CONTRACT_OUT_OF_SCOPE::proxy_replacement_mode::{_normalize_text(proxy_replacement_mode)}")
    if _normalize_symbol_pairs(formal_replacement_pairs):
        reasons.append("OUTPUT_CONTRACT_OUT_OF_SCOPE::formal_replacement_pairs")
        evidence["formal_replacement_pairs"] = _normalize_symbol_pairs(formal_replacement_pairs)

    runtime_selection_obj = dict(runtime_selection_summary or {})
    if _normalize_text(runtime_selection_obj.get("core_slot_selected_symbol")):
        reasons.append("OUTPUT_CONTRACT_OUT_OF_SCOPE::core_slot_selected_symbol")
    if _normalize_text(runtime_selection_obj.get("growth_slot_selected_symbol")):
        reasons.append("OUTPUT_CONTRACT_OUT_OF_SCOPE::growth_slot_selected_symbol")
    if dict(runtime_selection_obj.get("slot_selection_reason_codes") or {}):
        reasons.append("OUTPUT_CONTRACT_OUT_OF_SCOPE::slot_selection_reason_codes")
    if dict(runtime_selection_obj.get("slot_under_deploy_reason_codes") or {}):
        reasons.append("OUTPUT_CONTRACT_OUT_OF_SCOPE::slot_under_deploy_reason_codes")

    classification = "formal_mainline"
    if reasons:
        classification = "research_only"
    if any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in (
            "FORMAL_EXCLUDED_ASSET_USED::",
            "LIMITED_DEFENSE_SCOPE_OUT_OF_SCOPE::",
            "SIGNAL_SEMANTICS_OUT_OF_SCOPE::",
            "OUTPUT_CONTRACT_OUT_OF_SCOPE::",
            "GOVERNOR_BOUNDARY_OUT_OF_SCOPE::",
        )
    ):
        classification = "do_not_promote"

    return {
        "classification": classification,
        "formal_mainline_compatible": classification == "formal_mainline",
        "reason_codes": reasons,
        "evidence": sanitize_json(evidence),
    }


def build_etf_beta_phase1_summary(
    *,
    governed_contract: dict[str, Any] | None,
    universe_meta: dict[str, Any] | None,
    governor_snapshot: dict[str, Any] | None = None,
    runtime_selection_summary: dict[str, Any] | None = None,
    effective_state_5: Any = None,
) -> dict[str, Any] | None:
    governed_obj = dict(governed_contract or {})
    raw_etf_beta = governed_obj.get("etf_beta")
    etf_beta = normalize_etf_beta_contract(raw_etf_beta)
    if not bool(etf_beta.get("enabled")):
        return None

    universe_obj = dict(universe_meta or {})
    input_etfs = _normalize_symbol_list(universe_obj.get("etf_symbols") or [])
    if not input_etfs:
        return None
    pool_version = _normalize_text(universe_obj.get("pool_version")) or _normalize_text(universe_obj.get("etf_batch"))
    shadow_symbols = _normalize_symbol_list(universe_obj.get("shadow_symbols") or [])
    shadow_role_map = _normalize_symbol_map(universe_obj.get("shadow_role_map"))
    deferred_symbols = _normalize_symbol_list(universe_obj.get("deferred_symbols") or [])
    deferred_reason_codes = _normalize_symbol_reason_map(universe_obj.get("deferred_reason_codes"))
    promotion_gate_by_symbol = sanitize_json(dict(universe_obj.get("promotion_gate_by_symbol") or {}))
    formal_eligibility_by_symbol = {
        str(symbol).strip().upper(): bool(value)
        for symbol, value in dict(universe_obj.get("formal_eligibility_by_symbol") or {}).items()
        if str(symbol).strip()
    }
    research_classification_by_symbol = {
        str(symbol).strip().upper(): str(value or "").strip()
        for symbol, value in dict(universe_obj.get("research_classification_by_symbol") or {}).items()
        if str(symbol).strip() and str(value or "").strip()
    }

    runtime_selection_obj = dict(runtime_selection_summary or {})
    eligible_etfs = _normalize_symbol_list(runtime_selection_obj.get("eligible_etfs") or [])
    selected_etfs = _normalize_symbol_list(runtime_selection_obj.get("selected_etfs") or [])
    selection_reason_codes = _normalize_symbol_reason_map(runtime_selection_obj.get("selection_reason_codes"))
    runtime_reason_codes = _normalize_reason_list(runtime_selection_obj.get("runtime_reason_codes"))
    summary_source_entry_type = (
        _normalize_text(runtime_selection_obj.get("source_entry_type"))
        or _normalize_text(etf_beta.get("source_entry_type"))
        or "cn_etf_research_entry"
    )

    sleeve_budget: dict[str, Any] = {}
    if isinstance(governor_snapshot, dict):
        sleeve_budget = dict((governor_snapshot.get("sleeve_budgets") or {}).get(CN_ETF_BETA_SLEEVE_ID) or {})

    target_selected_count_hint = (
        runtime_selection_obj.get("max_selected_symbols")
        or runtime_selection_obj.get("selected_cap")
        or sleeve_budget.get("target_selected_count")
        or len(selected_etfs)
        or None
    )
    exposure_semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=etf_beta,
        effective_state_5=(
            effective_state_5
            or (governor_snapshot or {}).get("regime_effective_state")
            or (governor_snapshot or {}).get("budget_effective_state_5")
            or (governor_snapshot or {}).get("effective_state_5")
        ),
        total_exposure_cap=(governor_snapshot or {}).get("total_exposure_cap"),
        slot_cap=sleeve_budget.get("slot_cap"),
        target_selected_count=target_selected_count_hint,
        sleeve_budget_snapshot=sleeve_budget,
    )

    formal_alignment = classify_etf_formal_alignment(
        input_etfs=input_etfs,
        core_beta_symbols=etf_beta.get("core_beta_symbols"),
        limited_defense_candidates=etf_beta.get("limited_defense_candidates"),
        fallback_mode=etf_beta.get("fallback_mode"),
        fallback_symbol=etf_beta.get("fallback_symbol"),
        strategy_role=etf_beta.get("strategy_role"),
        governor_boundary_mode=etf_beta.get("governor_boundary_mode"),
        local_policy_mode=etf_beta.get("local_policy_mode"),
        source_entry_type=summary_source_entry_type,
        research_rule_family=etf_beta.get("research_rule_family"),
        absolute_filter_profile=etf_beta.get("absolute_filter_profile"),
        candidate_pool_profile=etf_beta.get("candidate_pool_profile"),
        selection_chain_profile=etf_beta.get("selection_chain_profile"),
        controlled_accumulation_mode=etf_beta.get("controlled_accumulation_mode"),
        template_target_formal_symbols=etf_beta.get("template_target_formal_symbols"),
        template_proxy_map=etf_beta.get("template_proxy_map"),
        proxy_replacement_mode=etf_beta.get("proxy_replacement_mode"),
        formal_replacement_pairs=etf_beta.get("formal_replacement_pairs"),
        core_slot_symbols=etf_beta.get("core_slot_symbols"),
        growth_slot_symbols=etf_beta.get("growth_slot_symbols"),
        growth_seat_symbol=etf_beta.get("growth_seat_symbol"),
        runtime_selection_summary=runtime_selection_obj,
    )
    formal_scope = set(_normalize_symbol_list(etf_beta.get("core_beta_symbols"))) | set(
        _normalize_symbol_list(etf_beta.get("limited_defense_candidates"))
    )
    fallback_symbol = _normalize_text(etf_beta.get("fallback_symbol")).upper()
    if fallback_symbol and _normalize_text(etf_beta.get("fallback_mode")).lower() == "single_symbol":
        formal_scope.add(fallback_symbol)
    out_of_scope_etfs = [symbol for symbol in input_etfs if symbol not in formal_scope]
    under_deploy_reason_codes = _normalize_reason_list(
        list(runtime_selection_obj.get("under_deploy_reason_codes") or ())
        + list(sleeve_budget.get("under_deploy_reason_codes") or ())
    )

    sleeve_budget_used = sanitize_json(
        {
            "budget_owner": _normalize_text(governed_obj.get("governor", {}).get("owner")) or "global_portfolio_governor",
            "total_risk_budget": _safe_float((governor_snapshot or {}).get("total_risk_budget")),
            "total_exposure_cap": _safe_float((governor_snapshot or {}).get("total_exposure_cap")),
            "slot_cap": _safe_int(sleeve_budget.get("slot_cap"), default=0) or None,
            "available_slots": _safe_int(sleeve_budget.get("available_slots"), default=0) or None,
            "positions_after_sell": _safe_int(sleeve_budget.get("positions_after_sell"), default=0) or None,
            "candidate_count": len(eligible_etfs) or _safe_int(sleeve_budget.get("candidate_count"), default=0) or None,
            "selected_count": len(selected_etfs) or _safe_int(sleeve_budget.get("selected_count"), default=0) or None,
            "budget_share": _safe_float(sleeve_budget.get("budget_share")),
            "target_exposure": exposure_semantics.get("target_exposure"),
            "min_deployable_exposure": exposure_semantics.get("min_deployable_exposure"),
            "target_exposure_source": _summary_source_alias(exposure_semantics.get("target_exposure_source")),
            "min_deployable_exposure_source": _summary_source_alias(exposure_semantics.get("min_deployable_exposure_source")),
            "fallback_allowed": bool(exposure_semantics.get("fallback_allowed", False)),
            "under_deploy_reason_codes": under_deploy_reason_codes,
            "target_selected_count": exposure_semantics.get("target_selected_count"),
            "actual_exposure": _safe_float(sleeve_budget.get("actual_exposure")),
            "actual_risk_exposure": _safe_float(sleeve_budget.get("actual_risk_exposure")),
            "actual_fallback_exposure": _safe_float(sleeve_budget.get("actual_fallback_exposure")),
            "actual_other_exposure": _safe_float(sleeve_budget.get("actual_other_exposure")),
            "deployability_gap": _safe_float(sleeve_budget.get("deployability_gap")),
            "boundary_policy_mode": exposure_semantics.get("boundary_policy_mode"),
            "strategy_role": exposure_semantics.get("strategy_role"),
            "governor_boundary_mode": exposure_semantics.get("governor_boundary_mode"),
            "local_policy_mode": exposure_semantics.get("local_policy_mode"),
            "trans_up_contract_mode": exposure_semantics.get("trans_up_contract_mode"),
            "trans_up_single_seat_core_recovery": exposure_semantics.get("trans_up_single_seat_core_recovery"),
            "governor_hard_blocked": exposure_semantics.get("governor_hard_blocked"),
            "governor_hard_block_reason_codes": exposure_semantics.get("governor_hard_block_reason_codes"),
            "governor_budget_reason_codes": exposure_semantics.get("governor_budget_reason_codes"),
            "local_boundary_state": exposure_semantics.get("local_boundary_state"),
            "local_boundary_reason_codes": exposure_semantics.get("local_boundary_reason_codes"),
            "strategic_floor_cap": exposure_semantics.get("strategic_floor_cap"),
            "tactical_overlay_cap": exposure_semantics.get("tactical_overlay_cap"),
            "limited_defense_cap": exposure_semantics.get("limited_defense_cap"),
            "deployment_pace": exposure_semantics.get("deployment_pace"),
            "bull_partial_overlay_pace_ratio": exposure_semantics.get("bull_partial_overlay_pace_ratio"),
            "bull_pace_mode": exposure_semantics.get("bull_pace_mode"),
        }
    )

    formal_view = build_etf_beta_formal_view(exposure_semantics)
    research_view = build_etf_beta_research_view(exposure_semantics)
    account_transition_execution = sanitize_json(
        dict(runtime_selection_obj.get("account_transition_execution") or {})
    )
    if isinstance(account_transition_execution, dict) and account_transition_execution:
        formal_view = sanitize_json(
            {
                **dict(formal_view or {}),
                "account_transition_execution": account_transition_execution,
            }
        )
        research_view = sanitize_json(
            {
                **dict(research_view or {}),
                "account_transition_execution": account_transition_execution,
            }
        )

    summary_payload = {
        "sleeve_id": etf_beta.get("sleeve_id"),
        "system_role": etf_beta.get("system_role"),
        "source_entry_type": summary_source_entry_type,
        "source_preset_id": universe_obj.get("preset_id"),
        "source_batch_id": universe_obj.get("etf_batch"),
        "preset_id": universe_obj.get("preset_id"),
        "etf_batch": universe_obj.get("etf_batch"),
        "pool_version": pool_version,
        "research_only": bool(universe_obj.get("research_only", False)),
        "input_etfs": input_etfs,
        "eligible_etfs": eligible_etfs,
        "selected_etfs": selected_etfs,
        "out_of_scope_etfs": out_of_scope_etfs,
        "formal_scope_symbols": _normalize_symbol_list(universe_obj.get("formal_scope_symbols") or []),
        "shadow_symbols": shadow_symbols,
        "shadow_role_map": shadow_role_map,
        "deferred_symbols": deferred_symbols,
        "deferred_reason_codes": deferred_reason_codes,
        "research_classification_by_symbol": research_classification_by_symbol,
        "promotion_gate_by_symbol": promotion_gate_by_symbol,
        "formal_eligibility_by_symbol": formal_eligibility_by_symbol,
        "formal_core_beta_symbols": list(_normalize_symbol_list(etf_beta.get("core_beta_symbols"))),
        "limited_defense_candidates": list(_normalize_symbol_list(etf_beta.get("limited_defense_candidates"))),
        "selection_reason_codes": selection_reason_codes,
        "runtime_reason_codes": runtime_reason_codes,
        "coverage_start": universe_obj.get("coverage_start"),
        "coverage_end": universe_obj.get("coverage_end"),
        "daily_table": universe_obj.get("daily_table"),
        "price_series_semantics": universe_obj.get("price_series_semantics"),
        "formal_alignment_reference": CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
        "formal_etf_pool_version": _normalize_text(etf_beta.get("formal_etf_pool_version"))
        or _normalize_text(etf_beta.get("template_asset_pool_version"))
        or CN_ETF_FORMAL_PHASE1_POOL_VERSION,
        "formal_alignment_status": formal_alignment.get("classification"),
        "formal_mainline_compatible": bool(formal_alignment.get("formal_mainline_compatible", False)),
        "formal_alignment_reason_codes": list(formal_alignment.get("reason_codes") or []),
        "formal_alignment_evidence": dict(formal_alignment.get("evidence") or {}),
        "requested_budget": exposure_semantics.get("requested_budget"),
        "applied_budget": exposure_semantics.get("applied_budget"),
        "targets": dict(exposure_semantics.get("targets") or {}),
        "cash_weight": exposure_semantics.get("cash_weight"),
        "defense_weight": exposure_semantics.get("defense_weight"),
        "equity_core_bucket": exposure_semantics.get("equity_core_bucket"),
        "defense_tilt_bucket": exposure_semantics.get("defense_tilt_bucket"),
        "cash_buffer_bucket": exposure_semantics.get("cash_buffer_bucket"),
        "target_exposure": exposure_semantics.get("target_exposure"),
        "target_exposure_source": _summary_source_alias(exposure_semantics.get("target_exposure_source")),
        "min_deployable_exposure": exposure_semantics.get("min_deployable_exposure"),
        "min_deployable_exposure_source": _summary_source_alias(exposure_semantics.get("min_deployable_exposure_source")),
        "target_selected_count": exposure_semantics.get("target_selected_count"),
        "target_selected_count_source": exposure_semantics.get("target_selected_count_source"),
        "fallback_allowed": exposure_semantics.get("fallback_allowed"),
        "fallback_allowed_source": exposure_semantics.get("fallback_allowed_source"),
        "boundary_policy_mode": exposure_semantics.get("boundary_policy_mode"),
        "local_boundary_state": exposure_semantics.get("local_boundary_state"),
        "local_boundary_reason_codes": list(exposure_semantics.get("local_boundary_reason_codes") or []),
        "governor_hard_blocked": exposure_semantics.get("governor_hard_blocked"),
        "governor_hard_block_reason_codes": list(exposure_semantics.get("governor_hard_block_reason_codes") or []),
        "governor_budget_reason_codes": list(exposure_semantics.get("governor_budget_reason_codes") or []),
        "strategic_floor_cap": exposure_semantics.get("strategic_floor_cap"),
        "tactical_overlay_cap": exposure_semantics.get("tactical_overlay_cap"),
        "limited_defense_cap": exposure_semantics.get("limited_defense_cap"),
        "deployment_pace": exposure_semantics.get("deployment_pace"),
        "bull_partial_overlay_pace_ratio": exposure_semantics.get("bull_partial_overlay_pace_ratio"),
        "bull_pace_mode": exposure_semantics.get("bull_pace_mode"),
        "pace_policy_gap": exposure_semantics.get("pace_policy_gap"),
        "pace_policy_reason_code": exposure_semantics.get("pace_policy_reason_code"),
        "pace_policy_mode": exposure_semantics.get("pace_policy_mode"),
        "trans_up_contract_mode": exposure_semantics.get("trans_up_contract_mode"),
        "trans_up_single_seat_core_recovery": exposure_semantics.get("trans_up_single_seat_core_recovery"),
        "strategy_role": exposure_semantics.get("strategy_role"),
        "governor_boundary_mode": exposure_semantics.get("governor_boundary_mode"),
        "local_policy_mode": exposure_semantics.get("local_policy_mode"),
        "exposure_policy_family": exposure_semantics.get("exposure_policy_family"),
        "policy_scope": exposure_semantics.get("policy_scope"),
        "broad_based_only": exposure_semantics.get("broad_based_only"),
        "layering_policy": exposure_semantics.get("layering_policy"),
        "controlled_accumulation_mode": exposure_semantics.get("controlled_accumulation_mode"),
        "layering_band": exposure_semantics.get("layering_band"),
        "layering_active": exposure_semantics.get("layering_active"),
        "layering_reason_codes": list(exposure_semantics.get("layering_reason_codes") or []),
        "core_accumulator_symbols": list(exposure_semantics.get("core_accumulator_symbols") or []),
        "tactical_satellite_symbols": list(exposure_semantics.get("tactical_satellite_symbols") or []),
        "limited_defense_symbols": list(exposure_semantics.get("limited_defense_symbols") or []),
        "symbol_role_map": dict(exposure_semantics.get("symbol_role_map") or {}),
        "reason_codes": list(exposure_semantics.get("reason_codes") or []),
        "under_deploy_reason_codes": under_deploy_reason_codes,
        "actual_exposure": sleeve_budget_used.get("actual_exposure"),
        "actual_risk_exposure": sleeve_budget_used.get("actual_risk_exposure"),
        "actual_fallback_exposure": sleeve_budget_used.get("actual_fallback_exposure"),
        "actual_other_exposure": sleeve_budget_used.get("actual_other_exposure"),
        "deployability_gap": sleeve_budget_used.get("deployability_gap"),
        "vol_target": {
            "active": bool(runtime_selection_obj.get("etf_beta_vol_target_active", runtime_selection_obj.get("vol_target_active", False))),
            "window": runtime_selection_obj.get("etf_beta_vol_target_window", runtime_selection_obj.get("vol_target_window")),
            "annualized_target": runtime_selection_obj.get(
                "etf_beta_vol_target_annualized_target",
                runtime_selection_obj.get("vol_target_annualized_target"),
            ),
            "min_scale": runtime_selection_obj.get("etf_beta_vol_target_min_scale", runtime_selection_obj.get("vol_target_min_scale")),
            "max_scale": runtime_selection_obj.get("etf_beta_vol_target_max_scale", runtime_selection_obj.get("vol_target_max_scale")),
            "scale_by_symbol": dict(
                runtime_selection_obj.get("etf_beta_vol_target_scale_by_symbol")
                or runtime_selection_obj.get("vol_target_scale_by_symbol")
                or {}
            ),
            "realized_vol_by_symbol": dict(
                runtime_selection_obj.get("etf_beta_vol_target_realized_vol_by_symbol")
                or runtime_selection_obj.get("vol_target_realized_vol_by_symbol")
                or {}
            ),
        },
        "formal_view": formal_view,
        "research_view": research_view,
        "sleeve_budget_used": sleeve_budget_used,
        "governor_boundary": {
            "requested_budget": exposure_semantics.get("requested_budget"),
            "applied_budget": exposure_semantics.get("applied_budget"),
            "target_exposure": exposure_semantics.get("target_exposure"),
            "target_exposure_source": exposure_semantics.get("target_exposure_source"),
            "min_deployable_exposure": exposure_semantics.get("min_deployable_exposure"),
            "min_deployable_exposure_source": exposure_semantics.get("min_deployable_exposure_source"),
            "target_selected_count": exposure_semantics.get("target_selected_count"),
            "target_selected_count_source": exposure_semantics.get("target_selected_count_source"),
            "fallback_allowed": exposure_semantics.get("fallback_allowed"),
            "fallback_allowed_source": exposure_semantics.get("fallback_allowed_source"),
            "boundary_policy_mode": exposure_semantics.get("boundary_policy_mode"),
            "governor_hard_blocked": exposure_semantics.get("governor_hard_blocked"),
            "governor_hard_block_reason_codes": list(exposure_semantics.get("governor_hard_block_reason_codes") or []),
            "governor_budget_reason_codes": list(exposure_semantics.get("governor_budget_reason_codes") or []),
        },
        "local_policy_decision": {
            "allocation_engine_mode": _normalize_text(etf_beta.get("allocation_engine_mode")) or CN_ETF_BETA_ALLOCATION_ENGINE_MODE,
            "bucket_policy_profile": _normalize_text(etf_beta.get("bucket_policy_profile")) or CN_ETF_BETA_BUCKET_POLICY_PROFILE,
            "boundary_state": exposure_semantics.get("local_boundary_state"),
            "reason_codes": list(exposure_semantics.get("local_boundary_reason_codes") or []),
            "strategic_floor_cap": exposure_semantics.get("strategic_floor_cap"),
            "tactical_overlay_cap": exposure_semantics.get("tactical_overlay_cap"),
            "limited_defense_cap": exposure_semantics.get("limited_defense_cap"),
            "deployment_pace": exposure_semantics.get("deployment_pace"),
            "targets": dict(exposure_semantics.get("targets") or {}),
        },
    }
    return sanitize_json(summary_payload)


def extract_latest_etf_beta_runtime_selection(daily_df: pd.DataFrame) -> dict[str, Any] | None:
    if daily_df.empty or "diagnostics_input_json" not in daily_df.columns:
        return None
    df = daily_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        return None

    for _, row in df.iloc[::-1].iterrows():
        raw = row.get("diagnostics_input_json")
        payload: dict[str, Any] = {}
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                payload = parsed

        diagnostics = dict(payload.get("diagnostics") or {})
        formal_view = dict(diagnostics.get("etf_beta_formal_view") or {})
        research_view = dict(diagnostics.get("etf_beta_research_view") or {})
        eligible_etfs = _normalize_symbol_list(
            diagnostics.get("etf_beta_eligible_symbols")
            or research_view.get("eligible_etfs")
            or []
        )
        selected_etfs = _normalize_symbol_list(
            diagnostics.get("etf_beta_selected_symbols")
            or research_view.get("selected_etfs")
            or []
        )
        selection_reason_codes = _normalize_symbol_reason_map(
            diagnostics.get("etf_beta_selection_reason_codes")
            or research_view.get("selection_reason_codes")
            or {}
        )
        runtime_reason_codes = _normalize_reason_list(
            diagnostics.get("etf_beta_runtime_reason_codes")
            or research_view.get("runtime_reason_codes")
            or []
        )
        if not any((eligible_etfs, selected_etfs, selection_reason_codes, runtime_reason_codes)):
            continue

        strategy_role = diagnostics.get("etf_beta_strategy_role") or formal_view.get("strategy_role")
        local_policy_mode = diagnostics.get("etf_beta_local_policy_mode") or formal_view.get("local_policy_mode")
        is_formal_phase1 = _is_formal_phase1_stabilizer(strategy_role, local_policy_mode)

        return sanitize_json(
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "eligible_etfs": eligible_etfs,
                "selected_etfs": selected_etfs,
                "selection_reason_codes": selection_reason_codes,
                "runtime_reason_codes": runtime_reason_codes,
                "selected_cap": diagnostics.get("etf_beta_selected_cap"),
                "max_selected_symbols": diagnostics.get("etf_beta_max_selected_symbols"),
                "source_entry_type": diagnostics.get("etf_beta_source_entry_type"),
                "absolute_filter_profile": None if is_formal_phase1 else diagnostics.get("etf_beta_absolute_filter_profile"),
                "candidate_pool_profile": None if is_formal_phase1 else diagnostics.get("etf_beta_candidate_pool_profile"),
                "selection_chain_profile": None if is_formal_phase1 else diagnostics.get("etf_beta_selection_chain_profile"),
                "strategy_role": strategy_role,
                "governor_boundary_mode": diagnostics.get("etf_beta_governor_boundary_mode") or formal_view.get("governor_boundary_mode"),
                "local_policy_mode": local_policy_mode,
                "boundary_policy_mode": diagnostics.get("etf_beta_boundary_policy_mode") or formal_view.get("boundary_policy_mode"),
                "controlled_accumulation_mode": None
                if is_formal_phase1
                else diagnostics.get("etf_beta_controlled_accumulation_mode") or research_view.get("controlled_accumulation_mode"),
                "core_slot_symbols": [] if is_formal_phase1 else list(diagnostics.get("etf_beta_core_slot_symbols") or []),
                "growth_slot_symbols": [] if is_formal_phase1 else list(diagnostics.get("etf_beta_growth_slot_symbols") or []),
                "core_slot_selected_symbol": None if is_formal_phase1 else diagnostics.get("etf_beta_core_slot_selected_symbol"),
                "growth_slot_selected_symbol": None if is_formal_phase1 else diagnostics.get("etf_beta_growth_slot_selected_symbol"),
                "slot_selection_reason_codes": {} if is_formal_phase1 else dict(diagnostics.get("etf_beta_slot_selection_reason_codes") or {}),
                "slot_under_deploy_reason_codes": {} if is_formal_phase1 else dict(diagnostics.get("etf_beta_slot_under_deploy_reason_codes") or {}),
                "under_deploy_reason_codes": _normalize_reason_list(diagnostics.get("etf_beta_under_deploy_reason_codes") or []),
                "vol_target_active": diagnostics.get("etf_beta_vol_target_active"),
                "vol_target_window": diagnostics.get("etf_beta_vol_target_window"),
                "vol_target_annualized_target": diagnostics.get("etf_beta_vol_target_annualized_target"),
                "vol_target_min_scale": diagnostics.get("etf_beta_vol_target_min_scale"),
                "vol_target_max_scale": diagnostics.get("etf_beta_vol_target_max_scale"),
                "vol_target_scale_by_symbol": dict(diagnostics.get("etf_beta_vol_target_scale_by_symbol") or {}),
                "vol_target_realized_vol_by_symbol": dict(diagnostics.get("etf_beta_vol_target_realized_vol_by_symbol") or {}),
                "account_transition_execution": sanitize_json(
                    dict(
                        formal_view.get("account_transition_execution")
                        or research_view.get("account_transition_execution")
                        or {
                            "owner": diagnostics.get("etf_beta_account_transition_execution_owner"),
                            "status": diagnostics.get("etf_beta_account_transition_execution_status"),
                            "reason_code": diagnostics.get("etf_beta_account_transition_execution_reason_code"),
                            "reject_reason": diagnostics.get("etf_beta_account_transition_execution_reject_reason"),
                            "transition_kind": diagnostics.get("etf_beta_account_transition_kind"),
                            "edge_from_state": diagnostics.get("etf_beta_account_transition_edge_from_state"),
                            "edge_to_state": diagnostics.get("etf_beta_account_transition_edge_to_state"),
                            "release_destination": diagnostics.get("etf_beta_account_transition_release_destination"),
                            "reference_paths": list(
                                diagnostics.get("etf_beta_account_transition_execution_reference_paths") or []
                            ),
                        }
                    )
                ),
            }
        )
    return None


__all__ = [
    "build_etf_beta_phase1_summary",
    "classify_etf_formal_alignment",
    "extract_latest_etf_beta_runtime_selection",
]
