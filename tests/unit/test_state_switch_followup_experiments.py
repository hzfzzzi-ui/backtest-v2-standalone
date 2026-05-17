from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.research.state_switch_followup_experiments import (
    load_window_inputs,
    round2_market_state,
    round3_industry_health,
    round4_candidate_alignment,
    run_followup_experiments,
)


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _build_inputs(root: Path) -> None:
    machine = root / "demo" / "M1_STYLE_STATE" / "machine"
    _write(
        machine / "style_state_daily.csv",
        [
            {"date": "2026-01-01", "style_state_label": "risk_off", "avg_ret20": -0.04},
            {"date": "2026-01-02", "style_state_label": "broad_bull", "avg_ret20": 0.05},
            {"date": "2026-01-03", "style_state_label": "risk_off", "avg_ret20": -0.03},
        ],
    )
    _write(
        machine / "industry_health_daily.csv",
        [
            {
                "date": "2026-01-01",
                "industry_market_health_label": "industry_broad_weak",
                "industry_breadth_healthy": 0.1,
                "industry_breadth_weak": 0.7,
            },
            {
                "date": "2026-01-02",
                "industry_market_health_label": "industry_rotation",
                "industry_breadth_healthy": 0.4,
                "industry_breadth_weak": 0.3,
            },
        ],
    )
    _write(
        machine / "rotation_pressure_daily.csv",
        [
            {
                "date": "2026-01-01",
                "rotation_pressure_label": "held_broad_weak",
                "held_weak_ratio": 0.8,
                "held_healthy_ratio": 0.1,
                "stock_ret": -0.02,
                "combo_ret": -0.01,
            },
            {
                "date": "2026-01-02",
                "rotation_pressure_label": "held_broad_healthy",
                "held_weak_ratio": 0.0,
                "held_healthy_ratio": 0.8,
                "stock_ret": 0.03,
                "combo_ret": 0.02,
            },
            {
                "date": "2026-01-03",
                "rotation_pressure_label": "rotation_pressure",
                "held_weak_ratio": 0.5,
                "held_healthy_ratio": 0.2,
                "stock_ret": -0.01,
                "combo_ret": -0.005,
            },
        ],
    )
    _write(
        machine / "entry_candidate_pressure_daily.csv",
        [
            {
                "date": "2026-01-01",
                "entry_vs_held_alignment_label": "entry_sorting_risk",
                "entry_weak_ratio": 0.9,
                "entry_healthy_ratio": 0.1,
                "held_weak_ratio": 0.8,
                "held_healthy_ratio": 0.1,
                "stock_ret": -0.02,
                "combo_ret": -0.01,
            }
        ],
    )
    _write(
        machine / "candidate_pool_pressure_daily.csv",
        [
            {
                "date": "2026-01-01",
                "candidate_vs_held_diagnosis_label": "deployment_blocked_with_weak_holdings",
                "candidate_weak_ratio": 0.0,
                "candidate_healthy_ratio": 0.8,
                "cash_blocked_stock_count": 2,
                "held_weak_ratio": 0.8,
                "held_healthy_ratio": 0.1,
                "stock_ret": -0.02,
                "combo_ret": -0.01,
            }
        ],
    )


def test_rounds_build_expected_shadow_tables(tmp_path: Path) -> None:
    _build_inputs(tmp_path)
    inputs = load_window_inputs(tmp_path, "demo")

    round2 = round2_market_state(inputs)
    round3 = round3_industry_health(inputs)
    round4 = round4_candidate_alignment(inputs)

    assert set(round2) == {
        "round2_market_state_by_label",
        "round2_market_state_transitions",
        "round2_market_state_transition_summary",
    }
    assert not round2["round2_market_state_by_label"].empty
    assert "risk_off" in set(round2["round2_market_state_by_label"]["label"])
    assert not round3["round3_held_weak_ratio_buckets"].empty
    assert round4["round4_candidate_problem_days"].shape[0] == 1


def test_run_followup_experiments_writes_summary(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "outputs"
    _build_inputs(input_root)

    result = run_followup_experiments(input_root=input_root, output_root=output_root, windows=("demo",))

    assert result["research_only"] is True
    assert result["baseline_mutation"] is False
    assert result["nav_recompute"] is False
    assert (output_root / "summary.json").exists()
    assert (output_root / "summary.md").exists()
    assert (output_root / "demo" / "round4_candidate_diagnosis_by_label.csv").exists()
