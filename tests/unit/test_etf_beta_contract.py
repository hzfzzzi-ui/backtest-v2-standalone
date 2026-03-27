from __future__ import annotations

import pytest

from backend.core.config.etf_beta_contract import (
    CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
    build_etf_beta_phase1_summary,
    classify_etf_formal_alignment,
    normalize_etf_beta_contract,
    resolve_etf_beta_exposure_semantics,
)


def test_resolve_etf_beta_exposure_semantics_supports_broad_based_governed_policy() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "research_rule_family": "broad_based_rotation_template_a",
            "exposure_policy_family": "broad_based_governed_v1",
            "policy_scope": "broad_based_only",
            "broad_based_only": True,
            "layering_policy": "light_trans_down_accumulate",
            "max_selected_symbols": 2,
            "target_exposure_by_state_5": {
                "BULL": 1.0,
                "TRANS_UP": 0.9,
                "LIGHT": 0.6,
                "TRANS_DOWN": 0.3,
                "RISK_OFF": 0.0,
            },
            "min_deployable_exposure_by_state_5": {
                "BULL": 0.5,
                "TRANS_UP": 0.45,
                "LIGHT": 0.3,
                "TRANS_DOWN": 0.15,
                "RISK_OFF": 0.0,
            },
            "target_selected_count_by_state_5": {
                "BULL": 2,
                "TRANS_UP": 2,
                "LIGHT": 2,
                "TRANS_DOWN": 1,
                "RISK_OFF": 0,
            },
            "fallback_allowed_by_state_5": {
                "BULL": True,
                "TRANS_UP": True,
                "LIGHT": True,
                "TRANS_DOWN": True,
                "RISK_OFF": False,
            },
        }
    )

    light = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="LIGHT",
        slot_cap=1,
        target_selected_count=1,
    )
    trans_down = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="TRANS_DOWN",
        slot_cap=0,
        target_selected_count=0,
    )

    assert light["policy_scope"] == "broad_based_only"
    assert light["broad_based_only"] is True
    assert light["layering_band"] == "LIGHT_ACCUMULATE"
    assert light["layering_active"] is True
    assert light["target_selected_count"] == 2
    assert light["target_selected_count_source"] == "state_map::LIGHT"
    assert light["fallback_allowed"] is True
    assert light["fallback_allowed_source"] == "state_map::LIGHT"

    assert trans_down["layering_band"] == "CONTROLLED_TRANS_DOWN"
    assert trans_down["layering_active"] is True
    assert "ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN" in trans_down["layering_reason_codes"]
    assert trans_down["target_exposure"] == 0.3
    assert trans_down["target_selected_count"] == 1
    assert trans_down["fallback_allowed"] is True


def test_build_etf_beta_phase1_summary_emits_policy_and_layering_fields() -> None:
    governed_contract = {
        "etf_beta": normalize_etf_beta_contract(
            {
                "enabled": True,
                "research_rule_family": "broad_based_rotation_template_a",
                "exposure_policy_family": "broad_based_governed_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "layering_policy": "light_trans_down_accumulate",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "target_exposure_by_state_5": {"LIGHT": 0.6, "TRANS_DOWN": 0.3},
                "min_deployable_exposure_by_state_5": {"LIGHT": 0.3, "TRANS_DOWN": 0.15},
                "target_selected_count_by_state_5": {"LIGHT": 2, "TRANS_DOWN": 1},
                "fallback_allowed_by_state_5": {"LIGHT": True, "TRANS_DOWN": True},
            }
        )
    }
    universe_meta = {
        "preset_id": "cn_broad_based_governed_exposure_policy",
        "etf_batch": "cn_broad_based_only",
        "etf_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ", "511010.SH"],
    }
    runtime_selection = {
        "selected_cap": 1,
        "selected_etfs": ["510300.SH"],
        "eligible_etfs": ["510300.SH", "510500.SH"],
        "runtime_reason_codes": ["ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN"],
        "selection_reason_codes": {"510300.SH": ["ETF_BETA_CORE_SCOPE"]},
        "target_selected_count": 1,
        "target_selected_count_source": "state_map::TRANS_DOWN",
        "target_exposure": 0.3,
        "target_exposure_source": "state_map::TRANS_DOWN",
        "min_deployable_exposure": 0.15,
        "min_deployable_exposure_source": "state_map::TRANS_DOWN",
        "fallback_allowed": True,
        "fallback_allowed_source": "state_map::TRANS_DOWN",
        "exposure_policy_family": "broad_based_governed_v1",
        "policy_scope": "broad_based_only",
        "broad_based_only": True,
        "layering_policy": "light_trans_down_accumulate",
        "layering_band": "CONTROLLED_TRANS_DOWN",
        "layering_active": True,
        "layering_reason_codes": ["ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN"],
    }
    governor_snapshot = {
        "regime_effective_state": "TRANS_DOWN",
        "total_exposure_cap": 0.3,
        "sleeve_budgets": {
            "cn_etf_beta": {
                "slot_cap": 0,
                "target_exposure": 0.3,
                "min_deployable_exposure": 0.15,
                "fallback_allowed": True,
                "actual_exposure": 0.28,
                "actual_risk_exposure": 0.18,
                "actual_fallback_exposure": 0.10,
                "deployability_gap": 0.02,
            }
        },
    }

    summary = build_etf_beta_phase1_summary(
        governed_contract=governed_contract,
        universe_meta=universe_meta,
        governor_snapshot=governor_snapshot,
        runtime_selection_summary=runtime_selection,
    )

    assert summary is not None
    assert summary["exposure_policy_family"] == "broad_based_governed_v1"
    assert summary["policy_scope"] == "broad_based_only"
    assert summary["broad_based_only"] is True
    assert summary["layering_policy"] == "light_trans_down_accumulate"
    assert summary["layering_band"] == "CONTROLLED_TRANS_DOWN"
    assert summary["layering_active"] is True
    assert summary["layering_reason_codes"] == ["ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN"]
    assert summary["target_selected_count_source"] == "state_map::TRANS_DOWN"
    assert summary["fallback_allowed_source"] == "state_map::TRANS_DOWN"


def test_classify_etf_formal_alignment_accepts_phase1_formal_path() -> None:
    alignment = classify_etf_formal_alignment(
        input_etfs=["510300.SH", "510500.SH", "510050.SH", "512100.SH", "512890.SH"],
        core_beta_symbols=["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
        limited_defense_candidates=["512890.SH"],
        fallback_mode="cash",
        fallback_symbol=None,
        strategy_role="auxiliary_beta_sleeve",
        governor_boundary_mode="consume_governor_sleeve_budget",
        local_policy_mode="legacy_beta_selection",
        source_entry_type="cn_etf_research_entry",
        research_rule_family="etf_beta_v1_control",
        absolute_filter_profile=None,
        candidate_pool_profile=None,
        selection_chain_profile=None,
        controlled_accumulation_mode="none",
        template_target_formal_symbols=["510300.SH", "510500.SH", "510050.SH", "512100.SH", "512890.SH"],
        template_proxy_map={},
        proxy_replacement_mode="none",
        formal_replacement_pairs={},
        core_slot_symbols=[],
        growth_slot_symbols=[],
        growth_seat_symbol=None,
        runtime_selection_summary={},
    )

    assert alignment["classification"] == "formal_mainline"
    assert alignment["formal_mainline_compatible"] is True
    assert alignment["reason_codes"] == []
    assert alignment["evidence"]["reference_doc"] == CN_ETF_FORMAL_ALIGNMENT_REFERENCE


def test_build_etf_beta_phase1_summary_marks_out_of_scope_assets_do_not_promote() -> None:
    summary = build_etf_beta_phase1_summary(
        governed_contract={
            "etf_beta": normalize_etf_beta_contract(
                {
                    "enabled": True,
                    "research_rule_family": "broad_based_rotation_template_a",
                    "strategy_role": "governed_broad_based_standalone_mainline",
                    "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                    "governor_boundary_mode": "consume_governor_state_and_budget",
                    "local_policy_mode": "broad_based_rotation_mainline",
                    "controlled_accumulation_mode": "light_and_controlled_trans_down",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "159915.SZ"],
                    "limited_defense_candidates": [],
                    "fallback_mode": "single_symbol",
                    "fallback_symbol": "511010.SH",
                    "template_target_formal_symbols": ["510300.SH", "510500.SH", "159915.SZ"],
                }
            )
        },
        universe_meta={
            "preset_id": "cn_broad_based_standalone_mainline",
            "etf_batch": "cn_broad_based_only",
            "etf_symbols": ["510300.SH", "510500.SH", "159915.SZ", "511010.SH"],
        },
    )

    assert summary is not None
    assert summary["formal_alignment_status"] == "do_not_promote"
    assert summary["formal_mainline_compatible"] is False
    assert any(code.startswith("FORMAL_EXCLUDED_ASSET_USED::input_etfs::159915.SZ") for code in summary["formal_alignment_reason_codes"])
    assert any(code.startswith("FORMAL_EXCLUDED_ASSET_USED::fallback_symbol::511010.SH") for code in summary["formal_alignment_reason_codes"])


def test_normalize_etf_beta_contract_rejects_non_broad_based_symbol_for_standalone_mainline() -> None:
    with pytest.raises(ValueError, match="governed broad-based standalone mainline"):
        normalize_etf_beta_contract(
            {
                "enabled": True,
                "strategy_role": "governed_broad_based_standalone_mainline",
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "governor_boundary_mode": "consume_governor_state_and_budget",
                "local_policy_mode": "broad_based_rotation_mainline",
                "research_rule_family": "broad_based_rotation_template_a",
                "core_beta_symbols": ["510300.SH", "518880.SH"],
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
            }
        )


def test_build_etf_beta_phase1_summary_emits_governor_boundary_and_local_policy_split_for_standalone_mainline() -> None:
    governed_contract = {
        "etf_beta": normalize_etf_beta_contract(
            {
                "enabled": True,
                "strategy_role": "governed_broad_based_standalone_mainline",
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "governor_boundary_mode": "consume_governor_state_and_budget",
                "local_policy_mode": "broad_based_rotation_mainline",
                "research_rule_family": "broad_based_rotation_template_a",
                "exposure_policy_family": "broad_based_standalone_mainline_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "controlled_accumulation_mode": "light_and_controlled_trans_down",
                "core_beta_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ"],
                "fallback_mode": "single_symbol",
                "fallback_symbol": "511010.SH",
                "target_exposure_by_state_5": {"LIGHT": 0.7, "TRANS_DOWN": 0.35},
                "min_deployable_exposure_by_state_5": {"LIGHT": 0.2, "TRANS_DOWN": 0.1},
                "target_selected_count_by_state_5": {"LIGHT": 2, "TRANS_DOWN": 1},
                "fallback_allowed_by_state_5": {"LIGHT": True, "TRANS_DOWN": True},
            }
        )
    }
    summary = build_etf_beta_phase1_summary(
        governed_contract=governed_contract,
        universe_meta={
            "preset_id": "cn_broad_based_standalone_mainline",
            "etf_batch": "cn_broad_based_only",
            "etf_symbols": ["510300.SH", "510500.SH", "512100.SH", "512890.SH", "159915.SZ", "511010.SH"],
        },
        governor_snapshot={
            "regime_effective_state": "TRANS_DOWN",
            "total_exposure_cap": 0.35,
            "sleeve_budgets": {
                "cn_etf_beta": {
                    "slot_cap": 1,
                    "target_exposure": 0.35,
                    "min_deployable_exposure": 0.1,
                    "fallback_allowed": True,
                    "actual_exposure": 0.31,
                    "actual_risk_exposure": 0.22,
                    "actual_fallback_exposure": 0.09,
                    "deployability_gap": 0.04,
                }
            },
        },
        runtime_selection_summary={
            "selected_cap": 1,
            "eligible_etfs": ["510300.SH", "510500.SH"],
            "selected_etfs": ["510500.SH"],
            "selection_reason_codes": {"510500.SH": ["ETF_BETA_CORE_SCOPE", "RS_WINNER"]},
            "runtime_reason_codes": ["ETF_BETA_STANDALONE_MAINLINE_ACTIVE"],
            "target_selected_count": 1,
            "target_selected_count_source": "state_map::TRANS_DOWN",
            "target_exposure": 0.35,
            "target_exposure_source": "state_map::TRANS_DOWN",
            "min_deployable_exposure": 0.1,
            "min_deployable_exposure_source": "state_map::TRANS_DOWN",
            "fallback_allowed": True,
            "fallback_allowed_source": "state_map::TRANS_DOWN",
            "controlled_accumulation_mode": "light_and_controlled_trans_down",
            "under_deploy_reason_codes": ["ETF_BETA_STANDALONE_UNDERDEPLOY"],
            "deployability_gap": 0.04,
        },
    )

    assert summary is not None
    assert summary["strategy_role"] == "governed_broad_based_standalone_mainline"
    assert summary["source_entry_type"] == "cn_etf_broad_based_standalone_mainline_entry"
    assert summary["governor_boundary_mode"] == "consume_governor_state_and_budget"
    assert summary["local_policy_mode"] == "broad_based_rotation_mainline"
    assert summary["controlled_accumulation_mode"] == "light_and_controlled_trans_down"
    assert summary["governor_boundary"]["target_exposure"] == 0.35
    assert summary["local_policy_decision"]["selected_etfs"] == ["510500.SH"]
    assert "ETF_BETA_STANDALONE_MAINLINE_ACTIVE" in summary["local_policy_decision"]["runtime_reason_codes"]


def test_normalize_etf_beta_contract_accepts_bottleneck_study_profiles() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "research_rule_family": "broad_based_rotation_template_a",
            "absolute_filter_profile": "ma150_ret12",
            "candidate_pool_profile": "standard_overlap_pool",
            "selection_chain_profile": "core_growth_slot",
            "absolute_filter_mode": "ma200_and_positive_12m",
        }
    )

    assert contract["absolute_filter_profile"] == "ma150_ret12"
    assert contract["candidate_pool_profile"] == "standard_overlap_pool"
    assert contract["selection_chain_profile"] == "core_growth_slot"


def test_build_etf_beta_phase1_summary_emits_bottleneck_profile_fields() -> None:
    summary = build_etf_beta_phase1_summary(
        governed_contract={
            "etf_beta": normalize_etf_beta_contract(
                {
                    "enabled": True,
                    "research_rule_family": "broad_based_rotation_template_a",
                    "absolute_filter_profile": "ma200_only",
                    "candidate_pool_profile": "proxy_expanded_pool",
                    "selection_chain_profile": "global_top2_6_3_1",
                }
            )
        },
        universe_meta={"preset_id": "cn_etf", "etf_symbols": ["510300.SH", "510500.SH"]},
        governor_snapshot={},
        runtime_selection_summary={
            "absolute_filter_profile": "ma200_only",
            "candidate_pool_profile": "proxy_expanded_pool",
            "selection_chain_profile": "global_top2_6_3_1",
            "absolute_filter_reject_count": 3,
            "absolute_filter_reject_reason_counts": {"ABSOLUTE_MA200_NOT_ABOVE": 3},
            "candidate_pool_symbols": ["510300.SH", "510500.SH", "159915.SZ"],
            "candidate_pool_coverage_summary": {"symbol_count": 3},
            "candidate_pool_reject_reason_counts": {"POOL_PROFILE_EXCLUDED::DIVIDEND_STANDARD": 1},
            "selection_chain_winner_counts": {"selected_count": 2},
            "selection_chain_reject_reason_counts": {"SELECTION_CHAIN_RANK_BELOW_CUTOFF": 1},
        },
    )

    assert summary is not None
    assert summary["absolute_filter_profile"] == "ma200_only"
    assert summary["candidate_pool_profile"] == "proxy_expanded_pool"
    assert summary["selection_chain_profile"] == "global_top2_6_3_1"
    assert summary["absolute_filter_reject_reason_counts"]["ABSOLUTE_MA200_NOT_ABOVE"] == 3
    assert summary["selection_chain_winner_counts"]["selected_count"] == 2
