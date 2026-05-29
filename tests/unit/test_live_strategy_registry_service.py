from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.services.live_strategy_registry_service import (
    LIVE_STRATEGY_REGISTRY_SCHEMA_VERSION,
    LiveStrategyPublishBlocked,
    LiveStrategyRegistry,
    load_and_validate_live_strategy_publish_gate,
    load_live_strategy_registry,
)


def _write_registry(path: Path, *, status: str = "live_approved", omit: str | None = None) -> None:
    record = {
        "strategy_id": "demo_live_strategy",
        "status": status,
        "baseline_id": "CN_STOCK_ETF_COMBO_BASELINE_V3",
        "config_path": "backend/configs/pams_cn_pg.json",
        "config_hash": "cfg_hash_demo",
        "execution_contract_hash": "exec_hash_demo",
        "asset_scope": "cn_a_equity",
        "account_scopes": ["default_personal_account"],
        "publish_schedule": "cn_a_after_close",
        "approval_record": {"approved_by": "manual", "approved_at": "2026-05-29"},
    }
    if omit is not None:
        record.pop(omit)
    path.write_text(
        json.dumps(
            {
                "schema_version": LIVE_STRATEGY_REGISTRY_SCHEMA_VERSION,
                "strategies": [record],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_load_live_strategy_registry_empty_default() -> None:
    registry = load_live_strategy_registry(Path("missing_live_strategy_registry.json"))

    assert registry.schema_version == LIVE_STRATEGY_REGISTRY_SCHEMA_VERSION
    assert registry.strategies == []


def test_live_approved_strategy_passes_publish_gate(tmp_path: Path) -> None:
    path = tmp_path / "live_strategy_registry.json"
    _write_registry(path)

    record = load_and_validate_live_strategy_publish_gate(
        strategy_id="demo_live_strategy",
        baseline_id="CN_STOCK_ETF_COMBO_BASELINE_V3",
        config_hash="cfg_hash_demo",
        execution_contract_hash="exec_hash_demo",
        account_scope="default_personal_account",
        registry_path=path,
    )

    assert record.strategy_id == "demo_live_strategy"
    assert record.status == "live_approved"


def test_registry_rejects_missing_required_field(tmp_path: Path) -> None:
    path = tmp_path / "live_strategy_registry.json"
    _write_registry(path, omit="execution_contract_hash")

    with pytest.raises(ValidationError):
        load_live_strategy_registry(path)


@pytest.mark.parametrize(
    "status",
    ["research_only", "diagnostic_probe", "controlled_experiment", "shadow", "ab_test", "retired"],
)
def test_non_live_approved_strategy_is_blocked(tmp_path: Path, status: str) -> None:
    path = tmp_path / "live_strategy_registry.json"
    _write_registry(path, status=status)

    with pytest.raises(LiveStrategyPublishBlocked) as exc_info:
        load_and_validate_live_strategy_publish_gate(
            strategy_id="demo_live_strategy",
            baseline_id="CN_STOCK_ETF_COMBO_BASELINE_V3",
            config_hash="cfg_hash_demo",
            execution_contract_hash="exec_hash_demo",
            account_scope="default_personal_account",
            registry_path=path,
        )

    assert exc_info.value.failure_reason_codes == ["strategy_not_live_approved"]


def test_publish_gate_reports_hash_and_scope_mismatches(tmp_path: Path) -> None:
    path = tmp_path / "live_strategy_registry.json"
    _write_registry(path)

    with pytest.raises(LiveStrategyPublishBlocked) as exc_info:
        load_and_validate_live_strategy_publish_gate(
            strategy_id="demo_live_strategy",
            baseline_id="CN_STOCK_ETF_COMBO_BASELINE_V3",
            config_hash="changed_hash",
            execution_contract_hash="changed_exec_hash",
            account_scope="other_account",
            registry_path=path,
        )

    assert exc_info.value.failure_reason_codes == [
        "config_hash_mismatch",
        "execution_contract_hash_mismatch",
        "account_scope_not_allowed",
    ]


def test_default_registry_config_file_is_empty_and_valid() -> None:
    registry = load_live_strategy_registry()

    assert isinstance(registry, LiveStrategyRegistry)
    assert registry.schema_version == LIVE_STRATEGY_REGISTRY_SCHEMA_VERSION
