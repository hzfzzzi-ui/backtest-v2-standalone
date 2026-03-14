from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.api.endpoints.backtest_v2_artifacts import (
    _build_counters,
    _sanitize_historical_stock_names,
    write_manifest,
)


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
    assert "optional_artifacts" not in manifest
    assert manifest["stage_pipeline"]["execution_shell"] == "stage_pipeline_shell_legacy_adapter"
    assert manifest["stage_summary"]["artifact"] == "stage_summary.json"


def test_sanitize_historical_stock_names_drops_current_st_name_without_pit_flag() -> None:
    trades_df = pd.DataFrame(
        [
            {"date": "2016-08-29", "symbol": "sz000793", "side": "BUY"},
            {"date": "2018-08-06", "symbol": "sz000793", "side": "SELL"},
            {"date": "2020-01-02", "symbol": "sh600519", "side": "BUY"},
        ]
    )

    out = _sanitize_historical_stock_names(
        trades_df,
        {"sz000793": "ST鍗庨椈", "sh600519": "璐靛窞鑼呭彴"},
        {"2016-08-29|sz000793": "-", "2018-08-06|sz000793": "-", "2020-01-02|sh600519": "-"},
    )

    assert "sz000793" not in out
    assert out["sh600519"] == "璐靛窞鑼呭彴"


def test_sanitize_historical_stock_names_keeps_pit_st_name() -> None:
    trades_df = pd.DataFrame([{"date": "2025-03-18", "symbol": "sz000793", "side": "BUY"}])

    out = _sanitize_historical_stock_names(
        trades_df,
        {"sz000793": "ST鍗庨椈"},
        {"2025-03-18|sz000793": "PIT_ST"},
    )

    assert out["sz000793"] == "ST鍗庨椈"


def test_build_counters_reads_sorting_diagnostics_from_daily_csv(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_test"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "mf_rank_triggered": 1,
                "mf_rank_applied": 1,
                "mf_candidates_when_triggered": 3,
                "mf_topk_reject_count": 2,
                "mf_concentrated_selected_count": 1,
                "mf_gate_on": 1,
                "strong_risk_on": 0,
                "mf_rank_suppressed_by_strong_gate": 0,
                "selected_count": 2,
            },
            {
                "mf_rank_triggered": 0,
                "mf_rank_applied": 0,
                "mf_candidates_when_triggered": 0,
                "mf_topk_reject_count": 0,
                "mf_concentrated_selected_count": 0,
                "mf_gate_on": 0,
                "strong_risk_on": 1,
                "mf_rank_suppressed_by_strong_gate": 1,
                "selected_count": 0,
            },
        ]
    ).to_csv(results_dir / "portfolio_daily.csv", index=False)
    pd.DataFrame([{"reason_code": "ATR_STOP_LOSS", "triggered_rule": "ATR_TRAIL_UPDATE"}]).to_csv(
        results_dir / "portfolio_trades.csv",
        index=False,
    )

    counters = _build_counters(
        {
            "avg_positions": 4.2,
            "max_positions": 10,
            "trend_slope_block_count": 0,
            "mf_rank_applied_rate": 0.0,
            "mf_gate_on_rate": 0.0,
            "raw_signal": 10,
            "blocked": 1,
            "orders": 2,
            "skipped": 0,
            "closed_trades": 1,
        },
        results_dir,
        funnel_obj={},
    )

    assert counters["mf_rank_trigger_days"] == 1
    assert counters["mf_rank_trigger_rate"] == 0.5
    assert counters["mf_rank_applied_days"] == 1
    assert counters["mf_rank_applied_rate"] == 0.5
    assert counters["mf_avg_candidates_when_triggered"] == 3.0
    assert counters["mf_topk_reject_count"] == 2
    assert counters["mf_concentrated_buy_rate"] == 0.5
    assert counters["mf_gate_on_days"] == 1
    assert counters["mf_gate_on_rate"] == 0.5
    assert counters["gate_on_rate"] == 0.5
    assert counters["strong_risk_on_days"] == 1
    assert counters["strong_risk_on_rate"] == 0.5
    assert counters["mf_rank_suppressed_by_strong_gate_days"] == 1


def test_build_counters_maps_order_reject_aliases_to_cash_and_lot_counts(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_test"
    results_dir.mkdir(parents=True, exist_ok=True)

    counters = _build_counters(
        {
            "avg_positions": 0.0,
            "max_positions": 10,
            "candidate_diag_reason_counts": {
                "SKIP_CASH_INSUFFICIENT": 1,
                "SKIP_NO_CASH": 4,
                "SKIP_LOT_TOO_SMALL": 2,
                "SKIP_QTY_ZERO": 3,
            },
        },
        results_dir,
        funnel_obj={},
    )

    assert counters["cash_skip_count"] == 5
    assert counters["lot_skip_count"] == 5
