from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research import study_loader, study_runner
from backend.research.account_state_score_catalog import build_account_state_score_catalog
from backend.research.account_state_score_snapshots import (
    build_account_state_combo_score_snapshot,
    build_account_state_score_snapshots,
)
from backend.research.snapshot_backed_study import run_snapshot_backed_research_study
from backend.research.stock_alpha_factor_catalog import build_stock_alpha_factor_catalog
from backend.research.stock_alpha_factor_snapshots import (
    build_stock_alpha_factor_score_snapshot,
    build_stock_alpha_factor_snapshots,
)


def _price_history() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=180)
    rows: list[dict[str, object]] = []
    bases = {
        "sh600000": 10.0,
        "sz000001": 12.0,
        "sh601318": 14.0,
        "sz300750": 16.0,
    }
    slopes = {
        "sh600000": 0.08,
        "sz000001": 0.05,
        "sh601318": 0.03,
        "sz300750": 0.10,
    }
    for symbol, base in bases.items():
        slope = slopes[symbol]
        for idx, dt in enumerate(dates):
            close = base + slope * idx
            rows.append(
                {
                    "date": dt,
                    "symbol": symbol,
                    "close": close,
                    "high": close * 1.01,
                    "amount": 1.5e8 + idx * 1.0e6,
                }
            )
    return pd.DataFrame(rows)


def _benchmark_history() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=180)
    rows: list[dict[str, object]] = []
    for idx, dt in enumerate(dates):
        close = 3400.0 + 0.8 * idx + 20.0 * ((idx % 15) / 15.0)
        rows.append({"date": dt, "symbol": "sh000300", "close": close})
    return pd.DataFrame(rows)


def test_repo_study_definitions_load_for_snapshot_backed_runtime() -> None:
    stock_study = study_loader.load_study_definition("snapshots/stock_alpha_snapshot_backed_demo")
    state_study = study_loader.load_study_definition("snapshots/account_state_snapshot_backed_demo")
    assert stock_study.metadata["runner_mode"] == "snapshot_backed_research_runtime"
    assert stock_study.metadata["snapshot_surface_kind"] == "stock_alpha"
    assert state_study.metadata["runner_mode"] == "snapshot_backed_research_runtime"
    assert state_study.metadata["snapshot_surface_kind"] == "account_state"


def test_custom_runner_study_delegates_to_snapshot_backed_runtime(monkeypatch) -> None:
    study = study_loader.load_study_definition("snapshots/stock_alpha_snapshot_backed_demo")
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "snapshot_backed_only"}

    monkeypatch.setattr(study_runner, "run_snapshot_backed_research_study", _fake_runner)
    result = study_runner.run_study(
        study,
        only_window_keys=["2326"],
        only_variant_names=["B0_SNAPSHOT"],
        write_dual_output=False,
        append_to_baseline=False,
    )
    assert result["status"] == "snapshot_backed_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1


def test_run_snapshot_backed_research_study_for_stock_alpha(tmp_path: Path) -> None:
    factor_snapshot = build_stock_alpha_factor_snapshots(_price_history())
    factor_score = build_stock_alpha_factor_score_snapshot(
        factor_snapshot,
        factor_ids=["breakout_distance", "residual_strength"],
        factor_weights={"breakout_distance": 1.0, "residual_strength": 1.0},
    )
    catalog_path = tmp_path / "factor_catalog.json"
    factor_path = tmp_path / "factor_snapshot.csv"
    score_path = tmp_path / "factor_score_snapshot.csv"
    catalog_path.write_text(json.dumps(build_stock_alpha_factor_catalog(), ensure_ascii=False, indent=2), encoding="utf-8")
    factor_snapshot.to_csv(factor_path, index=False, encoding="utf-8-sig")
    factor_score.to_csv(score_path, index=False, encoding="utf-8-sig")

    study = study_loader.load_study_definition("snapshots/stock_alpha_snapshot_backed_demo")
    plan = study_runner.build_execution_plan(study, only_window_keys=["2326"], only_variant_names=["B0_SNAPSHOT"])
    payload = plan[0]["request_payload"]
    payload["run_params"]["snapshot_inputs"][0]["path"] = str(catalog_path)
    payload["run_params"]["snapshot_inputs"][1]["path"] = str(factor_path)
    payload["run_params"]["snapshot_inputs"][2]["path"] = str(score_path)
    payload["run_params"]["snapshot_inputs"][0]["config_hash"] = "hash-factor"

    result = run_snapshot_backed_research_study(
        study=study,
        plan=plan,
        write_dual_output=True,
        append_to_baseline=False,
    )
    run = result["runs"][0]
    analysis_path = Path(run["machine_outputs"]["analysis"])
    lineage_path = Path(run["machine_outputs"]["snapshot_lineage"])
    assert analysis_path.exists()
    assert lineage_path.exists()
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert payload["analysis"]["surface_kind"] == "stock_alpha"
    assert payload["analysis"]["factor_snapshot"]["row_count"] > 0


def test_run_snapshot_backed_research_study_for_account_state(tmp_path: Path) -> None:
    score_snapshot = build_account_state_score_snapshots(_benchmark_history(), benchmark_symbol="sh000300")
    combo_snapshot = build_account_state_combo_score_snapshot(
        score_snapshot,
        score_ids=["risk_on_score", "recovery_score", "defense_score"],
        score_weights={"risk_on_score": 1.0, "recovery_score": 1.0, "defense_score": 1.0},
    )
    catalog_path = tmp_path / "score_catalog.json"
    score_path = tmp_path / "score_snapshot.csv"
    combo_path = tmp_path / "score_combo_snapshot.csv"
    catalog_path.write_text(json.dumps(build_account_state_score_catalog(), ensure_ascii=False, indent=2), encoding="utf-8")
    score_snapshot.to_csv(score_path, index=False, encoding="utf-8-sig")
    combo_snapshot.to_csv(combo_path, index=False, encoding="utf-8-sig")

    study = study_loader.load_study_definition("snapshots/account_state_snapshot_backed_demo")
    plan = study_runner.build_execution_plan(study, only_window_keys=["2326"], only_variant_names=["B0_SNAPSHOT"])
    payload = plan[0]["request_payload"]
    payload["run_params"]["snapshot_inputs"][0]["path"] = str(catalog_path)
    payload["run_params"]["snapshot_inputs"][1]["path"] = str(score_path)
    payload["run_params"]["snapshot_inputs"][2]["path"] = str(combo_path)
    payload["run_params"]["snapshot_inputs"][1]["config_hash"] = "hash-state"

    result = run_snapshot_backed_research_study(
        study=study,
        plan=plan,
        write_dual_output=True,
        append_to_baseline=False,
    )
    run = result["runs"][0]
    analysis_path = Path(run["machine_outputs"]["analysis"])
    lineage_path = Path(run["machine_outputs"]["snapshot_lineage"])
    assert analysis_path.exists()
    assert lineage_path.exists()
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert payload["analysis"]["surface_kind"] == "account_state"
    assert payload["analysis"]["score_snapshot"]["row_count"] > 0


def test_snapshot_backed_runtime_fail_fast_on_missing_input() -> None:
    study = study_loader.load_study_definition("snapshots/stock_alpha_snapshot_backed_demo")
    plan = study_runner.build_execution_plan(study, only_window_keys=["2326"], only_variant_names=["B0_SNAPSHOT"])
    payload = plan[0]["request_payload"]
    payload["run_params"]["snapshot_inputs"][0]["path"] = "outputs/studies/snapshots/__missing__/factor_catalog.json"
    try:
        run_snapshot_backed_research_study(
            study=study,
            plan=plan,
            write_dual_output=False,
            append_to_baseline=False,
        )
    except FileNotFoundError as exc:
        assert "snapshot input not found" in str(exc)
        return
    raise AssertionError("expected FileNotFoundError")
