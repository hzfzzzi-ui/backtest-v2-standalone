from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.research.holding_health_dashboard import (
    build_holding_health_dashboard,
    explode_held_industry_daily,
)


def test_explode_held_industry_daily_flags_health_downgrades() -> None:
    frame = pd.DataFrame(
        [
            {
                "date": "2026-05-06",
                "industry_index_code": "801080.SI",
                "industry_name": "电子",
                "industry_health_label": "healthy",
                "held_symbols": "sh600001;sz000001",
                "ret20": 0.12,
                "ret60": 0.20,
            },
            {
                "date": "2026-05-07",
                "industry_index_code": "801080.SI",
                "industry_name": "电子",
                "industry_health_label": "weak",
                "held_symbols": "sh600001",
                "ret20": -0.04,
                "ret60": -0.02,
            },
        ]
    )

    out = explode_held_industry_daily(frame)

    row = out.loc[(out["date"].eq(pd.Timestamp("2026-05-07"))) & (out["symbol"].eq("sh600001"))].iloc[0]
    assert bool(row["health_downgrade_flag"]) is True
    assert bool(row["new_weak_flag"]) is True
    assert row["transition_label"] == "healthy_to_weak"


def test_build_holding_health_dashboard_outputs_daily_positions_and_summary(tmp_path: Path) -> None:
    machine = tmp_path / "machine"
    output = tmp_path / "out"
    machine.mkdir()
    pd.DataFrame(
        [
            {
                "date": "2026-05-06",
                "held_stock_count": 2,
                "held_industry_count": 1,
                "held_healthy_count": 2,
                "held_watch_count": 0,
                "held_weak_count": 0,
                "held_unknown_count": 0,
                "held_healthy_ratio": 1.0,
                "held_weak_ratio": 0.0,
                "rotation_pressure_label": "held_broad_healthy",
                "rotation_pressure_reason": "ok",
                "stock_ret": 0.01,
                "combo_ret": 0.01,
            },
            {
                "date": "2026-05-07",
                "held_stock_count": 2,
                "held_industry_count": 1,
                "held_healthy_count": 0,
                "held_watch_count": 0,
                "held_weak_count": 2,
                "held_unknown_count": 0,
                "held_healthy_ratio": 0.0,
                "held_weak_ratio": 1.0,
                "rotation_pressure_label": "held_broad_weak",
                "rotation_pressure_reason": "weak",
                "stock_ret": -0.02,
                "combo_ret": -0.01,
            },
        ]
    ).to_csv(machine / "rotation_pressure_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-05-06",
                "industry_index_code": "801080.SI",
                "industry_name": "电子",
                "held_symbol_count": 2,
                "held_qty_sum": 200,
                "industry_health_label": "healthy",
                "held_symbols": "sh600001;sz000001",
                "ret20": 0.12,
                "ret60": 0.20,
            },
            {
                "date": "2026-05-07",
                "industry_index_code": "801080.SI",
                "industry_name": "电子",
                "held_symbol_count": 2,
                "held_qty_sum": 200,
                "industry_health_label": "weak",
                "held_symbols": "sh600001;sz000001",
                "ret20": -0.04,
                "ret60": -0.02,
            },
        ]
    ).to_csv(machine / "rotation_pressure_held_industry_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2026-05-07",
                "industry_index_code": "801730.SI",
                "industry_name": "电力设备",
                "industry_health_label": "healthy",
                "candidate_symbol_count": 1,
                "selected_symbol_count": 0,
                "cash_blocked_symbol_count": 1,
                "candidate_symbols": "sh600002",
                "selected_symbols": "",
                "cash_blocked_symbols": "sh600002",
                "ret20": 0.10,
                "ret60": 0.05,
            }
        ]
    ).to_csv(machine / "candidate_pool_industry_daily.csv", index=False)
    (machine / "candidate_signals_source_audit.json").write_text(
        json.dumps(
            {
                "source_scope": "rejected_or_diagnostic_candidates",
                "selected_row_count": 0,
                "reject_reason_counts": {"SKIP_NO_CASH": 1},
            }
        ),
        encoding="utf-8",
    )

    result = build_holding_health_dashboard(study_machine_dir=machine, output_dir=output)

    assert result["status"] == "OK"
    daily = pd.read_csv(output / "holding_health_daily.csv")
    positions = pd.read_csv(output / "holding_health_positions.csv")
    summary = json.loads((output / "holding_health_summary.json").read_text(encoding="utf-8"))
    assert len(daily) == 2
    assert len(positions) == 4
    assert summary["latest"]["alert_level"] == "yellow"
    assert summary["latest"]["held_weak_count"] == 2
    assert summary["latest"]["downgraded_holding_count"] == 2
    assert summary["latest"]["cash_blocked_candidate_count"] == 1
