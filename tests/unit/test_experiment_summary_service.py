from __future__ import annotations

from pathlib import Path

from backend.core.services import experiment_summary_service


def test_write_dual_output_bundle_creates_machine_and_human_outputs(tmp_path: Path) -> None:
    refs = experiment_summary_service.write_dual_output_bundle(
        exp_id="exp_demo",
        results_dir=tmp_path,
        title="Demo Study",
        baseline_id="baseline_V10_1",
        study_id="v10/demo",
        hypothesis="demo hypothesis",
        change_scope={"modules_modified": ["ranking"]},
        surface={
            "summary": {"exp_id": "exp_demo", "label": "exp_demo"},
            "perf": {"cagr": 0.12, "max_drawdown": -0.09, "sharpe": 1.0, "trades": 6},
            "audit": {"status": "pass"},
        },
        compare={"metrics": {"cagr": {"delta": 0.01}}},
        audit={"status": "pass"},
        run_meta={"status": "OK"},
        config_snapshot={"universe": {"start": "2024-01-01"}},
        verdict={"status": "PASS", "reason": "", "next_action": "promote_candidate"},
        window_key="main",
        variant_name="B0",
    )

    machine_root = tmp_path / "machine"
    human_root = tmp_path / "human"
    assert sorted(path.name for path in machine_root.iterdir()) == [
        "audit.json",
        "compare.json",
        "config_snapshot.json",
        "manifest.json",
        "nac.json",
        "perf.json",
        "run_meta.json",
        "surface.json",
    ]
    assert sorted(path.name for path in human_root.iterdir()) == ["conclusion.md", "summary.txt"]
    assert refs["machine"]["nac"] == "machine/nac.json"
    assert refs["human"]["conclusion"] == "human/conclusion.md"
