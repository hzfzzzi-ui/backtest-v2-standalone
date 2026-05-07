from __future__ import annotations

from typing import Any

from .common import (
    _clamp_unit_float,
    _controlled_accumulation_mode_from_layering_policy,
    _invalid_broad_based_mainline_symbols,
    _is_formal_stabilizer_role,
    _layering_policy_from_controlled_accumulation_mode,
    _normalize_choice,
    _normalize_controlled_accumulation_mode,
    _normalize_optional_choice,
    _normalize_state_bool_map,
    _normalize_state_float_map,
    _normalize_state_int_map,
    _normalize_state_symbol_float_map,
    _normalize_state_symbol_list_map,
    _normalize_symbol_float_map,
    _normalize_symbol_list,
    _normalize_symbol_map,
    _normalize_symbol_pairs,
    _normalize_text,
    _resolve_phase1_bucket_split,
    _resolve_phase1_defense_template,
    _resolve_phase1_equity_template,
    _resolve_stabilizer_role_map,
    _safe_float,
    _safe_int,
    _safe_notional_exposure,
)
from .defaults import (
    CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
    CN_ETF_BETA_ALLOCATION_ENGINE_MODE,
    CN_ETF_BETA_BUCKET_POLICY_PROFILE,
    CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO,
    CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE,
    CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
    CN_ETF_BETA_FALLBACK_MODE,
    CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE,
    CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
    CN_ETF_BETA_LAYERING_POLICY,
    CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE,
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
    CN_ETF_BETA_STRATEGY_ROLE,
    CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
    CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
    CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
    CN_ETF_BETA_VOL_TARGET_WINDOW,
    CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS,
    CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES,
    CN_ETF_PHASE1_EQUITY_TILT_LIMITS,
    build_default_etf_beta_contract,
)


def normalize_etf_beta_contract(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw_etf_beta = dict(raw or {})
    etf_beta = build_default_etf_beta_contract(enabled=bool(raw_etf_beta.get("enabled")))
    etf_beta.update(raw_etf_beta)
    raw_controlled_accumulation_mode = _normalize_text(raw_etf_beta.get("controlled_accumulation_mode"))
    explicit_phase1_contract = any(
        (
            _normalize_text(raw_etf_beta.get("strategy_role")) in {"phase1_allocation_engine", "strategic_beta_stabilizer"},
            _normalize_text(raw_etf_beta.get("source_entry_type")) == "cn_etf_phase1_allocation_entry",
            _normalize_text(raw_etf_beta.get("local_policy_mode")) == "phase1_bucket_allocation",
            _normalize_text(raw_etf_beta.get("boundary_policy_mode")) == CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE,
            _normalize_text(raw_etf_beta.get("exposure_policy_family")) == "phase1_governed_allocation_v1",
        )
    )

    etf_beta["sleeve_id"] = _normalize_text(etf_beta.get("sleeve_id")) or etf_beta["sleeve_id"]
    etf_beta["system_role"] = _normalize_text(etf_beta.get("system_role")) or "market_beta_sleeve"
    etf_beta["strategy_role"] = _normalize_choice(
        etf_beta.get("strategy_role"),
        default=CN_ETF_BETA_STRATEGY_ROLE,
        allowed={
            "auxiliary_beta_sleeve",
            "governed_broad_based_standalone_mainline",
            "phase1_allocation_engine",
            "strategic_beta_stabilizer",
        },
    )

    is_phase1 = _is_formal_stabilizer_role(etf_beta["strategy_role"], etf_beta.get("local_policy_mode"))
    etf_beta["governor_boundary_mode"] = _normalize_choice(
        etf_beta.get("governor_boundary_mode"),
        default=CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        allowed={"consume_governor_sleeve_budget", "consume_governor_state_and_budget"},
    )
    etf_beta["local_policy_mode"] = _normalize_choice(
        etf_beta.get("local_policy_mode"),
        default=CN_ETF_BETA_LOCAL_POLICY_MODE,
        allowed={"legacy_beta_selection", "broad_based_rotation_mainline", "phase1_bucket_allocation"},
    )
    if is_phase1 or etf_beta["local_policy_mode"] == "phase1_bucket_allocation":
        boundary_default = CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE
    else:
        boundary_default = CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE
    etf_beta["boundary_policy_mode"] = _normalize_choice(
        etf_beta.get("boundary_policy_mode"),
        default=boundary_default,
        allowed={CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE, CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE},
    )
    etf_beta["exposure_policy_family"] = _normalize_choice(
        etf_beta.get("exposure_policy_family"),
        default=CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
        allowed={"default", "broad_based_governed_v1", "broad_based_standalone_mainline_v1", "phase1_governed_allocation_v1"},
    )
    etf_beta["policy_scope"] = _normalize_choice(
        etf_beta.get("policy_scope"),
        default=CN_ETF_BETA_POLICY_SCOPE,
        allowed={"general", "broad_based_only"},
    )
    etf_beta["broad_based_only"] = (
        bool(etf_beta.get("broad_based_only"))
        if etf_beta.get("broad_based_only") is not None
        else etf_beta["policy_scope"] == "broad_based_only"
    )

    etf_beta["layering_policy"] = _normalize_choice(
        etf_beta.get("layering_policy"),
        default=CN_ETF_BETA_LAYERING_POLICY,
        allowed={"none", "light_accumulate", "light_trans_down_accumulate"},
    )
    controlled_mode = _normalize_controlled_accumulation_mode(etf_beta.get("controlled_accumulation_mode"))
    if raw_controlled_accumulation_mode:
        etf_beta["layering_policy"] = _layering_policy_from_controlled_accumulation_mode(controlled_mode)
    else:
        controlled_mode = _controlled_accumulation_mode_from_layering_policy(etf_beta["layering_policy"])
    etf_beta["controlled_accumulation_mode"] = controlled_mode or CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE

    etf_beta["template_id"] = _normalize_text(etf_beta.get("template_id")) or None
    etf_beta["template_asset_pool_version"] = _normalize_text(etf_beta.get("template_asset_pool_version")) or None
    etf_beta["template_role_map"] = _normalize_symbol_map(etf_beta.get("template_role_map"))
    etf_beta["template_proxy_map"] = _normalize_symbol_map(etf_beta.get("template_proxy_map"))
    etf_beta["template_target_formal_symbols"] = _normalize_symbol_list(etf_beta.get("template_target_formal_symbols"))
    etf_beta["proxy_replacement_mode"] = _normalize_choice(
        etf_beta.get("proxy_replacement_mode"),
        default="none",
        allowed={"none", "csi1000_proxy_only", "dividend_proxy_only", "full_standard_swap"},
    )
    etf_beta["formal_replacement_pairs"] = _normalize_symbol_pairs(etf_beta.get("formal_replacement_pairs"))
    etf_beta["core_slot_symbols"] = _normalize_symbol_list(etf_beta.get("core_slot_symbols"))
    etf_beta["growth_slot_symbols"] = _normalize_symbol_list(etf_beta.get("growth_slot_symbols"))
    growth_candidates = _normalize_symbol_list([etf_beta.get("growth_seat_symbol")])
    etf_beta["growth_seat_symbol"] = growth_candidates[0] if growth_candidates else None

    default_source_entry_type = (
        "cn_etf_phase1_allocation_entry"
        if is_phase1
        else (
            "cn_etf_broad_based_standalone_mainline_entry"
            if etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline"
            else "cn_etf_research_entry"
        )
    )
    etf_beta["budget_semantics"] = _normalize_text(etf_beta.get("budget_semantics")) or etf_beta["budget_semantics"]
    etf_beta["total_budget_owner"] = _normalize_text(etf_beta.get("total_budget_owner")) or "global_portfolio_governor"
    etf_beta["source_entry_type"] = _normalize_text(etf_beta.get("source_entry_type")) or default_source_entry_type
    etf_beta["phase1_scope_mode"] = _normalize_text(etf_beta.get("phase1_scope_mode")) or "core_beta_plus_limited_defense"

    etf_beta["core_beta_symbols"] = _normalize_symbol_list(etf_beta.get("core_beta_symbols")) or list(etf_beta["core_beta_symbols"])
    etf_beta["core_accumulator_symbols"] = _normalize_symbol_list(etf_beta.get("core_accumulator_symbols"))
    etf_beta["tactical_satellite_symbols"] = _normalize_symbol_list(etf_beta.get("tactical_satellite_symbols"))
    etf_beta["limited_defense_candidates"] = _normalize_symbol_list(etf_beta.get("limited_defense_candidates")) or list(
        etf_beta["limited_defense_candidates"]
    )
    (
        etf_beta["core_accumulator_symbols"],
        etf_beta["tactical_satellite_symbols"],
        etf_beta["limited_defense_candidates"],
        etf_beta["symbol_role_map"],
    ) = _resolve_stabilizer_role_map(etf_beta)

    etf_beta["research_rule_family"] = _normalize_choice(
        etf_beta.get("research_rule_family"),
        default=CN_ETF_BETA_RULE_FAMILY,
        allowed={
            "etf_beta_v1_control",
            "dual_momentum_basic",
            "dual_momentum_vol_target",
            "broad_based_rotation_template_a",
            "broad_based_rotation_template_a0_core_satellite_v2",
            "phase1_allocation_engine_v1",
        },
    )
    etf_beta["absolute_filter_profile"] = _normalize_optional_choice(
        etf_beta.get("absolute_filter_profile"),
        allowed={"ma200_ret12", "ma200_only", "ma150_ret12"},
    )
    etf_beta["candidate_pool_profile"] = _normalize_optional_choice(
        etf_beta.get("candidate_pool_profile"),
        allowed={"a0_proxy_pool", "proxy_expanded_pool", "standard_overlap_pool"},
    )
    etf_beta["selection_chain_profile"] = _normalize_optional_choice(
        etf_beta.get("selection_chain_profile"),
        allowed={"global_top2_12_6_3", "global_top2_6_3_1", "core_growth_slot"},
    )
    etf_beta["rebalance_frequency"] = _normalize_choice(
        etf_beta.get("rebalance_frequency"),
        default=CN_ETF_BETA_REBALANCE_FREQUENCY,
        allowed={"weekly", "biweekly", "monthly"},
    )
    etf_beta["allocation_engine_mode"] = _normalize_choice(
        etf_beta.get("allocation_engine_mode"),
        default=CN_ETF_BETA_ALLOCATION_ENGINE_MODE,
        allowed={"phase1_three_bucket_v1"},
    )
    etf_beta["bucket_policy_profile"] = _normalize_choice(
        etf_beta.get("bucket_policy_profile"),
        default=CN_ETF_BETA_BUCKET_POLICY_PROFILE,
        allowed={"phase1_state_template_v1"},
    )
    etf_beta["absolute_filter_mode"] = _normalize_choice(
        etf_beta.get("absolute_filter_mode"),
        default=CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        allowed={"none", "ma120", "positive_12m", "ma200_and_positive_12m", "ma200_only", "ma150_and_positive_12m"},
    )
    etf_beta["fallback_mode"] = _normalize_choice(
        etf_beta.get("fallback_mode"),
        default=CN_ETF_BETA_FALLBACK_MODE,
        allowed={"none", "cash", "single_symbol"},
    )
    fallback_candidates = _normalize_symbol_list([etf_beta.get("fallback_symbol")])
    etf_beta["fallback_symbol"] = fallback_candidates[0] if fallback_candidates else None

    etf_beta["relative_strength_fast_window"] = max(2, _safe_int(etf_beta.get("relative_strength_fast_window"), default=CN_ETF_BETA_RS_FAST_WINDOW))
    mid_window = _safe_int(etf_beta.get("relative_strength_mid_window"), default=CN_ETF_BETA_RS_MID_WINDOW)
    etf_beta["relative_strength_mid_window"] = max(2, mid_window) if mid_window >= 2 else None
    etf_beta["relative_strength_slow_window"] = max(2, _safe_int(etf_beta.get("relative_strength_slow_window"), default=CN_ETF_BETA_RS_SLOW_WINDOW))

    fast_weight = _safe_float(etf_beta.get("relative_strength_fast_weight"))
    mid_weight = _safe_float(etf_beta.get("relative_strength_mid_weight"))
    slow_weight = _safe_float(etf_beta.get("relative_strength_slow_weight"))
    fast_weight = CN_ETF_BETA_RS_FAST_WEIGHT if fast_weight is None else max(0.0, fast_weight)
    mid_weight = CN_ETF_BETA_RS_MID_WEIGHT if mid_weight is None else max(0.0, mid_weight)
    slow_weight = CN_ETF_BETA_RS_SLOW_WEIGHT if slow_weight is None else max(0.0, slow_weight)
    if etf_beta["relative_strength_mid_window"] is None:
        mid_weight = 0.0
    if fast_weight + mid_weight + slow_weight <= 1e-12:
        fast_weight, mid_weight, slow_weight = CN_ETF_BETA_RS_FAST_WEIGHT, CN_ETF_BETA_RS_MID_WEIGHT, CN_ETF_BETA_RS_SLOW_WEIGHT
    etf_beta["relative_strength_fast_weight"] = fast_weight
    etf_beta["relative_strength_mid_weight"] = mid_weight
    etf_beta["relative_strength_slow_weight"] = slow_weight

    max_selected_symbols = _safe_int(etf_beta.get("max_selected_symbols"), default=0)
    if max_selected_symbols > 0:
        etf_beta["max_selected_symbols"] = max_selected_symbols
    else:
        etf_beta["max_selected_symbols"] = 3 if is_phase1 else None

    etf_beta["target_exposure"] = _safe_notional_exposure(etf_beta.get("target_exposure"))
    etf_beta["min_deployable_exposure"] = _safe_notional_exposure(etf_beta.get("min_deployable_exposure"))
    etf_beta["target_exposure_by_state_5"] = _normalize_state_float_map(etf_beta.get("target_exposure_by_state_5"))
    etf_beta["min_deployable_exposure_by_state_5"] = _normalize_state_float_map(etf_beta.get("min_deployable_exposure_by_state_5"))
    etf_beta["fallback_allowed"] = bool(etf_beta.get("fallback_allowed")) if etf_beta.get("fallback_allowed") is not None else None
    etf_beta["target_selected_count_by_state_5"] = _normalize_state_int_map(etf_beta.get("target_selected_count_by_state_5"))
    etf_beta["fallback_allowed_by_state_5"] = _normalize_state_bool_map(etf_beta.get("fallback_allowed_by_state_5"))
    default_weak_state_policy = dict(build_default_etf_beta_contract(enabled=bool(raw_etf_beta.get("enabled"))).get("weak_state_defense_policy") or {})
    default_weak_state_policy_target_weight_map = _normalize_state_symbol_float_map(
        default_weak_state_policy.get("target_weights_by_state_5")
    )
    raw_weak_state_policy = dict(raw_etf_beta.get("weak_state_defense_policy") or {})
    weak_state_policy = {**default_weak_state_policy, **raw_weak_state_policy}
    weak_state_policy["enabled"] = bool(weak_state_policy.get("enabled", False))
    weak_state_policy["policy_id"] = _normalize_text(weak_state_policy.get("policy_id")) or _normalize_text(
        default_weak_state_policy.get("policy_id")
    ) or None
    weak_state_policy["minimum_defense_seats_by_state_5"] = _normalize_state_int_map(
        weak_state_policy.get("minimum_defense_seats_by_state_5")
    )
    weak_state_policy["allow_core_beta_by_state_5"] = _normalize_state_bool_map(
        weak_state_policy.get("allow_core_beta_by_state_5")
    )
    weak_state_policy_target_weight_map = _normalize_state_symbol_float_map(
        weak_state_policy.get("target_weights_by_state_5")
    )
    if not weak_state_policy_target_weight_map:
        weak_state_policy_target_weight_map = dict(default_weak_state_policy_target_weight_map)
    weak_state_policy_candidate_map = _normalize_state_symbol_list_map(
        weak_state_policy.get("defense_candidate_symbols_by_state_5")
    )
    if not weak_state_policy_candidate_map:
        weak_state_policy_candidate_map = _normalize_state_symbol_list_map(
            default_weak_state_policy.get("defense_candidate_symbols_by_state_5")
        )
    formal_weak_state_symbol_scope = {
        symbol
        for symbol_weights in default_weak_state_policy_target_weight_map.values()
        for symbol in symbol_weights
    }
    invalid_weak_state_symbols = sorted(
        {
            symbol
            for symbols in weak_state_policy_candidate_map.values()
            for symbol in symbols
            if symbol not in formal_weak_state_symbol_scope
        }
    )
    if is_phase1 and explicit_phase1_contract and invalid_weak_state_symbols:
        raise ValueError(
            "phase1 allocation engine received non-formal weak-state defense symbols: "
            + ", ".join(invalid_weak_state_symbols)
        )
    invalid_weak_state_target_symbols = sorted(
        {
            symbol
            for symbol_weights in weak_state_policy_target_weight_map.values()
            for symbol in symbol_weights
            if symbol not in formal_weak_state_symbol_scope
        }
    )
    if is_phase1 and explicit_phase1_contract and invalid_weak_state_target_symbols:
        raise ValueError(
            "phase1 allocation engine received non-formal weak-state target symbols: "
            + ", ".join(invalid_weak_state_target_symbols)
        )
    defense_candidate_symbol_scope = formal_weak_state_symbol_scope - set(etf_beta["core_accumulator_symbols"])
    weak_state_policy["defense_candidate_symbols_by_state_5"] = {
        state_5: [symbol for symbol in symbols if symbol in defense_candidate_symbol_scope]
        for state_5, symbols in weak_state_policy_candidate_map.items()
    }
    weak_state_policy["target_weights_by_state_5"] = {
        state_5: {
            symbol: float(weight)
            for symbol, weight in dict(symbol_weights or {}).items()
            if symbol in formal_weak_state_symbol_scope
        }
        for state_5, symbol_weights in weak_state_policy_target_weight_map.items()
    }
    etf_beta["weak_state_defense_policy"] = weak_state_policy

    if is_phase1:
        etf_beta["equity_core_bucket_by_state_5"] = _resolve_phase1_bucket_split(
            etf_beta.get("equity_core_bucket_by_state_5"),
            bucket_key="equity_core_bucket",
        )
        etf_beta["defense_tilt_bucket_by_state_5"] = _resolve_phase1_bucket_split(
            etf_beta.get("defense_tilt_bucket_by_state_5"),
            bucket_key="defense_tilt_bucket",
        )
        etf_beta["cash_buffer_bucket_by_state_5"] = _resolve_phase1_bucket_split(
            etf_beta.get("cash_buffer_bucket_by_state_5"),
            bucket_key="cash_buffer_bucket",
        )
        etf_beta["equity_core_tilt_limits"] = _normalize_symbol_float_map(etf_beta.get("equity_core_tilt_limits")) or dict(
            CN_ETF_PHASE1_EQUITY_TILT_LIMITS
        )
        etf_beta["equity_core_template_weights"] = _normalize_symbol_float_map(etf_beta.get("equity_core_template_weights"))
        etf_beta["defense_asset_weights"] = _resolve_phase1_defense_template(etf_beta.get("defense_asset_weights"))
    else:
        etf_beta["equity_core_bucket_by_state_5"] = _normalize_state_float_map(etf_beta.get("equity_core_bucket_by_state_5"))
        etf_beta["defense_tilt_bucket_by_state_5"] = _normalize_state_float_map(etf_beta.get("defense_tilt_bucket_by_state_5"))
        etf_beta["cash_buffer_bucket_by_state_5"] = _normalize_state_float_map(etf_beta.get("cash_buffer_bucket_by_state_5"))
        etf_beta["equity_core_tilt_limits"] = _normalize_symbol_float_map(etf_beta.get("equity_core_tilt_limits"))
        etf_beta["equity_core_template_weights"] = _normalize_symbol_float_map(etf_beta.get("equity_core_template_weights"))
        etf_beta["defense_asset_weights"] = _normalize_symbol_float_map(etf_beta.get("defense_asset_weights"))

    vol_target_window = _safe_int(etf_beta.get("vol_target_window"), default=CN_ETF_BETA_VOL_TARGET_WINDOW)
    etf_beta["vol_target_window"] = max(5, int(vol_target_window or CN_ETF_BETA_VOL_TARGET_WINDOW))
    vol_target = _safe_float(etf_beta.get("vol_target_annualized_target"))
    etf_beta["vol_target_annualized_target"] = (
        CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET
        if vol_target is None or float(vol_target) <= 0.0
        else float(vol_target)
    )
    vol_target_min_scale = _safe_float(etf_beta.get("vol_target_min_scale"))
    vol_target_max_scale = _safe_float(etf_beta.get("vol_target_max_scale"))
    etf_beta["vol_target_min_scale"] = CN_ETF_BETA_VOL_TARGET_MIN_SCALE if vol_target_min_scale is None else max(0.0, min(float(vol_target_min_scale), 1.0))
    etf_beta["vol_target_max_scale"] = CN_ETF_BETA_VOL_TARGET_MAX_SCALE if vol_target_max_scale is None else max(0.0, min(float(vol_target_max_scale), 1.0))
    if etf_beta["vol_target_min_scale"] > etf_beta["vol_target_max_scale"]:
        etf_beta["vol_target_min_scale"], etf_beta["vol_target_max_scale"] = etf_beta["vol_target_max_scale"], etf_beta["vol_target_min_scale"]

    if is_phase1:
        etf_beta["bull_partial_overlay_pace_ratio"] = _clamp_unit_float(
            etf_beta.get("bull_partial_overlay_pace_ratio"),
            default=CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO,
        )
    elif etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline":
        etf_beta["bull_partial_overlay_pace_ratio"] = _clamp_unit_float(
            etf_beta.get("bull_partial_overlay_pace_ratio"),
            default=1.0,
        )
    else:
        etf_beta["bull_partial_overlay_pace_ratio"] = 0.0

    if is_phase1 and explicit_phase1_contract:
        invalid_core = [symbol for symbol in etf_beta["core_beta_symbols"] if symbol not in set(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS)]
        invalid_defense = [symbol for symbol in etf_beta["limited_defense_candidates"] if symbol not in set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES)]
        if invalid_core or invalid_defense:
            bad_symbols = ", ".join(sorted({*invalid_core, *invalid_defense}))
            raise ValueError(f"phase1 allocation engine received non-formal symbols: {bad_symbols}")
    elif etf_beta["strategy_role"] == "governed_broad_based_standalone_mainline":
        # Keep normalization permissive for standalone research lines.
        # Formal alignment is classified downstream; normalize must not reject
        # research-only mixes or fallback symbols that older callers accepted.
        pass

    return etf_beta


__all__ = ["normalize_etf_beta_contract"]
