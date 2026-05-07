from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research import study_loader, study_runner
from backend.research.account_state_score_study import run_account_state_score_study


def _benchmark_history() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=180)
    rows: list[dict[str, object]] = []
    for idx, dt in enumerate(dates):
        base = 3400.0 + 0.5 * idx
        close = base + 18.0 * ((idx % 20) / 20.0) - 9.0 * ((idx % 7) / 7.0)
        rows.append(
            {
                "date": dt,
                "symbol": "sh000300",
                "close": close,
            }
        )
    return pd.DataFrame(rows)


def test_repo_study_definition_loads_for_account_state_score_surface() -> None:
    study = study_loader.load_study_definition("state_scores/account_state_score_surface_demo")
    assert study.study_id == "state_scores/account_state_score_surface_demo"
    assert study.windows[0].key == "2326"
    assert study.metadata["runner_mode"] == "account_state_score_surface"


def test_custom_runner_study_delegates_to_account_state_score_surface(monkeypatch) -> None:
    study = study_loader.load_study_definition("state_scores/account_state_score_surface_demo")
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "account_state_surface_only"}

    monkeypatch.setattr(study_runner, "run_account_state_score_study", _fake_runner)
    result = study_runner.run_study(
        study,
        only_window_keys=["2326"],
        only_variant_names=["B0_EQUAL"],
        write_dual_output=False,
        append_to_baseline=False,
    )
    assert result["status"] == "account_state_surface_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1


def test_run_account_state_score_study_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    study = study_loader.load_study_definition("state_scores/account_state_score_surface_demo")
    plan = study_runner.build_execution_plan(study, only_window_keys=["2326"], only_variant_names=["B0_EQUAL"])

    class _Provider:
        def load_ohlcv_daily(self, symbols, start, end, source):
            frame = _benchmark_history().copy()
            frame = frame.loc[frame["symbol"].isin([str(s).lower() for s in symbols])].reset_index(drop=True)
            return frame

    monkeypatch.setattr(
        "backend.research.account_state_score_study._create_provider_from_payload",
        lambda payload: (_Provider(), {"config_source": "stub"}, "hash-demo"),
    )
    monkeypatch.setattr(
        "backend.research.account_state_score_study._outputs_root",
        lambda: tmp_path,
    )

    result = run_account_state_score_study(
        study=study,
        plan=plan,
        write_dual_output=True,
        append_to_baseline=False,
    )

    run = result["runs"][0]
    analysis_path = Path(run["machine_outputs"]["analysis"])
    snapshot_path = Path(run["machine_outputs"]["score_snapshot"])
    summary_path = Path(run["human_outputs"]["summary"])

    assert analysis_path.exists()
    assert snapshot_path.exists()
    assert summary_path.exists()

    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert payload["study_id"] == "state_scores/account_state_score_surface_demo"
    assert "single_score" in payload["analysis"]
    assert "combo_score" in payload["analysis"]
