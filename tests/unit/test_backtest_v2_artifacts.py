from __future__ import annotations

import json
from pathlib import Path

from backend.api.endpoints.backtest_v2_artifacts import write_manifest


def test_write_manifest_includes_foundation_protocol_fields(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_test"
    results_dir.mkdir(parents=True, exist_ok=True)
    for name in ("input_config.json", "resolved_config.json", "compiled_plan.json"):
        (results_dir / name).write_text("{}", encoding="utf-8")
    (results_dir / "baseline_compare.json").write_text(
        json.dumps({"status": "PASS"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _, manifest = write_manifest(
        results_dir,
        {
            "exp_id": "exp_test",
            "status": "OK",
            "artifacts": {
                "perf": "perf.json",
                "stage_summary": "stage_summary.json",
                "input_config": "input_config.json",
                "resolved_config": "resolved_config.json",
                "compiled_plan": "compiled_plan.json",
            },
            "total_return": 0.25,
            "max_drawdown": -0.10,
            "cagr": 0.12,
            "sharpe": 1.1,
            "trades": 4,
            "turnover": 0.2,
            "stage_pipeline": {
                "execution_shell": "stage_pipeline_shell_legacy_adapter",
                "stage_order": ["S1", "S2", "S7"],
                "enabled_stages": ["S1", "S2", "S7"],
            },
            "stage_summary": {
                "schema_version": "stage_pipeline_summary@1",
            },
        },
    )

    assert manifest["exp_id"] == "exp_test"
    assert manifest["experiment_id"] == "exp_test"
    assert manifest["schema_version"] == "backtest_v2_experiment_manifest@2"
    assert manifest["baseline_compare_status"] == "PASS"
    assert manifest["config_snapshots"] == {
        "input_config": "input_config.json",
        "resolved_config": "resolved_config.json",
        "compiled_plan": "compiled_plan.json",
    }
    assert manifest["artifacts"]["baseline_compare"] == "baseline_compare.json"
    assert manifest["artifacts"]["stage_summary"] == "stage_summary.json"
    assert manifest["core_artifacts"] == {
        "perf": "perf.json",
        "input_config": "input_config.json",
        "resolved_config": "resolved_config.json",
        "compiled_plan": "compiled_plan.json",
        "baseline_compare": "baseline_compare.json",
        "stage_summary": "stage_summary.json",
    }
    assert manifest["optional_artifacts"]["report"] == {
        "path": None,
        "available": False,
        "kind": "html_export",
    }
    assert manifest["stage_pipeline"]["execution_shell"] == "stage_pipeline_shell_legacy_adapter"
    assert manifest["stage_summary"]["artifact"] == "stage_summary.json"
