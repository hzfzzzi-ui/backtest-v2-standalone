from __future__ import annotations

from types import SimpleNamespace

from backend.core.audit.experiment_audit import (
    build_accounting_integrity_audit,
    build_stage_pipeline_meta,
    build_stage_summary,
    merge_experiment_audit,
)


def test_build_stage_summary_deduplicates_warnings_and_counts_days() -> None:
    pipeline_result = SimpleNamespace(
        execution_shell="foundation_shell",
        daily_loop_mode="single_path",
        summary={
            "schema_version": "stage_pipeline_summary@1",
            "stage_order": ["S1", "S2", "S7"],
            "enabled_stages": ["S1", "S2", "S7"],
        },
        daily_results=(
            SimpleNamespace(
                warnings=("A", "A"),
                filled_orders=("x",),
                scheduled_for_next_day=("o",),
            ),
            SimpleNamespace(
                warnings=("B",),
                filled_orders=(),
                scheduled_for_next_day=(),
            ),
        ),
    )

    stage_summary = build_stage_summary(route_id="legacy_route", pipeline_result=pipeline_result)

    assert stage_summary["route_id"] == "legacy_route"
    assert stage_summary["warnings"] == ["A", "B"]
    assert stage_summary["days_with_warnings"] == 2
    assert stage_summary["days_with_fills"] == 1
    assert stage_summary["days_with_scheduled_orders"] == 1


def test_merge_experiment_audit_uses_shared_stage_contract() -> None:
    stage_summary = {
        "schema_version": "stage_pipeline_summary@1",
        "execution_shell": "foundation_shell",
        "daily_loop_mode": "single_path",
        "route_id": "legacy_route",
        "stage_order": ["S1", "S2", "S7"],
        "enabled_stages": ["S1", "S2", "S7"],
        "warnings": ["A"],
        "trading_days": 10,
        "days_with_warnings": 1,
        "days_with_fills": 2,
        "days_with_scheduled_orders": 3,
    }
    stage_pipeline = build_stage_pipeline_meta(stage_summary)

    audit = merge_experiment_audit(
        {"existing": True},
        stage_pipeline=stage_pipeline,
        stage_summary=stage_summary,
        exp_id="exp_test",
    )

    assert audit["existing"] is True
    assert audit["exp_id"] == "exp_test"
    assert audit["stage_pipeline"]["route_id"] == "legacy_route"
    assert audit["warnings"] == ["A"]
    assert audit["days_with_fills"] == 2


def test_build_accounting_integrity_audit_passes_with_canonical_daily_snapshots() -> None:
    audit = build_accounting_integrity_audit(
        initial_cash=100000.0,
        daily_snapshots=[
            {
                "day": "2026-03-02",
                "cash_after": 89999.0,
                "positions_after": {"sh600000": 100},
                "trade_rows": [
                    {
                        "symbol": "sh600000",
                        "side": "BUY",
                        "qty": 100,
                        "net_amount": 10001.0,
                    }
                ],
                "nav": 100099.0,
                "market_value": 10100.0,
                "max_positions": 10,
            },
            {
                "day": "2026-03-03",
                "cash_after": 101996.0,
                "positions_after": {},
                "trade_rows": [
                    {
                        "symbol": "sh600000",
                        "side": "SELL",
                        "qty": 100,
                        "net_amount": 11997.0,
                    }
                ],
                "nav": 101996.0,
                "market_value": 0.0,
                "max_positions": 10,
            },
        ],
    )

    assert audit["status"] == "PASS"
    assert audit["summary"]["cash_check_fail"] == 0
    assert audit["summary"]["position_check_fail"] == 0
    assert audit["summary"]["nav_check_fail"] == 0
    assert audit["summary"]["days_with_evidence"] == 2


def test_build_accounting_integrity_audit_fails_on_negative_cash_and_position_mismatch() -> None:
    audit = build_accounting_integrity_audit(
        initial_cash=100000.0,
        daily_snapshots=[
            {
                "day": "2026-03-02",
                "cash_after": -1.0,
                "positions_after": {"sh600000": 200, "sz000001": 100},
                "trade_rows": [
                    {
                        "symbol": "sh600000",
                        "side": "BUY",
                        "qty": 100,
                        "net_amount": 10001.0,
                    }
                ],
                "nav": -1.0,
                "market_value": 0.0,
                "max_positions": 1,
            }
        ],
    )

    assert audit["status"] == "FAIL"
    assert audit["summary"]["cash_check_fail"] == 1
    assert audit["summary"]["position_check_fail"] == 1
    assert audit["summary"]["negative_cash_days"] == 1
    assert audit["summary"]["max_positions_breach_days"] == 1


def test_build_accounting_integrity_audit_tolerates_rounded_trade_row_cash_drift() -> None:
    audit = build_accounting_integrity_audit(
        initial_cash=100.0,
        daily_snapshots=[
            {
                "day": "2026-03-02",
                "cash_after": 199.982,
                "positions_after": {},
                "trade_rows": [
                    {
                        "symbol": f"sh6000{idx:02d}",
                        "side": "SELL",
                        "qty": 100,
                        "net_amount": 25.0,
                    }
                    for idx in range(4)
                ],
                "nav": 199.982,
                "market_value": 0.0,
                "max_positions": 20,
            }
        ],
    )

    assert audit["status"] == "PASS"
    assert audit["summary"]["cash_check_fail"] == 0


def test_build_accounting_integrity_audit_uses_hard_cap_not_effective_cap_for_position_breach() -> None:
    audit = build_accounting_integrity_audit(
        initial_cash=100000.0,
        daily_snapshots=[
            {
                "day": "2026-03-02",
                "cash_after": 99700.0,
                "positions_after": {
                    "sh600000": 100,
                    "sh600001": 100,
                    "sh600002": 100,
                },
                "trade_rows": [
                    {"symbol": "sh600000", "side": "BUY", "qty": 100, "net_amount": 100.0},
                    {"symbol": "sh600001", "side": "BUY", "qty": 100, "net_amount": 100.0},
                    {"symbol": "sh600002", "side": "BUY", "qty": 100, "net_amount": 100.0},
                ],
                "nav": 100000.0,
                "market_value": 300.0,
                "max_positions": 10,
                "effective_max_positions": 10,
            },
            {
                "day": "2026-03-03",
                "cash_after": 99700.0,
                "positions_after": {
                    "sh600000": 100,
                    "sh600001": 100,
                    "sh600002": 100,
                },
                "trade_rows": [],
                "nav": 100000.0,
                "market_value": 300.0,
                "max_positions": 10,
                "effective_max_positions": 2,
            }
        ],
    )

    assert audit["status"] == "PASS"
    assert audit["summary"]["max_positions_breach_days"] == 0


def test_build_accounting_integrity_audit_returns_unknown_when_evidence_is_missing() -> None:
    audit = build_accounting_integrity_audit(
        initial_cash=100000.0,
        daily_snapshots=[
            {
                "day": "2026-03-02",
                "cash_after": 100000.0,
                "positions_after": {"sh600000": 100},
                "nav": 100000.0,
                "market_value": 0.0,
                "max_positions": 10,
            }
        ],
    )

    assert audit["status"] == "UNKNOWN"
    assert audit["summary"]["days_with_evidence"] == 0
    assert audit["summary"]["missing_evidence_days"] == 1
