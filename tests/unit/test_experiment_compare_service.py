from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from backend.core.services import experiment_compare_service


def test_compare_experiment_to_baseline_reports_linked_exp_source_of_truth(monkeypatch, tmp_path: Path) -> None:
    baseline_dir = tmp_path / "outputs" / "baselines" / "baseline_V10_1" / "machine"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "latest_champion.json").write_text(
        json.dumps(
            {
                "perf": {
                    "cagr": 0.10,
                    "max_drawdown": -0.20,
                    "sharpe": 0.50,
                    "trades": 100,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        experiment_compare_service.baseline_access,
        "load_baseline_record",
        lambda baseline_id: {"baseline_id": baseline_id, "linked_exp_id": "exp_base"},
    )
    monkeypatch.setattr(
        experiment_compare_service.baseline_access,
        "baseline_dir",
        lambda baseline_id: tmp_path / "outputs" / "baselines" / baseline_id,
    )

    def _fake_contract(exp_id: str) -> dict:
        if exp_id == "exp_base":
            return {
                "perf": {
                    "total_return": 1.0,
                    "cagr": 0.12,
                    "max_drawdown": -0.18,
                    "sharpe": 0.72,
                    "calmar": 0.66,
                    "trades": 88,
                    "turnover": 0.02,
                }
            }
        return {
            "perf": {
                "total_return": 1.5,
                "cagr": 0.14,
                "max_drawdown": -0.16,
                "sharpe": 0.80,
                "calmar": 0.88,
                "trades": 90,
                "turnover": 0.03,
            }
        }

    monkeypatch.setattr(
        experiment_compare_service.experiment_query_service,
        "get_execution_regression_contract",
        _fake_contract,
    )

    result = experiment_compare_service.compare_experiment_to_baseline(
        exp_id="exp_candidate",
        baseline_id="baseline_V10_1",
    )

    assert result["status"] == "ok"
    assert result["baseline_source_of_truth"]["kind"] == "linked_experiment"
    conflicts = result["baseline_source_of_truth"]["display_layer_conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["artifact"].endswith("machine/latest_champion.json")
    assert any(field["field"] == "cagr" for field in conflicts[0]["fields"])


def test_compare_experiment_to_baseline_falls_back_to_baseline_ledger_when_linked_exp_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    baseline_root = tmp_path / "outputs" / "baselines" / "baseline_V10_1"
    machine_dir = baseline_root / "machine"
    machine_dir.mkdir(parents=True, exist_ok=True)
    (machine_dir / "experiment_ledger.jsonl").write_text(
        json.dumps(
            {
                "baseline_id": "baseline_V10_1",
                "exp_id": "exp_base_missing",
                "summary": {
                    "perf": {
                        "cagr": 0.12,
                        "max_drawdown": -0.18,
                        "sharpe": 0.72,
                        "calmar": 0.66,
                        "trades": 88,
                        "turnover": 0.02,
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        experiment_compare_service.baseline_access,
        "load_baseline_record",
        lambda baseline_id: {"baseline_id": baseline_id, "linked_exp_id": "exp_base_missing"},
    )
    monkeypatch.setattr(
        experiment_compare_service.baseline_access,
        "baseline_dir",
        lambda baseline_id: baseline_root,
    )

    def _fake_contract(exp_id: str) -> dict:
        if exp_id == "exp_base_missing":
            raise HTTPException(status_code=404, detail="experiment not found")
        return {
            "perf": {
                "total_return": 1.5,
                "cagr": 0.14,
                "max_drawdown": -0.16,
                "sharpe": 0.80,
                "calmar": 0.88,
                "trades": 90,
                "turnover": 0.03,
            }
        }

    monkeypatch.setattr(
        experiment_compare_service.experiment_query_service,
        "get_execution_regression_contract",
        _fake_contract,
    )

    result = experiment_compare_service.compare_experiment_to_baseline(
        exp_id="exp_candidate",
        baseline_id="baseline_V10_1",
    )

    assert result["status"] == "baseline_ledger_fallback"
    assert result["baseline_source_of_truth"]["kind"] == "baseline_ledger_fallback"
    assert result["metrics"]["cagr"]["baseline"] == 0.12
    assert result["metrics"]["turnover"]["baseline"] == 0.02
