from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research import study_loader, study_runner
from backend.research.style_industry_state_switch_shadow_study import (
    DEFAULT_THRESHOLDS,
    STYLE_INDEX_SPECS,
    compute_candidate_pool_pressure_daily,
    compute_entry_candidate_pressure_daily,
    compute_industry_health_daily,
    compute_rotation_pressure_daily,
    compute_style_state_daily,
    run_style_industry_state_switch_shadow_study,
)
from backend.research.study_definition import validate_study_payload


def _synthetic_style_index_history(days: int = 90) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    rows: list[dict[str, object]] = []
    specs = {
        "000300.SH": 0.9990,
        "000905.SH": 1.0010,
        "000852.SH": 1.0025,
    }
    for symbol, growth in specs.items():
        for idx, dt in enumerate(dates):
            rows.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "open": 100.0 * (growth ** idx),
                    "high": 100.0 * (growth ** idx),
                    "low": 100.0 * (growth ** idx),
                    "close": 100.0 * (growth ** idx),
                    "volume": 1000,
                    "amount": 100000,
                }
            )
    return pd.DataFrame(rows)


def _synthetic_industry_index_history(days: int = 90) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    rows: list[dict[str, object]] = []
    specs = {
        "801010.SI": 1.0018,
        "801030.SI": 1.0004,
        "801050.SI": 0.9980,
    }
    for symbol, growth in specs.items():
        for idx, dt in enumerate(dates):
            rows.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "open": 100.0 * (growth ** idx),
                    "high": 100.0 * (growth ** idx),
                    "low": 100.0 * (growth ** idx),
                    "close": 100.0 * (growth ** idx),
                }
            )
    return pd.DataFrame(rows)


def _synthetic_trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2026-03-05", "symbol": "sh600001", "side": "BUY", "qty": 100, "sleeve_id": "stock_alpha_core"},
            {"date": "2026-03-05", "symbol": "sz000001", "side": "BUY", "qty": 100, "sleeve_id": "stock_alpha_core"},
            {"date": "2026-03-08", "symbol": "sh600001", "side": "SELL", "qty": 100, "sleeve_id": "stock_alpha_core"},
        ]
    )


def _synthetic_candidate_signals() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2026-03-05", "symbol": "sh600001", "is_candidate": True, "selected_flag": True, "reject_reason": "", "cash_blocked_flag": False, "final_score_rank": 1},
            {"date": "2026-03-05", "symbol": "sz000001", "is_candidate": True, "selected_flag": False, "reject_reason": "SKIP_NO_CASH", "cash_blocked_flag": True, "final_score_rank": 2},
            {"date": "2026-03-06", "symbol": "sz000001", "is_candidate": True, "selected_flag": False, "reject_reason": "NOT_IN_TOPK", "cash_blocked_flag": False, "final_score_rank": 3},
        ]
    )


def _synthetic_nav() -> pd.DataFrame:
    dates = pd.date_range("2026-03-01", periods=12, freq="D")
    return pd.DataFrame(
        {
            "date": [dt.strftime("%Y-%m-%d") for dt in dates],
            "stock_ret": [0.0, 0.0, 0.0, 0.0, -0.01, 0.02, -0.03, 0.01, 0.0, 0.0, 0.0, 0.0],
            "combo_ret": [0.0] * len(dates),
        }
    )


def _synthetic_stock_industry_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "sh600001", "industry_l1": "农林牧渔", "start_date": "2026-01-01", "end_date": None},
            {"symbol": "sz000001", "industry_l1": "有色金属", "start_date": "2026-01-01", "end_date": None},
        ]
    )


def _study(tmp_path: Path):
    return validate_study_payload(
        {
            "study_id": "cn_stock_etf/demo_style_state_shadow",
            "title": "Demo Style State Shadow",
            "asset_scope": "cn_a_equity",
            "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
            "hypothesis": "style state shadow should be research-only",
            "change_scope": {"modules_modified": ["research_only_style_state_shadow"]},
            "variants": [{"name": "M1_STYLE_STATE"}],
            "windows": [{"key": "main", "role": "main", "start": "2026-01-01", "end": "2026-03-31"}],
            "hard_gates": {},
            "required_outputs": ["machine_bundle", "human_bundle"],
            "request_template": {
                "config_path": "backend/configs/pams_cn_pg.json",
                "runner_params": {
                    "style_index_history_csv": str(tmp_path / "style_index_history.csv"),
                    "industry_index_history_csv": str(tmp_path / "industry_index_history.csv"),
                    "baseline_artifact_root": str(tmp_path / "baseline"),
                },
            },
            "metadata": {"runner_mode": "cn_stock_style_industry_state_switch_shadow", "research_only": True},
        }
    )


def test_compute_style_state_daily_detects_mid_small_beta() -> None:
    daily = compute_style_state_daily(
        _synthetic_style_index_history(),
        {key: float(value) for key, value in DEFAULT_THRESHOLDS.items()},
        specs=STYLE_INDEX_SPECS,
    )

    assert not daily.empty
    last = daily.iloc[-1]
    assert last["style_state_label"] == "mid_small_beta"
    assert last["coverage_status"] == "complete"
    assert float(last["csi1000_minus_hs300_ret20"]) > 0.03


def test_compute_industry_health_daily_builds_daily_breadth() -> None:
    daily, long_daily = compute_industry_health_daily(
        _synthetic_industry_index_history(),
        {key: float(value) for key, value in DEFAULT_THRESHOLDS.items()},
        specs={
            "801010.SI": {"symbol": "801010.SI", "name": "agri"},
            "801030.SI": {"symbol": "801030.SI", "name": "chem"},
            "801050.SI": {"symbol": "801050.SI", "name": "metal"},
        },
    )

    assert not daily.empty
    assert not long_daily.empty
    last = daily.iloc[-1]
    assert int(last["healthy_industry_count"]) >= 1
    assert int(last["weak_industry_count"]) >= 1
    assert last["industry_market_health_label"] == "industry_mixed"


def test_compute_rotation_pressure_daily_maps_holdings_to_i1_health() -> None:
    industry_daily, long_daily = compute_industry_health_daily(
        _synthetic_industry_index_history(),
        {key: float(value) for key, value in DEFAULT_THRESHOLDS.items()},
        specs={
            "801010.SI": {"symbol": "801010.SI", "name": "agri"},
            "801030.SI": {"symbol": "801030.SI", "name": "chem"},
            "801050.SI": {"symbol": "801050.SI", "name": "metal"},
        },
    )
    assert not industry_daily.empty

    daily, held = compute_rotation_pressure_daily(
        trades=_synthetic_trades(),
        nav=_synthetic_nav(),
        industry_history=_synthetic_stock_industry_history(),
        industry_long_daily=long_daily,
    )

    assert not daily.empty
    assert not held.empty
    pressure = daily.loc[daily["date"].eq("2026-03-07")].iloc[0]
    assert int(pressure["held_stock_count"]) == 2
    assert pressure["rotation_pressure_label"] in {"held_mixed", "rotation_pressure", "held_broad_weak"}


def test_compute_entry_candidate_pressure_daily_compares_entry_to_holdings() -> None:
    _, long_daily = compute_industry_health_daily(
        _synthetic_industry_index_history(),
        {key: float(value) for key, value in DEFAULT_THRESHOLDS.items()},
        specs={
            "801010.SI": {"symbol": "801010.SI", "name": "agri"},
            "801030.SI": {"symbol": "801030.SI", "name": "chem"},
            "801050.SI": {"symbol": "801050.SI", "name": "metal"},
        },
    )
    rotation_daily, _ = compute_rotation_pressure_daily(
        trades=_synthetic_trades(),
        nav=_synthetic_nav(),
        industry_history=_synthetic_stock_industry_history(),
        industry_long_daily=long_daily,
    )

    daily, entry_industry = compute_entry_candidate_pressure_daily(
        orders=_synthetic_trades(),
        nav=_synthetic_nav(),
        industry_history=_synthetic_stock_industry_history(),
        industry_long_daily=long_daily,
        rotation_daily=rotation_daily,
    )

    assert not daily.empty
    assert not entry_industry.empty
    row = daily.loc[daily["date"].eq("2026-03-05")].iloc[0]
    assert int(row["entry_stock_count"]) == 2
    assert row["entry_vs_held_alignment_label"] != "no_entry_signal"


def test_compute_candidate_pool_pressure_daily_uses_full_candidate_rows() -> None:
    _, long_daily = compute_industry_health_daily(
        _synthetic_industry_index_history(),
        {key: float(value) for key, value in DEFAULT_THRESHOLDS.items()},
        specs={
            "801010.SI": {"symbol": "801010.SI", "name": "agri"},
            "801030.SI": {"symbol": "801030.SI", "name": "chem"},
            "801050.SI": {"symbol": "801050.SI", "name": "metal"},
        },
    )
    rotation_daily, _ = compute_rotation_pressure_daily(
        trades=_synthetic_trades(),
        nav=_synthetic_nav(),
        industry_history=_synthetic_stock_industry_history(),
        industry_long_daily=long_daily,
    )

    daily, candidate_industry = compute_candidate_pool_pressure_daily(
        candidates=_synthetic_candidate_signals(),
        nav=_synthetic_nav(),
        industry_history=_synthetic_stock_industry_history(),
        industry_long_daily=long_daily,
        rotation_daily=rotation_daily,
    )

    assert not daily.empty
    assert not candidate_industry.empty
    row = daily.loc[daily["date"].eq("2026-03-05")].iloc[0]
    assert int(row["candidate_stock_count"]) == 2
    assert int(row["selected_stock_count"]) == 1
    assert int(row["cash_blocked_stock_count"]) == 1
    assert row["candidate_vs_held_diagnosis_label"] != "no_candidate_signal"


def test_runner_writes_research_only_outputs(tmp_path: Path, monkeypatch) -> None:
    csv_path = tmp_path / "style_index_history.csv"
    industry_csv_path = tmp_path / "industry_index_history.csv"
    _synthetic_style_index_history().to_csv(csv_path, index=False, encoding="utf-8-sig")
    _synthetic_industry_index_history().to_csv(industry_csv_path, index=False, encoding="utf-8-sig")
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True)
    _synthetic_nav().to_csv(baseline_dir / "nav.csv", index=False, encoding="utf-8-sig")
    _synthetic_trades().to_csv(baseline_dir / "portfolio_trades.csv", index=False, encoding="utf-8-sig")
    _synthetic_trades().to_csv(baseline_dir / "orders.csv", index=False, encoding="utf-8-sig")
    _synthetic_candidate_signals().to_csv(baseline_dir / "candidate_signals.csv", index=False, encoding="utf-8-sig")
    monkeypatch.setattr(
        "backend.research.style_industry_state_switch_shadow_study.outputs_root",
        lambda: tmp_path / "outputs",
    )
    monkeypatch.setattr(
        "backend.research.style_industry_state_switch_shadow_study._load_stock_industry_history_from_runtime",
        lambda **kwargs: (_synthetic_stock_industry_history(), {"missing_source": False}),
    )
    study = _study(tmp_path)
    plan = study_runner.build_execution_plan(study)

    result = run_style_industry_state_switch_shadow_study(study=study, plan=plan)

    assert result["research_only"] is True
    assert result["not_nav_backtest"] is True
    run = result["runs"][0]
    assert run["exp_id"] == ""
    assert run["implemented_layers"] == [
        "M1_STYLE_STATE",
        "I1_INDUSTRY_HEALTH",
        "R1_ROTATION_PRESSURE",
        "R2_ENTRY_CANDIDATE_ALIGNMENT",
        "R3_CANDIDATE_POOL_ALIGNMENT",
    ]
    assert Path(run["machine_outputs"]["daily"]).exists()
    assert Path(run["machine_outputs"]["industry_daily"]).exists()
    assert Path(run["machine_outputs"]["rotation_pressure_daily"]).exists()
    assert Path(run["machine_outputs"]["entry_candidate_pressure_daily"]).exists()
    assert Path(run["machine_outputs"]["candidate_pool_pressure_daily"]).exists()
    payload = json.loads(Path(run["machine_outputs"]["summary"]).read_text(encoding="utf-8"))
    assert payload["summary"]["latest_style_state"] == "mid_small_beta"
    assert payload["industry_summary"]["row_count"] > 0
    assert payload["rotation_pressure_summary"]["row_count"] > 0
    assert payload["entry_candidate_pressure_summary"]["row_count"] > 0
    assert payload["candidate_pool_pressure_summary"]["row_count"] > 0


def test_runner_missing_source_is_inconclusive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.research.style_industry_state_switch_shadow_study.outputs_root",
        lambda: tmp_path / "outputs",
    )
    study = _study(tmp_path)
    plan = study_runner.build_execution_plan(study)

    result = run_style_industry_state_switch_shadow_study(study=study, plan=plan)

    verdict = result["runs"][0]["verdict"]
    assert verdict["status"] == "inconclusive"
    assert "not found" in verdict["reason"]


def test_study_yaml_dry_run_has_style_state_runner() -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1")
    plan = study_runner.build_execution_plan(study, only_window_keys=["recent_2526"])

    assert study.metadata["runner_mode"] == "cn_stock_style_industry_state_switch_shadow"
    assert plan[0]["variant_name"] == "M1_STYLE_STATE"
    assert plan[0]["request_payload"]["runner_params"]["style_index_symbols"]["csi1000"] == "000852.SH"


def test_study_runner_delegates_to_style_state_runner(monkeypatch) -> None:
    study = study_loader.load_study_definition("cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1")

    def _fake_runner(**kwargs):
        assert kwargs["study"].study_id == study.study_id
        return {
            "study_id": study.study_id,
            "status": "OK",
            "research_only": True,
            "not_nav_backtest": True,
            "runs": [],
        }

    monkeypatch.setattr(study_runner, "run_style_industry_state_switch_shadow_study", _fake_runner)

    result = study_runner.run_study(study, only_window_keys=["recent_2526"])

    assert result["study_id"] == study.study_id
