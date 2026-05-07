from __future__ import annotations

from datetime import date

import pytest

from backend.core.stage_pipeline import (
    ALLOWED_BUILTIN_MODULE_KINDS,
    AccountingSnapshot,
    ActionIntentAction,
    ActionIntentContract,
    ExecutionAuditContract,
    ExecutionAuditRecord,
    RuntimePlan,
    SubsystemBudgetContract,
    register_builtin_module,
    registered_builtin_modules,
    reset_builtin_module_registry,
    resolve_builtin_modules,
)
from backend.core.stage_pipeline.contracts import (
    TargetBookContract,
    TargetBookItem,
)


def teardown_function() -> None:
    reset_builtin_module_registry()


def test_runtime_execution_and_accounting_contracts_are_read_only() -> None:
    plan = RuntimePlan(
        runtime_config={"strategy": {"name": "breakout_trend"}},
        execution_overrides={"max_positions": 10},
        strategy_route="provider_breakout_runtime",
        provider_ref="BreakoutTrendProvider",
        execution_assumptions={"signal_clock": "POST_CLOSE", "execution_clock": "NEXT_OPEN"},
        pipeline_modules={"gates": ("benchmark_regime",)},
    )
    intent = ActionIntentContract(
        as_of_date=date(2026, 3, 15),
        owner_system="trend",
        actions=(
            ActionIntentAction(
                action_index=1,
                symbol="sh600000",
                side="BUY",
                priority=1,
                reason_codes=("ENTRY",),
                suggested_size_value=0.2,
                suggested_size_unit="weight",
                suggested_size_basis="subsystem_budget_relative",
                source_intent_id="intent_001",
                notes={"selected_symbols": ["sh600000"]},
            ),
        ),
    )
    audit = ExecutionAuditContract(
        as_of_date=date(2026, 3, 15),
        records=(
            ExecutionAuditRecord(
                action_index=1,
                owner_system="trend",
                symbol="sh600000",
                side="BUY",
                requested_size_value=0.2,
                requested_size_unit="weight",
                requested_size_basis="subsystem_budget_relative",
                outcome="accepted",
                reason_codes=("ENTRY",),
                final_qty=100,
            ),
        ),
    )
    snapshot = AccountingSnapshot(
        cash=1000000.0,
        positions={"sh600000": 100},
        filled_orders=({"symbol": "sh600000", "qty": 100},),
        trade_rows=({"symbol": "sh600000", "side": "BUY"},),
        daily_marks={"nav": 1.02},
        counters={"orders": 1},
    )

    assert plan.to_mapping()["strategy_route"] == "provider_breakout_runtime"
    assert intent.to_payload()["as_of_date"] == "2026-03-15"
    assert audit.to_payload()["summary"]["accepted_count"] == 1
    assert snapshot.to_payload()["counters"]["orders"] == 1

    with pytest.raises(TypeError):
        plan.runtime_config["strategy"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        intent.actions[0].notes["selected_symbols"] = []  # type: ignore[index]
    with pytest.raises(TypeError):
        audit.records[0].notes["x"] = 1  # type: ignore[index]
    with pytest.raises(TypeError):
        snapshot.positions["sh600000"] = 0  # type: ignore[index]


def test_target_book_contract_is_read_only() -> None:
    target_book = TargetBookContract(
        decision_date=date(2026, 3, 15),
        execution_date=date(2026, 3, 16),
        targets=(
            TargetBookItem(
                symbol="sh600000",
                target_weight=0.2,
                owner_system="trend",
                reason_codes=("ENTRY",),
                priority=1,
            ),
        ),
    )

    assert target_book.to_payload()["contract_version"] == "target_book_v1"

    with pytest.raises(TypeError):
        target_book.notes["x"] = 1  # type: ignore[index]


def test_subsystem_budget_contract_is_read_only() -> None:
    budget = SubsystemBudgetContract(
        as_of_date=date(2026, 3, 15),
        owner_system="cn_stock_trend_alpha_core",
        budget_value=0.75,
        allow_new_risk=True,
        force_reduce_only=False,
        reason_codes=("STATE_BULL",),
    )

    assert budget.to_payload()["contract_version"] == "subsystem_budget_v1"

    with pytest.raises(TypeError):
        budget.notes["x"] = 1  # type: ignore[index]


def test_builtin_registry_and_resolver_only_allow_first_wave_module_kinds() -> None:
    assert ALLOWED_BUILTIN_MODULE_KINDS == (
        "candidate_filters",
        "rankers",
        "gates",
        "exits",
        "sizers",
        "reporters",
    )

    register_builtin_module("gates", "benchmark_regime", lambda: {"kind": "gate"})
    register_builtin_module("reporters", "audit_tap", lambda: {"kind": "reporter"})

    resolved = resolve_builtin_modules(
        {
            "gates": ["benchmark_regime"],
            "reporters": ["audit_tap"],
        }
    )

    assert [(item.kind, item.name) for item in resolved] == [
        ("gates", "benchmark_regime"),
        ("reporters", "audit_tap"),
    ]
    assert registered_builtin_modules()["gates"]["benchmark_regime"]() == {"kind": "gate"}

    with pytest.raises(ValueError):
        register_builtin_module("planners", "unsupported", lambda: None)
