from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.api.backtest_v2.artifacts_diagnostics import _build_buy_stage_funnel, _build_recent_cash_blocked_buys
from backend.api.backtest_v2.impl import (
    _build_counters,
    _sanitize_historical_stock_names,
    stabilize_experiment_result,
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
                "execution_shell": "stage_pipeline_shell_bridge",
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
    assert manifest["stage_pipeline"]["execution_shell"] == "stage_pipeline_shell_bridge"
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
                "final_score_rank_triggered": 1,
                "final_score_rank_applied": 1,
                "final_score_candidates_when_triggered": 3,
                "final_score_topk_reject_count": 2,
                "final_score_concentrated_selected_count": 1,
                "final_score_rank_gate_on": 1,
                "strong_risk_on": 0,
                "final_score_rank_suppressed_by_strong_gate": 0,
                "selected_count": 2,
            },
            {
                "final_score_rank_triggered": 0,
                "final_score_rank_applied": 0,
                "final_score_candidates_when_triggered": 0,
                "final_score_topk_reject_count": 0,
                "final_score_concentrated_selected_count": 0,
                "final_score_rank_gate_on": 0,
                "strong_risk_on": 1,
                "final_score_rank_suppressed_by_strong_gate": 1,
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
    assert counters["planning_cash_skip_count"] == 5
    assert counters["fill_cash_reject_count"] == 0
    assert counters["lot_skip_count"] == 5


def test_build_counters_exposes_fill_cash_reject_layer_when_present(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_test_fill_cash"
    results_dir.mkdir(parents=True, exist_ok=True)

    counters = _build_counters(
        {
            "avg_positions": 0.0,
            "max_positions": 10,
            "planning_reject_reason_counts": {"SKIP_NO_CASH": 3},
            "fill_reject_reason_counts": {"INSUFFICIENT_CASH": 2},
        },
        results_dir,
        funnel_obj={},
    )

    assert counters["cash_skip_count"] == 3
    assert counters["planning_cash_skip_count"] == 3
    assert counters["fill_cash_reject_count"] == 2


def test_build_buy_stage_funnel_preserves_unavailable_stage_counts(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_stage_unavailable"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "raw_buy_signal_count": 8,
                "buy_candidate_count": 5,
                "after_held_filter_count": 3,
                "after_slot_filter_count": None,
                "after_cash_lot_count": None,
                "diagnostics_input_json": json.dumps(
                    {
                        "route_id": "strict_inline_runtime",
                        "raw_buy_signal_count": 8,
                        "raw_buy_candidate_count": 5,
                        "raw_after_held_filter_count": 3,
                        "raw_after_slot_filter_count": None,
                        "raw_after_cash_lot_count": None,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(results_dir / "portfolio_daily.csv", index=False)

    rows, _ = _build_buy_stage_funnel(
        {"universe_meta": {"tradable_symbols": 12}},
        results_dir,
        buy_orders_count=2,
    )

    s7 = next(row for row in rows if row["stage_key"] == "s7")
    s8 = next(row for row in rows if row["stage_key"] == "s8")
    assert s7["available"] is True
    assert s7["input_count"] == 3
    assert s7["output_count"] == 2
    assert s8["available"] is False
    assert s8["input_count"] is None
    assert s8["output_count"] is None


def test_build_buy_stage_funnel_keeps_true_zero_counts_measured(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_stage_zero"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "raw_buy_signal_count": 6,
                "buy_candidate_count": 6,
                "after_held_filter_count": 0,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 0,
                "diagnostics_input_json": json.dumps(
                    {
                        "route_id": "strict_inline_runtime",
                        "raw_buy_signal_count": 6,
                        "raw_buy_candidate_count": 6,
                        "raw_after_held_filter_count": 0,
                        "raw_after_slot_filter_count": 0,
                        "raw_after_cash_lot_count": 0,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(results_dir / "portfolio_daily.csv", index=False)

    rows, _ = _build_buy_stage_funnel(
        {"universe_meta": {"tradable_symbols": 12}},
        results_dir,
        buy_orders_count=0,
    )

    s6 = next(row for row in rows if row["stage_key"] == "s6")
    s7 = next(row for row in rows if row["stage_key"] == "s7")
    s8 = next(row for row in rows if row["stage_key"] == "s8")
    assert s6["available"] is True
    assert s6["output_count"] == 0
    assert s7["available"] is True
    assert s7["output_count"] == 0
    assert s8["available"] is True
    assert s8["output_count"] == 0


def test_build_buy_stage_funnel_centralizes_breakout_route_normalization(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_stage_breakout"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "raw_buy_signal_count": 7,
                "buy_candidate_count": 5,
                "after_held_filter_count": 3,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 1,
                "diagnostics_input_json": json.dumps(
                    {
                        "route_id": "provider_breakout_runtime",
                        "candidates_count": 0,
                        "selected_count": 1,
                        "benchmark_regime_on": True,
                        "raw_buy_signal_count": 7,
                        "raw_buy_candidate_count": 5,
                        "raw_after_held_filter_count": 3,
                        "raw_after_slot_filter_count": None,
                        "raw_after_cash_lot_count": None,
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_csv(results_dir / "portfolio_daily.csv", index=False)

    rows, _ = _build_buy_stage_funnel(
        {"universe_meta": {"tradable_symbols": 12}},
        results_dir,
        buy_orders_count=1,
    )

    s5 = next(row for row in rows if row["stage_key"] == "s5")
    s6 = next(row for row in rows if row["stage_key"] == "s6")
    s7 = next(row for row in rows if row["stage_key"] == "s7")
    s8 = next(row for row in rows if row["stage_key"] == "s8")
    assert s5["output_count"] == 3
    assert s6["output_count"] == 3
    assert s7["output_count"] == 3
    assert s8["output_count"] == 1


def test_stabilize_experiment_result_writes_canonical_candidate_diagnostics(tmp_path: Path) -> None:
    bt_root = tmp_path / "backtest_v2"
    bt_root.mkdir(parents=True, exist_ok=True)
    results_dir = tmp_path / "exp_diag"
    results_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "date": "2026-03-01",
                "symbol": "sh600000",
                "alpha_source": "breakout_55",
                "residual_strength_score": 0.8,
                "sector_strength_score": 0.7,
                "volume_price_quality_score": 0.6,
                "mf_score": 0.9,
                "selected": 1,
            },
            {
                "date": "2026-03-01",
                "symbol": "sh600519",
                "alpha_source": "breakout_20",
                "residual_strength_score": 0.4,
                "sector_strength_score": 0.3,
                "volume_price_quality_score": 0.2,
                "mf_score": 0.5,
                "selected": 0,
            },
        ]
    ).to_csv(results_dir / "portfolio_candidates.csv", index=False)

    out = stabilize_experiment_result(
        bt_root=bt_root,
        result={
            "exp_id": "exp_diag",
            "results_dir": str(results_dir),
            "status": "OK",
            "total_return": 0.01,
            "max_drawdown": -0.01,
            "cagr": 0.01,
            "sharpe": 0.5,
            "trades": 0,
            "raw_signal": 2,
            "blocked": 0,
            "orders": 0,
            "skipped": 0,
            "closed_trades": 0,
        },
        base_cfg={
            "universe": {"start": "2026-03-01", "end": "2026-03-31", "benchmark": "000300.SH"},
            "signal": {"strategy": "EMA_CROSS"},
        },
        overrides={},
        run_profile_summary=None,
    )

    artifacts = dict(out.get("artifacts") or {})
    assert artifacts["candidate_signals"] == "candidate_signals.csv"
    assert artifacts["cash_blocked_buys_recent"] == "cash_blocked_buys_recent.csv"
    assert artifacts["alpha_funnel"] == "alpha_funnel.csv"
    assert artifacts["score_diagnostics"] == "score_diagnostics.csv"

    candidate_df = pd.read_csv(results_dir / "candidate_signals.csv")
    alpha_funnel_df = pd.read_csv(results_dir / "alpha_funnel.csv")
    diagnostics_df = pd.read_csv(results_dir / "score_diagnostics.csv")

    assert list(candidate_df["selected_flag"].astype(bool)) == [True, False]
    assert int(alpha_funnel_df["candidate_count"].sum()) == 2
    assert int(alpha_funnel_df["selected_count"].sum()) == 1
    assert list(diagnostics_df["candidate_rank"]) == [1, 2]


def test_build_recent_cash_blocked_buys_keeps_only_last_five_trading_days(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_cash_blocked"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"date": f"2026-03-{day:02d}", "nav": 1.0} for day in range(1, 8)]
    ).to_csv(results_dir / "portfolio_daily.csv", index=False)
    candidate_df = pd.DataFrame(
        [
            {
                "date": "2026-03-01",
                "symbol": "sh600001",
                "reject_reason": "SKIP_NO_CASH",
                "cash_available": 8000.0,
                "estimated_qty": 100,
                "estimated_amount": 10000.0,
                "estimated_price": 100.0,
                "alpha_source": "breakout_55",
                "cash_blocked_reason": "SKIP_NO_CASH",
            },
            {
                "date": "2026-03-03",
                "symbol": "sh600002",
                "reject_reason": "SKIP_NO_CASH",
                "cash_available": 7000.0,
                "estimated_qty": 100,
                "estimated_amount": 12000.0,
                "estimated_price": 120.0,
                "alpha_source": "breakout_55",
                "cash_blocked_reason": "SKIP_NO_CASH",
            },
            {
                "date": "2026-03-06",
                "symbol": "sh600003",
                "reject_reason": "SKIP_NO_CASH",
                "cash_available": 9000.0,
                "estimated_qty": 100,
                "estimated_amount": 13000.0,
                "estimated_price": 130.0,
                "alpha_source": "breakout_20",
                "cash_blocked_reason": "SKIP_NO_CASH",
            },
            {
                "date": "2026-03-07",
                "symbol": "sh600004",
                "reject_reason": "NOT_SELECTED_CASH_AWARE",
                "cash_available": 9000.0,
                "estimated_qty": 100,
                "estimated_amount": 15000.0,
                "estimated_price": 150.0,
                "alpha_source": "breakout_20",
                "cash_blocked_reason": "",
            },
        ]
    )

    out_path = _build_recent_cash_blocked_buys(results_dir, candidate_df)
    out_df = pd.read_csv(out_path)

    assert list(out_df["symbol"]) == ["sh600003", "sh600002"]
    assert list(out_df["date"]) == ["2026-03-06", "2026-03-03"]
    assert float(out_df.iloc[0]["cash_available"]) == 9000.0
    assert int(out_df.iloc[0]["estimated_qty"]) == 100
    assert float(out_df.iloc[0]["estimated_amount"]) == 13000.0


def test_build_recent_cash_blocked_buys_writes_empty_csv_when_no_recent_cash_reject(tmp_path: Path) -> None:
    results_dir = tmp_path / "exp_cash_blocked_empty"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"date": "2026-03-07", "nav": 1.0}]).to_csv(results_dir / "portfolio_daily.csv", index=False)

    out_path = _build_recent_cash_blocked_buys(
        results_dir,
        pd.DataFrame(
            [
                {
                    "date": "2026-03-07",
                    "symbol": "sh600005",
                    "reject_reason": "NOT_SELECTED_CASH_AWARE",
                }
            ]
        ),
    )
    out_df = pd.read_csv(out_path)

    assert list(out_df.columns) == [
        "date",
        "symbol",
        "reject_reason",
        "cash_available",
        "estimated_qty",
        "estimated_amount",
        "estimated_price",
        "alpha_source",
        "cash_blocked_reason",
    ]
    assert out_df.empty
