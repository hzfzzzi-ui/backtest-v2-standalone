from __future__ import annotations

import json

import pandas as pd

from backend.api.backtest_v2.artifacts_finalize import ensure_standard_artifacts


def test_ensure_standard_artifacts_writes_regime_engine_snapshot(tmp_path) -> None:
    results_dir = tmp_path / "exp_regime"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "portfolio_daily.csv").write_text(
        "date,nav\n2026-03-02,1.0\n2026-03-03,1.1\n",
        encoding="utf-8",
    )
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
                "regime_engine": {
                    "engine": "market_regime_framework",
                    "benchmark": "000300.SH",
                    "fallback": {
                        "on_feature_unavailable": "ma200_legacy",
                        "required_blocks": ["trend_block", "risk_block"],
                        "emit_feature_availability": True,
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    base_cfg = {
        "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
        "data_source": {"data_role": "v1"},
        "schema_mapping": {},
        "regime_engine": {
            "engine": "market_regime_framework",
            "benchmark": "000300.SH",
            "fallback": {
                "on_feature_unavailable": "ma200_legacy",
                "required_blocks": ["trend_block", "risk_block"],
                "emit_feature_availability": True,
            },
        },
    }
    result = {
        "exp_id": "exp_regime_meta",
        "status": "OK",
        "tier": "T0",
        "start_date": "2026-03-02",
        "end_date": "2026-03-03",
        "total_return": 0.1,
        "max_drawdown": -0.02,
        "cagr": 0.1,
        "sharpe": 1.0,
    }

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result=result,
        base_cfg=base_cfg,
        overrides={},
    )

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert out["status"] == "OK"
    assert run_meta["regime"]["engine"] == "market_regime_framework"
    assert run_meta["regime"]["regime_semantics"] == "formal_multi_factor_regime"
    assert run_meta["regime"]["state_contract"]["primary_states"] == ["BULL", "TRANS_UP", "TRANS_DOWN", "RISK_OFF"]
    assert run_meta["regime"]["feature_availability_contract"]["required_blocks"] == ["trend_block", "risk_block"]
    assert run_meta["governed_a_share"]["stock_alpha_core"]["sleeve_id"] == "cn_stock_trend_alpha_core"
    assert run_meta["governed_a_share"]["stock_alpha_core"]["legacy_anchor"] == "baseline_V10.1"
    assert run_meta["report_consistency"]["stock_alpha_core_role"] == "cn_stock_trend_alpha_core"
    assert run_meta["report_consistency"]["stock_alpha_core_budget_semantics"] == "consume_governor_sleeve_budget"
    assert run_meta["report_consistency"]["stock_alpha_core_total_budget_owner"] == "global_portfolio_governor"
    assert run_meta["report_consistency"]["stock_alpha_core_phase1_excluded_capabilities"] == [
        "value_bluechip_satellite",
        "cn_etf_beta",
        "insurance_overlay",
    ]
    assert run_meta["report_consistency"]["regime_engine"] == "market_regime_framework"


def test_ensure_standard_artifacts_writes_regime_audit_bundle(tmp_path) -> None:
    results_dir = tmp_path / "exp_regime_audit"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,market_state,trade_mode,regime_engine,regime_confidence,regime_duration_bars,regime_transition_reason,feature_availability_json,risk_budget_multiplier,reason_codes_json,subscores_json,block_scores_json,manual_override_json,state_stability_metrics_json,base_state_5,effective_state_5,coarse_state,effective_coarse_state,defense_bias",
                '2026-03-02,1.0,BULL,TREND_MAIN,market_regime_framework,0.82,6,,"{""trend_block"": true, ""risk_block"": true}",1.0,"[""BULL_CONFIRMED""]","{""technical"": 0.82, ""sentiment"": null, ""macro_global"": null}","{""trend_block"": {""support"": 0.8, ""stress"": 0.1, ""net"": 0.7}}","{""active"": false, ""reason"": null, ""scope"": null, ""actor"": null}","{""pending_transition"": false, ""cooldown_active"": false}","BULL","BULL","RISK_ON","RISK_ON",0.0',
                '2026-03-03,1.1,TRANS_DOWN,TREND_LIGHT,market_regime_framework,0.44,1,RISK_BLOCK_WEAKNESS,"{""trend_block"": true, ""risk_block"": false}",0.35,"[""RISK_BLOCK_WEAKNESS""]","{""technical"": 0.44, ""sentiment"": 0.1, ""macro_global"": -0.2}","{""risk_block"": {""support"": 0.2, ""stress"": 0.9, ""net"": -0.7}}","{""active"": true, ""reason"": ""MANUAL_REVIEW"", ""scope"": ""cn_a_mainline"", ""actor"": ""pm"", ""target_state_5"": ""LIGHT""}","{""pending_transition"": true, ""cooldown_active"": false}","TRANS_DOWN","TRANS_UP","RISK_OFF","RISK_ON",0.7',
            ]
        ),
        encoding="utf-8",
    )
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
                "regime_engine": {
                    "engine": "market_regime_framework",
                    "persistence": {"confidence_floor": 0.55},
                    "fallback": {
                        "on_feature_unavailable": "ma200_legacy",
                        "required_blocks": ["trend_block", "risk_block"],
                        "emit_feature_availability": True,
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result={
            "exp_id": "exp_regime_audit",
            "status": "OK",
            "tier": "T0",
            "start_date": "2026-03-02",
            "end_date": "2026-03-03",
            "total_return": 0.1,
            "max_drawdown": -0.02,
            "cagr": 0.1,
            "sharpe": 1.0,
        },
        base_cfg={
            "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
            "schema_mapping": {},
            "regime_engine": {
                "engine": "market_regime_framework",
                "persistence": {"confidence_floor": 0.55},
                "fallback": {
                    "required_blocks": ["trend_block", "risk_block"],
                },
            },
        },
        overrides={},
    )

    artifacts = dict(out.get("artifacts") or {})
    assert artifacts.get("regime_audit_summary") == "regime_audit_summary.json"
    assert artifacts.get("regime_transition_debug") == "regime_transition_debug.csv"
    assert artifacts.get("regime_audit_report") == "regime_audit_report.md"

    summary = json.loads((results_dir / "regime_audit_summary.json").read_text(encoding="utf-8"))
    assert summary["summary"]["switch_count"] == 1
    assert summary["latest_state"]["why_today"] == "RISK_BLOCK_WEAKNESS"
    assert summary["latest_state"]["base_state_5"] == "TRANS_DOWN"
    assert summary["latest_state"]["effective_state_5"] == "TRANS_UP"
    assert summary["latest_state"]["coarse_state"] == "RISK_OFF"
    assert summary["latest_state"]["reason_codes"] == ["RISK_BLOCK_WEAKNESS"]
    assert summary["latest_state"]["manual_override"]["active"] is True
    assert summary["latest_state"]["manual_override"]["target_state_5"] == "TRANS_UP"

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert run_meta["regime"]["latest_state"]["base_state"] == "TRANS_DOWN"
    assert run_meta["regime"]["latest_state"]["effective_state"] == "TRANS_UP"
    assert run_meta["regime"]["latest_state"]["coarse_state"] == "RISK_OFF"
    assert run_meta["regime"]["latest_state"]["effective_coarse_state"] == "RISK_ON"
    assert run_meta["regime"]["latest_state"]["risk_budget_multiplier"] == 0.35
    assert run_meta["regime"]["latest_state"]["defense_bias"] == 0.7
    assert run_meta["regime"]["latest_state"]["block_scores"]["risk_block"]["net"] == -0.7
    assert run_meta["regime"]["latest_state"]["state_stability_metrics"]["pending_transition"] is True


def test_ensure_standard_artifacts_writes_weekly_five_state_regime_meta(tmp_path) -> None:
    results_dir = tmp_path / "exp_weekly_regime"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "portfolio_daily.csv").write_text(
        "\n".join(
            [
                "date,nav,market_state,market_state_5,trade_mode,regime_engine,market_state_score,risk_budget_multiplier,weekly_observation_flag",
                "2026-03-02,1.0,TURN_WEAK,TURN_WEAK,TREND_MAIN,weekly_five_state,2,0.15,1",
                "2026-03-03,1.1,TURN_WEAK,TURN_WEAK,TREND_MAIN,weekly_five_state,2,0.15,0",
            ]
        ),
        encoding="utf-8",
    )
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
                "regime_engine": {
                    "engine": "weekly_five_state",
                    "benchmark": "000001.SH",
                    "weekly_five_state": {"turn_weak_budget": 0.15},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result={
            "exp_id": "exp_weekly_regime",
            "status": "OK",
            "tier": "T0",
            "start_date": "2026-03-02",
            "end_date": "2026-03-03",
            "total_return": 0.1,
            "max_drawdown": -0.02,
            "cagr": 0.1,
            "sharpe": 1.0,
        },
        base_cfg={
            "universe": {"start": "2026-03-02", "end": "2026-03-03", "benchmark": "000300.SH"},
            "schema_mapping": {},
            "regime_engine": {
                "engine": "weekly_five_state",
                "benchmark": "000001.SH",
                "weekly_five_state": {"turn_weak_budget": 0.15},
            },
        },
        overrides={},
    )

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert out["status"] == "OK"
    assert run_meta["regime"]["engine"] == "weekly_five_state"
    assert run_meta["regime"]["regime_semantics"] == "weekly_five_state_regime"


def test_ensure_standard_artifacts_writes_governor_snapshot_into_run_meta(tmp_path) -> None:
    results_dir = tmp_path / "exp_governor_meta"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-02",
                "nav": 1.0,
                "market_state": "BULL",
                "market_state_5": "BULL",
                "trade_mode": "TREND_MAIN",
                "regime_engine": "market_regime_framework",
                "regime_confidence": 0.82,
                "regime_duration_bars": 6,
                "regime_transition_reason": "",
                "feature_availability_json": json.dumps({"trend_block": True}, ensure_ascii=False),
                "risk_budget_multiplier": 0.8,
                "governor_budget_json": json.dumps(
                        {
                            "contract_version": "cn_a_governor_budget@1",
                            "budget_owner": "global_portfolio_governor",
                            "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core",
                            "budget_consumer_system_role": "stock_alpha_sleeve",
                            "budget_semantics": "consume_governor_sleeve_budget",
                            "total_risk_budget": 0.8,
                            "total_exposure_cap": 0.6,
                            "hard_max_positions": 10,
                            "effective_max_positions": 6,
                            "drawdown_state": "REDUCED",
                            "recovery_state": "DRAWDOWN_RECOVERY_PENDING",
                            "cooldown_state": "INACTIVE",
                            "defense_floor": 0.0,
                            "phase1_boundary_excludes": [
                                "value_bluechip_satellite",
                                "cn_etf_beta",
                                "insurance_overlay",
                            ],
                            "budget_reason_codes": [
                                "DRAWDOWN_REDUCED",
                                "TOTAL_RISK_BUDGET_REDUCED",
                            ],
                        "sleeve_budgets": {
                            "cn_stock_trend_alpha_core": {
                                "slot_cap": 6,
                                "available_slots": 4,
                                "positions_after_sell": 2,
                                "candidate_count": 3,
                                "selected_count": 2,
                                "budget_share": 1.0,
                                "raw_sleeve_ids": ["trend", "mr"],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(results_dir / "portfolio_daily.csv", index=False)
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "universe": {"start": "2026-03-02", "end": "2026-03-02", "benchmark": "000300.SH"},
                "regime_engine": {"engine": "market_regime_framework"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    ensure_standard_artifacts(
        results_dir=results_dir,
        result={
            "exp_id": "exp_governor_meta",
            "status": "OK",
            "tier": "T0",
            "start_date": "2026-03-02",
            "end_date": "2026-03-02",
            "total_return": 0.01,
            "max_drawdown": -0.02,
            "cagr": 0.01,
            "sharpe": 1.0,
        },
        base_cfg={
            "universe": {"start": "2026-03-02", "end": "2026-03-02", "benchmark": "000300.SH"},
            "schema_mapping": {},
        },
        overrides={},
    )

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    snapshot = dict(run_meta["governed_snapshot"])
    assert snapshot["total_risk_budget"] == 0.8
    assert snapshot["risk_budget_multiplier"] == 0.8
    assert snapshot["total_exposure_cap"] == 0.6
    assert snapshot["drawdown_state"] == "REDUCED"
    assert snapshot["budget_owner"] == "global_portfolio_governor"
    assert snapshot["budget_consumer_sleeve_id"] == "cn_stock_trend_alpha_core"
    assert snapshot["budget_semantics"] == "consume_governor_sleeve_budget"
    assert snapshot["budget_reason_codes"] == ["DRAWDOWN_REDUCED", "TOTAL_RISK_BUDGET_REDUCED"]
    assert snapshot["sleeve_budgets_summary"]["system_sleeves"] == ["cn_stock_trend_alpha_core"]


def test_ensure_standard_artifacts_writes_cn_etf_beta_phase1_summary(tmp_path) -> None:
    results_dir = tmp_path / "exp_etf_beta_meta"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-03-20",
                "nav": 1.0,
                "market_state": "BULL",
                "market_state_5": "BULL",
                "trade_mode": "TREND_MAIN",
                "regime_engine": "ma200_legacy",
                "diagnostics_input_json": json.dumps(
                    {
                        "diagnostics": {
                            "etf_beta_rebalance_day": True,
                            "etf_beta_deployable_slot_cap": 2,
                            "etf_beta_max_selected_symbols": 2,
                            "etf_beta_selected_cap": 2,
                            "etf_beta_eligible_symbols": [
                                "510050.SH",
                                "510300.SH",
                                "510500.SH",
                                "512100.SH",
                            ],
                            "etf_beta_selected_symbols": [
                                "510300.SH",
                                "512100.SH",
                            ],
                            "etf_beta_selection_reason_codes": {
                                "510300.SH": ["ETF_BETA_CORE_SCOPE", "ABSOLUTE_TREND_PASS"],
                                "512100.SH": ["ETF_BETA_CORE_SCOPE", "ABSOLUTE_TREND_PASS"],
                            },
                            "etf_beta_runtime_reason_codes": ["ETF_BETA_WEEKLY_SELECTION_ACTIVE", "ETF_BETA_VOL_TARGET_ACTIVE"],
                            "etf_beta_under_deploy_reason_codes": [],
                            "etf_beta_vol_target_active": True,
                            "etf_beta_vol_target_window": 20,
                            "etf_beta_vol_target_annualized_target": 0.18,
                            "etf_beta_vol_target_min_scale": 0.35,
                            "etf_beta_vol_target_max_scale": 1.0,
                            "etf_beta_vol_target_scale_by_symbol": {
                                "510300.SH": 0.72,
                                "512100.SH": 0.61,
                            },
                            "etf_beta_vol_target_realized_vol_by_symbol": {
                                "510300.SH": 0.25,
                                "512100.SH": 0.295,
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "budget_owner": "global_portfolio_governor",
                        "budget_consumer_sleeve_id": "cn_etf_beta",
                        "budget_consumer_system_role": "market_beta_sleeve",
                        "budget_semantics": "consume_governor_sleeve_budget",
                        "total_risk_budget": 0.7,
                        "total_exposure_cap": 0.6,
                        "target_exposure": 0.2,
                        "target_exposure_source": "fixed",
                        "min_deployable_exposure": 0.1,
                        "min_deployable_exposure_source": "fixed",
                        "fallback_allowed": False,
                        "under_deploy_reason_codes": [],
                        "actual_exposure": 0.18,
                        "actual_risk_exposure": 0.15,
                        "actual_fallback_exposure": 0.03,
                        "actual_other_exposure": 0.0,
                        "deployability_gap": 0.02,
                        "hard_max_positions": 10,
                        "effective_max_positions": 6,
                        "drawdown_state": "NORMAL",
                        "recovery_state": "INACTIVE",
                        "cooldown_state": "INACTIVE",
                        "budget_reason_codes": ["TOTAL_RISK_BUDGET_REDUCED"],
                        "sleeve_budgets": {
                            "cn_etf_beta": {
                                "slot_cap": 6,
                                "available_slots": 6,
                                "positions_after_sell": 0,
                                "candidate_count": 4,
                                "selected_count": 4,
                                "budget_share": 1.0,
                                "target_exposure": 0.2,
                                "target_exposure_source": "fixed",
                                "min_deployable_exposure": 0.1,
                                "min_deployable_exposure_source": "fixed",
                                "fallback_allowed": False,
                                "under_deploy_reason_codes": [],
                                "target_selected_count": 2,
                                "actual_exposure": 0.18,
                                "actual_risk_exposure": 0.15,
                                "actual_fallback_exposure": 0.03,
                                "actual_other_exposure": 0.0,
                                "deployability_gap": 0.02,
                                "raw_sleeve_ids": ["cn_etf_beta"],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(results_dir / "portfolio_daily.csv", index=False)
    (results_dir / "run_config.json").write_text(
        json.dumps(
            {
                "asset_scope": "cn_etf",
                "universe": {"start": "2016-11-04", "end": "2026-03-20", "benchmark": ""},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    ensure_standard_artifacts(
        results_dir=results_dir,
        result={
            "exp_id": "exp_etf_beta_meta",
            "status": "OK",
            "tier": "T0",
            "start_date": "2016-11-04",
            "end_date": "2026-03-20",
            "total_return": 0.01,
            "max_drawdown": -0.02,
            "cagr": 0.01,
            "sharpe": 1.0,
            "universe_meta": {
                "universe_mode": "CUSTOM",
                "asset_scope": "cn_etf",
                "membership_source": "cn_etf_catalog_whitelist",
                "membership_data_quality": "whitelist_verified",
                "audit_status": "PASS",
                "preset_id": "cn_etf_first_wave_core",
                "etf_batch": "cn_etf_first_wave_core",
                "benchmark_source": "first_etf_symbol",
                "etf_symbols": [
                    "510050.SH",
                    "510300.SH",
                    "510500.SH",
                    "511010.SH",
                    "512100.SH",
                    "518880.SH",
                ],
                "coverage_start": "2013-01-04",
                "coverage_end": "2026-03-20",
                "daily_table": "pams_cn_etf_daily",
                "price_series_semantics": "executable_price_only_not_total_return",
            },
        },
        base_cfg={
            "asset_scope": "cn_etf",
            "universe": {"start": "2016-11-04", "end": "2026-03-20", "benchmark": ""},
            "schema_mapping": {},
        },
        overrides={"asset_scope": "cn_etf"},
    )

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    etf_beta = dict(run_meta["etf_beta"])
    assert run_meta["data"]["benchmark"] == "510050.SH"
    assert run_meta["data"]["benchmark_source"] == "universe_meta.benchmark_source::first_etf_symbol"
    assert etf_beta["source_entry_type"] == "cn_etf_research_entry"
    assert etf_beta["eligible_etfs"] == ["510050.SH", "510300.SH", "510500.SH", "512100.SH"]
    assert etf_beta["selected_etfs"] == ["510300.SH", "512100.SH"]
    assert etf_beta["out_of_scope_etfs"] == ["518880.SH"]
    assert etf_beta["runtime_reason_codes"] == ["ETF_BETA_WEEKLY_SELECTION_ACTIVE", "ETF_BETA_VOL_TARGET_ACTIVE"]
    assert etf_beta["target_selected_count"] == 2
    assert etf_beta["target_exposure"] == 0.2
    assert etf_beta["target_exposure_source"] == "budget_snapshot"
    assert etf_beta["min_deployable_exposure"] == 0.1
    assert etf_beta["min_deployable_exposure_source"] == "budget_snapshot"
    assert etf_beta["fallback_allowed"] is False
    assert etf_beta["under_deploy_reason_codes"] == []
    assert etf_beta["actual_exposure"] == 0.18
    assert etf_beta["actual_risk_exposure"] == 0.15
    assert etf_beta["actual_fallback_exposure"] == 0.03
    assert etf_beta["deployability_gap"] == 0.02
    assert etf_beta["vol_target"]["active"] is True
    assert etf_beta["vol_target"]["window"] == 20
    assert etf_beta["vol_target"]["scale_by_symbol"]["510300.SH"] == 0.72
    assert etf_beta["sleeve_budget_used"]["slot_cap"] == 6
    assert etf_beta["sleeve_budget_used"]["target_exposure"] == 0.2
    assert etf_beta["sleeve_budget_used"]["target_exposure_source"] == "budget_snapshot"
    assert etf_beta["sleeve_budget_used"]["actual_exposure"] == 0.18
    assert run_meta["report_consistency"]["etf_beta_role"] == "cn_etf_beta"
    assert run_meta["report_consistency"]["etf_beta_budget_semantics"] == "consume_governor_sleeve_budget"
    assert run_meta["report_consistency"]["etf_beta_selected_etfs"] == ["510300.SH", "512100.SH"]
    assert run_meta["governed_snapshot"]["asset_scope"] == "cn_etf"
    assert run_meta["governed_snapshot"]["budget_consumer_sleeve_id"] == "cn_etf_beta"
    assert run_meta["governed_snapshot"]["budget_consumer_system_role"] == "market_beta_sleeve"
    assert run_meta["governed_snapshot"]["risk_budget_multiplier"] == 0.7
    assert run_meta["governed_snapshot"]["target_exposure"] == 0.2
    assert run_meta["governed_snapshot"]["target_exposure_source"] == "fixed"
    assert run_meta["governed_snapshot"]["min_deployable_exposure"] == 0.1
    assert run_meta["governed_snapshot"]["min_deployable_exposure_source"] == "fixed"
    assert run_meta["governed_snapshot"]["fallback_allowed"] is False
    assert run_meta["governed_snapshot"]["actual_risk_exposure"] == 0.15
    assert run_meta["governed_snapshot"]["actual_fallback_exposure"] == 0.03
    assert run_meta["governed_snapshot"]["deployability_gap"] == 0.02
    assert run_meta["governed_snapshot"]["sleeve_budgets"]["cn_etf_beta"]["slot_cap"] == 6
    assert run_meta["governed_snapshot"]["sleeve_budgets"]["cn_etf_beta"]["target_selected_count"] == 2
    assert run_meta["attribution"]["summary"]["sleeve_log_count"] == 1
    assert run_meta["governed_snapshot"]["attribution_summary"]["sleeve_log_count"] == 1
    assert run_meta["governed_snapshot"]["sleeve_selection_summary"]["cn_etf_beta"]["out_of_scope_etfs"] == [
        "518880.SH",
    ]
    assert run_meta["governed_snapshot"]["sleeve_selection_summary"]["cn_etf_beta"]["target_selected_count"] == 2
    assert run_meta["governed_snapshot"]["sleeve_selection_summary"]["cn_etf_beta"]["runtime_reason_codes"] == [
        "ETF_BETA_WEEKLY_SELECTION_ACTIVE",
        "ETF_BETA_VOL_TARGET_ACTIVE",
    ]
    audit = json.loads((results_dir / "audit.json").read_text(encoding="utf-8"))
    assert audit["attribution_audit"]["summary"]["sleeve_log_count"] == 1
    assert (results_dir / "attribution_audit.json").exists()

