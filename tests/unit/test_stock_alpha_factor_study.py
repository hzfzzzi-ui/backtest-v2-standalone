from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research import study_loader, study_runner
from backend.research.stock_alpha_factor_study import run_stock_alpha_factor_study


def _price_history() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=70)
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


def test_repo_study_definition_loads_for_stock_alpha_factor_surface() -> None:
    study = study_loader.load_study_definition("factors/stock_alpha_factor_surface_demo")
    assert study.study_id == "factors/stock_alpha_factor_surface_demo"
    assert study.windows[0].key == "2326"
    assert study.metadata["runner_mode"] == "stock_alpha_factor_surface"


def test_custom_runner_study_delegates_to_stock_alpha_factor_surface(monkeypatch) -> None:
    study = study_loader.load_study_definition("factors/stock_alpha_factor_surface_demo")
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "factor_surface_only"}

    monkeypatch.setattr(study_runner, "run_stock_alpha_factor_study", _fake_runner)
    result = study_runner.run_study(
        study,
        only_window_keys=["2326"],
        only_variant_names=["B0_EQUAL"],
        write_dual_output=False,
        append_to_baseline=False,
    )
    assert result["status"] == "factor_surface_only"
    assert captured["study"] == study
    plan = captured["plan"]
    assert isinstance(plan, list) and len(plan) == 1


def test_run_stock_alpha_factor_study_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    study = study_loader.load_study_definition("factors/stock_alpha_factor_surface_demo")
    plan = study_runner.build_execution_plan(study, only_window_keys=["2326"], only_variant_names=["B0_EQUAL"])

    class _Provider:
        def load_ohlcv_daily(self, symbols, start, end, source):
            frame = _price_history().copy()
            frame = frame.loc[frame["symbol"].isin([str(s).lower() for s in symbols])].reset_index(drop=True)
            return frame

    monkeypatch.setattr(
        "backend.research.stock_alpha_factor_study._create_provider_from_payload",
        lambda payload: (_Provider(), {"config_source": "stub"}, "hash-demo"),
    )
    monkeypatch.setattr(
        "backend.research.stock_alpha_factor_study._outputs_root",
        lambda: tmp_path,
    )

    result = run_stock_alpha_factor_study(
        study=study,
        plan=plan,
        write_dual_output=True,
        append_to_baseline=False,
    )

    run = result["runs"][0]
    analysis_path = Path(run["machine_outputs"]["analysis"])
    snapshot_path = Path(run["machine_outputs"]["factor_snapshot"])
    summary_path = Path(run["human_outputs"]["summary"])

    assert analysis_path.exists()
    assert snapshot_path.exists()
    assert summary_path.exists()

    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert payload["study_id"] == "factors/stock_alpha_factor_surface_demo"
    assert "single_factor" in payload["analysis"]
    assert "factor_score" in payload["analysis"]
