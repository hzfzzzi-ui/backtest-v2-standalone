from __future__ import annotations

import json
from pathlib import Path

from backend.core.services import baseline_report_service


def test_append_experiment_to_baseline_appends_fail_and_only_promotes_pass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RESULTS_ROOT", str(tmp_path / "outputs"))

    fail_result = baseline_report_service.append_experiment_to_baseline(
        baseline_id="baseline_V10",
        exp_id="exp_fail",
        study_id="v10/demo",
        title="Demo Study",
        verdict={"status": "FAIL", "reason": "cagr<0.1"},
        perf={"cagr": 0.08, "max_drawdown": -0.1, "sharpe": 0.7, "trades": 4},
        compare={"metrics": {"cagr": {"delta": -0.01}}},
        human_output_refs={"conclusion": "human/conclusion.md"},
        window_key="main",
        variant_name="B0",
    )
    baseline_dir = tmp_path / "outputs" / "baselines" / "baseline_V10"
    assert fail_result["champion_updated"] is False
    assert not (baseline_dir / "machine" / "latest_champion.json").exists()

    pass_result = baseline_report_service.append_experiment_to_baseline(
        baseline_id="baseline_V10",
        exp_id="exp_pass",
        study_id="v10/demo",
        title="Demo Study",
        verdict={"status": "PASS", "reason": ""},
        perf={"cagr": 0.18, "max_drawdown": -0.09, "sharpe": 1.1, "trades": 6},
        compare={"metrics": {"cagr": {"delta": 0.03}}},
        human_output_refs={"conclusion": "human/conclusion.md"},
        window_key="main",
        variant_name="B1",
    )
    ledger_lines = (baseline_dir / "machine" / "experiment_ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    champion = json.loads((baseline_dir / "machine" / "latest_champion.json").read_text(encoding="utf-8"))
    report_index = json.loads((baseline_dir / "machine" / "report_index.json").read_text(encoding="utf-8"))

    assert len(ledger_lines) == 2
    assert pass_result["champion_updated"] is True
    assert champion["exp_id"] == "exp_pass"
    assert len(report_index["rows"]) == 2
