from __future__ import annotations

import json

import pandas as pd
import pytest

from backend.core.audit.research_audit import (
    aggregate_overall_status,
    build_research_audit,
    evaluate_accounting_integrity,
    evaluate_attribution_traceability,
    evaluate_etf_beta_sleeve,
    evaluate_unified_runtime_completeness,
    evaluate_execution_realism,
    evaluate_price_adjustment_integrity,
    evaluate_result_sanity,
    evaluate_timing_alignment,
    evaluate_universe_lineage,
)
from backend.core.config.etf_beta_contract import CN_ETF_FORMAL_ALIGNMENT_REFERENCE


def _etf_diag_payload(*, formal: dict | None = None, research: dict | None = None) -> str:
    return json.dumps(
        {
            "diagnostics": {
                "etf_beta_formal_view": dict(formal or {}),
                "etf_beta_research_view": dict(research or {}),
            }
        },
        ensure_ascii=False,
    )


def test_aggregate_overall_status_uses_fail_warn_unknown_pass_order() -> None:
    assert aggregate_overall_status({"a": {"status": "PASS"}, "b": {"status": "UNKNOWN"}}) == "UNKNOWN"
    assert aggregate_overall_status({"a": {"status": "WARN"}, "b": {"status": "PASS"}}) == "WARN"
    assert aggregate_overall_status({"a": {"status": "FAIL"}, "b": {"status": "PASS"}}) == "FAIL"
    assert aggregate_overall_status({"a": {"status": "PASS"}, "b": {"status": "PASS"}}) == "PASS"


def test_evaluate_universe_lineage_maps_current_snapshot_and_unknown() -> None:
    all_a_gate = evaluate_universe_lineage(
        run_meta={
            "data": {"universe_mode": "ALL_A"},
            "universe": {
                "universe_mode": "ALL_A",
                "symbols_source": "pit_security_master+pams_ohlcv_daily",
                "resolve_asof": "2026-03-01",
                "dynamic_all_a_entry": True,
            },
        }
    )
    assert all_a_gate["lineage_mode"] == "CURRENT_SNAPSHOT"
    assert all_a_gate["status"] == "FAIL"

    custom_gate = evaluate_universe_lineage(
        run_meta={
            "data": {"universe_mode": "CUSTOM"},
            "universe": {"universe_mode": "CUSTOM"},
        }
    )
    assert custom_gate["lineage_mode"] == "UNKNOWN"
    assert custom_gate["status"] == "UNKNOWN"


def test_evaluate_universe_lineage_uses_membership_audit_for_pit_dynamic() -> None:
    gate = evaluate_universe_lineage(
        run_meta={
            "data": {"universe_mode": "CSI1000"},
            "universe": {
                "universe_mode": "CSI1000",
                "membership_mode": "PIT_DYNAMIC",
                "membership_history_mode": "PIT_DYNAMIC",
                "historical_membership_dynamic": True,
                "symbols_source": "pit_index_constituents",
                "membership_source": "akshare_csi1000_static_fallback",
                "membership_data_quality": "static_fallback",
                "audit_status": "blocked",
                "audit_reason": "source_static",
                "distinct_start_dates": 1,
                "open_rows": 1000,
                "provider_floor_date": "2015-07-31",
                "refresh_event_count": 54,
                "zero_diff_refresh_event_count": 17,
                "rebalance_calendar_version": "seed-v1",
                "rebalance_calendar_source": "csindex_seed_schedule",
                "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
            },
        }
    )

    assert gate["lineage_mode"] == "PIT_DYNAMIC"
    assert gate["status"] == "FAIL"
    assert gate["evidence"]["audit_reason"] == "source_static"
    assert gate["evidence"]["provider_floor_date"] == "2015-07-31"
    assert gate["evidence"]["rebalance_calendar_version"] == "seed-v1"
    assert gate["metrics"]["distinct_start_dates"] == 1
    assert gate["metrics"]["refresh_event_count"] == 54


def test_evaluate_timing_alignment_aggregates_combo_component_passes(tmp_path) -> None:
    combo_dir = tmp_path / "combo"
    combo_dir.mkdir(parents=True, exist_ok=True)
    stock_dir = tmp_path / "stock_component"
    stock_dir.mkdir(parents=True, exist_ok=True)
    etf_dir = tmp_path / "etf_component"
    etf_dir.mkdir(parents=True, exist_ok=True)
    stock_run_meta = {
        "data": {"asset_scope": "cn_a_equity"},
        "stage_pipeline": {"execution_shell": "stage_pipeline_shell_bridge", "daily_loop_mode": "single_day_loop"},
        "timing_audit": {"status": "PASS", "contract_proved": True, "pit_safe": True, "matching_mode": "NEXT_OPEN"},
    }
    etf_run_meta = {
        "data": {"asset_scope": "cn_etf"},
        "stage_pipeline": {"execution_shell": "stage_pipeline_shell_bridge", "daily_loop_mode": "single_day_loop"},
        "timing_audit": {"status": "PASS", "contract_proved": True, "pit_safe": True, "matching_mode": "NEXT_OPEN"},
    }
    (stock_dir / "run_meta.json").write_text(json.dumps(stock_run_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (etf_dir / "run_meta.json").write_text(json.dumps(etf_run_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    gate = evaluate_timing_alignment(
        stage_summary={"execution_shell": "unified_combo_phase1", "daily_loop_mode": "unified_combo_phase1"},
        stage_pipeline={"execution_shell": "unified_combo_phase1", "daily_loop_mode": "unified_combo_phase1"},
        run_meta={
            "data": {"asset_role": "unified_multi_sleeve_combo"},
            "stage_pipeline": {"execution_shell": "unified_combo_phase1", "daily_loop_mode": "unified_combo_phase1"},
            "sleeves": {
                "stock_alpha_core": {"exp_id": "stock_component", "results_dir": str(stock_dir)},
                "etf_beta": {"exp_id": "etf_component", "results_dir": str(etf_dir)},
            },
        },
        results_dir=combo_dir,
    )

    assert gate["status"] == "PASS"
    assert gate["evidence"]["component_timing_statuses"] == {"stock_alpha_core": "PASS", "etf_beta": "PASS"}


def test_evaluate_universe_lineage_aggregates_combo_component_lineage(tmp_path) -> None:
    combo_dir = tmp_path / "combo"
    combo_dir.mkdir(parents=True, exist_ok=True)
    stock_dir = tmp_path / "stock_component"
    stock_dir.mkdir(parents=True, exist_ok=True)
    etf_dir = tmp_path / "etf_component"
    etf_dir.mkdir(parents=True, exist_ok=True)
    (stock_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "data": {"asset_scope": "cn_a_equity", "universe_mode": "CSI1000"},
                "universe": {
                    "membership_mode": "PIT_DYNAMIC",
                    "membership_history_mode": "PIT_DYNAMIC",
                    "membership_data_quality": "pit_verified",
                    "audit_status": "ok",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (etf_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "data": {"asset_scope": "cn_etf"},
                "universe": {"membership_data_quality": "whitelist_verified", "audit_status": "ok"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = evaluate_universe_lineage(
        run_meta={
            "data": {"asset_role": "unified_multi_sleeve_combo"},
            "stage_pipeline": {"execution_shell": "unified_combo_phase1"},
            "sleeves": {
                "stock_alpha_core": {"exp_id": "stock_component", "results_dir": str(stock_dir)},
                "etf_beta": {"exp_id": "etf_component", "results_dir": str(etf_dir)},
            },
        },
        results_dir=combo_dir,
    )

    assert gate["status"] == "PASS"
    assert gate["lineage_mode"] == "COMPONENT_AGGREGATED"


def test_evaluate_price_adjustment_integrity_warns_on_stale_adj_factor() -> None:
    gate = evaluate_price_adjustment_integrity(
        run_meta={
            "data_bundle": {
                "price_adj_mode": "hfq",
                "adj_factor_stats": {
                    "null_count": 2,
                    "symbols_with_missing_count": 1,
                    "max_consecutive_missing_rows": 5,
                    "max_consecutive_missing_after_valid_rows": 5,
                    "warn_threshold_rows": 5,
                    "fail_threshold_rows": 20,
                    "symbols_exceeding_warn_count": 1,
                    "symbols_exceeding_fail_count": 0,
                    "worst_after_valid_symbol": "sh600000",
                    "worst_after_valid_end_date": "2024-01-08",
                },
            }
        }
    )

    assert gate["status"] == "WARN"
    assert gate["metrics"]["symbols_exceeding_warn_count"] == 1


def test_evaluate_universe_lineage_passes_cn_etf_direct_symbols_whitelist() -> None:
    gate = evaluate_universe_lineage(
        run_meta={
            "data": {"asset_scope": "cn_etf", "universe_mode": "CUSTOM"},
            "universe": {
                "asset_scope": "cn_etf",
                "universe_mode": "CUSTOM",
                "membership_source": "cn_etf_catalog_whitelist",
                "membership_data_quality": "whitelist_verified",
                "audit_status": "PASS",
                "etf_batch": "cn_etf_first_wave_core",
                "etf_symbols": ["510300.SH", "512100.SH"],
                "coverage_start": "2016-11-04",
                "coverage_end": "2026-03-20",
                "price_series_semantics": "executable_price_only_not_total_return",
            },
        }
    )

    assert gate["lineage_mode"] == "DIRECT_SYMBOLS"
    assert gate["status"] == "PASS"
    assert gate["evidence"]["membership_source"] == "cn_etf_catalog_whitelist"
    assert gate["evidence"]["etf_batch"] == "cn_etf_first_wave_core"
    assert gate["evidence"]["coverage_end"] == "2026-03-20"


def test_evaluate_etf_beta_sleeve_passes_when_phase1_scope_and_budget_are_traceable() -> None:
    gate = evaluate_etf_beta_sleeve(
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 8, "closed_trades": 4},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "universe": {
                "asset_scope": "cn_etf",
                "preset_id": "cn_etf_first_wave_core",
                "etf_batch": "cn_etf_first_wave_core",
                "etf_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "coverage_start": "2013-01-04",
                "coverage_end": "2026-03-20",
                "daily_table": "pams_cn_etf_daily",
                "price_series_semantics": "executable_price_only_not_total_return",
            },
            "etf_beta": {
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "source_preset_id": "cn_etf_first_wave_core",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "research_rule_family": "phase1_allocation_engine_v1",
                "exposure_policy_family": "phase1_governed_allocation_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "layering_policy": "none",
                "layering_band": None,
                "layering_active": False,
                "layering_reason_codes": [],
                "absolute_filter_mode": "none",
                "fallback_mode": "none",
                "allocation_engine_mode": "phase1_three_bucket_v1",
                "bucket_policy_profile": "phase1_state_template_v1",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "formal_alignment_reference": "A鑲TF瀛愮郴缁熺瓥鐣ユ€濊矾md",
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_alignment_reason_codes": [],
                "formal_alignment_evidence": {"reference_doc": "A鑲TF瀛愮郴缁熺瓥鐣ユ€濊矾md"},
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "selected_etfs": ["510300.SH", "510500.SH", "510050.SH", "511010.SH"],
                "selection_reason_codes": {
                    "510300.SH": ["PHASE1_FORMAL_SCOPE"],
                    "510500.SH": ["PHASE1_FORMAL_SCOPE"],
                    "510050.SH": ["PHASE1_FORMAL_SCOPE"],
                    "511010.SH": ["PHASE1_FORMAL_SCOPE"],
                },
                "requested_budget": 0.7,
                "applied_budget": 0.7,
                "cash_weight": 0.14,
                "defense_weight": 0.0,
                "equity_core_bucket": 0.8,
                "defense_tilt_bucket": 0.0,
                "cash_buffer_bucket": 0.2,
                "targets": {
                    "510300.SH": 0.294,
                    "510500.SH": 0.161,
                    "510050.SH": 0.175,
                    "512100.SH": 0.070,
                },
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {
                    "coverage_start": "2013-01-04",
                    "coverage_end": "2026-03-20",
                    "daily_table": "pams_cn_etf_daily",
                    "price_series_semantics": "executable_price_only_not_total_return",
                },
                "sleeve_budget_used": {
                    "budget_owner": "global_portfolio_governor",
                    "total_risk_budget": 0.7,
                    "slot_cap": 4,
                    "selected_count": 2,
                },
                "governor_boundary": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "requested_budget": 0.7,
                    "applied_budget": 0.7,
                },
                "local_policy_decision": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "boundary_state": "ACTIVE",
                    "boundary_reason_codes": [
                        "BOUNDARY_POLICY::FORMAL_PHASE1_DOCUMENT_ALIGNED_V1",
                        "LOCAL_BOUNDARY_STATE::ACTIVE",
                    ],
                    "allocation_engine_mode": "phase1_three_bucket_v1",
                    "bucket_policy_profile": "phase1_state_template_v1",
                    "targets": {
                        "510300.SH": 0.294,
                        "510500.SH": 0.161,
                        "510050.SH": 0.175,
                        "512100.SH": 0.070,
                    },
                    "cash_weight": 0.14,
                    "defense_weight": 0.0,
                },
            },
        }
    )

    assert gate is not None
    assert gate["status"] == "PASS"
    assert gate["metrics"]["eligible_count"] == 5
    assert gate["metrics"]["out_of_scope_count"] == 0
    assert gate["metrics"]["order_count"] == 8
    assert gate["metrics"]["trade_count"] == 4
    assert gate["metrics"]["formal_alignment_status"] == "formal_mainline"
    assert gate["metrics"]["formal_mainline_compatible"] is True
    assert gate["metrics"]["boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert gate["evidence"]["relative_strength_windows"]["mid"] == 126
    assert gate["evidence"]["absolute_filter_mode"] == "none"
    assert gate["evidence"]["strategy_role"] == "phase1_allocation_engine"
    assert gate["evidence"]["boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert gate["evidence"]["formal_alignment_reference"] == "A鑲TF瀛愮郴缁熺瓥鐣ユ€濊矾md"


def test_evaluate_etf_beta_sleeve_attributes_zero_deploy_to_governor_boundary() -> None:
    gate = evaluate_etf_beta_sleeve(
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 1, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_alignment_reason_codes": [],
                "formal_alignment_evidence": {"reference_doc": CN_ETF_FORMAL_ALIGNMENT_REFERENCE},
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "selected_etfs": [],
                "selection_reason_codes": {},
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "requested_budget": 0.0,
                "applied_budget": 0.0,
                "targets": {},
                "governor_hard_blocked": True,
                "governor_hard_block_reason_codes": ["GOVERNOR_ZERO_REQUESTED_BUDGET"],
                "local_boundary_state": "GOVERNOR_HARD_BLOCK",
                "local_boundary_reason_codes": ["LOCAL_BOUNDARY_STATE::GOVERNOR_HARD_BLOCK"],
                "governor_boundary": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "hard_blocked": True,
                    "hard_block_reason_codes": ["GOVERNOR_ZERO_REQUESTED_BUDGET"],
                    "requested_budget": 0.0,
                    "applied_budget": 0.0,
                },
                "local_policy_decision": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "boundary_state": "GOVERNOR_HARD_BLOCK",
                    "boundary_reason_codes": ["LOCAL_BOUNDARY_STATE::GOVERNOR_HARD_BLOCK"],
                    "targets": {},
                },
                "sleeve_budget_used": {"budget_owner": "global_portfolio_governor", "slot_cap": 0},
            },
        }
    )

    assert gate is not None
    assert gate["metrics"]["zero_deploy_owner"] == "governor_boundary"
    assert gate["evidence"]["boundary_attribution"]["zero_deploy_owner"] == "governor_boundary"


def test_evaluate_etf_beta_sleeve_attributes_reduced_allocation_to_local_boundary() -> None:
    gate = evaluate_etf_beta_sleeve(
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 6, "closed_trades": 3},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_alignment_reason_codes": [],
                "formal_alignment_evidence": {"reference_doc": CN_ETF_FORMAL_ALIGNMENT_REFERENCE},
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "selected_etfs": ["510050.SH"],
                "selection_reason_codes": {"510050.SH": ["PHASE1_FORMAL_SCOPE"]},
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "requested_budget": 0.25,
                "applied_budget": 0.25,
                "targets": {"510050.SH": 0.1375, "511010.SH": 0.0375},
                "local_boundary_state": "REDUCED_ALLOCATION",
                "local_boundary_reason_codes": [
                    "BOUNDARY_POLICY::FORMAL_PHASE1_DOCUMENT_ALIGNED_V1",
                    "LOCAL_BOUNDARY_STATE::REDUCED_ALLOCATION",
                    "PHASE1_DOCUMENT_REDUCED_ALLOCATION",
                ],
                "governor_boundary": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "hard_blocked": False,
                    "requested_budget": 0.25,
                    "applied_budget": 0.25,
                },
                "local_policy_decision": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "boundary_state": "REDUCED_ALLOCATION",
                    "boundary_reason_codes": [
                        "BOUNDARY_POLICY::FORMAL_PHASE1_DOCUMENT_ALIGNED_V1",
                        "LOCAL_BOUNDARY_STATE::REDUCED_ALLOCATION",
                        "PHASE1_DOCUMENT_REDUCED_ALLOCATION",
                    ],
                    "targets": {"510050.SH": 0.1375, "511010.SH": 0.0375},
                },
                "sleeve_budget_used": {"budget_owner": "global_portfolio_governor", "slot_cap": 1},
            },
        }
    )

    assert gate is not None
    assert gate["metrics"]["reduced_allocation_owner"] == "local_boundary_decision"
    assert gate["evidence"]["boundary_attribution"]["reduced_allocation_owner"] == "local_boundary_decision"


def test_evaluate_etf_beta_sleeve_fails_when_smoke_has_zero_orders_or_trades() -> None:
    gate = evaluate_etf_beta_sleeve(
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 0, "closed_trades": 0},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "source_entry_type": "cn_etf_research_entry",
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "eligible_etfs": ["510300.SH"],
                "selected_etfs": [],
                "selection_reason_codes": {},
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "sleeve_budget_used": {"budget_owner": "global_portfolio_governor", "slot_cap": 2},
            },
        }
    )

    assert gate is not None
    assert gate["status"] == "FAIL"
    assert gate["metrics"]["order_count"] == 0
    assert gate["metrics"]["trade_count"] == 0


def test_evaluate_etf_beta_sleeve_warns_when_deployment_is_traceable_but_underdeployed(tmp_path) -> None:
    root = tmp_path / "exp_etf_underdeploy"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "gross_exposure": 0.0,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.0,
                "etf_actual_risk_exposure": 0.0,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.2,
                "governor_budget_json": json.dumps(
                    {
                        "target_exposure": 0.2,
                        "min_deployable_exposure": 0.1,
                        "fallback_allowed": False,
                        "layering_band": "LIGHT_ACCUMULATE",
                        "under_deploy_reason_codes": ["ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER"],
                    },
                    ensure_ascii=False,
                ),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "deployability_gap": 0.2,
                        "absolute_filter_reject_count": 2,
                        "absolute_filter_reject_reason_counts": {
                            "ABSOLUTE_MA200_NOT_ABOVE": 2,
                        },
                        "candidate_pool_reject_reason_counts": {
                            "POOL_PROFILE_EXCLUDED::DIVIDEND_STANDARD": 1,
                        },
                        "selection_chain_winner_counts": {
                            "eligible_after_selection_chain": 0,
                        },
                        "selection_chain_reject_reason_counts": {},
                    },
                ),
            },
            {
                "date": "2026-03-19",
                "gross_exposure": 0.05,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.05,
                "etf_actual_risk_exposure": 0.05,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.15,
                "governor_budget_json": json.dumps(
                    {
                        "target_exposure": 0.2,
                        "min_deployable_exposure": 0.1,
                        "fallback_allowed": False,
                        "layering_band": "CONTROLLED_TRANS_DOWN",
                        "under_deploy_reason_codes": ["ETF_BETA_UNDERFILLED_DEPLOYMENT"],
                    },
                    ensure_ascii=False,
                ),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "deployability_gap": 0.15,
                        "absolute_filter_reject_count": 1,
                        "absolute_filter_reject_reason_counts": {
                            "ABSOLUTE_RET12_NON_POSITIVE": 1,
                        },
                        "selection_chain_winner_counts": {
                            "eligible_after_selection_chain": 1,
                            "selected_count": 1,
                        },
                        "selection_chain_reject_reason_counts": {
                            "SELECTION_CHAIN_RANK_BELOW_CUTOFF": 1,
                        },
                    },
                ),
            },
            {
                "date": "2026-03-20",
                "gross_exposure": 0.08,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.08,
                "etf_actual_risk_exposure": 0.08,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.12,
                "governor_budget_json": json.dumps(
                    {
                        "target_exposure": 0.2,
                        "min_deployable_exposure": 0.1,
                        "fallback_allowed": False,
                        "layering_band": "CONTROLLED_TRANS_DOWN",
                        "under_deploy_reason_codes": ["ETF_BETA_UNDERFILLED_DEPLOYMENT"],
                    },
                    ensure_ascii=False,
                ),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "deployability_gap": 0.12,
                        "absolute_filter_reject_count": 0,
                        "selection_chain_winner_counts": {
                            "eligible_after_selection_chain": 1,
                            "selected_count": 1,
                        },
                        "selection_chain_reject_reason_counts": {
                            "SELECTION_CHAIN_RANK_BELOW_CUTOFF": 2,
                        },
                    },
                ),
            },
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {"date": "2026-03-19", "reason_code": "ETF_BETA_WEEKLY_RS"},
            {"date": "2026-03-20", "reason_code": "ETF_BETA_REBALANCE_EXIT"},
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 2, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510050.SH"],
                    "limited_defense_candidates": [],
                }
            },
            "etf_beta": {
                "source_entry_type": "cn_etf_research_entry",
                "formal_core_beta_symbols": ["510300.SH", "510050.SH"],
                "limited_defense_candidates": [],
                "input_etfs": ["510300.SH", "510050.SH"],
                "eligible_etfs": ["510300.SH"],
                "selected_etfs": ["510300.SH"],
                "selection_reason_codes": {
                    "510300.SH": ["FORMAL_CORE_BETA"],
                },
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "absolute_filter_profile": "ma200_ret12",
                "candidate_pool_profile": "a0_proxy_pool",
                "selection_chain_profile": "global_top2_12_6_3",
                "exposure_policy_family": "broad_based_governed_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "layering_policy": "light_trans_down_accumulate",
                "layering_band": "CONTROLLED_TRANS_DOWN",
                "layering_active": True,
                "layering_reason_codes": ["ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN"],
                "target_selected_count_source": "state_target_selected_count",
                "fallback_allowed_source": "state_fallback_allowed",
                "target_exposure": 0.2,
                "min_deployable_exposure": 0.1,
                "fallback_allowed": False,
                "under_deploy_reason_codes": ["ETF_BETA_UNDERFILLED_DEPLOYMENT"],
                "sleeve_budget_used": {
                    "budget_owner": "global_portfolio_governor",
                    "slot_cap": 2,
                    "target_exposure": 0.2,
                    "min_deployable_exposure": 0.1,
                    "fallback_allowed": False,
                    "layering_band": "CONTROLLED_TRANS_DOWN",
                    "under_deploy_reason_codes": ["ETF_BETA_UNDERFILLED_DEPLOYMENT"],
                },
            },
        },
    )

    assert gate is not None
    assert gate["status"] == "WARN"
    assert gate["metrics"]["avg_target_exposure"] == pytest.approx(0.2)
    assert gate["metrics"]["avg_actual_exposure"] == 0.043333333333333335
    assert gate["metrics"]["median_actual_exposure"] == pytest.approx(0.05)
    assert gate["metrics"]["avg_actual_risk_exposure"] == pytest.approx(0.043333333333333335)
    assert gate["metrics"]["avg_actual_fallback_exposure"] == pytest.approx(0.0)
    assert gate["metrics"]["avg_deployability_gap"] == pytest.approx(0.15666666666666668)
    assert gate["metrics"]["avg_actual_exposure_on_invested_days"] == 0.065
    assert gate["metrics"]["invested_day_count"] == 2
    assert gate["metrics"]["empty_day_ratio"] == pytest.approx(1.0 / 3.0)
    assert gate["metrics"]["below_30_ratio"] == pytest.approx(1.0)
    assert gate["metrics"]["signal_count"] == 0
    assert gate["metrics"]["fallback_buy_count"] == 0
    assert gate["metrics"]["unfilled_order_count"] == 1
    assert gate["metrics"]["deployment_assessment"] == "UNDERDEPLOYED"
    assert gate["metrics"]["under_deploy_reason_counts"]["ETF_BETA_UNDERFILLED_DEPLOYMENT"] == 2
    assert gate["metrics"]["absolute_filter_reject_day_count"] == 2
    assert gate["metrics"]["absolute_filter_reject_reason_counts"]["ABSOLUTE_MA200_NOT_ABOVE"] == 2
    assert gate["metrics"]["selection_chain_reject_reason_counts"]["SELECTION_CHAIN_RANK_BELOW_CUTOFF"] == 3
    assert gate["metrics"]["primary_bottleneck_layer"] == "absolute_filter"
    assert gate["metrics"]["layering_band_counts"]["CONTROLLED_TRANS_DOWN"] == 2
    assert gate["metrics"]["layering_band_counts"]["LIGHT_ACCUMULATE"] == 1
    assert gate["evidence"]["layering_band"] == "CONTROLLED_TRANS_DOWN"
    assert gate["evidence"]["exposure_policy_family"] == "broad_based_governed_v1"
    assert gate["evidence"]["absolute_filter_profile"] == "ma200_ret12"


def test_evaluate_etf_beta_sleeve_passes_formal_stabilizer_when_invested_day_deployment_is_sufficient(tmp_path) -> None:
    root = tmp_path / "exp_etf_formal_stabilizer_traceable"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "gross_exposure": 0.0,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.0,
                "etf_actual_risk_exposure": 0.0,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_actual_core_exposure": 0.0,
                "etf_actual_defense_exposure": 0.0,
                "etf_deployability_gap": 0.2,
                "governor_budget_json": json.dumps({"target_exposure": 0.2}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={
                        "strategy_role": "strategic_beta_stabilizer",
                        "governor_boundary_mode": "consume_governor_sleeve_budget",
                        "local_policy_mode": "phase1_bucket_allocation",
                        "source_entry_type": "cn_etf_phase1_allocation_entry",
                    },
                    research={"execution_path": "hold_until_rebalance"},
                ),
            },
            {
                "date": "2026-03-19",
                "gross_exposure": 0.12,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.12,
                "etf_actual_risk_exposure": 0.12,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_actual_core_exposure": 0.05,
                "etf_actual_defense_exposure": 0.07,
                "etf_deployability_gap": 0.08,
                "governor_budget_json": json.dumps({"target_exposure": 0.2}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={
                        "strategy_role": "strategic_beta_stabilizer",
                        "governor_boundary_mode": "consume_governor_sleeve_budget",
                        "local_policy_mode": "phase1_bucket_allocation",
                        "source_entry_type": "cn_etf_phase1_allocation_entry",
                    },
                    research={"execution_path": "monthly_rebalance"},
                ),
            },
            {
                "date": "2026-03-20",
                "gross_exposure": 0.11,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.11,
                "etf_actual_risk_exposure": 0.11,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_actual_core_exposure": 0.04,
                "etf_actual_defense_exposure": 0.07,
                "etf_deployability_gap": 0.09,
                "governor_budget_json": json.dumps({"target_exposure": 0.2}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={
                        "strategy_role": "strategic_beta_stabilizer",
                        "governor_boundary_mode": "consume_governor_sleeve_budget",
                        "local_policy_mode": "phase1_bucket_allocation",
                        "source_entry_type": "cn_etf_phase1_allocation_entry",
                    },
                    research={"execution_path": "hold_until_rebalance"},
                ),
            },
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {"date": "2026-03-19", "reason_code": "ETF_BETA_BIWEEKLY_RS"},
            {"date": "2026-03-20", "reason_code": "ETF_BETA_PHASE1_REBALANCE_RESET"},
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 2, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "strategy_role": "strategic_beta_stabilizer",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "formal_alignment_reference": CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_alignment_reason_codes": [],
                "formal_alignment_evidence": {
                    "reference_doc": CN_ETF_FORMAL_ALIGNMENT_REFERENCE,
                    "formal_etf_pool_version": "formal_etf_pool_v1",
                    "formal_phase1_core_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "formal_phase1_limited_defense_candidates": ["511010.SH"],
                    "formal_phase1_excluded_symbols": ["518880.SH", "588000.SH", "512890.SH"],
                },
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "511010.SH"],
                "selected_etfs": ["510300.SH", "511010.SH"],
                "selection_reason_codes": {
                    "510300.SH": ["PHASE1_FORMAL_SCOPE"],
                    "511010.SH": ["PHASE1_FORMAL_SCOPE"],
                },
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "target_exposure": 0.2,
                "min_deployable_exposure": 0.0,
                "fallback_allowed": False,
                "research_view": {
                    "execution_path": "hold_until_rebalance",
                    "requested_budget": 0.2,
                    "applied_budget": 0.2,
                },
                "governor_boundary": {"hard_blocked": False, "reason_codes": []},
                "local_policy_decision": {
                    "boundary_state": "REDUCED_ALLOCATION",
                    "reason_codes": ["PHASE1_DOCUMENT_REDUCED_ALLOCATION"],
                },
            },
        },
    )

    assert gate is not None
    assert gate["status"] == "PASS"
    assert gate["metrics"]["deployment_assessment"] == "TRACEABLE"
    assert gate["metrics"]["avg_actual_exposure"] == pytest.approx(0.07666666666666666)
    assert gate["metrics"]["avg_actual_exposure_on_invested_days"] == pytest.approx(0.115)


def test_evaluate_etf_beta_sleeve_separates_bull_and_trans_up_pace_bottlenecks(tmp_path) -> None:
    root = tmp_path / "exp_etf_bull_trans_up_bottleneck"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "effective_state_5": "BULL",
                "effective_max_positions": 2,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.0,
                "governor_budget_json": json.dumps({"target_exposure": 0.2}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "strategic_floor_cap": 0.108,
                        "tactical_overlay_cap": 0.072,
                        "deployment_pace": 0.144,
                        "bull_partial_overlay_pace_ratio": 0.5,
                        "bull_pace_mode": "partial_overlay_v1",
                        "pace_policy_gap": 0.056,
                        "rebalance_timing_gap": 0.144,
                        "execution_residual_gap": 0.0,
                        "execution_path": "hold_until_rebalance",
                    }
                ),
            },
            {
                "date": "2026-03-19",
                "effective_state_5": "BULL",
                "effective_max_positions": 2,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.18,
                "governor_budget_json": json.dumps({"target_exposure": 0.2}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "strategic_floor_cap": 0.108,
                        "tactical_overlay_cap": 0.072,
                        "deployment_pace": 0.144,
                        "bull_partial_overlay_pace_ratio": 0.5,
                        "bull_pace_mode": "partial_overlay_v1",
                        "pace_policy_gap": 0.056,
                        "rebalance_timing_gap": 0.0,
                        "execution_residual_gap": 0.0,
                        "execution_path": "monthly_rebalance",
                    }
                ),
            },
            {
                "date": "2026-03-20",
                "effective_state_5": "TRANS_UP",
                "effective_max_positions": 1,
                "etf_target_exposure": 0.1,
                "etf_actual_exposure": 0.0527,
                "governor_budget_json": json.dumps({"target_exposure": 0.1}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "strategic_floor_cap": 0.0527,
                        "tactical_overlay_cap": 0.0,
                        "deployment_pace": 0.0527,
                        "bull_partial_overlay_pace_ratio": None,
                        "bull_pace_mode": "",
                        "pace_policy_gap": 0.0473,
                        "rebalance_timing_gap": 0.0,
                        "execution_residual_gap": 0.0,
                        "execution_path": "trans_up_state_change_redeploy",
                    }
                ),
            },
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-03-19",
                "side": "BUY",
                "symbol": "sh510300",
                "reason_code": "ETF_BETA_MONTHLY_RS",
                "meta_json": json.dumps(
                    {
                        "sleeve_id": "cn_etf_beta",
                        "state_5": "BULL",
                        "execution_path": "monthly_rebalance",
                        "target_weight": 0.18,
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "date": "2026-03-20",
                "side": "BUY",
                "symbol": "sh510300",
                "reason_code": "ETF_BETA_TRANS_UP_REDEPLOY",
                "meta_json": json.dumps(
                    {
                        "sleeve_id": "cn_etf_beta",
                        "state_5": "TRANS_UP",
                        "execution_path": "trans_up_state_change_redeploy",
                        "target_weight": 0.0527,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 2, "closed_trades": 2},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "strategy_role": "strategic_beta_stabilizer",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_alignment_reason_codes": [],
                "formal_alignment_evidence": {"reference_doc": CN_ETF_FORMAL_ALIGNMENT_REFERENCE},
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "selected_etfs": ["510300.SH"],
                "selection_reason_codes": {"510300.SH": ["PHASE1_FORMAL_SCOPE"]},
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "sleeve_budget_used": {"budget_owner": "global_portfolio_governor", "slot_cap": 2},
                "governor_boundary": {"boundary_policy_mode": "formal_phase1_document_aligned_v1"},
                "local_policy_decision": {"boundary_policy_mode": "formal_phase1_document_aligned_v1"},
            },
        },
    )

    assert gate is not None
    assert gate["metrics"]["avg_pace_policy_gap"] == pytest.approx((0.056 + 0.056 + 0.0473) / 3.0)
    assert gate["metrics"]["avg_rebalance_timing_gap"] == pytest.approx(0.144 / 3.0)
    assert gate["metrics"]["avg_execution_residual_gap"] == pytest.approx(0.0)

    summary = gate["metrics"]["bull_trans_up_bottleneck_summary"]
    assert summary["BULL"]["day_count"] == 2
    assert summary["BULL"]["avg_target_exposure"] == pytest.approx(0.2)
    assert summary["BULL"]["avg_deployment_pace"] == pytest.approx(0.144)
    assert summary["BULL"]["bull_partial_overlay_pace_ratio"] == pytest.approx(0.5)
    assert summary["BULL"]["bull_pace_mode"] == "partial_overlay_v1"
    assert summary["BULL"]["avg_pace_policy_gap"] == pytest.approx(0.056)
    assert summary["BULL"]["avg_rebalance_timing_gap"] == pytest.approx(0.072)
    assert summary["BULL"]["positive_target_zero_actual_days"] == 1
    assert summary["BULL"]["execution_path_day_counts"] == {
        "hold_until_rebalance": 1,
        "monthly_rebalance": 1,
    }
    assert summary["BULL"]["buy_count"] == 1
    assert summary["BULL"]["buy_execution_path_counts"] == {"monthly_rebalance": 1}

    assert summary["TRANS_UP"]["day_count"] == 1
    assert summary["TRANS_UP"]["avg_target_exposure"] == pytest.approx(0.1)
    assert summary["TRANS_UP"]["avg_actual_exposure"] == pytest.approx(0.0527)
    assert summary["TRANS_UP"]["avg_tactical_overlay_target"] == pytest.approx(0.0)
    assert summary["TRANS_UP"]["bull_partial_overlay_pace_ratio"] is None
    assert summary["TRANS_UP"]["bull_pace_mode"] is None
    assert summary["TRANS_UP"]["avg_pace_policy_gap"] == pytest.approx(0.0473)
    assert summary["TRANS_UP"]["execution_path_day_counts"] == {"trans_up_state_change_redeploy": 1}
    assert summary["TRANS_UP"]["buy_reason_code_counts"] == {"ETF_BETA_TRANS_UP_REDEPLOY": 1}


def test_evaluate_etf_beta_sleeve_fails_when_orders_and_daily_targets_drift(tmp_path) -> None:
    root = tmp_path / "exp_etf_target_drift"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "gross_exposure": 0.2,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.18,
                "etf_actual_risk_exposure": 0.18,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.02,
                "governor_budget_json": json.dumps({"target_exposure": 0.2}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={"target_exposure": 0.2},
                    research={"requested_budget": 0.2, "applied_budget": 0.2},
                ),
            }
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "symbol": "sh510300",
                "reason_code": "ETF_BETA_MONTHLY_RS",
                "meta_json": json.dumps(
                    {
                        "alpha_id": "cn_etf_beta",
                        "sleeve_id": "cn_etf_beta",
                        "target_weight": 0.18,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 1, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "selected_etfs": ["510300.SH", "510500.SH"],
                "selection_reason_codes": {
                    "510300.SH": ["PHASE1_FORMAL_SCOPE"],
                    "510500.SH": ["PHASE1_FORMAL_SCOPE"],
                },
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "requested_budget": 0.2,
                "applied_budget": 0.2,
                "target_exposure": 0.2,
                "min_deployable_exposure": 0.0,
                "fallback_allowed": False,
                "governor_boundary": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "requested_budget": 0.2,
                    "applied_budget": 0.2,
                    "target_exposure": 0.2,
                },
                "local_policy_decision": {
                    "allocation_engine_mode": "phase1_three_bucket_v1",
                    "bucket_policy_profile": "phase1_state_template_v1",
                },
            },
        },
    )

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["target_contract_drift_detected"] is True
    assert gate["metrics"]["target_contract_drift_day_count"] == 1
    drift_example = gate["evidence"]["deployment_evidence"]["target_contract_drift_examples"][0]
    assert drift_example["order_target_weight"] == pytest.approx(0.18)
    assert drift_example["portfolio_daily_target_exposure"] == pytest.approx(0.2)


def test_evaluate_etf_beta_sleeve_uses_signal_date_for_next_open_target_reconciliation(tmp_path) -> None:
    root = tmp_path / "exp_etf_target_signal_date"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "gross_exposure": 0.2,
                "etf_target_exposure": 0.2,
                "etf_actual_exposure": 0.18,
                "etf_actual_risk_exposure": 0.18,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.02,
                "governor_budget_json": json.dumps({"target_exposure": 0.2}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={"target_exposure": 0.2},
                    research={"requested_budget": 0.2, "applied_budget": 0.2},
                ),
            },
            {
                "date": "2026-03-19",
                "gross_exposure": 0.1,
                "etf_target_exposure": 0.1,
                "etf_actual_exposure": 0.19,
                "etf_actual_risk_exposure": 0.19,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.09,
                "governor_budget_json": json.dumps({"target_exposure": 0.1}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={"target_exposure": 0.1},
                    research={"requested_budget": 0.1, "applied_budget": 0.1},
                ),
            },
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-03-19",
                "symbol": "sh510300",
                "reason_code": "ETF_BETA_MONTHLY_RS",
                "meta_json": json.dumps(
                    {
                        "alpha_id": "cn_etf_beta",
                        "sleeve_id": "cn_etf_beta",
                        "signal_date": "2026-03-18",
                        "scheduled_date": "2026-03-19",
                        "target_weight": 0.2,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 1, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "strategy_role": "phase1_allocation_engine",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "selected_etfs": ["510300.SH", "510500.SH"],
                "selection_reason_codes": {
                    "510300.SH": ["PHASE1_FORMAL_SCOPE"],
                    "510500.SH": ["PHASE1_FORMAL_SCOPE"],
                },
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "requested_budget": 0.2,
                "applied_budget": 0.2,
                "target_exposure": 0.2,
                "min_deployable_exposure": 0.0,
                "fallback_allowed": False,
                "governor_boundary": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "requested_budget": 0.2,
                    "applied_budget": 0.2,
                    "target_exposure": 0.2,
                },
                "local_policy_decision": {
                    "allocation_engine_mode": "phase1_three_bucket_v1",
                    "bucket_policy_profile": "phase1_state_template_v1",
                },
            },
        },
    )

    assert gate["status"] in {"PASS", "WARN"}
    assert gate["metrics"]["target_contract_drift_detected"] is False
    assert gate["metrics"]["target_contract_drift_day_count"] == 0
    assert "target_contract_drift_examples" not in gate["evidence"]["deployment_evidence"]


def test_evaluate_etf_beta_sleeve_treats_trans_up_single_seat_core_recovery_as_contract_truth(tmp_path) -> None:
    root = tmp_path / "exp_etf_trans_up_core_recovery"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "gross_exposure": 0.0527,
                "etf_target_exposure": 0.1,
                "etf_actual_exposure": 0.0527,
                "etf_actual_risk_exposure": 0.0527,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_actual_core_exposure": 0.0527,
                "etf_actual_satellite_exposure": 0.0,
                "etf_actual_defense_exposure": 0.0,
                "etf_deployability_gap": 0.0473,
                "governor_budget_json": json.dumps(
                    {
                        "target_exposure": 0.1,
                        "strategic_floor_cap": 0.0527,
                        "tactical_overlay_cap": 0.0,
                        "deployment_pace": 0.0527,
                        "trans_up_contract_mode": "single_seat_core_recovery",
                        "trans_up_single_seat_core_recovery": True,
                    },
                    ensure_ascii=False,
                ),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={"target_exposure": 0.1, "targets": {"510300.SH": 0.0527}},
                    research={
                        "requested_budget": 0.1,
                        "applied_budget": 0.1,
                        "strategic_floor_cap": 0.0527,
                        "tactical_overlay_cap": 0.0,
                        "limited_defense_cap": 0.0,
                        "deployment_pace": 0.0527,
                        "trans_up_contract_mode": "single_seat_core_recovery",
                        "trans_up_single_seat_core_recovery": True,
                    },
                ),
            }
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-03-19",
                "symbol": "sh510300",
                "reason_code": "ETF_BETA_TRANS_UP_REDEPLOY",
                "meta_json": json.dumps(
                    {
                        "alpha_id": "cn_etf_beta",
                        "sleeve_id": "cn_etf_beta",
                        "signal_date": "2026-03-18",
                        "target_weight": 0.0527,
                        "trans_up_contract_mode": "single_seat_core_recovery",
                        "trans_up_single_seat_core_recovery": True,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 1, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "strategy_role": "strategic_beta_stabilizer",
                "source_entry_type": "cn_etf_phase1_allocation_entry",
                "governor_boundary_mode": "consume_governor_sleeve_budget",
                "local_policy_mode": "phase1_bucket_allocation",
                "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                "formal_alignment_status": "formal_mainline",
                "formal_mainline_compatible": True,
                "formal_alignment_evidence": {"reference_doc": CN_ETF_FORMAL_ALIGNMENT_REFERENCE},
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "selected_etfs": ["510300.SH"],
                "selection_reason_codes": {"510300.SH": ["PHASE1_FORMAL_SCOPE", "TRANS_UP_SINGLE_SEAT_CORE_RECOVERY"]},
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "requested_budget": 0.1,
                "applied_budget": 0.1,
                "targets": {"510300.SH": 0.0527},
                "target_exposure": 0.1,
                "trans_up_contract_mode": "single_seat_core_recovery",
                "trans_up_single_seat_core_recovery": True,
                "governor_boundary": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "requested_budget": 0.1,
                    "applied_budget": 0.1,
                    "target_exposure": 0.1,
                    "trans_up_contract_mode": "single_seat_core_recovery",
                    "trans_up_single_seat_core_recovery": True,
                },
                "local_policy_decision": {
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "boundary_state": "ACTIVE",
                    "boundary_reason_codes": [
                        "BOUNDARY_POLICY::FORMAL_PHASE1_DOCUMENT_ALIGNED_V1",
                        "LOCAL_BOUNDARY_STATE::ACTIVE",
                        "TRANS_UP_SINGLE_SEAT_CORE_RECOVERY",
                    ],
                    "targets": {"510300.SH": 0.0527},
                    "trans_up_contract_mode": "single_seat_core_recovery",
                    "trans_up_single_seat_core_recovery": True,
                },
                "sleeve_budget_used": {
                    "budget_owner": "global_portfolio_governor",
                    "slot_cap": 1,
                    "target_exposure": 0.1,
                    "strategic_floor_cap": 0.0527,
                    "tactical_overlay_cap": 0.0,
                    "deployment_pace": 0.0527,
                    "trans_up_contract_mode": "single_seat_core_recovery",
                    "trans_up_single_seat_core_recovery": True,
                },
            },
        },
    )

    assert gate is not None
    assert gate["status"] in {"PASS", "WARN"}
    assert gate["evidence"]["trans_up_contract_mode"] == "single_seat_core_recovery"
    assert gate["evidence"]["trans_up_single_seat_core_recovery"] is True
    assert gate["metrics"]["tactical_overlay_target"] == pytest.approx(0.0)
    assert gate["metrics"]["avg_actual_satellite_exposure"] == pytest.approx(0.0)
    assert gate["metrics"]["target_contract_drift_detected"] is False


def test_evaluate_etf_beta_sleeve_uses_final_target_weight_for_standalone_delta_orders(tmp_path) -> None:
    root = tmp_path / "exp_etf_standalone_delta_final_target"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "gross_exposure": 1.0,
                "etf_target_exposure": 1.0,
                "etf_actual_exposure": 0.8,
                "etf_actual_risk_exposure": 0.8,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.2,
                "governor_budget_json": json.dumps({"target_exposure": 1.0}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={"target_exposure": 1.0, "targets": {"510300.SH": 1.0}},
                    research={
                        "requested_budget": 1.0,
                        "applied_budget": 1.0,
                        "target_exposure": 1.0,
                        "execution_path": "bull_inter_rebalance_deploy",
                    },
                ),
            }
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-03-19",
                "symbol": "sh510300",
                "reason_code": "ETF_BETA_BULL_INTER_REBALANCE_DEPLOY_ACTIVE",
                "meta_json": json.dumps(
                    {
                        "alpha_id": "cn_etf_beta",
                        "sleeve_id": "cn_etf_beta",
                        "signal_date": "2026-03-18",
                        "execution_path": "bull_inter_rebalance_deploy",
                        "target_weight": 0.2,
                        "final_target_weight": 1.0,
                        "target_weight_basis": "delta_deploy_gap",
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 1, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "strategy_role": "governed_broad_based_standalone_mainline",
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "governor_boundary_mode": "consume_governor_state_and_budget",
                "local_policy_mode": "broad_based_rotation_mainline",
                "boundary_policy_mode": "legacy_state_slot_caps_v1",
                "formal_alignment_status": "research_only",
                "formal_mainline_compatible": False,
                "formal_core_beta_symbols": ["510300.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510300.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "511010.SH"],
                "selected_etfs": ["510300.SH"],
                "selection_reason_codes": {"510300.SH": ["ETF_BETA_CORE_SCOPE"]},
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "requested_budget": 1.0,
                "applied_budget": 1.0,
                "target_exposure": 1.0,
                "min_deployable_exposure": 0.45,
                "fallback_allowed": True,
                "governor_boundary": {"target_exposure": 1.0},
                "local_policy_decision": {"targets": {"510300.SH": 1.0}},
            },
        },
    )

    assert gate["metrics"]["target_contract_drift_detected"] is False
    assert gate["metrics"]["target_contract_drift_day_count"] == 0
    assert "target_contract_drift_examples" not in gate["evidence"]["deployment_evidence"]


def test_evaluate_etf_beta_sleeve_ignores_full_fallback_replacement_when_final_target_matches_live_target(tmp_path) -> None:
    root = tmp_path / "exp_etf_standalone_full_fallback_replacement"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2016-07-12",
                "gross_exposure": 1.0,
                "etf_target_exposure": 1.0,
                "etf_actual_exposure": 0.0,
                "etf_actual_risk_exposure": 0.0,
                "etf_actual_fallback_exposure": 0.0,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 1.0,
                "governor_budget_json": json.dumps({"target_exposure": 1.0}, ensure_ascii=False),
                "diagnostics_input_json": _etf_diag_payload(
                    formal={
                        "target_exposure": 1.0,
                        "targets": {
                            "510050.SH": 0.2,
                            "510300.SH": 0.4,
                            "510500.SH": 0.3,
                            "512100.SH": 0.1,
                        },
                    },
                    research={
                        "requested_budget": 1.0,
                        "applied_budget": 1.0,
                        "target_exposure": 1.0,
                        "execution_path": "bull_inter_rebalance_deploy",
                    },
                ),
            }
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2016-07-13",
                "symbol": "sh511010",
                "reason_code": "ETF_BETA_FALLBACK_BUY",
                "meta_json": json.dumps(
                    {
                        "alpha_id": "cn_etf_beta",
                        "sleeve_id": "cn_etf_beta",
                        "signal_date": "2016-07-12",
                        "execution_path": "bull_inter_rebalance_deploy",
                        "target_weight": 0.9988983032646169,
                        "requested_target_weight": 1.0,
                        "final_target_weight": 1.0,
                        "target_weight_basis": "delta_deploy_gap",
                        "target_exposure": 1.0,
                        "selection_reason_codes": [
                            "ETF_BETA_FALLBACK_SINGLE_SYMBOL",
                            "FALLBACK_SYMBOL::511010.SH",
                            "STATE::BULL",
                        ],
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 1, "closed_trades": 1},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510050.SH", "510300.SH", "510500.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                }
            },
            "etf_beta": {
                "strategy_role": "governed_broad_based_standalone_mainline",
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "governor_boundary_mode": "consume_governor_state_and_budget",
                "local_policy_mode": "broad_based_rotation_mainline",
                "boundary_policy_mode": "legacy_state_slot_caps_v1",
                "formal_alignment_status": "research_only",
                "formal_mainline_compatible": False,
                "formal_core_beta_symbols": ["510050.SH", "510300.SH", "510500.SH", "512100.SH"],
                "limited_defense_candidates": ["511010.SH"],
                "input_etfs": ["510050.SH", "510300.SH", "510500.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["511010.SH"],
                "selected_etfs": ["511010.SH"],
                "selection_reason_codes": {"511010.SH": ["ETF_BETA_FALLBACK_SINGLE_SYMBOL"]},
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "requested_budget": 1.0,
                "applied_budget": 1.0,
                "target_exposure": 1.0,
                "min_deployable_exposure": 0.45,
                "fallback_allowed": True,
                "governor_boundary": {"target_exposure": 1.0},
                "local_policy_decision": {
                    "targets": {
                        "510050.SH": 0.2,
                        "510300.SH": 0.4,
                        "510500.SH": 0.3,
                        "512100.SH": 0.1,
                    }
                },
            },
        },
    )

    assert gate["metrics"]["target_contract_drift_detected"] is False
    assert gate["metrics"]["target_contract_drift_day_count"] == 0
    assert "target_contract_drift_examples" not in gate["evidence"]["deployment_evidence"]


def test_evaluate_etf_beta_sleeve_passes_for_governed_broad_based_standalone_mainline(tmp_path) -> None:
    root = tmp_path / "exp_etf_standalone_mainline"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-18",
                "gross_exposure": 0.42,
                "etf_target_exposure": 0.45,
                "etf_actual_exposure": 0.42,
                "etf_actual_risk_exposure": 0.34,
                "etf_actual_fallback_exposure": 0.08,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.03,
                "governor_budget_json": json.dumps(
                    {
                        "target_exposure": 0.45,
                        "min_deployable_exposure": 0.2,
                        "fallback_allowed": True,
                        "layering_band": "CONTROLLED_TRANS_DOWN",
                        "under_deploy_reason_codes": [],
                    },
                    ensure_ascii=False,
                ),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "layering_band": "CONTROLLED_TRANS_DOWN",
                        "under_deploy_reason_codes": [],
                        "controlled_accumulation_mode": "light_and_controlled_trans_down",
                        "absolute_filter_reject_count": 1,
                        "absolute_filter_reject_reason_counts": {"ABSOLUTE_MA200_NOT_ABOVE": 1},
                        "candidate_pool_reject_reason_counts": {"POOL_PROFILE_EXCLUDED::DIVIDEND_STANDARD": 1},
                        "selection_chain_winner_counts": {"selected_count": 2},
                        "selection_chain_reject_reason_counts": {"SELECTION_CHAIN_RANK_BELOW_CUTOFF": 1},
                        "runtime_selection": {
                            "absolute_filter_profile": "ma200_only",
                            "candidate_pool_profile": "proxy_expanded_pool",
                            "selection_chain_profile": "global_top2_6_3_1",
                        },
                    }
                ),
            },
            {
                "date": "2026-03-19",
                "gross_exposure": 0.38,
                "etf_target_exposure": 0.45,
                "etf_actual_exposure": 0.38,
                "etf_actual_risk_exposure": 0.30,
                "etf_actual_fallback_exposure": 0.08,
                "etf_actual_other_exposure": 0.0,
                "etf_deployability_gap": 0.07,
                "governor_budget_json": json.dumps(
                    {
                        "target_exposure": 0.45,
                        "min_deployable_exposure": 0.2,
                        "fallback_allowed": True,
                        "layering_band": "CONTROLLED_TRANS_DOWN",
                        "under_deploy_reason_codes": [],
                    },
                    ensure_ascii=False,
                ),
                "diagnostics_input_json": _etf_diag_payload(
                    research={
                        "layering_band": "CONTROLLED_TRANS_DOWN",
                        "under_deploy_reason_codes": [],
                        "controlled_accumulation_mode": "light_and_controlled_trans_down",
                        "absolute_filter_reject_count": 0,
                        "selection_chain_winner_counts": {"selected_count": 2},
                        "selection_chain_reject_reason_counts": {"SELECTION_CHAIN_RANK_BELOW_CUTOFF": 1},
                        "runtime_selection": {
                            "absolute_filter_profile": "ma200_only",
                            "candidate_pool_profile": "proxy_expanded_pool",
                            "selection_chain_profile": "global_top2_6_3_1",
                        },
                    }
                ),
            },
        ]
    ).to_csv(root / "portfolio_daily.csv", index=False)
    pd.DataFrame(
        [
            {"date": "2026-03-18", "reason_code": "ETF_BETA_WEEKLY_RS"},
            {"date": "2026-03-19", "reason_code": "ETF_BETA_FALLBACK_BUY"},
            {"date": "2026-03-20", "reason_code": "ETF_BETA_REBALANCE_EXIT"},
        ]
    ).to_csv(root / "orders.csv", index=False)

    gate = evaluate_etf_beta_sleeve(
        results_dir=root,
        run_meta={
            "data": {"asset_scope": "cn_etf"},
            "counters": {"orders": 3, "closed_trades": 2},
            "governed_a_share": {
                "etf_beta": {
                    "enabled": True,
                    "sleeve_id": "cn_etf_beta",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "159915.SZ"],
                    "limited_defense_candidates": [],
                }
            },
            "etf_beta": {
                "strategy_role": "governed_broad_based_standalone_mainline",
                "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                "governor_boundary_mode": "consume_governor_state_and_budget",
                "local_policy_mode": "broad_based_rotation_mainline",
                "controlled_accumulation_mode": "light_and_controlled_trans_down",
                "formal_alignment_reference": "A鑲TF瀛愮郴缁熺瓥鐣ユ€濊矾md",
                "formal_alignment_status": "do_not_promote",
                "formal_mainline_compatible": False,
                "formal_alignment_reason_codes": [
                    "FORMAL_EXCLUDED_ASSET_USED::input_etfs::159915.SZ",
                    "FORMAL_EXCLUDED_ASSET_USED::input_etfs::518880.SH",
                    "SIGNAL_SEMANTICS_OUT_OF_SCOPE::research_rule_family::broad_based_rotation_template_a",
                ],
                "formal_alignment_evidence": {"reference_doc": "A鑲TF瀛愮郴缁熺瓥鐣ユ€濊矾md"},
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "159915.SZ"],
                "limited_defense_candidates": [],
                "input_etfs": ["510300.SH", "510500.SH", "159915.SZ", "518880.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "159915.SZ"],
                "selected_etfs": ["510500.SH", "159915.SZ"],
                "selection_reason_codes": {
                    "510500.SH": ["RS_TOP2", "ABSOLUTE_FILTER_PASS"],
                    "159915.SZ": ["GROWTH_SLOT", "ABSOLUTE_FILTER_PASS"],
                },
                "out_of_scope_etfs": [],
                "out_of_scope_reason_codes": {},
                "coverage_summary": {"daily_table": "pams_cn_etf_daily"},
                "absolute_filter_profile": "ma200_only",
                "candidate_pool_profile": "proxy_expanded_pool",
                "selection_chain_profile": "global_top2_6_3_1",
                "exposure_policy_family": "broad_based_standalone_mainline_v1",
                "policy_scope": "broad_based_only",
                "broad_based_only": True,
                "layering_policy": "light_trans_down_accumulate",
                "layering_band": "CONTROLLED_TRANS_DOWN",
                "layering_active": True,
                "layering_reason_codes": ["ETF_BETA_LAYERING_CONTROLLED_TRANS_DOWN"],
                "target_selected_count_source": "state_map::TRANS_DOWN",
                "fallback_allowed_source": "state_map::TRANS_DOWN",
                "target_exposure": 0.45,
                "min_deployable_exposure": 0.2,
                "fallback_allowed": True,
                "under_deploy_reason_codes": [],
                "governor_boundary": {
                    "effective_state_5": "TRANS_DOWN",
                    "budget_owner": "global_portfolio_governor",
                    "budget_reason_codes": ["BUDGET_OK"],
                    "target_exposure": 0.45,
                },
                "local_policy_decision": {
                    "strategy_role": "governed_broad_based_standalone_mainline",
                    "local_policy_mode": "broad_based_rotation_mainline",
                    "controlled_accumulation_mode": "light_and_controlled_trans_down",
                    "selected_etfs": ["510500.SH", "159915.SZ"],
                    "runtime_reason_codes": ["ETF_BETA_STANDALONE_MAINLINE_ACTIVE"],
                    "under_deploy_reason_codes": [],
                    "fallback_mode": "single_symbol",
                    "fallback_symbol": "511010.SH",
                },
                "sleeve_budget_used": {
                    "budget_owner": "global_portfolio_governor",
                    "slot_cap": 2,
                    "target_exposure": 0.45,
                    "min_deployable_exposure": 0.2,
                    "fallback_allowed": True,
                    "actual_exposure": 0.38,
                    "actual_risk_exposure": 0.30,
                    "actual_fallback_exposure": 0.08,
                    "deployability_gap": 0.07,
                },
            },
        },
    )

    assert gate is not None
    assert gate["status"] == "FAIL"
    assert gate["metrics"]["formal_alignment_status"] == "do_not_promote"
    assert gate["metrics"]["formal_mainline_compatible"] is False
    assert gate["metrics"]["has_governor_boundary_split"] is True
    assert gate["metrics"]["has_local_policy_split"] is True
    assert gate["metrics"]["fallback_exposure_day_count"] == 2
    assert gate["metrics"]["controlled_accumulation_day_count"] == 2
    assert gate["metrics"]["absolute_filter_reject_day_count"] == 1
    assert gate["metrics"]["selection_chain_reject_reason_counts"]["SELECTION_CHAIN_RANK_BELOW_CUTOFF"] == 2
    assert gate["evidence"]["strategy_role"] == "governed_broad_based_standalone_mainline"
    assert gate["evidence"]["absolute_filter_profile"] == "ma200_only"
    assert gate["evidence"]["candidate_pool_profile"] == "proxy_expanded_pool"
    assert gate["evidence"]["selection_chain_profile"] == "global_top2_6_3_1"
    assert gate["evidence"]["formal_alignment_reference"] == "A鑲TF瀛愮郴缁熺瓥鐣ユ€濊矾md"
    assert gate["evidence"]["source_entry_type"] == "cn_etf_broad_based_standalone_mainline_entry"
    assert gate["evidence"]["governor_boundary"]["effective_state_5"] == "TRANS_DOWN"
    assert gate["evidence"]["local_policy_decision"]["local_policy_mode"] == "broad_based_rotation_mainline"


def test_evaluate_attribution_traceability_passes_when_summary_and_refs_exist(tmp_path) -> None:
    root = tmp_path / "exp_attr"
    root.mkdir(parents=True, exist_ok=True)
    (root / "regime_audit_summary.json").write_text(
        json.dumps(
            {
                "summary": {
                    "base_state_5": "TRANS_UP",
                    "effective_state_5": "TRANS_UP",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "attribution_audit.json").write_text(
        json.dumps(
            {
                "contract_version": "cn_a_attribution_audit@1",
                "summary": {
                    "state_log_count": 2,
                    "budget_log_count": 2,
                    "sleeve_log_count": 1,
                    "manual_override_log_count": 0,
                },
                "reason_code_summary": {
                    "state_reason_codes": {"TREND_BREAK": 1},
                    "budget_reason_codes": {"TOTAL_RISK_BUDGET_REDUCED": 1},
                    "sleeve_reason_codes": {"FORMAL_CORE_BETA": 1},
                    "manual_override_reasons": {},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = evaluate_attribution_traceability(
        results_dir=root,
        run_meta={
            "governed_a_share": {"enabled": True},
            "governed_snapshot": {
                "base_state": "TRANS_UP",
                "effective_state": "TRANS_UP",
                "coarse_state": "RISK_ON",
                "effective_coarse_state": "RISK_ON",
                "risk_budget_multiplier": 0.5,
                "budget_reason_codes": ["TOTAL_RISK_BUDGET_REDUCED"],
            },
            "regime": {
                "latest_state": {
                    "base_state": "TRANS_UP",
                    "effective_state": "TRANS_UP",
                    "coarse_state": "RISK_ON",
                    "effective_coarse_state": "RISK_ON",
                    "reason_codes": ["TREND_BREAK"],
                    "manual_override": {"active": False, "reason": None, "scope": None, "actor": None},
                }
            },
        },
    )

    assert gate is not None
    assert gate["status"] == "PASS"
    assert gate["metrics"]["state_log_count"] == 2
    assert gate["metrics"]["has_attribution_ref"] is True
    assert gate["metrics"]["has_regime_ref"] is True
    assert gate["metrics"]["has_governor_snapshot"] is True
    assert gate["metrics"]["has_regime_snapshot"] is True


def test_evaluate_attribution_traceability_passes_for_unified_combo_governor_snapshot(tmp_path) -> None:
    root = tmp_path / "exp_unified_attr"
    root.mkdir(parents=True, exist_ok=True)
    (root / "regime_audit_summary.json").write_text(
        json.dumps({"summary": {"base_state_5": "RISK_OFF", "effective_state_5": "RISK_OFF"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "attribution_audit.json").write_text(
        json.dumps(
            {
                "contract_version": "cn_a_attribution_audit@1",
                "summary": {
                    "state_log_count": 1,
                    "budget_log_count": 1,
                    "sleeve_log_count": 2,
                    "manual_override_log_count": 0,
                },
                "reason_code_summary": {
                    "state_reason_codes": {"STOCK::NO_REASON_CODES": 1},
                    "budget_reason_codes": {"ETF::NO_DEPLOYABLE_SLOTS": 1},
                    "sleeve_reason_codes": {"ETF::ETF_BETA_SLOT_CAP_ZERO": 1},
                    "manual_override_reasons": {},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = evaluate_attribution_traceability(
        results_dir=root,
        run_meta={
            "data": {
                "asset_role": "unified_multi_sleeve_combo",
            },
            "stage_pipeline": {
                "execution_shell": "unified_combo_phase1",
            },
            "governed_a_share": {"enabled": True},
            "governed_snapshot": {
                "regime_source_state": "RISK_OFF",
                "regime_effective_state": "RISK_OFF",
                "coarse_state": "RISK_OFF",
                "effective_coarse_state": "RISK_OFF",
                "total_risk_budget": 0.3,
                "budget_reason_codes": ["ETF::NO_DEPLOYABLE_SLOTS"],
            },
            "regime": {
                "latest_state": {
                    "base_state": "RISK_OFF",
                    "effective_state": "RISK_OFF",
                    "coarse_state": "RISK_OFF",
                    "effective_coarse_state": "RISK_OFF",
                    "reason_codes": ["STOCK::NO_REASON_CODES", "ETF::NO_REASON_CODES"],
                    "manual_override": {"active": False, "reason": None, "scope": None, "actor": None},
                }
            },
        },
    )

    assert gate is not None
    assert gate["status"] == "PASS"
    assert gate["metrics"]["has_governor_snapshot"] is True
    assert gate["evidence"]["governed_snapshot"]["base_state"] == "RISK_OFF"
    assert gate["evidence"]["governed_snapshot"]["risk_budget_multiplier"] == pytest.approx(0.3)


def test_evaluate_execution_realism_flags_hard_fail_on_suspended_trade() -> None:
    trades = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "sh600000", "side": "BUY", "price": 10.0, "fill_price": 10.0},
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600000",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "is_suspended": True,
            }
        ]
    )

    gate = evaluate_execution_realism(trades_df=trades, bars_df=bars)

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["suspended_trade_count"] == 1


def test_evaluate_execution_realism_warns_for_small_limit_lock_ratio() -> None:
    trades = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": f"sh600{i:03d}",
                "side": "BUY",
                "price": 10.0 if i else 11.0,
                "fill_price": 10.0 if i else 11.0,
            }
            for i in range(100)
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": f"sh600{i:03d}",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "is_suspended": False,
            }
            for i in range(100)
        ]
    )

    gate = evaluate_execution_realism(trades_df=trades, bars_df=bars)

    assert gate["status"] == "WARN"
    assert gate["metrics"]["limit_up_buy_count"] == 1
    assert gate["metrics"]["limit_locked_trade_ratio"] == 0.01


def test_evaluate_execution_realism_normalizes_four_decimal_limit_prices_to_tick_size() -> None:
    trades = pd.DataFrame(
        [
            {
                "date": "2024-10-22",
                "symbol": "sz002261",
                "side": "BUY",
                "price": 26.98,
                "fill_price": 26.9854,
            },
            {
                "date": "2020-02-04",
                "symbol": "sz002797",
                "side": "SELL",
                "price": 6.24,
                "fill_price": 6.2388,
            },
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "date": "2024-10-22",
                "symbol": "sz002261",
                "open": 26.98,
                "high": 26.98,
                "low": 24.53,
                "close": 25.27,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 26.983,
                "limit_down": 22.077,
                "is_suspended": False,
            },
            {
                "date": "2020-02-04",
                "symbol": "sz002797",
                "open": 6.24,
                "high": 6.82,
                "low": 6.24,
                "close": 6.71,
                "volume": 1000,
                "amount": 10000,
                "limit_up": 7.623,
                "limit_down": 6.237,
                "is_suspended": False,
            },
        ]
    )

    gate = evaluate_execution_realism(trades_df=trades, bars_df=bars)

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["limit_up_buy_count"] == 1
    assert gate["metrics"]["limit_down_sell_count"] == 1
    assert gate["evidence"]["samples"]["limit_up_buy"][0]["limit_up"] == 26.98
    assert gate["evidence"]["samples"]["limit_down_sell"][0]["limit_down"] == 6.24


def test_evaluate_accounting_integrity_fails_on_execution_audit_violations() -> None:
    gate = evaluate_accounting_integrity(
        result={
            "metrics": {
                "audit": {
                    "accounting_integrity": {
                        "contract_version": "accounting_integrity_audit@1",
                        "status": "FAIL",
                        "reason": "Detected invariant violations.",
                        "summary": {
                            "trading_days": 2,
                            "days_with_evidence": 2,
                            "missing_evidence_days": 0,
                            "cash_check_fail": 1,
                            "position_check_fail": 0,
                            "nav_check_fail": 0,
                            "invalid_nav_days": 0,
                            "negative_cash_days": 0,
                            "max_positions_breach_days": 0,
                        },
                        "samples": {"cash_check_fail": [{"day": "2026-03-02"}]},
                    }
                }
            }
        }
    )

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["cash_check_fail"] == 1
    assert gate["evidence"]["source"] == "result"


def test_evaluate_accounting_integrity_returns_unknown_when_evidence_missing() -> None:
    gate = evaluate_accounting_integrity(result={})

    assert gate["status"] == "UNKNOWN"
    assert gate["metrics"]["trading_days"] == 0


def test_evaluate_timing_alignment_derives_pass_from_price_only_next_day_artifacts(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_pass"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "compiled_plan.json").write_text(
        json.dumps(
            {
                "runtime_config": {
                    "execution": {"t_plus_one": True},
                    "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": False}},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "input_config.json").write_text(
        json.dumps(
            {
                "strategy_pack": "BREAKOUT_TREND",
                "sector_gate": {"enabled": False},
                "position_risk": {"cost_model": {"matching": "next_open"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "PASS"
    assert gate["metrics"]["contract_proved"] is True
    assert gate["metrics"]["pit_safe"] is True


def test_evaluate_timing_alignment_derives_pass_from_top_level_compiled_plan_stage_pipeline_shell(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_top_level"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "compiled_plan.json").write_text(
        json.dumps(
            {
                "execution": {"t_plus_one": True},
                "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": False}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "input_config.json").write_text("{}", encoding="utf-8")

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "PASS"
    assert gate["evidence"]["matching_mode"] == "NEXT_OPEN"
    assert gate["metrics"]["contract_proved"] is True


def test_evaluate_timing_alignment_keeps_unknown_when_membership_signal_is_enabled(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_unknown"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "compiled_plan.json").write_text(
        json.dumps(
            {
                "runtime_config": {
                    "execution": {"t_plus_one": True},
                    "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": True}},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "input_config.json").write_text(
        json.dumps(
            {
                "strategy_pack": "BREAKOUT_TREND",
                "sector_gate": {"enabled": True},
                "position_risk": {"cost_model": {"matching": "next_open"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "UNKNOWN"
    assert gate["metrics"]["contract_proved"] is True
    assert gate["metrics"]["pit_safe"] is False


def test_evaluate_timing_alignment_fails_on_same_day_fill_from_lineage_ledger(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_same_day_fill"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "signal_id": "sig_1",
                "signal_date": "2024-01-02",
                "order_id": "ord_1",
                "scheduled_date": "2024-01-03",
                "last_scheduled_date": "2024-01-03",
                "schedule_attempts": 1,
                "fill_id": "fil_1",
                "fill_date": "2024-01-02",
                "symbol": "sh600000",
                "side": "BUY",
                "qty": 100,
                "reason_code": "ENTRY",
                "terminal_status": "filled",
                "terminal_reason": "",
                "deferred_count": 0,
            }
        ]
    ).to_csv(results_dir / "execution_lineage_ledger.csv", index=False)
    (results_dir / "audit.json").write_text("{}", encoding="utf-8")

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "FAIL"
    assert gate["metrics"]["lineage_same_day_fill_count"] == 1


def test_evaluate_timing_alignment_prefers_lineage_evidence_when_available(tmp_path) -> None:
    results_dir = tmp_path / "exp_timing_lineage_pass"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "compiled_plan.json").write_text(
        json.dumps(
            {
                "runtime_config": {
                    "execution": {"t_plus_one": True},
                    "strategy": {"name": "breakout_trend", "params": {"enable_sector_gate": False}},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "input_config.json").write_text(
        json.dumps(
            {
                "strategy_pack": "BREAKOUT_TREND",
                "sector_gate": {"enabled": False},
                "position_risk": {"cost_model": {"matching": "next_open"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "signal_id": "sig_1",
                "signal_date": "2024-01-02",
                "order_id": "ord_1",
                "scheduled_date": "2024-01-03",
                "last_scheduled_date": "2024-01-03",
                "schedule_attempts": 1,
                "fill_id": "fil_1",
                "fill_date": "2024-01-03",
                "symbol": "sh600000",
                "side": "BUY",
                "qty": 100,
                "reason_code": "ENTRY",
                "terminal_status": "filled",
                "terminal_reason": "",
                "deferred_count": 0,
            }
        ]
    ).to_csv(results_dir / "execution_lineage_ledger.csv", index=False)
    (results_dir / "audit.json").write_text("{}", encoding="utf-8")

    gate = evaluate_timing_alignment(
        stage_summary={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        stage_pipeline={
            "execution_shell": "stage_pipeline_shell_bridge",
            "daily_loop_mode": "single_day_loop",
            "route_id": "provider_breakout_runtime",
        },
        results_dir=results_dir,
    )

    assert gate["status"] == "PASS"
    assert gate["metrics"]["lineage_rows"] == 1
    assert gate["metrics"]["lineage_same_day_fill_count"] == 0

def test_evaluate_result_sanity_returns_unknown_when_sample_too_small() -> None:
    gate = evaluate_result_sanity(
        perf={"total_return": 0.2, "sharpe": 8.0, "cagr": 2.0, "trades": 5},
        run_meta={"counters": {"closed_trades": 5}, "stage_pipeline": {"trading_days": 100}},
        symbol_performance_df=pd.DataFrame(
            [{"symbol": "sh600000", "net_pnl": 1000.0}, {"symbol": "sz000001", "net_pnl": 500.0}]
        ),
    )

    assert gate["status"] == "UNKNOWN"


def test_build_research_audit_reuses_evidence_refs_instead_of_embedding_payload(tmp_path) -> None:
    results_dir = tmp_path / "exp_ra"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "data": {"universe_mode": "HS300_ZZ500"},
                "universe": {
                    "universe_mode": "HS300_ZZ500",
                    "symbols_source": "pit_index_constituents",
                    "load_table": "pit_index_constituents",
                    "resolve_asof": "2016-03-01",
                    "dynamic_all_a_entry": False,
                },
                "counters": {"closed_trades": 30},
                "stage_pipeline": {
                    "schema_version": "stage_pipeline_summary@1",
                    "execution_shell": "stage_pipeline_shell_bridge",
                    "daily_loop_mode": "single_day_loop",
                    "route_id": "provider_breakout_runtime",
                    "trading_days": 300,
                },
                "report_consistency": {"resolved_config_hash": "abc123"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "manifest.json").write_text(
        json.dumps(
            {
                "config_snapshots": {
                    "input_config": "input_config.json",
                    "resolved_config": "resolved_config.json",
                    "compiled_plan": "compiled_plan.json",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "perf.json").write_text(
        json.dumps(
            {"total_return": 0.2, "sharpe": 1.2, "cagr": 0.1, "trades": 30},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_dir / "audit.json").write_text("{}", encoding="utf-8")
    (results_dir / "stage_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "stage_pipeline_summary@1",
                "execution_shell": "stage_pipeline_shell_bridge",
                "daily_loop_mode": "single_day_loop",
                "route_id": "provider_breakout_runtime",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    audit = build_research_audit(results_dir=results_dir)

    assert audit["contract_version"] == "research_audit@1"
    assert audit["gates"]["accounting_integrity"]["status"] == "UNKNOWN"
    assert audit["evidence_refs"]["audit"] == "audit.json"
    assert audit["evidence_refs"]["execution_lineage_ledger"] is None
    assert audit["evidence_refs"]["regime_audit_summary"] is None
    assert audit["evidence_refs"]["run_meta"] == "run_meta.json"
    assert audit["evidence_refs"]["manifest"] == "manifest.json"
    assert audit["evidence_refs"]["stage_summary"] == "stage_summary.json"
    assert "run_meta" not in audit
    assert "manifest" not in audit
    assert "stage_summary" not in audit


