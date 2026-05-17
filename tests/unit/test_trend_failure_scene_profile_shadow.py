from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.trend_failure_scene_profile_shadow import (
    load_scene_inputs,
    run_trend_failure_scene_profile,
    summarize_scene,
)


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _build_inputs(position_root: Path, state_root: Path) -> None:
    _write(
        position_root / "demo" / "position_risk_detail.csv",
        [
            {
                "date": "2026-01-02",
                "symbol": "sh600001",
                "industry_name": "计算机",
                "position_risk_state": "watch_lagging",
                "forward_ret20": -0.10,
                "mfe20": 0.03,
                "mae20": -0.18,
                "ret20": 0.02,
                "close_vs_ma20": -0.01,
                "drawdown20": -0.08,
            },
            {
                "date": "2026-01-02",
                "symbol": "sh600002",
                "industry_name": "电子",
                "position_risk_state": "healthy_continue",
                "forward_ret20": 0.08,
                "mfe20": 0.12,
                "mae20": -0.04,
                "ret20": 0.12,
                "close_vs_ma20": 0.04,
                "drawdown20": -0.02,
            },
        ],
    )
    machine = state_root / "demo" / "M1_STYLE_STATE" / "machine"
    _write(
        machine / "style_state_daily.csv",
        [{"date": "2026-01-02", "style_state_label": "split_rotation", "avg_ret20": -0.01, "avg_ret60": -0.02, "worst_drawdown60": -0.10}],
    )
    _write(
        machine / "industry_health_daily.csv",
        [
            {
                "date": "2026-01-02",
                "industry_market_health_label": "industry_broad_weak",
                "healthy_industry_count": 2,
                "weak_industry_count": 10,
                "industry_breadth_healthy": 0.1,
                "industry_breadth_weak": 0.7,
            }
        ],
    )
    _write(
        machine / "rotation_pressure_daily.csv",
        [{"date": "2026-01-02", "held_stock_count": 2, "held_weak_ratio": 0.5, "held_healthy_ratio": 0.1, "rotation_pressure_label": "held_mixed"}],
    )


def test_load_scene_inputs_merges_daily_state_and_flags_failures(tmp_path: Path) -> None:
    position_root = tmp_path / "positions"
    state_root = tmp_path / "state"
    _build_inputs(position_root, state_root)

    scene = load_scene_inputs(position_root, state_root, window_key="demo", variant="M1_STYLE_STATE")

    assert "style_state_label" in scene.columns
    assert "industry_market_health_label" in scene.columns
    assert bool(scene.loc[scene["symbol"].eq("sh600001"), "failure_outcome_flag"].iloc[0]) is True
    assert scene.loc[scene["symbol"].eq("sh600002"), "failure_outcome_flag"].iloc[0] == False


def test_run_profile_writes_outputs(tmp_path: Path) -> None:
    position_root = tmp_path / "positions"
    state_root = tmp_path / "state"
    output_root = tmp_path / "outputs"
    _build_inputs(position_root, state_root)

    scene = load_scene_inputs(position_root, state_root, window_key="demo", variant="M1_STYLE_STATE")
    year_summary = summarize_scene(scene, ["year"], min_rows=1)
    assert not year_summary.empty

    result = run_trend_failure_scene_profile(
        position_root=position_root,
        state_root=state_root,
        output_root=output_root,
        windows=("demo",),
    )
    assert result["research_only"] is True
    assert (output_root / "demo" / "scene_detail.csv").exists()
    assert (output_root / "demo" / "single_scene_matrix.csv").exists()
    assert (output_root / "summary.md").exists()
