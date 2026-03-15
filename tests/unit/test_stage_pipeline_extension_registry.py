from __future__ import annotations

from datetime import date

import pytest

from backend.core.stage_pipeline import (
    ALLOWED_BUILTIN_MODULE_KINDS,
    AccountingSnapshot,
    ExecutionIntent,
    RuntimePlan,
    register_builtin_module,
    registered_builtin_modules,
    reset_builtin_module_registry,
    resolve_builtin_modules,
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
    intent = ExecutionIntent(
        as_of_date=date(2026, 3, 15),
        buy_candidates=("sh600000",),
        sell_candidates=("sz000001",),
        hold_overrides=("sh600519",),
        risk_flags=("RISK_ON",),
        ranking_payload={"selected_symbols": ["sh600000"]},
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
    assert snapshot.to_payload()["counters"]["orders"] == 1

    with pytest.raises(TypeError):
        plan.runtime_config["strategy"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        intent.ranking_payload["selected_symbols"] = []  # type: ignore[index]
    with pytest.raises(TypeError):
        snapshot.positions["sh600000"] = 0  # type: ignore[index]


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
