from __future__ import annotations

import json
from pathlib import Path

from backend.research import study_conclusion_registry


def test_study_conclusion_registry_normalizes_legacy_pass_to_gate_status(tmp_path: Path) -> None:
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_demo"
    exp_dir.mkdir(parents=True)

    result = study_conclusion_registry.append_study_conclusion(
        study_id="demo/study",
        compared_baseline_id="BASE",
        verdict={"status": "PASS", "reason": "min_trades passed", "checks": {"min_trades": {"passed": True}}},
        exp_id="exp_demo",
        window_key="1626",
        variant_name="A1",
        compare={"metrics": {"cagr": {"candidate": 0.01, "baseline": 0.02, "delta": -0.01}}},
        results_dir=exp_dir,
    )

    entry = result["entry"]
    assert entry["verdict"] == "inconclusive"
    assert entry["gate_status"] == "PASS"
    assert entry["gate_reason"] == "min_trades passed"
    assert entry["gate_checks"] == {"min_trades": {"passed": True}}

    registry_path = tmp_path / "outputs" / result["registry"]
    rows = [json.loads(line) for line in registry_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["verdict"] == "inconclusive"
    assert rows[0]["gate_status"] == "PASS"


def test_study_conclusion_registry_accepts_formal_verdict_with_gate_status(tmp_path: Path) -> None:
    exp_dir = tmp_path / "outputs" / "experiments" / "exp_demo"
    exp_dir.mkdir(parents=True)

    result = study_conclusion_registry.append_study_conclusion(
        study_id="demo/study",
        compared_baseline_id="BASE",
        verdict={
            "status": "falsified",
            "reason": "same-window compare worsened",
            "gate_status": "PASS",
            "gate_checks": {"min_trades": {"passed": True}},
        },
        exp_id="exp_demo",
        window_key="1626",
        variant_name="A1",
        compare={"metrics": {"cagr": {"candidate": 0.01, "baseline": 0.02, "delta": -0.01}}},
        results_dir=exp_dir,
    )

    entry = result["entry"]
    assert entry["verdict"] == "falsified"
    assert entry["gate_status"] == "PASS"
    assert entry["gate_checks"] == {"min_trades": {"passed": True}}
