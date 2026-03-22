from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.engine_vector.moneyflow_overlay import resolve_moneyflow_overlay_snapshot


def test_moneyflow_overlay_snapshot_resolves_latest_observation_and_gate(tmp_path) -> None:
    factor_panel = tmp_path / "monthly_factor_panel.csv"
    coverage_ledger = tmp_path / "monthly_coverage_ledger.csv"
    pd.DataFrame(
        [
            {
                "month": "2023-07-01",
                "symbol": "sh600001",
                "monthly_divergence_rate": 0.01,
                "observation_date": "2023-07-31",
                "execution_date": "2023-08-01",
                "month_end_valid": True,
                "monthly_factor_valid": True,
            },
            {
                "month": "2023-07-01",
                "symbol": "sh600002",
                "monthly_divergence_rate": 0.02,
                "observation_date": "2023-07-31",
                "execution_date": "2023-08-01",
                "month_end_valid": True,
                "monthly_factor_valid": True,
            },
            {
                "month": "2023-08-01",
                "symbol": "sh600001",
                "monthly_divergence_rate": 0.03,
                "observation_date": "2023-08-31",
                "execution_date": "2023-09-01",
                "month_end_valid": True,
                "monthly_factor_valid": True,
            },
            {
                "month": "2023-08-01",
                "symbol": "sh600002",
                "monthly_divergence_rate": 0.01,
                "observation_date": "2023-08-31",
                "execution_date": "2023-09-01",
                "month_end_valid": True,
                "monthly_factor_valid": True,
            },
        ]
    ).to_csv(factor_panel, index=False)
    pd.DataFrame(
        [
            {
                "trade_date": "2023-07-31",
                "allow_in_research": True,
                "gate_status": "tradable",
                "gate_reason": "",
            },
            {
                "trade_date": "2023-08-31",
                "allow_in_research": False,
                "gate_status": "coverage_blocked",
                "gate_reason": "coverage_below_threshold",
            },
        ]
    ).to_csv(coverage_ledger, index=False)

    asset_context = {
        "moneyflow_overlay": {
            "enabled": True,
            "mode": "tiebreak",
            "factor_panel_path": str(factor_panel),
            "coverage_ledger_path": str(coverage_ledger),
            "score_field": "monthly_divergence_rate",
        }
    }

    before_first = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2023, 7, 28))
    assert before_first.enabled is True
    assert before_first.gate_on is False
    assert before_first.gate_status == "pending_first_observation"

    july = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2023, 8, 15))
    assert july.gate_on is True
    assert july.observation_date == date(2023, 7, 31)
    assert july.score_map["sh600001"] == 1.0
    assert july.score_map["sh600002"] == 0.0

    august = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2023, 9, 5))
    assert august.gate_on is False
    assert august.observation_date == date(2023, 8, 31)
    assert august.gate_status == "coverage_blocked"
    assert august.gate_reason == "coverage_below_threshold"
    assert august.score_map["sh600002"] == 1.0
    assert august.score_map["sh600001"] == 0.0
