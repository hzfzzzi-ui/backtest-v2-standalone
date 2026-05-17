from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.position_risk_state_shadow import (
    assign_position_risk_state,
    run_position_risk_state_shadow,
    summarize_by_state,
    summarize_by_window_day,
)


def _detail() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "symbol": "sh600001",
                "industry_is_weak": True,
                "stock_strong_flag": False,
                "stock_weak_confirmed_flag": True,
                "ret5": -0.04,
                "ret10": -0.06,
                "ret20": -0.08,
                "close_vs_ma20": -0.05,
                "drawdown20": -0.10,
                "forward_ret20": 0.20,
                "mfe20": 0.25,
                "mae20": -0.05,
            },
            {
                "date": "2026-01-02",
                "symbol": "sh600002",
                "industry_is_weak": True,
                "stock_strong_flag": True,
                "stock_weak_confirmed_flag": False,
                "ret5": 0.02,
                "ret10": 0.03,
                "ret20": 0.10,
                "close_vs_ma20": 0.04,
                "drawdown20": -0.03,
                "forward_ret20": -0.10,
                "mfe20": 0.05,
                "mae20": -0.20,
            },
            {
                "date": "2026-01-03",
                "symbol": "sh600003",
                "industry_is_weak": False,
                "stock_strong_flag": True,
                "stock_weak_confirmed_flag": False,
                "ret5": -0.01,
                "ret10": 0.02,
                "ret20": 0.08,
                "close_vs_ma20": 0.03,
                "drawdown20": -0.06,
                "forward_ret20": 0.01,
                "mfe20": 0.08,
                "mae20": -0.04,
            },
        ]
    )


def test_assign_position_risk_state_uses_current_columns_only() -> None:
    assigned = assign_position_risk_state(_detail())

    by_symbol = assigned.set_index("symbol")
    assert by_symbol.loc["sh600001", "position_risk_state"] == "risk_confirmed"
    assert by_symbol.loc["sh600002", "position_risk_state"] == "repairing"
    assert by_symbol.loc["sh600003", "position_risk_state"] == "watch_pullback"
    assert bool(by_symbol.loc["sh600001", "exit_candidate_flag"]) is True


def test_summaries_and_runner_write_outputs(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    window_dir = input_root / "demo"
    window_dir.mkdir(parents=True)
    _detail().to_csv(window_dir / "position_state_detail.csv", index=False, encoding="utf-8-sig")

    assigned = assign_position_risk_state(_detail())
    state_summary = summarize_by_state(assigned)
    daily_summary = summarize_by_window_day(assigned)
    assert "risk_confirmed" in set(state_summary["state"])
    assert "risk_confirmed_ratio" in daily_summary.columns

    result = run_position_risk_state_shadow(input_root=input_root, output_root=tmp_path / "outputs", windows=("demo",))
    assert result["research_only"] is True
    assert result["current_info_only_for_state"] is True
    assert (tmp_path / "outputs" / "demo" / "position_risk_detail.csv").exists()
    assert (tmp_path / "outputs" / "summary.md").exists()
