from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from backend.core.config.cn_a_governed_mainline import build_governor_budget_snapshot
from backend.core.stage_pipeline.adapters.daily_accounting import build_daily_row


def test_build_governor_budget_snapshot_distinguishes_etf_slot_cap_from_breadth() -> None:
    snapshot = build_governor_budget_snapshot(
        asset_scope="cn_etf",
        hard_max_positions=10,
        effective_max_positions=0,
        risk_budget_multiplier=0.0,
        drawdown=0.0,
        drawdown_state="NORMAL",
        effective_state_5="TRANS_DOWN",
        breadth_max_positions=10,
        breadth_cap_active=False,
        sleeve_slot_cap_active=True,
        sleeve_slot_cap_source="phase1_targets",
    )

    assert snapshot["breadth_cap_active"] is False
    assert snapshot["sleeve_slot_cap_active"] is True
    assert snapshot["sleeve_slot_cap_source"] == "phase1_targets"
    assert "ETF_BETA_SLOT_CAP_ACTIVE" in snapshot["budget_reason_codes"]
    assert "BREADTH_CAP_ACTIVE" not in snapshot["budget_reason_codes"]
    assert "NO_DEPLOYABLE_SLOTS" in snapshot["budget_reason_codes"]


def test_build_governor_budget_snapshot_preserves_real_breadth_label() -> None:
    snapshot = build_governor_budget_snapshot(
        asset_scope="cn_a_equity",
        hard_max_positions=10,
        effective_max_positions=5,
        risk_budget_multiplier=0.8,
        drawdown=0.0,
        drawdown_state="NORMAL",
        effective_state_5="LIGHT",
        breadth_max_positions=5,
        breadth_cap_active=True,
        sleeve_slot_cap_active=False,
    )

    assert snapshot["breadth_cap_active"] is True
    assert snapshot["sleeve_slot_cap_active"] is False
    assert "BREADTH_CAP_ACTIVE" in snapshot["budget_reason_codes"]
    assert "ETF_BETA_SLOT_CAP_ACTIVE" not in snapshot["budget_reason_codes"]


def test_build_governor_budget_snapshot_excludes_etf_private_boundary_fields() -> None:
    snapshot = build_governor_budget_snapshot(
        asset_scope="cn_etf",
        hard_max_positions=10,
        effective_max_positions=2,
        risk_budget_multiplier=1.0,
        drawdown=0.0,
        drawdown_state="NORMAL",
        effective_state_5="BULL",
        breadth_max_positions=10,
        breadth_cap_active=False,
        sleeve_slot_cap_active=True,
        sleeve_slot_cap_source="phase1_targets",
        target_exposure=0.2,
        strategic_floor_cap=0.108,
        tactical_overlay_cap=0.072,
        deployment_pace=0.144,
        hard_block_flags=["ALLOW_NEW_RISK"],
        min_deployable_exposure=0.0,
        target_exposure_source="governor_total_exposure_cap",
        min_deployable_exposure_source="phase1_allocation_engine",
        fallback_allowed=False,
        under_deploy_reason_codes=["PACE_POLICY_GAP"],
        actual_exposure=0.12,
        actual_risk_exposure=0.12,
        actual_fallback_exposure=0.0,
        actual_other_exposure=0.0,
    )

    assert snapshot["target_exposure"] == 0.2
    assert snapshot["sleeve_budgets"]["cn_etf_beta"]["target_exposure"] == 0.2
    for forbidden_field in (
        "strategic_floor_cap",
        "tactical_overlay_cap",
        "deployment_pace",
        "hard_block_flags",
        "min_deployable_exposure",
        "target_exposure_source",
        "min_deployable_exposure_source",
        "fallback_allowed",
        "under_deploy_reason_codes",
        "actual_exposure",
        "actual_risk_exposure",
        "actual_fallback_exposure",
        "actual_other_exposure",
        "deployability_gap",
    ):
        assert forbidden_field not in snapshot
        assert forbidden_field not in snapshot["sleeve_budgets"]["cn_etf_beta"]


def test_build_daily_row_carries_split_slot_cap_fields_into_governor_snapshot() -> None:
    runtime = SimpleNamespace(
        cash=1000000.0,
        positions={},
        request=SimpleNamespace(max_positions=10, asset_context={"asset_scope": "cn_etf"}),
    )
    controls = {
        "effective_max_positions": 0,
        "breadth_score": None,
        "breadth_max_positions": 10,
        "breadth_cap_active": False,
        "dd_state": "NORMAL",
        "regime_engine": "ma200_legacy",
        "regime_confidence": None,
        "regime_duration_bars": None,
        "regime_transition_reason": "",
        "feature_availability": {},
        "market_state_5": "TRANS_DOWN",
        "base_state_5": "TRANS_DOWN",
        "effective_state_5": "TRANS_DOWN",
        "coarse_state": "RISK_OFF",
        "effective_coarse_state": "RISK_OFF",
        "market_state_score": None,
        "market_state_raw": "TRANS_DOWN",
        "market_state_smoothed": "TRANS_DOWN",
        "risk_budget_multiplier": 0.0,
        "sleeve_slot_cap_active": True,
        "sleeve_slot_cap_source": "phase1_targets",
        "reason_codes": [],
        "block_scores": {},
        "subscores": {},
        "manual_override": {},
        "state_stability_metrics": {},
        "defense_bias": None,
        "weekly_observation_flag": False,
    }

    row = build_daily_row(
        runtime,
        day=date(2026, 3, 28),
        nav=1000000.0,
        daily_ret=0.0,
        drawdown=0.0,
        gross_exposure=0.0,
        turnover_pct=0.0,
        top5=[],
        controls=controls,
        etf_exposure_semantics=None,
    )

    governor_budget = json.loads(row["governor_budget_json"])
    assert row["breadth_cap_active"] is False
    assert row["sleeve_slot_cap_active"] is True
    assert row["sleeve_slot_cap_source"] == "phase1_targets"
    assert governor_budget["breadth_cap_active"] is False
    assert governor_budget["sleeve_slot_cap_active"] is True
    assert governor_budget["sleeve_slot_cap_source"] == "phase1_targets"
    assert "ETF_BETA_SLOT_CAP_ACTIVE" in governor_budget["budget_reason_codes"]
    assert "BREADTH_CAP_ACTIVE" not in governor_budget["budget_reason_codes"]
