from __future__ import annotations

from pathlib import Path
import json

from backend.research.study_definition import validate_study_payload
from backend.research import study_runner


def _study():
    return validate_study_payload(
        {
            "study_id": "v10/demo",
            "title": "Demo Study",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "residual split should improve ranking stability",
            "change_scope": {"modules_modified": ["ranking"]},
            "variants": [
                {
                    "name": "B0",
                    "config_patches": [
                        {"path": "signal_generation.ranking.residual_window", "value": 40},
                    ],
                }
            ],
            "windows": [
                {
                    "key": "main",
                    "role": "main",
                    "start": "2024-01-01",
                    "end": "2024-02-01",
                }
            ],
            "hard_gates": {"min_cagr": 0.1, "min_trades": 1},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {"fast_mode": True, "config_json": {"universe": {"benchmark": "000300.SH"}}},
        }
    )


def test_build_execution_plan_applies_window_and_variant_patch() -> None:
    plan = study_runner.build_execution_plan(_study())
    payload = plan[0]["request_payload"]
    assert payload["start_date"] == "2024-01-01"
    assert payload["end_date"] == "2024-02-01"
    assert payload["asset_scope"] == "cn_a_equity"
    assert payload["config_json"]["signal_generation"]["ranking"]["residual_window"] == 40
    assert payload["config_json"]["universe"]["start"] == "2024-01-01"


def test_build_execution_plan_can_patch_config_loaded_from_config_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "baseline.json"
    cfg_path.write_text(
        json.dumps({"signal_generation": {"ranking": {"residual_window": 20}}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    study = validate_study_payload(
        {
            "study_id": "v10/demo_path",
            "title": "Demo From Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "path-backed patching",
            "change_scope": {"modules_modified": ["ranking"]},
            "variants": [
                {
                    "name": "B0",
                    "config_patches": [
                        {"path": "signal_generation.ranking.residual_window", "value": 40},
                    ],
                }
            ],
            "windows": [{"key": "main", "role": "main", "start": "2024-01-01", "end": "2024-02-01"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {"config_path": str(cfg_path)},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["asset_scope"] == "cn_a_equity"
    assert payload["config_path"] == str(study_runner._default_runtime_config_path())
    assert payload["config_json"]["signal_generation"]["ranking"]["residual_window"] == 40


def test_build_execution_plan_resolves_relative_config_path_from_repo_root(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "configs" / "baseline.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({"universe": {"benchmark": "000300.SH"}}, ensure_ascii=False, indent=2), encoding="utf-8")
    runtime_cfg_path = tmp_path / "backend" / "configs" / "pams_cn_pg.json"
    runtime_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path.write_text(json.dumps({"db": {}, "schema_mapping": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(study_runner, "_repo_root", lambda: tmp_path)
    study = validate_study_payload(
        {
            "study_id": "v10/demo_relative_path",
            "title": "Demo Relative Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "relative path should stay executable",
            "change_scope": {"modules_modified": ["universe"]},
            "variants": [{"name": "B0"}],
            "windows": [{"key": "main", "role": "main", "start": "2024-01-01", "end": "2024-02-01"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {"config_path": "configs/baseline.json"},
            "metadata": {"materialize_config_json": True},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["config_path"] == str(runtime_cfg_path.resolve())
    assert payload["config_json"]["universe"]["benchmark"] == "000300.SH"


def test_build_execution_plan_loads_workbench_config_path_and_applies_window_bounds(tmp_path: Path) -> None:
    runtime_cfg_path = tmp_path / "runtime.json"
    runtime_cfg_path.write_text(
        json.dumps(
            {
                "db": {},
                "schema_mapping": {},
                "universe": {"benchmark": "000300.SH", "start": "2016-01-01", "end": "2026-01-01"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    study = validate_study_payload(
        {
            "study_id": "v10/demo_workbench_path",
            "title": "Demo Workbench Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "path-backed runtime config should stay executable",
            "change_scope": {"modules_modified": ["runtime"]},
            "variants": [
                {
                    "name": "B0",
                    "request_overrides": {
                        "workbench_config": {
                            "asset_context": {
                                "moneyflow_overlay": {"enabled": True, "mode": "shadow"},
                            }
                        }
                    },
                }
            ],
            "windows": [{"key": "main", "role": "main", "start": "2023-07-03", "end": "2026-03-16"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {
                "config_path": "backend/configs/pams_cn_pg.json",
                "workbench_config_path": str(runtime_cfg_path),
                "enable_multifactor_rank": True,
                "max_positions": 10,
            },
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["workbench_config"]["universe"]["start"] == "2023-07-03"
    assert payload["workbench_config"]["universe"]["end"] == "2026-03-16"
    assert payload["workbench_config"]["asset_context"]["moneyflow_overlay"]["mode"] == "shadow"


def test_build_execution_plan_can_merge_window_runtime_config_with_variant_overlay_mode(tmp_path: Path, monkeypatch) -> None:
    runtime_base_cfg = tmp_path / "research" / "studies" / "v10" / "configs" / "moneyflow_monthly_shadow_s1" / "1226_base.json"
    runtime_base_cfg.parent.mkdir(parents=True, exist_ok=True)
    runtime_base_cfg.write_text(
        json.dumps(
            {
                "db": {},
                "schema_mapping": {},
                "universe": {"benchmark": "000300.SH"},
                "asset_context": {
                    "moneyflow_overlay": {
                        "factor_snapshot_path": "outputs/studies/factors/moneyflow_factor_real_mainline_s2/1226/A_H20_CONTROL/machine/factor_snapshot.csv",
                        "score_source": "moneyflow_factor_real_mainline_s2:A_H20_CONTROL:1226",
                        "source_kind": "daily_factor_snapshot",
                        "factor_id": "monthly_divergence_rate",
                        "score_field": "rank_value",
                        "available_column": "availability_flag",
                        "lower_is_better": False,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    default_runtime_cfg = tmp_path / "backend" / "configs" / "pams_cn_pg.json"
    default_runtime_cfg.parent.mkdir(parents=True, exist_ok=True)
    default_runtime_cfg.write_text(json.dumps({"db": {}, "schema_mapping": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(study_runner, "_repo_root", lambda: tmp_path)
    study = validate_study_payload(
        {
            "study_id": "v10/demo_moneyflow_shadow",
            "title": "Demo Moneyflow Shadow",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "window-level source path plus variant-level overlay mode should compose cleanly",
            "change_scope": {"modules_modified": ["asset_context.moneyflow_overlay"]},
            "variants": [
                {
                    "name": "BULL_ONLY_TIEBREAK",
                    "request_overrides": {
                        "runtime_config_json": {
                            "asset_context": {
                                "moneyflow_overlay": {
                                    "enabled": True,
                                    "mode": "bull_only_tiebreak",
                                    "factor_role": "rank",
                                    "apply_layer": "candidate",
                                }
                            }
                        }
                    },
                }
            ],
            "windows": [
                {
                    "key": "1226",
                    "role": "audit",
                    "start": "2012-01-04",
                    "end": "2026-03-01",
                    "request_overrides": {"runtime_config_path": "research/studies/v10/configs/moneyflow_monthly_shadow_s1/1226_base.json"},
                }
            ],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
            "request_template": {"config_path": "backend/configs/pams_cn_pg.json"},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    overlay_cfg = payload["runtime_config_json"]["asset_context"]["moneyflow_overlay"]
    assert payload["config_path"] == str(default_runtime_cfg.resolve())
    assert payload["runtime_config_path"] == str(runtime_base_cfg.resolve())
    assert overlay_cfg["factor_snapshot_path"] == "outputs/studies/factors/moneyflow_factor_real_mainline_s2/1226/A_H20_CONTROL/machine/factor_snapshot.csv"
    assert overlay_cfg["score_source"] == "moneyflow_factor_real_mainline_s2:A_H20_CONTROL:1226"
    assert overlay_cfg["mode"] == "bull_only_tiebreak"
    assert overlay_cfg["source_kind"] == "daily_factor_snapshot"
    assert overlay_cfg["factor_id"] == "monthly_divergence_rate"
    assert overlay_cfg["enabled"] is True


def test_build_execution_plan_resolves_variant_override_config_path(tmp_path: Path, monkeypatch) -> None:
    runtime_cfg_path = tmp_path / "backend" / "configs" / "pams_cn_pg.json"
    runtime_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path.write_text(json.dumps({"db": {}, "schema_mapping": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    variant_cfg_path = tmp_path / "research" / "studies" / "v10" / "configs" / "demo.json"
    variant_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    variant_cfg_path.write_text(json.dumps({"mode": "experiment"}, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(study_runner, "_repo_root", lambda: tmp_path)
    study = validate_study_payload(
        {
            "study_id": "v10/demo_variant_path",
            "title": "Demo Variant Path",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "variant config_path should resolve from repo root",
            "change_scope": {"modules_modified": ["request_overrides.config_path"]},
            "variants": [
                {
                    "name": "B0",
                    "request_overrides": {"config_path": "research/studies/v10/configs/demo.json"},
                }
            ],
            "windows": [{"key": "main", "role": "main", "start": "2024-01-01", "end": "2024-02-01"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "study_conclusion"],
            "request_template": {"config_path": "backend/configs/pams_cn_pg.json"},
        }
    )

    payload = study_runner.build_execution_plan(study)[0]["request_payload"]
    assert payload["config_path"] == str(variant_cfg_path.resolve())


def test_run_study_delegates_to_runtime_and_output_services(monkeypatch, tmp_path: Path) -> None:
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_demo"
    exp_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "run_experiment_sync",
        lambda payload: {"exp_id": "exp_demo", "results_dir": str(exp_dir)},
    )
    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "resolve_results_dir",
        lambda **kwargs: exp_dir,
    )
    monkeypatch.setattr(
        study_runner,
        "_load_run_meta",
        lambda exp_id, results_dir: {"status": "OK", "counters": {"orders": 3}},
    )
    monkeypatch.setattr(
        study_runner,
        "_load_config_snapshot",
        lambda exp_id, results_dir: {"universe": {"start": "2024-01-01", "end": "2024-02-01"}},
    )
    monkeypatch.setattr(
        study_runner.experiment_query_service,
        "get_experiment_surface",
        lambda exp_id: {
            "summary": {"exp_id": exp_id, "label": exp_id},
            "perf": {"cagr": 0.15, "max_drawdown": -0.08, "sharpe": 1.1, "trades": 5},
            "audit": {"status": "pass"},
        },
    )
    monkeypatch.setattr(
        study_runner.experiment_compare_service,
        "compare_experiment_to_baseline",
        lambda **kwargs: {"metrics": {"cagr": {"delta": 0.02}, "max_drawdown": {"delta": 0.01}}},
    )
    monkeypatch.setattr(
        study_runner.experiment_summary_service,
        "write_dual_output_bundle",
        lambda **kwargs: {"machine": {"nac": "machine/nac.json"}, "human": {"conclusion": "human/conclusion.md"}},
    )
    monkeypatch.setattr(
        study_runner.baseline_report_service,
        "append_experiment_to_baseline",
        lambda **kwargs: {"ledger": "machine/experiment_ledger.jsonl", "champion_updated": False},
    )
    monkeypatch.setattr(
        study_runner.study_conclusion_registry,
        "append_study_conclusion",
        lambda **kwargs: {"registry": "studies/conclusions/v10/demo/registry.jsonl"},
    )

    result = study_runner.run_study(_study())
    run = result["runs"][0]
    assert run["exp_id"] == "exp_demo"
    assert run["verdict"]["status"] == "PASS"
    assert run["machine_outputs"]["nac"] == "machine/nac.json"
    assert run["baseline_outputs"] == {}
    assert run["conclusion_outputs"]["registry"] == "studies/conclusions/v10/demo/registry.jsonl"


def test_run_study_can_opt_in_to_baseline_append(monkeypatch, tmp_path: Path) -> None:
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_demo"
    exp_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "run_experiment_sync",
        lambda payload: {"exp_id": "exp_demo", "results_dir": str(exp_dir)},
    )
    monkeypatch.setattr(
        study_runner.experiment_runtime_access,
        "resolve_results_dir",
        lambda **kwargs: exp_dir,
    )
    monkeypatch.setattr(study_runner, "_load_run_meta", lambda exp_id, results_dir: {})
    monkeypatch.setattr(study_runner, "_load_config_snapshot", lambda exp_id, results_dir: {})
    monkeypatch.setattr(
        study_runner.experiment_query_service,
        "get_experiment_surface",
        lambda exp_id: {"perf": {"cagr": 0.15, "max_drawdown": -0.08, "sharpe": 1.1, "trades": 5}, "audit": {}},
    )
    monkeypatch.setattr(
        study_runner.experiment_compare_service,
        "compare_experiment_to_baseline",
        lambda **kwargs: {"metrics": {}, "baseline_source_of_truth": {"kind": "linked_experiment"}},
    )
    monkeypatch.setattr(
        study_runner.experiment_summary_service,
        "write_dual_output_bundle",
        lambda **kwargs: {"machine": {}, "human": {}},
    )
    monkeypatch.setattr(
        study_runner.study_conclusion_registry,
        "append_study_conclusion",
        lambda **kwargs: {"registry": "studies/conclusions/v10/demo/registry.jsonl"},
    )
    monkeypatch.setattr(
        study_runner.baseline_report_service,
        "append_experiment_to_baseline",
        lambda **kwargs: {"ledger": "machine/experiment_ledger.jsonl", "champion_updated": False},
    )

    result = study_runner.run_study(_study(), append_to_baseline=True)
    assert result["runs"][0]["baseline_outputs"]["ledger"] == "machine/experiment_ledger.jsonl"


def test_custom_runner_study_delegates_to_stock_lifecycle_fragility_surface(monkeypatch) -> None:
    study = validate_study_payload(
        {
            "study_id": "factors/stock_lifecycle_fragility_demo",
            "title": "Lifecycle Demo",
            "asset_scope": "cn_a_equity",
            "baseline_id": "baseline_V10_1",
            "hypothesis": "lifecycle fragility should explain exit risk",
            "change_scope": {"modules_modified": ["backend.research.stock_lifecycle_fragility_study"]},
            "variants": [{"name": "B0_EQUAL"}],
            "windows": [{"key": "1226", "role": "audit", "start": "2012-01-04", "end": "2026-03-20"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle", "baseline_append"],
            "request_template": {
                "runtime_config_path": "outputs/experiments/exp_20260409_052948616_a4c5/run_config.json",
                "config_path": "backend/configs/pams_cn_pg.json",
            },
            "metadata": {"runner_mode": "stock_lifecycle_fragility_surface"},
        }
    )
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "stock_lifecycle_fragility_only"}

    monkeypatch.setattr(study_runner, "run_stock_lifecycle_fragility_study", _fake_runner)
    result = study_runner.run_study(
        study,
        only_window_keys=["1226"],
        only_variant_names=["B0_EQUAL"],
        write_dual_output=False,
        append_to_baseline=False,
    )
    assert result["status"] == "stock_lifecycle_fragility_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1
