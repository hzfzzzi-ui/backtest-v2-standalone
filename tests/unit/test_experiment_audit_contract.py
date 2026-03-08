from __future__ import annotations

from types import SimpleNamespace

from backend.core.audit.experiment_audit import (
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
