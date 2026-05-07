from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research import study_loader, study_runner
from backend.research.moneyflow_factor_study import run_moneyflow_factor_study


def _price_history() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=90)
    rows: list[dict[str, object]] = []
    bases = {"sh600000": 10.0, "sz000001": 12.0, "sh601318": 14.0, "sz300750": 16.0}
    slopes = {"sh600000": 0.06, "sz000001": 0.04, "sh601318": 0.03, "sz300750": 0.08}
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
                    "amount": 1.2e8 + idx * 5.0e5,
                    "circ_mv": 5.0e9 + idx * 1.0e7,
                }
            )
    return pd.DataFrame(rows)


def _moneyflow_history() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=90)
    rows: list[dict[str, object]] = []
    amps = {"sh600000": 5.0e6, "sz000001": 9.0e6, "sh601318": 3.0e6, "sz300750": 7.0e6}
    for symbol, amp in amps.items():
        for idx, dt in enumerate(dates):
            rows.append(
                {
                    "trade_date": dt,
                    "symbol": symbol,
                    "net_mf_amount": amp + ((idx % 10) - 5) * 1.0e5,
                }
            )
    return pd.DataFrame(rows)


def test_repo_study_definition_loads_for_moneyflow_factor_surface() -> None:
    study = study_loader.load_study_definition("factors/moneyflow_factor_surface_demo")
    assert study.study_id == "factors/moneyflow_factor_surface_demo"
    assert study.metadata["runner_mode"] == "moneyflow_factor_surface"


def test_custom_runner_study_delegates_to_moneyflow_factor_surface(monkeypatch) -> None:
    study = study_loader.load_study_definition("factors/moneyflow_factor_surface_demo")
    captured: dict[str, object] = {}

    def _fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "moneyflow_factor_only"}

    monkeypatch.setattr(study_runner, "run_moneyflow_factor_study", _fake_runner)
    result = study_runner.run_study(
        study,
        only_window_keys=["2326"],
        only_variant_names=["B0_EQUAL"],
        write_dual_output=False,
        append_to_baseline=False,
    )
    assert result["status"] == "moneyflow_factor_only"
    assert captured["study"] == study
    assert isinstance(captured["plan"], list) and len(captured["plan"]) == 1


def test_run_moneyflow_factor_study_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    study = study_loader.load_study_definition("factors/moneyflow_factor_surface_demo")
    plan = study_runner.build_execution_plan(study, only_window_keys=["2326"], only_variant_names=["B0_EQUAL"])

    class _Provider:
        def load_ohlcv_daily(self, symbols, start, end, source=""):
            frame = _price_history()
            return frame.loc[frame["symbol"].isin([str(item).lower() for item in symbols])].copy()

        def load_stock_moneyflow(self, symbols, start, end, table="pit_stock_moneyflow_v2"):
            frame = _moneyflow_history()
            return frame.loc[frame["symbol"].isin([str(item).lower() for item in symbols])].copy()

    monkeypatch.setattr(
        "backend.research.moneyflow_factor_study._create_provider_from_payload",
        lambda payload: (_Provider(), {"config_source": "stub"}, "hash-demo"),
    )
    monkeypatch.setattr(
        "backend.research.moneyflow_factor_study._outputs_root",
        lambda: tmp_path,
    )

    result = run_moneyflow_factor_study(
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
    assert payload["study_id"] == "factors/moneyflow_factor_surface_demo"
    assert "single_factor" in payload["analysis"]
    assert "factor_score" in payload["analysis"]
