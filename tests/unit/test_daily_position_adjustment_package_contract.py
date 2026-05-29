from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.contracts.daily_position_adjustment_package import (
    PACKAGE_SCHEMA_VERSION,
    DailyPositionAdjustmentPackage,
    validate_daily_position_adjustment_package,
)

VALID_SHARED_FIXTURES = [
    "valid_daily_position_adjustment_package_v1.json",
    "ready_sell_daily_position_adjustment_package_v1.json",
    "hold_daily_position_adjustment_package_v1.json",
    "blocked_daily_position_adjustment_package_v1.json",
    "no_op_daily_position_adjustment_package_v1.json",
]


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "live_signal_packages" / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def test_valid_daily_position_adjustment_package_fixture() -> None:
    payload = _load_fixture("valid_daily_position_adjustment_package_v1.json")
    package = validate_daily_position_adjustment_package(payload)

    assert package.header.schema_version == PACKAGE_SCHEMA_VERSION
    assert package.package_status == "ready"
    assert package.source.publish_mode == "live"
    assert package.action_sheet[0].idempotency_key


@pytest.mark.parametrize("fixture_name", VALID_SHARED_FIXTURES)
def test_shared_live_signal_package_fixtures_are_valid(fixture_name: str) -> None:
    payload = _load_fixture(fixture_name)
    package = validate_daily_position_adjustment_package(payload)

    assert package.header.schema_version == PACKAGE_SCHEMA_VERSION
    assert package.header.package_id
    assert package.source.strategy_id


def test_shared_fixtures_cover_buy_sell_hold_blocked_no_op_and_invalid() -> None:
    action_types: set[str] = set()
    package_statuses: set[str] = set()
    for fixture_name in VALID_SHARED_FIXTURES:
        payload = _load_fixture(fixture_name)
        package = validate_daily_position_adjustment_package(payload)
        package_statuses.add(package.package_status)
        action_types.update(action.action_type for action in package.action_sheet)
        if package.validation.failure_reason_codes:
            package_statuses.add("blocked_with_failure_codes")

    with pytest.raises(ValidationError):
        validate_daily_position_adjustment_package(_load_fixture("invalid_daily_position_adjustment_package_v1.json"))

    assert {"buy", "sell", "hold"}.issubset(action_types)
    assert {"ready", "no_op", "blocked", "blocked_with_failure_codes"}.issubset(package_statuses)


def test_unknown_package_schema_version_is_rejected() -> None:
    payload = _load_fixture("valid_daily_position_adjustment_package_v1.json")
    payload["header"]["schema_version"] = "daily_position_adjustment_package@2"

    with pytest.raises(ValidationError):
        validate_daily_position_adjustment_package(payload)


def test_ready_package_requires_action_sheet() -> None:
    payload = _load_fixture("valid_daily_position_adjustment_package_v1.json")
    payload["action_sheet"] = []

    with pytest.raises(ValidationError):
        validate_daily_position_adjustment_package(payload)


def test_action_sheet_requires_account_consumable_fields() -> None:
    payload = _load_fixture("valid_daily_position_adjustment_package_v1.json")
    payload["action_sheet"][0].pop("reference_price_basis")

    with pytest.raises(ValidationError):
        validate_daily_position_adjustment_package(payload)


@pytest.mark.parametrize(
    "clock_field",
    ["signal_date", "execution_date", "signal_clock", "execution_clock", "reference_price_basis"],
)
def test_clock_requires_explicit_signal_execution_and_price_basis(clock_field: str) -> None:
    payload = _load_fixture("valid_daily_position_adjustment_package_v1.json")
    payload["clock"].pop(clock_field)

    with pytest.raises(ValidationError):
        validate_daily_position_adjustment_package(payload)


@pytest.mark.parametrize("action_field", ["reference_price", "reference_price_basis"])
def test_action_sheet_requires_explicit_reference_price_fields(action_field: str) -> None:
    payload = _load_fixture("valid_daily_position_adjustment_package_v1.json")
    payload["action_sheet"][0].pop(action_field)

    with pytest.raises(ValidationError):
        validate_daily_position_adjustment_package(payload)


def test_blocked_package_requires_failure_reason_codes() -> None:
    payload = _load_fixture("valid_daily_position_adjustment_package_v1.json")
    payload["package_status"] = "blocked"
    payload["validation"] = {
        "status": "blocked",
        "failure_reason_codes": [],
        "stale": True,
        "drifted": False,
    }

    with pytest.raises(ValidationError):
        validate_daily_position_adjustment_package(payload)


def test_contract_json_schema_exposes_required_top_level_fields() -> None:
    schema = DailyPositionAdjustmentPackage.model_json_schema()

    assert schema["title"] == "DailyPositionAdjustmentPackage"
    assert set(schema["required"]) == {
        "header",
        "source",
        "clock",
        "scope",
        "inputs",
        "package_status",
        "target_positions",
        "action_sheet",
        "risk_flags",
        "validation",
    }
