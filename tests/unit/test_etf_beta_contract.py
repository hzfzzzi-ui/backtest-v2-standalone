from __future__ import annotations

import pytest

from backend.core.config.etf_beta_contract import (
    CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
    build_default_etf_beta_contract,
    build_etf_beta_phase1_summary,
    classify_etf_formal_alignment,
    normalize_etf_beta_contract,
    resolve_etf_beta_exposure_semantics,
)


def test_build_default_etf_beta_contract_uses_phase1_allocation_defaults() -> None:
    contract = build_default_etf_beta_contract(enabled=True)

    assert contract["strategy_role"] == "strategic_beta_stabilizer"
    assert contract["source_entry_type"] == "cn_etf_phase1_allocation_entry"
    assert contract["research_rule_family"] == "phase1_allocation_engine_v1"
    assert contract["local_policy_mode"] == "phase1_bucket_allocation"
    assert contract["boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert contract["exposure_policy_family"] == "phase1_governed_allocation_v1"
    assert contract["bull_partial_overlay_pace_ratio"] == pytest.approx(0.5)
    assert contract["absolute_filter_mode"] == "none"
    assert contract["fallback_mode"] == "none"
    assert contract["core_beta_symbols"] == ["510300.SH", "510500.SH", "510050.SH", "512100.SH"]
    assert contract["limited_defense_candidates"] == ["511010.SH"]


def test_resolve_etf_beta_exposure_semantics_emits_phase1_buckets_and_targets() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "strategy_role": "phase1_allocation_engine",
            "source_entry_type": "cn_etf_phase1_allocation_entry",
            "research_rule_family": "phase1_allocation_engine_v1",
            "governor_boundary_mode": "consume_governor_sleeve_budget",
            "local_policy_mode": "phase1_bucket_allocation",
            "exposure_policy_family": "phase1_governed_allocation_v1",
            "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
            "limited_defense_candidates": ["511010.SH"],
        }
    )

    semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="TRANS_DOWN",
        total_exposure_cap=0.5,
        sleeve_budget_snapshot={"target_exposure": 0.4},
    )

    assert semantics["requested_budget"] == pytest.approx(0.4)
    assert semantics["applied_budget"] == pytest.approx(0.4)
    assert semantics["equity_core_bucket"] == pytest.approx(0.45)
    assert semantics["defense_tilt_bucket"] == pytest.approx(0.10)
    assert semantics["cash_buffer_bucket"] == pytest.approx(0.45)
    assert semantics["cash_weight"] == pytest.approx(0.0)
    assert semantics["defense_weight"] == pytest.approx(0.22)
    assert semantics["targets"]["511010.SH"] == pytest.approx(0.22)
    assert "510500.SH" not in semantics["targets"]
    assert "512100.SH" not in semantics["targets"]
    assert semantics["strategic_floor_cap"] == pytest.approx(0.18)
    assert semantics["tactical_overlay_cap"] == pytest.approx(0.0)
    assert sum(float(value) for value in semantics["targets"].values()) == pytest.approx(0.4)
    assert semantics["boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert semantics["local_boundary_state"] == "REDUCED_ALLOCATION"
    assert semantics["governor_hard_blocked"] is False
    assert semantics["target_selected_count"] == 3
    assert semantics["fallback_allowed"] is False
    assert "PHASE1_ALLOCATION_ENGINE::THREE_BUCKET" in semantics["reason_codes"]
    assert "STRATEGIC_BETA_STABILIZER::THREE_BUCKET" in semantics["reason_codes"]


def test_resolve_etf_beta_exposure_semantics_blocks_phase1_when_governor_disallows_new_risk() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "strategy_role": "phase1_allocation_engine",
            "source_entry_type": "cn_etf_phase1_allocation_entry",
            "research_rule_family": "phase1_allocation_engine_v1",
            "governor_boundary_mode": "consume_governor_sleeve_budget",
            "local_policy_mode": "phase1_bucket_allocation",
            "exposure_policy_family": "phase1_governed_allocation_v1",
            "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
            "limited_defense_candidates": ["511010.SH"],
            "max_selected_symbols": 3,
        }
    )

    semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="RISK_OFF",
        total_exposure_cap=0.3,
        slot_cap=1,
        target_selected_count=1,
        sleeve_budget_snapshot={"target_exposure": 0.3, "allow_new_risk": False},
    )

    assert semantics["requested_budget"] == pytest.approx(0.3)
    assert semantics["applied_budget"] == pytest.approx(0.0)
    assert semantics["targets"] == {}
    assert semantics["governor_hard_blocked"] is True
    assert semantics["governor_hard_block_reason_codes"] == ["GOVERNOR_ALLOW_NEW_RISK_FALSE"]
    assert semantics["local_boundary_state"] == "GOVERNOR_HARD_BLOCK"
    assert semantics["target_selected_count"] == 0


def test_resolve_etf_beta_exposure_semantics_ignores_out_of_range_multiplier_for_phase1_target() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "strategy_role": "phase1_allocation_engine",
            "source_entry_type": "cn_etf_phase1_allocation_entry",
            "research_rule_family": "phase1_allocation_engine_v1",
            "governor_boundary_mode": "consume_governor_sleeve_budget",
            "local_policy_mode": "phase1_bucket_allocation",
            "exposure_policy_family": "phase1_governed_allocation_v1",
            "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
            "limited_defense_candidates": ["511010.SH"],
        }
    )

    semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="BULL",
        total_exposure_cap=0.2,
        slot_cap=2,
        target_selected_count=2,
        sleeve_budget_snapshot={"target_exposure": 1.8},
    )

    assert semantics["requested_budget"] == pytest.approx(0.2)
    assert semantics["applied_budget"] == pytest.approx(0.2)
    assert semantics["target_exposure"] == pytest.approx(0.2)
    assert semantics["target_exposure_source"] == "governor_total_exposure_cap"
    assert "GOVERNOR_TARGET_EXPOSURE_OUT_OF_RANGE" in semantics["governor_budget_reason_codes"]
    assert semantics["deployment_pace"] == pytest.approx(0.144)
    assert semantics["bull_partial_overlay_pace_ratio"] == pytest.approx(0.5)
    assert semantics["bull_pace_mode"] == "partial_overlay_v1"
    assert semantics["pace_policy_gap"] == pytest.approx(0.056)
    assert semantics["pace_policy_reason_code"] == "ETF_BETA_DEPLOYMENT_PACE_BULL_PARTIAL_OVERLAY"
    assert semantics["pace_policy_mode"] == "partial_overlay_v1_between_rebalances"
    assert all(float(value) <= 1.0 for value in semantics["targets"].values())


def test_resolve_etf_beta_exposure_semantics_aligns_trans_up_to_single_seat_core_recovery() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "strategy_role": "strategic_beta_stabilizer",
            "source_entry_type": "cn_etf_phase1_allocation_entry",
            "research_rule_family": "phase1_allocation_engine_v1",
            "governor_boundary_mode": "consume_governor_sleeve_budget",
            "local_policy_mode": "phase1_bucket_allocation",
            "exposure_policy_family": "phase1_governed_allocation_v1",
            "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
            "limited_defense_candidates": ["511010.SH"],
            "max_selected_symbols": 3,
        }
    )

    semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="TRANS_UP",
        total_exposure_cap=0.1,
        slot_cap=1,
        target_selected_count=2,
        sleeve_budget_snapshot={"target_exposure": 0.1, "target_selected_count": 2},
    )

    assert semantics["trans_up_contract_mode"] == "single_seat_core_recovery"
    assert semantics["trans_up_single_seat_core_recovery"] is True
    assert semantics["target_selected_count"] == 1
    assert semantics["target_selected_count_source"] == "trans_up_single_seat_core_recovery"
    assert semantics["strategic_floor_cap"] == pytest.approx(0.0527)
    assert semantics["tactical_overlay_cap"] == pytest.approx(0.0)
    assert semantics["limited_defense_cap"] == pytest.approx(0.0)
    assert semantics["bull_partial_overlay_pace_ratio"] is None
    assert semantics["bull_pace_mode"] is None
    assert semantics["pace_policy_gap"] == pytest.approx(0.0473)
    assert semantics["pace_policy_reason_code"] == "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY"
    assert "TRANS_UP_SINGLE_SEAT_CORE_RECOVERY" in semantics["local_boundary_reason_codes"]
    assert set(semantics["targets"]) == {"510300.SH", "510050.SH"}
    assert all(
        contract["symbol_role_map"][symbol] == "core_accumulator"
        for symbol in semantics["targets"]
    )


def test_resolve_etf_beta_exposure_semantics_supports_standalone_mainline_full_deployability() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "strategy_role": "governed_broad_based_standalone_mainline",
            "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
            "governor_boundary_mode": "consume_governor_state_and_budget",
            "local_policy_mode": "broad_based_rotation_mainline",
            "research_rule_family": "broad_based_rotation_template_a",
            "exposure_policy_family": "broad_based_standalone_mainline_v1",
            "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "588000.SH"],
            "limited_defense_candidates": ["511010.SH", "518880.SH"],
            "target_exposure_by_state_5": {
                "BULL": 1.0,
                "TRANS_UP": 0.9,
                "TRANS_UP": 0.9,
                "TRANS_DOWN": 0.4,
                "RISK_OFF": 0.15,
            },
            "min_deployable_exposure_by_state_5": {
                "BULL": 0.45,
                "TRANS_UP": 0.35,
                "TRANS_UP": 0.35,
                "TRANS_DOWN": 0.1,
                "RISK_OFF": 0.05,
            },
            "target_selected_count_by_state_5": {
                "BULL": 2,
                "TRANS_UP": 2,
                "TRANS_UP": 2,
                "TRANS_DOWN": 1,
                "RISK_OFF": 1,
            },
            "fallback_allowed_by_state_5": {
                "BULL": True,
                "TRANS_UP": True,
                "TRANS_UP": True,
                "TRANS_DOWN": True,
                "RISK_OFF": True,
            },
        }
    )

    bull = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="BULL",
        sleeve_budget_snapshot={},
    )
    trans_up = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="TRANS_UP",
        sleeve_budget_snapshot={},
    )
    risk_off = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="RISK_OFF",
        sleeve_budget_snapshot={},
    )

    assert bull["deployment_pace"] == pytest.approx(1.0)
    assert bull["pace_policy_gap"] == pytest.approx(0.0)
    assert trans_up["deployment_pace"] == pytest.approx(0.9)
    assert trans_up["pace_policy_gap"] == pytest.approx(0.0)
    assert risk_off["deployment_pace"] == pytest.approx(0.15)
    assert risk_off["pace_policy_gap"] == pytest.approx(0.0)
    assert risk_off["layering_band"] == "RISK_OFF_CORE_ACCUMULATE"
    assert risk_off["layering_active"] is True
    assert "ETF_BETA_LAYERING_RISK_OFF_CORE_ACCUMULATE" in risk_off["layering_reason_codes"]


def test_build_etf_beta_phase1_summary_emits_phase1_budget_and_target_fields() -> None:
    governed_contract = {
        "etf_beta": normalize_etf_beta_contract(
            {
                "enabled": True,
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "research_rule_family": "phase1_allocation_engine_v1",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "exposure_policy_family": "phase1_governed_allocation_v1",
                "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
            }
        )
    }
    summary = build_etf_beta_phase1_summary(
        governed_contract=governed_contract,
        universe_meta={
            "preset_id": "cn_etf_first_wave_core",
            "etf_batch": "cn_etf_first_wave_core",
            "etf_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
            "coverage_start": "2013-01-04",
            "coverage_end": "2026-03-20",
            "daily_table": "pams_cn_etf_daily",
            "price_series_semantics": "executable_price_only_not_total_return",
        },
        governor_snapshot={
            "regime_effective_state": "TRANS_UP",
            "total_exposure_cap": 0.7,
            "sleeve_budgets": {
                "cn_etf_beta": {
                    "slot_cap": 3,
                    "target_exposure": 0.6,
                    "actual_exposure": 0.52,
                }
            },
        },
    )

    assert summary is not None
    assert summary["formal_alignment_status"] == "formal_mainline"
    assert summary["requested_budget"] == pytest.approx(0.6)
    assert summary["applied_budget"] == pytest.approx(0.6)
    assert summary["boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert summary["local_boundary_state"] == "ACTIVE"
    assert summary["cash_weight"] == pytest.approx(0.06)
    assert summary["defense_weight"] == pytest.approx(0.0)
    assert summary["targets"]["510300.SH"] == pytest.approx(0.204)
    assert summary["targets"]["510050.SH"] == pytest.approx(0.1122)
    assert summary["bull_partial_overlay_pace_ratio"] is None
    assert summary["bull_pace_mode"] is None
    assert summary["governor_boundary"]["requested_budget"] == pytest.approx(0.6)
    assert summary["governor_boundary"]["boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert summary["local_policy_decision"]["allocation_engine_mode"] == "phase1_three_bucket_v1"
    assert summary["local_policy_decision"]["bucket_policy_profile"] == "phase1_state_template_v1"


def test_resolve_etf_beta_exposure_semantics_standalone_mainline_trans_up_uses_live_target_deploy() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "strategy_role": "governed_broad_based_standalone_mainline",
            "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
            "governor_boundary_mode": "consume_governor_state_and_budget",
            "local_policy_mode": "broad_based_rotation_mainline",
            "research_rule_family": "broad_based_rotation_template_a",
            "exposure_policy_family": "broad_based_standalone_mainline_v1",
            "core_beta_symbols": ["510300.SH", "510050.SH", "588000.SH"],
            "limited_defense_candidates": ["511010.SH", "518880.SH"],
            "target_exposure_by_state_5": {"TRANS_UP": 0.9},
            "min_deployable_exposure_by_state_5": {"TRANS_UP": 0.35},
            "target_selected_count_by_state_5": {"TRANS_UP": 2},
            "fallback_allowed_by_state_5": {"TRANS_UP": True},
            "equity_core_bucket_by_state_5": {"TRANS_UP": 0.8},
            "defense_tilt_bucket_by_state_5": {"TRANS_UP": 0.1},
            "cash_buffer_bucket_by_state_5": {"TRANS_UP": 0.1},
        }
    )

    semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="TRANS_UP",
        total_exposure_cap=0.9,
        sleeve_budget_snapshot={"target_exposure": 0.9, "target_selected_count": 2},
    )

    assert semantics["trans_up_contract_mode"] is None
    assert semantics["trans_up_single_seat_core_recovery"] is False
    assert semantics["tactical_overlay_cap"] > 0.0
    assert semantics["deployment_pace"] == pytest.approx(0.9)
    assert semantics["pace_policy_gap"] == pytest.approx(0.0)
    assert semantics["target_selected_count"] == 2


def test_resolve_etf_beta_exposure_semantics_standalone_mainline_risk_off_keeps_positive_deploy_pace() -> None:
    contract = normalize_etf_beta_contract(
        {
            "enabled": True,
            "strategy_role": "governed_broad_based_standalone_mainline",
            "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
            "governor_boundary_mode": "consume_governor_state_and_budget",
            "local_policy_mode": "broad_based_rotation_mainline",
            "controlled_accumulation_mode": "light_and_controlled_trans_down",
            "research_rule_family": "broad_based_rotation_template_a",
            "exposure_policy_family": "broad_based_standalone_mainline_v1",
            "core_beta_symbols": ["510300.SH", "510050.SH", "588000.SH"],
            "limited_defense_candidates": ["511010.SH", "518880.SH"],
            "target_exposure_by_state_5": {"RISK_OFF": 0.15},
            "min_deployable_exposure_by_state_5": {"RISK_OFF": 0.05},
            "target_selected_count_by_state_5": {"RISK_OFF": 1},
            "fallback_allowed_by_state_5": {"RISK_OFF": True},
            "equity_core_bucket_by_state_5": {"RISK_OFF": 0.15},
            "defense_tilt_bucket_by_state_5": {"RISK_OFF": 0.45},
            "cash_buffer_bucket_by_state_5": {"RISK_OFF": 0.4},
        }
    )

    semantics = resolve_etf_beta_exposure_semantics(
        etf_beta_contract=contract,
        effective_state_5="RISK_OFF",
        total_exposure_cap=0.15,
        sleeve_budget_snapshot={"target_exposure": 0.15, "target_selected_count": 1},
    )

    assert semantics["deployment_pace"] == pytest.approx(0.15)
    assert semantics["governor_hard_blocked"] is False
    assert semantics["pace_policy_gap"] == pytest.approx(0.0)
    assert semantics["layering_band"] == "RISK_OFF_CORE_ACCUMULATE"


def test_classify_etf_formal_alignment_accepts_phase1_formal_path() -> None:
    alignment = classify_etf_formal_alignment(
        input_etfs=["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
        core_beta_symbols=["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
        limited_defense_candidates=["511010.SH"],
        fallback_mode="none",
        fallback_symbol=None,
        strategy_role="phase1_allocation_engine",
        governor_boundary_mode="consume_governor_sleeve_budget",
        local_policy_mode="phase1_bucket_allocation",
        source_entry_type="cn_etf_phase1_allocation_entry",
        research_rule_family="phase1_allocation_engine_v1",
        absolute_filter_profile=None,
        candidate_pool_profile=None,
        selection_chain_profile=None,
        controlled_accumulation_mode="none",
        template_target_formal_symbols=["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
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


def test_classify_etf_formal_alignment_rejects_research_assets_from_formal_mainline() -> None:
    alignment = classify_etf_formal_alignment(
        input_etfs=["510300.SH", "510500.SH", "159915.SZ"],
        core_beta_symbols=["510300.SH", "510500.SH", "159915.SZ"],
        limited_defense_candidates=[],
        fallback_mode="single_symbol",
        fallback_symbol="518880.SH",
        strategy_role="phase1_allocation_engine",
        governor_boundary_mode="consume_governor_sleeve_budget",
        local_policy_mode="phase1_bucket_allocation",
        source_entry_type="cn_etf_phase1_allocation_entry",
        research_rule_family="phase1_allocation_engine_v1",
        absolute_filter_profile=None,
        candidate_pool_profile=None,
        selection_chain_profile=None,
        controlled_accumulation_mode="none",
        template_target_formal_symbols=["510300.SH", "510500.SH", "159915.SZ"],
        template_proxy_map={},
        proxy_replacement_mode="none",
        formal_replacement_pairs={},
        core_slot_symbols=[],
        growth_slot_symbols=[],
        growth_seat_symbol=None,
        runtime_selection_summary={},
    )

    assert alignment["classification"] == "do_not_promote"
    assert alignment["formal_mainline_compatible"] is False
    assert any(code.startswith("FORMAL_EXCLUDED_ASSET_USED::input_etfs::159915.SZ") for code in alignment["reason_codes"])
    assert any(code.startswith("FORMAL_EXCLUDED_ASSET_USED::fallback_symbol::518880.SH") for code in alignment["reason_codes"])


def test_normalize_etf_beta_contract_rejects_non_formal_symbol_for_phase1_engine() -> None:
    with pytest.raises(ValueError, match="phase1 allocation engine"):
        normalize_etf_beta_contract(
            {
                "enabled": True,
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "local_policy_mode": "phase1_bucket_allocation",
                "research_rule_family": "phase1_allocation_engine_v1",
                "core_beta_symbols": ["510300.SH", "159915.SZ"],
                "limited_defense_candidates": ["511010.SH"],
            }
        )

