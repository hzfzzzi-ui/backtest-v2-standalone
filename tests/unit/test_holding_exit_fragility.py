from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.engine_vector.holding_exit_fragility import resolve_holding_exit_fragility_snapshot


def test_holding_exit_fragility_snapshot_resolves_for_holding_layer(tmp_path) -> None:
    factor_snapshot = tmp_path / "factor_snapshot.csv"
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600001",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.85,
                "available": True,
            },
            {
                "date": "2024-01-02",
                "symbol": "sh600002",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.25,
                "available": True,
            },
        ]
    ).to_csv(factor_snapshot, index=False)

    asset_context = {
        "holding_exit_fragility": {
            "enabled": True,
            "apply_layer": "holding_exit",
            "source_kind": "daily_factor_snapshot",
            "factor_snapshot_path": str(factor_snapshot),
            "factor_id": "pre_profit_failure_context_risk",
            "action": "exit_candidate",
            "risk_bucket_top_pct": 0.2,
        }
    }

    snapshot = resolve_holding_exit_fragility_snapshot(asset_context, day=date(2024, 1, 2))
    assert snapshot.enabled is True
    assert snapshot.valid is True
    assert snapshot.gate_on is True
    assert snapshot.action == "exit_candidate"
    assert snapshot.score_map["sh600001"] == 0.85


def test_holding_exit_fragility_snapshot_rejects_candidate_layer(tmp_path) -> None:
    factor_snapshot = tmp_path / "factor_snapshot.csv"
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600001",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.85,
                "available": True,
            },
        ]
    ).to_csv(factor_snapshot, index=False)

    asset_context = {
        "holding_exit_fragility": {
            "enabled": True,
            "apply_layer": "candidate",
            "source_kind": "daily_factor_snapshot",
            "factor_snapshot_path": str(factor_snapshot),
            "factor_id": "pre_profit_failure_context_risk",
            "action": "exit_candidate",
        }
    }

    snapshot = resolve_holding_exit_fragility_snapshot(asset_context, day=date(2024, 1, 2))
    assert snapshot.enabled is True
    assert snapshot.valid is False
    assert snapshot.gate_on is False
    assert snapshot.gate_status == "invalid_layer"


def test_holding_exit_fragility_snapshot_rejects_non_lifecycle_role(tmp_path) -> None:
    factor_snapshot = tmp_path / "factor_snapshot.csv"
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600001",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.85,
                "available": True,
            },
        ]
    ).to_csv(factor_snapshot, index=False)

    asset_context = {
        "holding_exit_fragility": {
            "enabled": True,
            "factor_role": "context",
            "apply_layer": "holding_exit",
            "source_kind": "daily_factor_snapshot",
            "factor_snapshot_path": str(factor_snapshot),
            "factor_id": "pre_profit_failure_context_risk",
            "action": "watch",
        }
    }

    snapshot = resolve_holding_exit_fragility_snapshot(asset_context, day=date(2024, 1, 2))
    assert snapshot.enabled is True
    assert snapshot.valid is False
    assert snapshot.gate_on is False
    assert snapshot.gate_status == "invalid_role"
