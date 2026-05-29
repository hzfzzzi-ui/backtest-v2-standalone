from __future__ import annotations

import pytest

from backend.core.contracts.daily_position_adjustment_package import validate_daily_position_adjustment_package
from backend.core.services.live_package_publisher_service import (
    build_daily_position_adjustment_package_from_reconcile,
    package_to_payload,
)
from backend.core.services.live_strategy_registry_service import LiveStrategyRecord


BASELINE_ID = "CN_STOCK_ETF_COMBO_BASELINE_V3"
CONFIG_HASH = "cfg_hash_demo"
EXECUTION_CONTRACT_HASH = "exec_hash_demo"
ACCOUNT_SCOPE = "default_personal_account"


def _strategy(*, status: str = "live_approved") -> LiveStrategyRecord:
    return LiveStrategyRecord(
        strategy_id="demo_live_strategy",
        status=status,  # type: ignore[arg-type]
        baseline_id=BASELINE_ID,
        config_path="backend/configs/pams_cn_pg.json",
        config_hash=CONFIG_HASH,
        execution_contract_hash=EXECUTION_CONTRACT_HASH,
        asset_scope="cn_a_equity",
        account_scopes=[ACCOUNT_SCOPE],
        publish_schedule="cn_a_after_close",
        approval_record={"approved_by": "manual", "approved_at": "2026-05-29"},
    )


def _action_sheet() -> list[dict]:
    return [
        {
            "symbol": "sh600519",
            "name": "Kweichow Moutai",
            "action_type": "buy",
            "current_qty": 0,
            "sellable_qty": 0,
            "suggested_qty": 100,
            "target_qty": 100,
            "delta_qty": 100,
            "reference_price": 1500.0,
            "reference_price_basis": "latest_close",
            "reason_code": "BUY_BREAKOUT",
            "reason_tags": ["breakout", "rank=1"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.2,
        },
        {
            "symbol": "sh600036",
            "name": "China Merchants Bank",
            "action_type": "sell",
            "current_qty": 200,
            "sellable_qty": 200,
            "suggested_qty": 200,
            "target_qty": 0,
            "delta_qty": -200,
            "reference_price": 42.5,
            "reference_price_basis": "latest_close",
            "reason_code": "SELL_EXIT",
            "reason_tags": ["exit"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.0,
        },
        {
            "symbol": "sh600000",
            "name": "Shanghai Pudong Development Bank",
            "action_type": "hold",
            "current_qty": 100,
            "sellable_qty": 100,
            "suggested_qty": 0,
            "target_qty": 100,
            "delta_qty": 0,
            "reference_price": 10.8,
            "reference_price_basis": "latest_close",
            "reason_code": "HOLD",
            "reason_tags": ["currently_held"],
            "blocked": False,
            "blocked_reason": "",
            "target_weight": 0.12,
        },
    ]


def _reconcile(*, action_sheet: list[dict] | None = None, config_hash: str = CONFIG_HASH) -> dict:
    return {
        "reconcile_id": "rc_demo_20260529",
        "account_id": ACCOUNT_SCOPE,
        "snapshot_id": "holdings_default_20260529",
        "snapshot_trade_date": "2026-05-29",
        "as_of_date": "2026-05-29",
        "strategy_source": {
            "exp_id": "run_demo_cn_a_20260529",
            "created_at": "2026-05-29T15:05:00+08:00",
            "config_hash": config_hash,
            "asset_scope": "cn_a_equity",
        },
        "execution_assumptions": {
            "signal_clock": "POST_CLOSE",
            "execution_clock": "NEXT_OPEN",
            "reference_price_basis": "latest_close",
        },
        "action_sheet": _action_sheet() if action_sheet is None else action_sheet,
    }


def _build_package(**overrides):
    params = {
        "reconcile_payload": _reconcile(),
        "strategy": _strategy(),
        "baseline_id": BASELINE_ID,
        "execution_contract_hash": EXECUTION_CONTRACT_HASH,
        "execution_date": "2026-06-01",
        "generated_at": "2026-05-29T15:30:00+08:00",
    }
    params.update(overrides)
    reconcile_payload = params.pop("reconcile_payload")
    return build_daily_position_adjustment_package_from_reconcile(reconcile_payload, **params)


def test_builds_ready_package_from_reconcile_action_sheet() -> None:
    package = _build_package()
    payload = package_to_payload(package)
    validated = validate_daily_position_adjustment_package(payload)

    assert validated.package_status == "ready"
    assert validated.validation.status == "passed"
    assert validated.source.strategy_id == "demo_live_strategy"
    assert validated.source.config_hash == CONFIG_HASH
    assert validated.scope.account_scope == ACCOUNT_SCOPE
    assert validated.inputs.reconcile_id == "rc_demo_20260529"
    assert len(validated.target_positions) == 3
    assert [action.action_type for action in validated.action_sheet] == ["buy", "sell"]
    assert validated.action_sheet[0].current_qty == 0
    assert validated.action_sheet[0].suggested_qty == 100
    assert validated.action_sheet[0].reference_price_basis == "latest_close"
    assert validated.action_sheet[0].expires_at == "2026-06-01T15:00:00+08:00"


def test_package_ids_and_action_idempotency_are_stable_for_same_inputs() -> None:
    first = _build_package()
    second = _build_package()

    assert first.header.package_id == second.header.package_id
    assert first.header.idempotency_key == second.header.idempotency_key
    assert first.action_sheet[0].idempotency_key == second.action_sheet[0].idempotency_key


def test_no_op_package_is_explicit_when_only_hold_rows_exist() -> None:
    hold_rows = [row for row in _action_sheet() if row["action_type"] == "hold"]
    package = _build_package(reconcile_payload=_reconcile(action_sheet=hold_rows))

    assert package.package_status == "no_op"
    assert package.action_sheet == []
    assert package.validation.status == "passed"
    assert package.risk_flags[0].code == "no_action_required"
    validate_daily_position_adjustment_package(package_to_payload(package))


def test_live_publish_gate_blocks_stale_and_hash_drift() -> None:
    package = _build_package(
        reconcile_payload=_reconcile(config_hash="changed_config_hash"),
        stale=True,
        drifted=True,
    )

    assert package.package_status == "blocked"
    assert package.validation.status == "blocked"
    assert package.validation.failure_reason_codes == [
        "config_hash_mismatch",
        "stale_reconcile",
        "drifted_reconcile",
    ]
    assert [flag.code for flag in package.risk_flags][:3] == package.validation.failure_reason_codes
    validate_daily_position_adjustment_package(package_to_payload(package))


def test_live_publish_gate_blocks_non_live_strategy_but_audit_copy_can_be_ready() -> None:
    shadow_strategy = _strategy(status="shadow")

    live_package = _build_package(strategy=shadow_strategy)
    assert live_package.package_status == "blocked"
    assert live_package.validation.failure_reason_codes == ["strategy_not_live_approved"]

    audit_package = _build_package(strategy=shadow_strategy, publish_mode="audit_copy")
    assert audit_package.package_status == "ready"
    assert audit_package.source.publish_mode == "audit_copy"
    assert audit_package.validation.failure_reason_codes == []
    validate_daily_position_adjustment_package(package_to_payload(audit_package))


@pytest.mark.parametrize(
    "status",
    ["research_only", "diagnostic_probe", "controlled_experiment", "shadow", "ab_test", "retired"],
)
def test_live_publish_gate_blocks_all_non_live_strategy_statuses(status: str) -> None:
    package = _build_package(strategy=_strategy(status=status))

    assert package.package_status == "blocked"
    assert package.validation.status == "blocked"
    assert package.validation.failure_reason_codes == ["strategy_not_live_approved"]


def test_blocked_action_row_produces_blocked_package_and_action_reason() -> None:
    rows = _action_sheet()
    rows[0] = {**rows[0], "blocked": True, "blocked_reason": "cash_check_failed"}
    package = _build_package(reconcile_payload=_reconcile(action_sheet=rows))

    assert package.package_status == "blocked"
    assert "cash_check_failed" in package.validation.failure_reason_codes
    assert package.action_sheet[0].action_status == "blocked"
    assert package.action_sheet[0].blocked is True
    assert "cash_check_failed" in package.action_sheet[0].reason_codes
    validate_daily_position_adjustment_package(package_to_payload(package))
