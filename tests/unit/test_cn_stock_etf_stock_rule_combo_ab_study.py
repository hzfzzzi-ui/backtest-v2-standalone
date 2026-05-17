from __future__ import annotations

import json
from pathlib import Path

from backend.research import study_loader, study_runner
from backend.research import cn_stock_etf_stock_rule_combo_ab_study as combo_ab
from backend.research.study_definition import validate_study_payload


def test_stock_rule_combo_ab_dry_run_matrix_has_expected_controls() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_high_chase_d5_combo_ab_v1")
    plan = study_runner.build_execution_plan(study)

    assert len(plan) == 12
    assert [variant.name for variant in study.variants] == [
        "B0_COMBO_V3_REPLAY",
        "HC_D5_IMMEDIATE_COMBO",
        "HC_D5_WATCH_DAY5_COMBO",
        "HC_D5_WATCH_DAY10_COMBO",
    ]
    assert [window.key for window in study.windows] == ["1626", "1217", "1226"]


def test_stock_rule_combo_ab_payload_patches_only_stock_runtime_and_keeps_unified_nav_truth() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_high_chase_d5_combo_ab_v1")
    plan = study_runner.build_execution_plan(
        study,
        only_variant_names=["HC_D5_IMMEDIATE_COMBO"],
        only_window_keys=["1626"],
    )
    payload = combo_ab.build_stock_rule_combo_request_payload(study, plan[0])
    config_json = payload["config_json"]
    unified_runtime = config_json["unified_runtime"]
    source_contract = unified_runtime["component_source_contract"]
    combo_context_source_contract = unified_runtime["combo_context"]["component_source_contract"]
    stock_component = source_contract["components"]["stock_component"]
    etf_component = source_contract["components"]["etf_component"]
    stock_compile = stock_component["compile_input"]
    etf_compile = etf_component["compile_input"]
    stock_runtime = stock_compile["runtime_config"]
    etf_runtime = etf_compile["runtime_config"]
    stock_params = stock_runtime["strategy"]["params"]

    assert payload["asset_scope"] == "cn_a_equity"
    assert "execution_contract" not in unified_runtime
    assert "execution_contract" not in unified_runtime["combo_context"]
    assert source_contract == combo_context_source_contract
    assert config_json["universe"]["start"] == "2016-01-01"
    assert config_json["universe"]["end"] == "2026-05-08"
    assert stock_compile["semantic_config"]["universe"]["start"] == "2016-01-01"
    assert etf_compile["semantic_config"]["universe"]["end"] == "2026-05-08"
    assert stock_runtime["universe"]["start"] == "2016-01-01"
    assert stock_runtime["universe"]["end"] == "2026-05-08"
    assert etf_runtime["universe"]["start"] == "2016-01-01"
    assert etf_runtime["universe"]["end"] == "2026-05-08"
    assert stock_params["enable_mfe_mae_confirmation_exit"] is True
    assert stock_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert stock_params["mfe_mae_confirmation_action"] == "exit"
    assert stock_params["mfe_mae_confirmation_lookahead_bars"] == 3
    assert stock_params["mfe_mae_confirmation_min_mfe_pct"] == 0.02
    assert stock_params["mfe_mae_confirmation_max_mae_pct"] == -0.05
    assert stock_params["mfe_mae_confirmation_exit_pct"] == 0.5
    assert etf_runtime["asset_scope"] == "cn_etf"
    assert etf_component["source"]["source_kind"] == "study_shadow"
    assert stock_component["source"]["source_kind"] == "combo_stock_rule_ab"
    assert "precomputed_component_results" not in json.dumps(payload, ensure_ascii=False)


def test_stock_rule_combo_ab_watch_payload_patches_only_watch_params() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_high_chase_d5_combo_ab_v1")
    plan = study_runner.build_execution_plan(
        study,
        only_variant_names=["HC_D5_WATCH_DAY5_COMBO"],
        only_window_keys=["1626"],
    )
    payload = combo_ab.build_stock_rule_combo_request_payload(study, plan[0])
    stock_params = payload["config_json"]["unified_runtime"]["component_source_contract"]["components"][
        "stock_component"
    ]["compile_input"]["runtime_config"]["strategy"]["params"]
    etf_runtime = payload["config_json"]["unified_runtime"]["component_source_contract"]["components"]["etf_component"][
        "compile_input"
    ]["runtime_config"]

    assert stock_params["enable_mfe_mae_confirmation_exit"] is True
    assert stock_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert stock_params["mfe_mae_confirmation_action"] == "watch_day10"
    assert stock_params["mfe_mae_confirmation_lookahead_bars"] == 3
    assert stock_params["mfe_mae_watch_review_bars"] == 5
    assert stock_params["mfe_mae_watch_review_min_mfe_pct"] == 0.02
    assert stock_params["mfe_mae_watch_review_max_current_return_pct"] == 0.0
    assert stock_params["mfe_mae_watch_review_max_mae_pct"] == -0.05
    assert stock_params["mfe_mae_watch_deep_mae_immediate_pct"] == -0.08
    assert etf_runtime["asset_scope"] == "cn_etf"
    assert "precomputed_component_results" not in json.dumps(payload, ensure_ascii=False)


def test_stock_rule_combo_deep_mae_study_materializes_depth_variants() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_combo_ab_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["1626"])

    assert len(plan) == 6
    assert [variant.name for variant in study.variants] == [
        "B0_COMBO_V3_REPLAY",
        "HC_D5_IMMEDIATE_COMBO",
        "HC_D5_DEEP_ONLY_IMMEDIATE_COMBO",
        "HC_D5_MILD_WATCH_DEEP_IMMEDIATE_DAY10_COMBO",
        "HC_D5_DEEP_ONLY_WATCH_DAY10_COMBO",
        "HC_D5_ALL_WATCH_DAY10_COMBO",
    ]


def test_stock_rule_combo_deep_mae_payload_patches_only_stock_depth_params() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_combo_ab_v1")
    plan = study_runner.build_execution_plan(
        study,
        only_variant_names=["HC_D5_DEEP_ONLY_WATCH_DAY10_COMBO"],
        only_window_keys=["1626"],
    )
    payload = combo_ab.build_stock_rule_combo_request_payload(study, plan[0])
    source_contract = payload["config_json"]["unified_runtime"]["component_source_contract"]
    stock_runtime = source_contract["components"]["stock_component"]["compile_input"]["runtime_config"]
    etf_runtime = source_contract["components"]["etf_component"]["compile_input"]["runtime_config"]
    stock_params = stock_runtime["strategy"]["params"]

    assert stock_params["enable_mfe_mae_confirmation_exit"] is True
    assert stock_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert stock_params["mfe_mae_confirmation_action"] == "watch_day10"
    assert stock_params["mfe_mae_confirmation_lookahead_bars"] == 3
    assert stock_params["mfe_mae_confirmation_min_mfe_pct"] == 0.02
    assert stock_params["mfe_mae_confirmation_max_mae_pct"] == -0.08
    assert stock_params["mfe_mae_watch_review_bars"] == 10
    assert stock_params["mfe_mae_watch_review_max_mae_pct"] == -0.08
    assert stock_params["mfe_mae_watch_deep_mae_immediate_pct"] == -1.0
    assert stock_runtime["universe"]["start"] == "2016-01-01"
    assert etf_runtime["asset_scope"] == "cn_etf"
    assert etf_runtime["universe"]["start"] == "2016-01-01"
    assert "precomputed_component_results" not in json.dumps(payload, ensure_ascii=False)


def test_stock_rule_combo_restore_candidate_study_patches_only_restore_params() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_etf_d6_restore_candidate_ab_v1")
    plan = study_runner.build_execution_plan(
        study,
        only_variant_names=["HC_D5_IMMEDIATE_RESTORE_COMBO"],
        only_window_keys=["1626"],
    )
    payload = combo_ab.build_stock_rule_combo_request_payload(study, plan[0])
    source_contract = payload["config_json"]["unified_runtime"]["component_source_contract"]
    stock_runtime = source_contract["components"]["stock_component"]["compile_input"]["runtime_config"]
    etf_runtime = source_contract["components"]["etf_component"]["compile_input"]["runtime_config"]
    stock_params = stock_runtime["strategy"]["params"]

    assert len(study.variants) == 3
    assert stock_params["enable_mfe_mae_confirmation_exit"] is True
    assert stock_params["mfe_mae_confirmation_scope"] == "high_chase"
    assert stock_params["mfe_mae_confirmation_action"] == "exit"
    assert stock_params["mfe_mae_confirmation_max_mae_pct"] == -0.05
    assert stock_params["enable_mfe_mae_restore_candidate"] is True
    assert stock_params["mfe_mae_restore_candidate_scope"] == "high_chase"
    assert stock_params["mfe_mae_restore_candidate_max_bars"] == 40
    assert stock_params["mfe_mae_restore_candidate_target_basis"] == "original_target"
    assert stock_params["mfe_mae_restore_candidate_clear_on_fill"] is True
    assert etf_runtime["asset_scope"] == "cn_etf"
    assert "precomputed_component_results" not in json.dumps(payload, ensure_ascii=False)


def test_stock_rule_combo_same_window_comparison_includes_all_candidates() -> None:
    runs = [
        {
            "window_key": "1626",
            "variant_name": "B0_COMBO_V3_REPLAY",
            "exp_id": "b0",
            "perf": {"cagr": 0.10, "sharpe": 0.8, "max_drawdown": -0.2, "calmar": 0.5, "trades": 100},
            "stock_d5_trigger_count": 0,
            "stock_d5_reason_counts": {"total": 0},
            "component_exp_ids": {"stock_exp_id": "stock_b0", "etf_exp_id": "etf_b0"},
        },
        {
            "window_key": "1626",
            "variant_name": "HC_D5_IMMEDIATE_COMBO",
            "exp_id": "immediate",
            "perf": {"cagr": 0.11, "sharpe": 0.9, "max_drawdown": -0.19, "calmar": 0.58, "trades": 110},
            "stock_d5_trigger_count": 10,
            "stock_d5_reason_counts": {"total": 10},
            "component_exp_ids": {"stock_exp_id": "stock_i", "etf_exp_id": "etf_i"},
        },
        {
            "window_key": "1626",
            "variant_name": "HC_D5_WATCH_DAY5_COMBO",
            "exp_id": "watch5",
            "perf": {"cagr": 0.12, "sharpe": 1.0, "max_drawdown": -0.18, "calmar": 0.67, "trades": 105},
            "stock_d5_trigger_count": 7,
            "stock_d5_reason_counts": {"total": 7},
            "component_exp_ids": {"stock_exp_id": "stock_w5", "etf_exp_id": "etf_w5"},
        },
    ]

    comparisons = combo_ab._same_window_comparisons(runs)

    assert [row["variant_name"] for row in comparisons] == ["HC_D5_IMMEDIATE_COMBO", "HC_D5_WATCH_DAY5_COMBO"]
    assert comparisons[0]["metrics_delta"]["cagr"] == 0.009999999999999995
    assert comparisons[1]["candidate_d5_trigger_count"] == 7


def test_stock_rule_combo_runner_result_records_component_exp_ids_and_d5_count(monkeypatch, tmp_path: Path) -> None:
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_stock_rule_combo",
            "title": "Demo Combo Stock Rule",
            "asset_scope": "cn_a_equity",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "HC_D5_IMMEDIATE_COMBO"}],
            "windows": [{"key": "1626", "role": "main", "start": "2016-01-01", "end": "2026-05-08"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
        }
    )
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_combo"
    exp_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        combo_ab,
        "build_stock_rule_combo_request_payload",
        lambda study, item: {"study_meta": {"demo": True}},
    )
    monkeypatch.setattr(
        combo_ab.experiment_runtime_access,
        "run_experiment_sync",
        lambda payload: {"exp_id": "exp_combo", "results_dir": str(exp_dir)},
    )
    monkeypatch.setattr(
        combo_ab.experiment_runtime_access,
        "resolve_results_dir",
        lambda **kwargs: exp_dir,
    )
    monkeypatch.setattr(
        combo_ab.experiment_query_service,
        "get_experiment_surface",
        lambda exp_id: {"perf": {"cagr": 0.12, "max_drawdown": -0.2, "sharpe": 0.8, "trades": 10}, "audit": {}},
    )
    monkeypatch.setattr(
        combo_ab.experiment_compare_service,
        "compare_experiment_to_baseline",
        lambda **kwargs: {"metrics": {"cagr": {"delta": 0.01}}},
    )
    monkeypatch.setattr(
        combo_ab,
        "_load_run_meta",
        lambda exp_id, results_dir: {
            "dependencies": {
                "component_runs": {
                    "stock_alpha_core": {"exp_id": "exp_stock"},
                    "etf_beta": {"exp_id": "exp_etf"},
                }
            }
        },
    )
    monkeypatch.setattr(combo_ab, "_load_config_snapshot", lambda exp_id, results_dir: {})
    monkeypatch.setattr(
        combo_ab,
        "_stock_d5_reason_counts",
        lambda exp_id: {
            "MFE_MAE_CONFIRMATION_EXIT": 20,
            "MFE_MAE_CONFIRMATION_WATCH_EXIT": 5,
            "total": 25,
        },
    )
    monkeypatch.setattr(
        combo_ab.experiment_summary_service,
        "write_dual_output_bundle",
        lambda **kwargs: {"machine": {"perf": "machine/perf.json"}, "human": {"summary": "human/summary.md"}},
    )
    monkeypatch.setattr(
        combo_ab,
        "_study_root",
        lambda study: tmp_path / "outputs" / "studies" / "cn_stock_etf" / "demo_stock_rule_combo",
    )

    result = combo_ab.run_cn_stock_etf_stock_rule_combo_ab_study(
        study=study,
        plan=[
            {
                "window_key": "1626",
                "window_role": "main",
                "variant_name": "HC_D5_IMMEDIATE_COMBO",
                "request_payload": {},
            }
        ],
    )

    run = result["runs"][0]
    assert run["research_only"] is True
    assert run["exp_id"] == "exp_combo"
    assert run["component_exp_ids"] == {"stock_exp_id": "exp_stock", "etf_exp_id": "exp_etf"}
    assert run["stock_d5_trigger_count"] == 25
    assert run["stock_d5_reason_counts"]["MFE_MAE_CONFIRMATION_EXIT"] == 20
    assert run["stock_d5_reason_counts"]["MFE_MAE_CONFIRMATION_WATCH_EXIT"] == 5
    assert run["baseline_outputs"] == {}
    assert run["machine_outputs"]["perf"] == "machine/perf.json"


def test_study_runner_delegates_to_stock_rule_combo_runner(monkeypatch) -> None:
    study = validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_stock_rule_combo",
            "title": "Demo Combo Stock Rule",
            "asset_scope": "cn_a_equity",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "demo",
            "change_scope": {"modules_modified": ["demo"]},
            "variants": [{"name": "B0_COMBO_V3_REPLAY"}],
            "windows": [{"key": "1626", "role": "main", "start": "2016-01-01", "end": "2026-05-08"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
            "metadata": {"runner_mode": "cn_stock_etf_stock_rule_combo_ab"},
        }
    )
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "stock_rule_combo_only"}

    monkeypatch.setattr(study_runner, "run_cn_stock_etf_stock_rule_combo_ab_study", _fake_runner)
    result = study_runner.run_study(study, only_window_keys=["1626"], only_variant_names=["B0_COMBO_V3_REPLAY"])

    assert result["status"] == "stock_rule_combo_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1
