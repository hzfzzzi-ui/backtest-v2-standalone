from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.api.endpoints.backtest_v2 import _extract_reason_code_counts, _normalized_run_meta_counters
from backend.api.endpoints.backtest_v2_artifacts import stabilize_experiment_result


def test_canonical_artifact_contract_and_missing_fields(tmp_path: Path) -> None:
    bt_root = tmp_path / "backtest_V2"
    bt_root.mkdir(parents=True, exist_ok=True)
    results_dir = tmp_path / "exp_case"

    base_cfg = {
        "universe": {"start": "2024-01-01", "end": "2024-12-31", "benchmark": "000300.SH"},
        "signal": {"strategy": "EMA_CROSS"},
    }
    result = {
        "exp_id": "exp_case",
        "results_dir": str(results_dir),
        "status": "OK",
        "total_return": -0.02,
        "max_drawdown": -0.1,
        "cagr": -0.02,
        "sharpe": 0.1,
        "trades": 0,
        "raw_signal": 0,
        "blocked": 0,
        "orders": 0,
        "skipped": 0,
        "closed_trades": 0,
    }

    out = stabilize_experiment_result(
        bt_root=bt_root,
        result=result,
        base_cfg=base_cfg,
        overrides={},
        run_profile_summary=None,
    )

    artifacts = dict(out.get("artifacts") or {})
    assert artifacts.get("reason_codes") == "reason_codes.csv"
    assert artifacts.get("symbol_performance") == "symbol_performance.csv"

    assert (results_dir / "reason_codes.csv").exists()
    assert (results_dir / "symbol_performance.csv").exists()

    run_meta = json.loads((results_dir / "run_meta.json").read_text(encoding="utf-8"))
    counters = dict(run_meta.get("counters") or {})
    for key in ["raw_signal", "blocked", "orders", "skipped", "closed_trades"]:
        assert key in counters
    for legacy in ["raw_signal_count", "blocked_count", "orders_count", "skipped_count", "closed_trades_count"]:
        assert legacy not in counters

    missing = set(run_meta.get("missing_fields") or [])
    assert "missing_reason_code_source" in missing
    assert "missing_symbol_performance_source" in missing

    sp = pd.read_csv(results_dir / "symbol_performance.csv")
    assert sp.empty


def test_legacy_read_compatibility_reason_file_and_counter_alias(tmp_path: Path) -> None:
    group_dir = tmp_path / "G1"
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / "reason_code_counts.csv").write_text(
        "code,count\nATR_STOP_LOSS,3\nTIME_EXIT,2\n",
        encoding="utf-8",
    )

    reason_counts = _extract_reason_code_counts(group_dir)
    assert reason_counts.get("atr_stop_exit_count") == 3
    assert reason_counts.get("time_exit_count") == 2

    normalized, hits = _normalized_run_meta_counters(
        {
            "counters": {
                "raw_signal_count": 11,
                "blocked_count": 4,
                "orders_count": 7,
                "skipped_count": 2,
                "closed_trades_count": 5,
            }
        }
    )
    assert hits == 5
    assert normalized.get("raw_signal") == 11
    assert normalized.get("blocked") == 4
    assert normalized.get("orders") == 7
    assert normalized.get("skipped") == 2
    assert normalized.get("closed_trades") == 5
