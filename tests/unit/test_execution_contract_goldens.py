from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from backend.api.backtest_v2.runner_output_helpers import build_unified_combo_execution_contract
from backend.core.stage_pipeline import (
    ActionIntentAction,
    ActionIntentContract,
    ExecutionAuditContract,
    ExecutionAuditRecord,
    RiskOverrideContract,
    SubsystemBudgetContract,
)


def _golden(name: str) -> dict:
    root = Path(__file__).resolve().parents[1] / "goldens" / "execution_contracts"
    return json.loads((root / name).read_text(encoding="utf-8"))


def test_action_intent_contract_matches_golden_payload() -> None:
    contract = ActionIntentContract(
        as_of_date=date(2026, 4, 4),
        owner_system="stock_alpha",
        actions=(
            ActionIntentAction(
                action_index=1,
                symbol="SH600000",
                side="buy",
                priority=1,
                reason_codes=("ENTRY_BREAKOUT",),
                suggested_size_value=0.25,
                suggested_size_unit="weight",
                suggested_size_basis="subsystem_budget_relative",
                source_intent_id="intent_stock_alpha_001",
                notes={"signal_strength": 0.82},
            ),
            ActionIntentAction(
                action_index=2,
                symbol="sh600519",
                side="BUY",
                priority=1,
                reason_codes=("ENTRY_REPAIR",),
                suggested_size_value=0.15,
                suggested_size_unit="weight",
                suggested_size_basis="subsystem_budget_relative",
                source_intent_id="intent_stock_alpha_002",
            ),
            ActionIntentAction(
                action_index=3,
                symbol="sh600036",
                side="SELL",
                priority=2,
                reason_codes=("EXIT_SIGNAL",),
                suggested_size_value=0.5,
                suggested_size_unit="ratio",
                suggested_size_basis="sellable_qty_relative",
                source_intent_id="intent_stock_alpha_003",
                notes={"sellable_qty": 400},
            ),
        ),
    )
    assert contract.to_payload() == _golden("action_intent_v1.json")


def test_risk_override_contract_matches_golden_payload() -> None:
    contract = RiskOverrideContract(
        as_of_date=date(2026, 4, 4),
        override_owner="global_portfolio_governor",
        scope="symbol",
        action="FORCE_EXIT",
        target_symbol="SH510300",
        reason_codes=("RISK_LOCKED", "FORCE_EXIT_SYMBOL"),
        notes={"origin": "governor_snapshot"},
    )
    assert contract.to_payload() == _golden("risk_override_v1.json")


def test_subsystem_budget_contract_matches_golden_payload() -> None:
    contract = SubsystemBudgetContract(
        as_of_date=date(2026, 4, 4),
        owner_system="cn_stock_trend_alpha_core",
        budget_value=0.6,
        strategic_floor_cap=0.2,
        tactical_overlay_cap=0.4,
        deployment_pace="normal",
        allow_new_risk=True,
        force_reduce_only=False,
        reason_codes=("STATE_BULL", "RECOVERY_INACTIVE"),
        notes={"source": "governor_budget_snapshot"},
    )
    assert contract.to_payload() == _golden("subsystem_budget_v1.json")


def test_execution_audit_contract_matches_golden_payload() -> None:
    contract = ExecutionAuditContract(
        as_of_date=date(2026, 4, 4),
        records=(
            ExecutionAuditRecord(
                action_index=1,
                owner_system="stock_alpha",
                symbol="sh600000",
                side="BUY",
                requested_size_value=0.25,
                requested_size_unit="weight",
                requested_size_basis="subsystem_budget_relative",
                outcome="blocked",
                reason_codes=("REDUCE_ONLY_BLOCKED",),
                blocked_by_override=True,
                final_qty=0,
            ),
            ExecutionAuditRecord(
                action_index=2,
                owner_system="stock_alpha",
                symbol="sh600036",
                side="SELL",
                requested_size_value=0.8,
                requested_size_unit="ratio",
                requested_size_basis="sellable_qty_relative",
                outcome="clipped",
                reason_codes=("CLIPPED_TO_SELLABLE",),
                clipped_to_sellable=True,
                rounded_to_lot=True,
                final_qty=300,
                notes={"sellable_qty": 320, "lot_size": 100},
            ),
            ExecutionAuditRecord(
                action_index=3,
                owner_system="stock_alpha",
                symbol="sh600519",
                side="BUY",
                requested_size_value=0.1,
                requested_size_unit="weight",
                requested_size_basis="subsystem_budget_relative",
                outcome="skipped",
                reason_codes=("HIGHER_PRIORITY_FILLED_CASH",),
                skipped_for_priority=True,
                final_qty=0,
            ),
        ),
    )
    assert contract.to_payload() == _golden("execution_audit_v1.json")


def test_unified_combo_execution_contract_matches_golden_payload() -> None:
    contract = build_unified_combo_execution_contract(
        combo_mode="account_budget_controlled_dynamic_mix",
        benchmark="CN_STOCK_ETF_50_50",
        weights={
            "cn_stock_trend_alpha_core": 0.6,
            "cn_etf_beta": 0.4,
        },
        stock_runtime_config={
            "asset_scope": "cn_a_equity",
            "governed_a_share": {
                "enabled": True,
                "stock_alpha_core": {
                    "enabled": True,
                    "budget_semantics": "consume_governor_sleeve_budget",
                },
            },
        },
        etf_runtime_config={
            "asset_scope": "cn_etf",
            "governed_a_share": {
                "enabled": True,
                "etf_beta": {
                    "enabled": True,
                    "strategy_role": "strategic_beta_stabilizer",
                },
            },
        },
        stock_execution_overrides={},
        etf_execution_overrides={},
        account_budget_control={
            "contract_version": "account_budget_control@1",
            "enabled": True,
        },
    )
    assert contract == _golden("unified_combo_execution_contract_v1.json")


def test_unified_combo_execution_contract_carries_component_overrides() -> None:
    contract = build_unified_combo_execution_contract(
        combo_mode="account_budget_controlled_dynamic_mix",
        benchmark="CN_STOCK_ETF_50_50",
        weights={"cn_stock_trend_alpha_core": 0.5, "cn_etf_beta": 0.5},
        stock_runtime_config={"asset_scope": "cn_a_equity"},
        etf_runtime_config={"asset_scope": "cn_etf"},
        stock_execution_overrides={"enable_multifactor_rank": True, "mf_topk": 10},
        etf_execution_overrides={"max_positions": 2},
        account_budget_control={"enabled": True},
    )

    components = contract["components"]
    assert components["stock_component"]["execution_overrides"]["enable_multifactor_rank"] is True
    assert components["stock_component"]["execution_overrides"]["mf_topk"] == 10
    assert components["etf_component"]["execution_overrides"]["max_positions"] == 2


def test_action_intent_contract_rejects_invalid_buy_basis() -> None:
    with pytest.raises(ValueError, match="BUY suggested_size_basis"):
        ActionIntentAction(
            action_index=1,
            symbol="sh600000",
            side="BUY",
            priority=1,
            reason_codes=("ENTRY",),
            suggested_size_value=0.2,
            suggested_size_unit="weight",
            suggested_size_basis="portfolio_relative",
        )


def test_action_intent_contract_rejects_same_symbol_opposite_sides() -> None:
    with pytest.raises(ValueError, match="same symbol"):
        ActionIntentContract(
            as_of_date=date(2026, 4, 4),
            owner_system="stock_alpha",
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
                ),
                ActionIntentAction(
                    action_index=2,
                    symbol="sh600000",
                    side="SELL",
                    priority=2,
                    reason_codes=("EXIT",),
                    suggested_size_value=0.5,
                    suggested_size_unit="ratio",
                    suggested_size_basis="sellable_qty_relative",
                ),
            ),
        )


def test_risk_override_contract_requires_target_symbol_for_symbol_scope() -> None:
    with pytest.raises(ValueError, match="target_symbol"):
        RiskOverrideContract(
            as_of_date=date(2026, 4, 4),
            override_owner="global_portfolio_governor",
            scope="symbol",
            action="FORCE_EXIT",
            reason_codes=("FORCE_EXIT_SYMBOL",),
        )
