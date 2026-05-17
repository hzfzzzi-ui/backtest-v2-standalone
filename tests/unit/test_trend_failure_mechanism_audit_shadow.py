from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research.trend_failure_mechanism_audit_shadow import (
    add_mechanism_flags,
    run_trend_failure_mechanism_audit,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _row(symbol: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date": "2026-01-05",
        "symbol": symbol,
        "industry_name": "计算机",
        "industry_health_label": "weak",
        "industry_is_weak": True,
        "industry_ret20": -0.12,
        "industry_ret60": -0.16,
        "industry_weak_duration": 12,
        "ret5": 0.03,
        "ret10": 0.12,
        "ret20": 0.24,
        "close_vs_ma20": 0.18,
        "drawdown20": -0.16,
        "forward_ret5": -0.03,
        "forward_ret20": -0.18,
        "mfe20": 0.02,
        "mae20": -0.22,
        "bad_fwd20_flag": True,
        "deep_mae20_flag": True,
        "low_mfe20_flag": True,
        "failure_outcome_flag": True,
        "style_state_label": "split_rotation",
        "industry_market_health_label": "industry_broad_weak",
        "industry_breadth_weak": 0.7,
        "industry_breadth_healthy": 0.1,
        "rotation_pressure_label": "rotation_pressure",
        "position_risk_state": "watch_lagging",
        "year": 2026,
    }
    row.update(overrides)
    return row


def test_add_mechanism_flags_labels_failure_modes() -> None:
    frame = pd.DataFrame(
        [
            _row("sh600001"),
            _row(
                "sh600002",
                industry_health_label="healthy",
                industry_is_weak=False,
                ret20=0.01,
                close_vs_ma20=0.01,
                bad_fwd20_flag=False,
                deep_mae20_flag=False,
                low_mfe20_flag=False,
                failure_outcome_flag=False,
                position_risk_state="healthy_continue",
            ),
        ]
    )

    labeled = add_mechanism_flags(frame)

    assert bool(labeled.loc[0, "high_chase_like_flag"])
    assert bool(labeled.loc[0, "trend_exhaustion_after_flag"])
    assert bool(labeled.loc[0, "industry_breakdown_flag"])
    assert bool(labeled.loc[0, "market_breadth_weak_flag"])
    assert bool(labeled.loc[0, "delayed_exit_like_flag"])
    assert "high_chase_like" in labeled.loc[0, "mechanism_reasons"]
    assert not bool(labeled.loc[1, "trend_exhaustion_after_flag"])


def test_run_trend_failure_mechanism_audit_writes_summary(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    (input_root / "1226").mkdir(parents=True)
    _write_csv(
        input_root / "1226" / "scene_detail.csv",
        [
            _row("sh600001"),
            _row("sh600002", ret20=0.05, close_vs_ma20=0.03, forward_ret20=-0.06),
        ],
    )
    summary = {
        "windows": [
            {
                "window_key": "1226",
                "worst_single_scenes": [
                    {"dimension": "industry_name", "scene_key": "计算机", "industry_name": "计算机"}
                ],
                "worst_combo_scenes": [
                    {
                        "dimension": "industry_market_health_label+position_risk_state+industry_name",
                        "scene_key": "industry_broad_weak|watch_lagging|计算机",
                        "industry_market_health_label": "industry_broad_weak",
                        "position_risk_state": "watch_lagging",
                        "industry_name": "计算机",
                    }
                ],
            }
        ]
    }
    (input_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")

    result = run_trend_failure_mechanism_audit(input_root=input_root, output_root=output_root)

    assert result["windows"][0]["audited_scenes"] == 2
    assert (output_root / "1226" / "mechanism_detail.csv").exists()
    assert (output_root / "1226" / "scene_mechanism_summary.csv").exists()
    scene_summary = pd.read_csv(output_root / "1226" / "scene_mechanism_summary.csv")
    assert "dominant_failure_mechanism" in scene_summary.columns
