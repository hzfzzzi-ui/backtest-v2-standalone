from __future__ import annotations

from typing import Any

CN_ETF_BETA_SLEEVE_ID = "cn_etf_beta"
CN_ETF_BETA_BUDGET_SEMANTICS = "consume_governor_sleeve_budget"
CN_ETF_BETA_CORE_SYMBOLS = (
    "510300.SH",
    "510500.SH",
    "510050.SH",
    "512100.SH",
)
CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES = ("511010.SH",)
CN_ETF_BETA_RULE_FAMILY = "phase1_allocation_engine_v1"
CN_ETF_BETA_EXPOSURE_POLICY_FAMILY = "phase1_governed_allocation_v1"
CN_ETF_BETA_POLICY_SCOPE = "broad_based_only"
CN_ETF_BETA_LAYERING_POLICY = "none"
CN_ETF_BETA_STRATEGY_ROLE = "strategic_beta_stabilizer"
CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE = "consume_governor_sleeve_budget"
CN_ETF_BETA_LOCAL_POLICY_MODE = "phase1_bucket_allocation"
CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE = "none"
CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE = "formal_phase1_document_aligned_v1"
CN_ETF_BETA_LEGACY_BOUNDARY_POLICY_MODE = "legacy_state_slot_caps_v1"
CN_ETF_BETA_REBALANCE_FREQUENCY = "monthly"
CN_ETF_BETA_ABSOLUTE_FILTER_MODE = "none"
CN_ETF_BETA_FALLBACK_MODE = "none"
CN_ETF_BETA_ABSOLUTE_FILTER_PROFILE: str | None = None
CN_ETF_BETA_CANDIDATE_POOL_PROFILE: str | None = None
CN_ETF_BETA_SELECTION_CHAIN_PROFILE: str | None = None
CN_ETF_BETA_ALLOCATION_ENGINE_MODE = "phase1_three_bucket_v1"
CN_ETF_BETA_BUCKET_POLICY_PROFILE = "phase1_state_template_v1"
CN_ETF_BETA_RS_FAST_WINDOW = 60
CN_ETF_BETA_RS_MID_WINDOW = 0
CN_ETF_BETA_RS_SLOW_WINDOW = 120
CN_ETF_BETA_RS_FAST_WEIGHT = 0.4
CN_ETF_BETA_RS_MID_WEIGHT = 0.0
CN_ETF_BETA_RS_SLOW_WEIGHT = 0.6
CN_ETF_BETA_VOL_TARGET_WINDOW = 20
CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET = 0.18
CN_ETF_BETA_VOL_TARGET_MIN_SCALE = 0.35
CN_ETF_BETA_VOL_TARGET_MAX_SCALE = 1.0
CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO = 0.5
CN_ETF_FORMAL_ALIGNMENT_REFERENCE = "A閼差搵TF鐎涙劗閮寸紒鐔虹摜閻ｃ儲鈧繆鐭緈d"
CN_ETF_FORMAL_ALIGNMENT_CLASSIFICATIONS = (
    "formal_mainline",
    "research_only",
    "do_not_promote",
)
CN_ETF_FORMAL_PHASE1_POOL_VERSION = "formal_etf_pool_v1"
CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS = CN_ETF_BETA_CORE_SYMBOLS
CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES = CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES
CN_ETF_BETA_CORE_ACCUMULATOR_SYMBOLS = ("510300.SH", "510050.SH")
CN_ETF_BETA_TACTICAL_SATELLITE_SYMBOLS = ("510500.SH", "512100.SH")
CN_ETF_FORMAL_PHASE1_EXCLUDED_SYMBOLS = (
    "518880.SH",
    "588000.SH",
    "512890.SH",
    "159915.SZ",
)
CN_ETF_PHASE1_BUCKET_SPLIT_BY_STATE_5 = {
    "BULL": {"equity_core_bucket": 0.9, "defense_tilt_bucket": 0.0, "cash_buffer_bucket": 0.1},
    "TRANS_UP": {"equity_core_bucket": 0.85, "defense_tilt_bucket": 0.05, "cash_buffer_bucket": 0.10},
    "TRANS_DOWN": {"equity_core_bucket": 0.45, "defense_tilt_bucket": 0.10, "cash_buffer_bucket": 0.45},
    "RISK_OFF": {"equity_core_bucket": 0.15, "defense_tilt_bucket": 0.15, "cash_buffer_bucket": 0.70},
}
CN_ETF_PHASE1_EQUITY_TEMPLATE_WEIGHTS_BY_STATE_5 = {
    "BULL": {"510300.SH": 0.4, "510500.SH": 0.3, "510050.SH": 0.2, "512100.SH": 0.1},
    "TRANS_UP": {"510300.SH": 0.4, "510500.SH": 0.28, "510050.SH": 0.22, "512100.SH": 0.10},
    "TRANS_DOWN": {"510300.SH": 0.4, "510500.SH": 0.15, "510050.SH": 0.4, "512100.SH": 0.05},
    "RISK_OFF": {"510300.SH": 0.35, "510500.SH": 0.05, "510050.SH": 0.55, "512100.SH": 0.05},
}
CN_ETF_PHASE1_EQUITY_TILT_LIMITS = {
    "510300.SH": 0.55,
    "510500.SH": 0.35,
    "510050.SH": 0.55,
    "512100.SH": 0.15,
}
CN_ETF_PHASE1_DEFENSE_WEIGHTS = {"511010.SH": 1.0}
CN_ETF_WEAK_STATE_DEFENSE_POLICY_ID = "formal_weak_state_defense_v1"
CN_ETF_WEAK_STATE_TARGET_WEIGHTS_BY_STATE_5 = {
    "TRANS_DOWN": {"511010.SH": 0.55, "510300.SH": 0.45},
    "RISK_OFF": {"511010.SH": 0.70, "510300.SH": 0.30},
}
CN_ETF_WEAK_STATE_DEFENSE_MIN_SEATS_BY_STATE_5 = {
    "TRANS_DOWN": 1,
    "RISK_OFF": 1,
}
CN_ETF_WEAK_STATE_DEFENSE_ALLOW_CORE_BETA_BY_STATE_5 = {
    "TRANS_DOWN": True,
    "RISK_OFF": True,
}
CN_ETF_WEAK_STATE_DEFENSE_CANDIDATE_SYMBOLS_BY_STATE_5 = {
    "TRANS_DOWN": ["511010.SH"],
    "RISK_OFF": ["511010.SH"],
}

_CANONICAL_STATE_5_ALIASES = {
    "BULL": "BULL",
    "BULL_MAIN": "BULL",
    "TRANS_UP": "TRANS_UP",
    "TURN_STRONG": "TRANS_UP",
    "LIGHT": "TRANS_UP",
    "LIGHT_TREND": "TRANS_UP",
    "TRANS_DOWN": "TRANS_DOWN",
    "TURN_WEAK": "TRANS_DOWN",
    "RISK_OFF": "RISK_OFF",
    "BEAR": "RISK_OFF",
    "DEFENSIVE": "RISK_OFF",
}

_BROAD_BASED_MAINLINE_ALLOWED_BUCKETS = {
    "broad_equity",
    "large_cap_equity",
    "mid_cap_equity",
    "small_cap_equity",
    "small_cap_equity_standard",
    "growth_equity",
    "technology_growth",
    "dividend_low_vol",
    "dividend_standard",
}
_BROAD_BASED_MAINLINE_FALLBACK_BUCKETS = {"bond"}
_ABSOLUTE_FILTER_PROFILES = {"ma200_ret12", "ma200_only", "ma150_ret12"}
_CANDIDATE_POOL_PROFILES = {"a0_proxy_pool", "proxy_expanded_pool", "standard_overlap_pool"}
_SELECTION_CHAIN_PROFILES = {"global_top2_12_6_3", "global_top2_6_3_1", "core_growth_slot"}
_FORMAL_PHASE1_SYMBOL_SCOPE = set(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS) | set(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES)
_FORMAL_SIGNAL_SEMANTICS_ALLOWED = {
    "research_rule_family": {"phase1_allocation_engine_v1"},
    "strategy_role": {"phase1_allocation_engine", "strategic_beta_stabilizer"},
    "local_policy_mode": {"phase1_bucket_allocation"},
}
_FORMAL_GOVERNOR_BOUNDARY_ALLOWED = {
    "governor_boundary_mode": {"consume_governor_sleeve_budget"},
    "source_entry_type": {"cn_etf_phase1_allocation_entry"},
}
_ETF_BETA_FORMAL_VIEW_KEYS = frozenset(
    {
        "effective_state_5",
        "strategy_role",
        "governor_boundary_mode",
        "local_policy_mode",
        "boundary_policy_mode",
        "exposure_policy_family",
        "policy_scope",
        "broad_based_only",
        "reason_codes",
        "target_exposure",
        "target_exposure_source",
        "min_deployable_exposure",
        "min_deployable_exposure_source",
        "target_selected_count",
        "target_selected_count_source",
        "fallback_allowed",
        "fallback_allowed_source",
        "targets",
        "governor_hard_blocked",
        "governor_hard_block_reason_codes",
        "governor_budget_reason_codes",
        "local_boundary_state",
        "local_boundary_reason_codes",
        "weak_state_defense_policy_id",
        "weak_state_defense_policy_active",
        "weak_state_defense_candidate_symbols",
        "weak_state_defense_allow_core_beta",
        "weak_state_target_weights_by_state_5",
        "weak_state_active_target_weights",
        "weak_state_defense_deployability_floor_applied",
        "weak_state_defense_unavailable_reason_codes",
        "weak_state_inter_rebalance_defense_redeploy_active",
        "weak_state_inter_rebalance_defense_redeploy_reason_code",
        "weak_state_inter_rebalance_defense_redeploy_reject_reason",
        "weak_state_inter_rebalance_defense_redeploy_symbols",
        "weak_state_inter_rebalance_defense_current_symbols",
        "weak_state_inter_rebalance_defense_posture_satisfied",
        "account_transition_execution",
    }
)
_ETF_BETA_RESEARCH_VIEW_KEYS = frozenset(
    {
        "requested_budget",
        "applied_budget",
        "targets",
        "cash_weight",
        "defense_weight",
        "equity_core_bucket",
        "defense_tilt_bucket",
        "cash_buffer_bucket",
        "layering_policy",
        "controlled_accumulation_mode",
        "layering_band",
        "layering_active",
        "layering_reason_codes",
        "target_exposure_by_state_5",
        "min_deployable_exposure_by_state_5",
        "target_selected_count_by_state_5",
        "fallback_allowed_by_state_5",
        "equity_core_bucket_by_state_5",
        "defense_tilt_bucket_by_state_5",
        "cash_buffer_bucket_by_state_5",
        "equity_core_template_weights",
        "equity_core_tilt_limits",
        "defense_asset_weights",
        "strategic_floor_cap",
        "tactical_overlay_cap",
        "limited_defense_cap",
        "deployment_pace",
        "bull_partial_overlay_pace_ratio",
        "bull_pace_mode",
        "pace_policy_gap",
        "pace_policy_reason_code",
        "pace_policy_mode",
        "deployability_gap",
        "execution_path",
        "rebalance_timing_gap",
        "rebalance_timing_reason_code",
        "execution_residual_gap",
        "gap_primary_owner",
        "hard_block_flags",
        "trans_up_contract_mode",
        "trans_up_single_seat_core_recovery",
        "trans_up_redeploy_active",
        "trans_up_redeploy_reason_code",
        "trans_up_redeploy_reject_reason",
        "trans_up_redeploy_floor_gap",
        "trans_up_redeploy_edge_from_state",
        "under_deploy_reason_codes",
        "runtime_reason_codes",
        "absolute_filter_reject_count",
        "absolute_filter_reject_reason_counts",
        "candidate_pool_symbols",
        "candidate_pool_coverage_summary",
        "candidate_pool_reject_reason_counts",
        "selection_chain_winner_counts",
        "selection_chain_reject_reason_counts",
        "slot_selection_reason_codes",
        "slot_under_deploy_reason_codes",
        "core_slot_target_exposure",
        "growth_slot_target_exposure",
        "core_slot_target_actual_exposure",
        "growth_slot_target_actual_exposure",
        "runtime_vol_target",
        "runtime_selection",
        "pool_version",
        "research_only",
        "formal_scope_symbols",
        "shadow_symbols",
        "shadow_role_map",
        "deferred_symbols",
        "deferred_reason_codes",
        "research_classification_by_symbol",
        "promotion_gate_by_symbol",
        "formal_eligibility_by_symbol",
        "core_accumulator_symbols",
        "tactical_satellite_symbols",
        "limited_defense_symbols",
        "symbol_role_map",
        "weak_state_defense_policy_id",
        "weak_state_defense_policy_active",
        "weak_state_defense_candidate_symbols",
        "weak_state_defense_allow_core_beta",
        "weak_state_target_weights_by_state_5",
        "weak_state_active_target_weights",
        "weak_state_defense_deployability_floor_applied",
        "weak_state_defense_unavailable_reason_codes",
        "weak_state_inter_rebalance_defense_redeploy_active",
        "weak_state_inter_rebalance_defense_redeploy_reason_code",
        "weak_state_inter_rebalance_defense_redeploy_reject_reason",
        "weak_state_inter_rebalance_defense_redeploy_symbols",
        "weak_state_inter_rebalance_defense_current_symbols",
        "weak_state_inter_rebalance_defense_posture_satisfied",
        "account_transition_execution",
    }
)


def build_default_etf_beta_contract(*, enabled: bool) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "sleeve_id": CN_ETF_BETA_SLEEVE_ID,
        "system_role": "market_beta_sleeve",
        "strategy_role": CN_ETF_BETA_STRATEGY_ROLE,
        "governor_boundary_mode": CN_ETF_BETA_GOVERNOR_BOUNDARY_MODE,
        "local_policy_mode": CN_ETF_BETA_LOCAL_POLICY_MODE,
        "boundary_policy_mode": CN_ETF_BETA_FORMAL_BOUNDARY_POLICY_MODE,
        "exposure_policy_family": CN_ETF_BETA_EXPOSURE_POLICY_FAMILY,
        "policy_scope": CN_ETF_BETA_POLICY_SCOPE,
        "broad_based_only": True,
        "layering_policy": CN_ETF_BETA_LAYERING_POLICY,
        "controlled_accumulation_mode": CN_ETF_BETA_CONTROLLED_ACCUMULATION_MODE,
        "allocation_engine_mode": CN_ETF_BETA_ALLOCATION_ENGINE_MODE,
        "bucket_policy_profile": CN_ETF_BETA_BUCKET_POLICY_PROFILE,
        "template_id": None,
        "template_asset_pool_version": CN_ETF_FORMAL_PHASE1_POOL_VERSION,
        "template_role_map": None,
        "template_proxy_map": None,
        "template_target_formal_symbols": None,
        "proxy_replacement_mode": None,
        "formal_replacement_pairs": None,
        "core_slot_symbols": None,
        "growth_slot_symbols": None,
        "growth_seat_symbol": None,
        "budget_semantics": CN_ETF_BETA_BUDGET_SEMANTICS,
        "total_budget_owner": "global_portfolio_governor",
        "source_entry_type": "cn_etf_phase1_allocation_entry",
        "phase1_scope_mode": "core_beta_plus_limited_defense",
        "equity_core_bucket_by_state_5": dict(
            (state, values["equity_core_bucket"])
            for state, values in CN_ETF_PHASE1_BUCKET_SPLIT_BY_STATE_5.items()
        ),
        "defense_tilt_bucket_by_state_5": dict(
            (state, values["defense_tilt_bucket"])
            for state, values in CN_ETF_PHASE1_BUCKET_SPLIT_BY_STATE_5.items()
        ),
        "cash_buffer_bucket_by_state_5": dict(
            (state, values["cash_buffer_bucket"])
            for state, values in CN_ETF_PHASE1_BUCKET_SPLIT_BY_STATE_5.items()
        ),
        "equity_core_template_weights": {},
        "equity_core_tilt_limits": dict(CN_ETF_PHASE1_EQUITY_TILT_LIMITS),
        "defense_asset_weights": dict(CN_ETF_PHASE1_DEFENSE_WEIGHTS),
        "core_beta_symbols": list(CN_ETF_BETA_CORE_SYMBOLS),
        "core_accumulator_symbols": list(CN_ETF_BETA_CORE_ACCUMULATOR_SYMBOLS),
        "tactical_satellite_symbols": list(CN_ETF_BETA_TACTICAL_SATELLITE_SYMBOLS),
        "limited_defense_candidates": list(CN_ETF_BETA_LIMITED_DEFENSE_CANDIDATES),
        "research_rule_family": CN_ETF_BETA_RULE_FAMILY,
        "absolute_filter_profile": CN_ETF_BETA_ABSOLUTE_FILTER_PROFILE,
        "candidate_pool_profile": CN_ETF_BETA_CANDIDATE_POOL_PROFILE,
        "selection_chain_profile": CN_ETF_BETA_SELECTION_CHAIN_PROFILE,
        "rebalance_frequency": CN_ETF_BETA_REBALANCE_FREQUENCY,
        "absolute_filter_mode": CN_ETF_BETA_ABSOLUTE_FILTER_MODE,
        "fallback_mode": CN_ETF_BETA_FALLBACK_MODE,
        "fallback_symbol": None,
        "relative_strength_fast_window": CN_ETF_BETA_RS_FAST_WINDOW,
        "relative_strength_mid_window": None,
        "relative_strength_slow_window": CN_ETF_BETA_RS_SLOW_WINDOW,
        "relative_strength_fast_weight": CN_ETF_BETA_RS_FAST_WEIGHT,
        "relative_strength_mid_weight": None,
        "relative_strength_slow_weight": CN_ETF_BETA_RS_SLOW_WEIGHT,
        "max_selected_symbols": None,
        "target_exposure": None,
        "min_deployable_exposure": None,
        "target_exposure_by_state_5": None,
        "min_deployable_exposure_by_state_5": None,
        "fallback_allowed": None,
        "target_selected_count_by_state_5": None,
        "fallback_allowed_by_state_5": None,
        "weak_state_defense_policy": {
            "enabled": True,
            "policy_id": CN_ETF_WEAK_STATE_DEFENSE_POLICY_ID,
            "minimum_defense_seats_by_state_5": dict(CN_ETF_WEAK_STATE_DEFENSE_MIN_SEATS_BY_STATE_5),
            "defense_candidate_symbols_by_state_5": dict(CN_ETF_WEAK_STATE_DEFENSE_CANDIDATE_SYMBOLS_BY_STATE_5),
            "allow_core_beta_by_state_5": dict(CN_ETF_WEAK_STATE_DEFENSE_ALLOW_CORE_BETA_BY_STATE_5),
            "target_weights_by_state_5": {
                state_5: dict(symbol_weights)
                for state_5, symbol_weights in CN_ETF_WEAK_STATE_TARGET_WEIGHTS_BY_STATE_5.items()
            },
        },
        "vol_target_window": CN_ETF_BETA_VOL_TARGET_WINDOW,
        "vol_target_annualized_target": CN_ETF_BETA_VOL_TARGET_ANNUALIZED_TARGET,
        "vol_target_min_scale": CN_ETF_BETA_VOL_TARGET_MIN_SCALE,
        "vol_target_max_scale": CN_ETF_BETA_VOL_TARGET_MAX_SCALE,
        "bull_partial_overlay_pace_ratio": CN_ETF_BETA_BULL_PARTIAL_OVERLAY_PACE_RATIO,
    }


__all__ = [
    name
    for name in globals()
    if name not in {"Any", "__builtins__", "__cached__", "__doc__", "__file__", "__loader__", "__name__", "__package__", "__spec__"}
]

