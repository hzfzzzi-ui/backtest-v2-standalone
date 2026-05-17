from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.watch_lagging_deep_dive_shadow import (
    build_watch_lagging_features,
    run_watch_lagging_deep_dive,
    summarize_concentration,
    summarize_group,
)


def _detail() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "symbol": "sh600001",
                "industry_name": "电子",
                "position_risk_state": "watch_lagging",
                "ret5": -0.12,
                "ret10": -0.05,
                "ret20": 0.03,
                "close_vs_ma20": -0.06,
                "drawdown20": -0.12,
                "industry_weak_duration": 2,
                "industry_ret20": -0.04,
                "forward_ret5": -0.02,
                "forward_ret20": -0.10,
                "mfe20": 0.03,
                "mae20": -0.16,
            },
            {
                "date": "2026-01-03",
                "symbol": "sh600002",
                "industry_name": "通信",
                "position_risk_state": "healthy_continue",
                "ret5": 0.02,
                "ret20": 0.10,
                "close_vs_ma20": 0.03,
                "drawdown20": -0.02,
                "industry_weak_duration": 0,
                "industry_ret20": 0.02,
                "forward_ret20": 0.08,
                "mfe20": 0.12,
                "mae20": -0.03,
            },
        ]
    )


def test_build_watch_lagging_features_filters_and_buckets() -> None:
    watch = build_watch_lagging_features(_detail())

    assert len(watch) == 1
    row = watch.iloc[0]
    assert row["ret5_bucket"] == "ret5_deep_drop"
    assert row["ret20_bucket"] == "ret20_positive_weak"
    assert row["close_vs_ma20_bucket"] == "below_ma20"
    assert row["drawdown20_bucket"] == "dd20_deep"
    assert row["industry_weak_duration_bucket"] == "weak_just_1_3d"


def test_run_watch_lagging_deep_dive_writes_outputs(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    window_dir = input_root / "demo"
    window_dir.mkdir(parents=True)
    _detail().to_csv(window_dir / "position_risk_detail.csv", index=False, encoding="utf-8-sig")

    result = run_watch_lagging_deep_dive(input_root=input_root, output_root=tmp_path / "outputs", windows=("demo",))

    assert result["research_only"] is True
    assert result["target_state"] == "watch_lagging"
    assert (tmp_path / "outputs" / "demo" / "watch_lagging_detail.csv").exists()
    assert (tmp_path / "outputs" / "demo" / "setup_summary.csv").exists()
    assert (tmp_path / "outputs" / "summary.md").exists()

    watch = build_watch_lagging_features(_detail())
    assert not summarize_group(watch, "setup_key").empty
    assert not summarize_concentration(watch, "industry_name").empty
