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
            "baseline_id": "baseline_V10",
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
            "baseline_id": "baseline_V10",
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
    assert payload["config_json"]["signal_generation"]["ranking"]["residual_window"] == 40


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

    result = study_runner.run_study(_study())
    run = result["runs"][0]
    assert run["exp_id"] == "exp_demo"
    assert run["verdict"]["status"] == "PASS"
    assert run["machine_outputs"]["nac"] == "machine/nac.json"
    assert run["baseline_outputs"]["ledger"] == "machine/experiment_ledger.jsonl"
