from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


LIVE_STRATEGY_REGISTRY_SCHEMA_VERSION = "live_strategy_registry@1"
LiveStrategyStatus = Literal["live_approved", "research_only", "shadow", "ab_test", "retired"]


class LiveStrategyPublishBlocked(RuntimeError):
    def __init__(self, failure_reason_codes: list[str]) -> None:
        self.failure_reason_codes = list(failure_reason_codes)
        super().__init__(",".join(self.failure_reason_codes))


class _StrictRegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LiveStrategyRecord(_StrictRegistryModel):
    strategy_id: str = Field(..., min_length=1)
    status: LiveStrategyStatus
    baseline_id: str = Field(..., min_length=1)
    config_path: str = Field(..., min_length=1)
    config_hash: str = Field(..., min_length=1)
    execution_contract_hash: str = Field(..., min_length=1)
    asset_scope: str = Field(..., min_length=1)
    account_scopes: list[str] = Field(..., min_length=1)
    publish_schedule: str = Field(..., min_length=1)
    approval_record: dict = Field(..., min_length=1)


class LiveStrategyRegistry(_StrictRegistryModel):
    schema_version: str = Field(default=LIVE_STRATEGY_REGISTRY_SCHEMA_VERSION)
    strategies: list[LiveStrategyRecord] = Field(default_factory=list)


def default_live_strategy_registry_path(repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    return root / "backend" / "configs" / "live_strategy_registry.json"


def load_live_strategy_registry(path: Path | str | None = None) -> LiveStrategyRegistry:
    registry_path = Path(path) if path is not None else default_live_strategy_registry_path()
    if not registry_path.exists():
        return LiveStrategyRegistry()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid live strategy registry json: {registry_path}") from exc
    return LiveStrategyRegistry.model_validate(payload)


def find_live_strategy(registry: LiveStrategyRegistry, strategy_id: str) -> LiveStrategyRecord | None:
    target = str(strategy_id or "").strip()
    if not target:
        return None
    for record in registry.strategies:
        if record.strategy_id == target:
            return record
    return None


def validate_live_strategy_publish_gate(
    record: LiveStrategyRecord,
    *,
    baseline_id: str,
    config_hash: str,
    execution_contract_hash: str,
    account_scope: str | None = None,
) -> None:
    failure_reason_codes: list[str] = []
    if record.status != "live_approved":
        failure_reason_codes.append("strategy_not_live_approved")
    if str(baseline_id or "").strip() != record.baseline_id:
        failure_reason_codes.append("baseline_id_mismatch")
    if str(config_hash or "").strip() != record.config_hash:
        failure_reason_codes.append("config_hash_mismatch")
    if str(execution_contract_hash or "").strip() != record.execution_contract_hash:
        failure_reason_codes.append("execution_contract_hash_mismatch")
    requested_scope = str(account_scope or "").strip()
    if requested_scope and requested_scope not in set(record.account_scopes):
        failure_reason_codes.append("account_scope_not_allowed")
    if failure_reason_codes:
        raise LiveStrategyPublishBlocked(failure_reason_codes)


def load_and_validate_live_strategy_publish_gate(
    *,
    strategy_id: str,
    baseline_id: str,
    config_hash: str,
    execution_contract_hash: str,
    account_scope: str | None = None,
    registry_path: Path | str | None = None,
) -> LiveStrategyRecord:
    registry = load_live_strategy_registry(registry_path)
    record = find_live_strategy(registry, strategy_id)
    if record is None:
        raise LiveStrategyPublishBlocked(["strategy_not_registered"])
    validate_live_strategy_publish_gate(
        record,
        baseline_id=baseline_id,
        config_hash=config_hash,
        execution_contract_hash=execution_contract_hash,
        account_scope=account_scope,
    )
    return record


__all__ = [
    "LIVE_STRATEGY_REGISTRY_SCHEMA_VERSION",
    "LiveStrategyPublishBlocked",
    "LiveStrategyRecord",
    "LiveStrategyRegistry",
    "ValidationError",
    "default_live_strategy_registry_path",
    "find_live_strategy",
    "load_and_validate_live_strategy_publish_gate",
    "load_live_strategy_registry",
    "validate_live_strategy_publish_gate",
]
