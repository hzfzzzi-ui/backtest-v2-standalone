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
    evaluate_result_sanity,
    evaluate_timing_alignment,
    evaluate_universe_lineage,
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
                    "template_id": "broad_based_rotation_template_a",
                    "template_asset_pool_version": "A0",
                    "template_role_map": {"510300.SH": "hs300", "512100.SH": "csi1000_proxy"},
                    "template_proxy_map": {"512100.SH": "CSI1000_STANDARD"},
                    "template_target_formal_symbols": ["510300.SH", "510500.SH", "CSI1000_STANDARD", "DIVIDEND_STANDARD"],
                    "growth_seat_symbol": "159915.SZ",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["512890.SH"],
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
                "source_entry_type": "cn_etf_research_entry",
                "source_preset_id": "cn_etf_first_wave_core",
                "template_id": "broad_based_rotation_template_a",
                "template_asset_pool_version": "A0",
                "template_role_map": {"510300.SH": "hs300", "512100.SH": "csi1000_proxy"},
                "template_proxy_map": {"512100.SH": "CSI1000_STANDARD"},
                "template_target_formal_symbols": ["510300.SH", "510500.SH", "CSI1000_STANDARD", "DIVIDEND_STANDARD"],
                "proxy_replacement_mode": "csi1000_proxy_only",
                "formal_replacement_pairs": {"512100.SH": "159845.SZ"},
                "core_slot_symbols": ["510300.SH", "512100.SH"],
                "growth_slot_symbols": ["159915.SZ"],
                "growth_seat_symbol": "159915.SZ",
                "absolute_filter_mode": "ma200_and_positive_12m",
                "fallback_mode": "cash",
                "relative_strength_fast_window": 63,
                "relative_strength_mid_window": 126,
                "relative_strength_slow_window": 252,
                "relative_strength_fast_weight": 0.2,
                "relative_strength_mid_weight": 0.3,
                "relative_strength_slow_weight": 0.5,
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["512890.SH"],
                "input_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
                "eligible_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "selected_etfs": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "selection_reason_codes": {
                    "510300.SH": ["FORMAL_CORE_BETA"],
                    "510500.SH": ["FORMAL_CORE_BETA"],
                    "510050.SH": ["FORMAL_CORE_BETA"],
                    "512100.SH": ["FORMAL_CORE_BETA"],
                },
                "core_slot_selected_symbol": "510300.SH",
                "growth_slot_selected_symbol": "159915.SZ",
                "slot_selection_reason_codes": {
                    "core_slot": ["SELECTED::510300.SH"],
                    "growth_slot": ["SELECTED::159915.SZ"],
                },
                "slot_under_deploy_reason_codes": {},
                "out_of_scope_etfs": ["511010.SH"],
                "out_of_scope_reason_codes": {"511010.SH": ["OUT_OF_PHASE1_FORMAL_SCOPE"]},
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
                    "selected_count": 4,
                },
            },
        }
    )

    assert gate is not None
    assert gate["status"] == "PASS"
    assert gate["metrics"]["eligible_count"] == 4
    assert gate["evidence"]["proxy_replacement_mode"] == "csi1000_proxy_only"
    assert gate["evidence"]["core_slot_selected_symbol"] == "510300.SH"
    assert gate["evidence"]["growth_slot_selected_symbol"] == "159915.SZ"
    assert gate["metrics"]["out_of_scope_count"] == 1
    assert gate["metrics"]["order_count"] == 8
    assert gate["metrics"]["trade_count"] == 4
    assert gate["evidence"]["template_id"] == "broad_based_rotation_template_a"
    assert gate["evidence"]["template_asset_pool_version"] == "A0"
    assert gate["evidence"]["template_proxy_map"]["512100.SH"] == "CSI1000_STANDARD"
    assert gate["evidence"]["relative_strength_windows"]["mid"] == 126
    assert gate["evidence"]["absolute_filter_mode"] == "ma200_and_positive_12m"


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
                    "limited_defense_candidates": ["512890.SH"],
                }
            },
            "etf_beta": {
                "source_entry_type": "cn_etf_research_entry",
                "formal_core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                "limited_defense_candidates": ["512890.SH"],
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
                        "under_deploy_reason_codes": ["ETF_BETA_NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER"],
                    },
                    ensure_ascii=False,
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
                        "under_deploy_reason_codes": ["ETF_BETA_UNDERFILLED_DEPLOYMENT"],
                    },
                    ensure_ascii=False,
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
                        "under_deploy_reason_codes": ["ETF_BETA_UNDERFILLED_DEPLOYMENT"],
                    },
                    ensure_ascii=False,
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
                    "under_deploy_reason_codes": ["ETF_BETA_UNDERFILLED_DEPLOYMENT"],
                },
            },
        },
    )

    assert gate is not None
    assert gate["status"] == "WARN"
    assert gate["metrics"]["avg_target_exposure"] == pytest.approx(0.2)
    assert gate["metrics"]["avg_actual_exposure"] == 0.043333333333333335
    assert gate["metrics"]["avg_actual_risk_exposure"] == pytest.approx(0.043333333333333335)
    assert gate["metrics"]["avg_actual_fallback_exposure"] == pytest.approx(0.0)
    assert gate["metrics"]["avg_deployability_gap"] == pytest.approx(0.15666666666666668)
    assert gate["metrics"]["avg_actual_exposure_on_invested_days"] == 0.065
    assert gate["metrics"]["invested_day_count"] == 2
    assert gate["metrics"]["fallback_buy_count"] == 0
    assert gate["metrics"]["deployment_assessment"] == "UNDERDEPLOYED"
    assert gate["metrics"]["under_deploy_reason_counts"]["ETF_BETA_UNDERFILLED_DEPLOYMENT"] == 2


def test_evaluate_attribution_traceability_passes_when_summary_and_refs_exist(tmp_path) -> None:
    root = tmp_path / "exp_attr"
    root.mkdir(parents=True, exist_ok=True)
    (root / "regime_audit_summary.json").write_text(
        json.dumps(
            {
                "summary": {
                    "base_state_5": "LIGHT",
                    "effective_state_5": "LIGHT",
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
                "base_state": "LIGHT",
                "effective_state": "LIGHT",
                "coarse_state": "NEUTRAL",
                "effective_coarse_state": "NEUTRAL",
                "risk_budget_multiplier": 0.5,
                "budget_reason_codes": ["TOTAL_RISK_BUDGET_REDUCED"],
            },
            "regime": {
                "latest_state": {
                    "base_state": "LIGHT",
                    "effective_state": "LIGHT",
                    "coarse_state": "NEUTRAL",
                    "effective_coarse_state": "NEUTRAL",
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


def test_evaluate_unified_runtime_completeness_passes_when_combo_and_sleeves_are_present(tmp_path) -> None:
    root = tmp_path / "exp_unified_combo"
    root.mkdir(parents=True, exist_ok=True)
    (root / "portfolio_daily.csv").write_text("date,nav\n2026-03-20,1.0\n", encoding="utf-8")
    (root / "portfolio_trades.csv").write_text("date,symbol,side,qty,price\n2026-03-20,sh600000,BUY,100,10\n", encoding="utf-8")
    (root / "regime_audit_summary.json").write_text(
        json.dumps({"summary": {"base_state_5": "LIGHT", "effective_state_5": "LIGHT"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "attribution_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "state_log_count": 1,
                    "budget_log_count": 1,
                    "sleeve_log_count": 2,
                    "manual_override_log_count": 0,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    gate = evaluate_unified_runtime_completeness(
        results_dir=root,
        run_meta={
            "data": {
                "asset_role": "unified_multi_sleeve_combo",
                "system_asset_scope": "cn_a_multi_sleeve",
            },
            "stage_pipeline": {
                "execution_shell": "unified_combo_phase1",
            },
            "combo_components": {
                "stock_component": {"exp_id": "exp_stock"},
                "etf_component": {"exp_id": "exp_etf"},
            },
            "regime": {
                "latest_state": {
                    "base_state": "LIGHT",
                    "effective_state": "LIGHT",
                }
            },
            "governed_snapshot": {
                "budget_owner": "global_portfolio_governor",
                "sleeve_budgets": {
                    "cn_stock_trend_alpha_core": {"slot_cap": 4},
                    "cn_etf_beta": {"slot_cap": 2},
                },
            },
            "attribution": {
                "summary": {
                    "state_log_count": 1,
                    "budget_log_count": 1,
                    "sleeve_log_count": 2,
                }
            },
            "sleeves": {
                "stock_alpha_core": {"exp_id": "exp_stock"},
                "etf_beta": {"exp_id": "exp_etf"},
            },
        },
    )

    assert gate is not None
    assert gate["status"] == "PASS"
    assert gate["metrics"]["component_count"] == 2
    assert gate["metrics"]["has_combo_governed_snapshot"] is True
    assert gate["metrics"]["has_combo_regime"] is True


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
