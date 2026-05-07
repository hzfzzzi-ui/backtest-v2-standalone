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


def test_moneyflow_overlay_snapshot_supports_daily_factor_snapshot(tmp_path) -> None:
    factor_snapshot = tmp_path / "factor_snapshot.csv"
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600001",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.9,
                "available": True,
            },
            {
                "date": "2024-01-02",
                "symbol": "sh600002",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.1,
                "available": True,
            },
            {
                "date": "2024-01-02",
                "symbol": "sh600003",
                "factor_id": "other_factor",
                "rank_value": 0.2,
                "available": True,
            },
            {
                "date": "2024-01-03",
                "symbol": "sh600001",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.2,
                "available": False,
            },
            {
                "date": "2024-01-03",
                "symbol": "sh600002",
                "factor_id": "pre_profit_failure_context_risk",
                "rank_value": 0.4,
                "available": False,
            },
        ]
    ).to_csv(factor_snapshot, index=False)

    asset_context = {
        "moneyflow_overlay": {
            "enabled": True,
            "mode": "band_rerank",
            "factor_role": "rank",
            "apply_layer": "ranking",
            "band_limit": 20,
            "source_kind": "daily_factor_snapshot",
            "factor_snapshot_path": str(factor_snapshot),
            "factor_id": "pre_profit_failure_context_risk",
            "score_field": "rank_value",
            "lower_is_better": True,
        }
    }

    before_first = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2024, 1, 1))
    assert before_first.enabled is True
    assert before_first.gate_on is False
    assert before_first.gate_status == "pending_first_observation"

    jan2 = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2024, 1, 2))
    assert jan2.gate_on is True
    assert jan2.observation_date == date(2024, 1, 2)
    assert jan2.band_limit == 20
    assert jan2.score_map["sh600002"] == 1.0
    assert jan2.score_map["sh600001"] == 0.0
    assert "sh600003" not in jan2.score_map

    jan3 = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2024, 1, 3))
    assert jan3.gate_on is False
    assert jan3.observation_date == date(2024, 1, 3)
    assert jan3.gate_status == "no_available_scores"
    assert jan3.gate_reason == "daily_factor_snapshot_unavailable"
    assert jan3.score_map == {}


def test_moneyflow_overlay_snapshot_rejects_context_role_with_veto_mode(tmp_path) -> None:
    factor_snapshot = tmp_path / "factor_snapshot.csv"
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600001",
                "factor_id": "monthly_divergence_rate",
                "rank_value": 0.9,
                "available": True,
            },
        ]
    ).to_csv(factor_snapshot, index=False)

    asset_context = {
        "moneyflow_overlay": {
            "enabled": True,
            "mode": "veto_bottom20",
            "factor_role": "context",
            "source_kind": "daily_factor_snapshot",
            "factor_snapshot_path": str(factor_snapshot),
            "factor_id": "monthly_divergence_rate",
        }
    }

    snapshot = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2024, 1, 2))
    assert snapshot.enabled is True
    assert snapshot.gate_on is False
    assert snapshot.gate_status == "invalid_action"
    assert snapshot.gate_reason == "moneyflow_overlay_role_action_mismatch:context->veto_bottom20"


def test_moneyflow_overlay_snapshot_rejects_band_rerank_modes_without_band_limit(tmp_path) -> None:
    factor_snapshot = tmp_path / "factor_snapshot.csv"
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600001",
                "factor_id": "monthly_divergence_rate",
                "rank_value": 0.9,
                "available": True,
            },
        ]
    ).to_csv(factor_snapshot, index=False)

    for mode in ("band_rerank", "bull_only_band_rerank", "bull_trans_up_band_rerank"):
        asset_context = {
            "moneyflow_overlay": {
                "enabled": True,
                "mode": mode,
                "factor_role": "rank",
                "apply_layer": "ranking",
                "source_kind": "daily_factor_snapshot",
                "factor_snapshot_path": str(factor_snapshot),
                "factor_id": "monthly_divergence_rate",
            }
        }

        snapshot = resolve_moneyflow_overlay_snapshot(asset_context, day=date(2024, 1, 2))
        assert snapshot.enabled is True
        assert snapshot.mode == mode
        assert snapshot.gate_on is False
        assert snapshot.gate_status == "invalid_band_limit"
        assert snapshot.gate_reason == "moneyflow_overlay_band_limit_required_for_band_rerank"
