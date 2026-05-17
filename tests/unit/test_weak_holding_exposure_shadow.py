from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.research.weak_holding_exposure_shadow import (
    build_episode_detail,
    build_trigger_detail,
    run_weak_holding_exposure_shadow,
    summarize_triggers,
)


def _rotation_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "held_stock_count": 5,
                "held_weak_ratio": 0.10,
                "held_healthy_ratio": 0.60,
                "rotation_pressure_label": "held_broad_healthy",
                "stock_ret": 0.01,
                "combo_ret": 0.01,
            },
            {
                "date": "2026-01-02",
                "held_stock_count": 5,
                "held_weak_ratio": 0.60,
                "held_healthy_ratio": 0.10,
                "rotation_pressure_label": "held_broad_weak",
                "stock_ret": -0.02,
                "combo_ret": -0.01,
            },
            {
                "date": "2026-01-03",
                "held_stock_count": 5,
                "held_weak_ratio": 0.70,
                "held_healthy_ratio": 0.00,
                "rotation_pressure_label": "held_broad_weak",
                "stock_ret": -0.03,
                "combo_ret": -0.02,
            },
            {
                "date": "2026-01-04",
                "held_stock_count": 5,
                "held_weak_ratio": 0.00,
                "held_healthy_ratio": 0.80,
                "rotation_pressure_label": "held_broad_healthy",
                "stock_ret": 0.04,
                "combo_ret": 0.03,
            },
        ]
    )


def test_trigger_detail_collapses_consecutive_episode() -> None:
    detail = build_trigger_detail(_rotation_rows(), window_key="demo", thresholds=(0.5,), horizons=(1, 2))

    assert len(detail) == 2
    assert detail["episode_id"].nunique() == 1
    assert detail.iloc[0]["stock_forward_1d"] == -0.03
    assert detail.iloc[0]["stock_forward_2d"] == pytest.approx(0.01)


def test_summary_and_episode_detail_are_written(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    machine = input_root / "demo" / "M1_STYLE_STATE" / "machine"
    machine.mkdir(parents=True)
    _rotation_rows().to_csv(machine / "rotation_pressure_daily.csv", index=False, encoding="utf-8-sig")

    result = run_weak_holding_exposure_shadow(input_root=input_root, output_root=tmp_path / "outputs", windows=("demo",), thresholds=(0.5,))

    assert result["research_only"] is True
    assert result["baseline_mutation"] is False
    assert result["nav_recompute"] is False
    assert (tmp_path / "outputs" / "demo" / "trigger_detail.csv").exists()
    assert (tmp_path / "outputs" / "summary.md").exists()

    detail = build_trigger_detail(_rotation_rows(), window_key="demo", thresholds=(0.5,))
    summary = summarize_triggers(detail, window_key="demo", thresholds=(0.5,))
    episodes = build_episode_detail(detail)
    assert int(summary.iloc[0]["trigger_days"]) == 2
    assert int(summary.iloc[0]["episode_count"]) == 1
    assert int(episodes.iloc[0]["days"]) == 2
