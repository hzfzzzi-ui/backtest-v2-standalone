from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PACKAGE_SCHEMA_VERSION = "daily_position_adjustment_package@1"

PackageStatus = Literal["ready", "no_op", "blocked", "invalid"]
PublishMode = Literal["live", "dry_run", "audit_copy"]
ActionType = Literal["buy", "sell", "hold", "increase", "reduce", "rebalance"]
ActionStatus = Literal["proposed", "no_op", "blocked"]
ValidationStatus = Literal["passed", "blocked", "invalid"]
RiskSeverity = Literal["info", "warning", "blocker"]


class _StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PackageHeader(_StrictContractModel):
    schema_version: str = Field(..., min_length=1)
    package_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)
    generated_at: str = Field(..., min_length=1)

    @field_validator("schema_version")
    @classmethod
    def _schema_version_must_match(cls, value: str) -> str:
        if value != PACKAGE_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {PACKAGE_SCHEMA_VERSION}")
        return value


class PackageSource(_StrictContractModel):
    strategy_id: str = Field(..., min_length=1)
    strategy_run_id: str = Field(..., min_length=1)
    baseline_id: str = Field(..., min_length=1)
    config_hash: str = Field(..., min_length=1)
    execution_contract_hash: str = Field(..., min_length=1)
    publish_mode: PublishMode = "live"


class PackageClock(_StrictContractModel):
    signal_date: str = Field(..., min_length=1)
    execution_date: str = Field(..., min_length=1)
    signal_clock: str = Field(..., min_length=1)
    execution_clock: str = Field(..., min_length=1)
    reference_price_basis: str = Field(..., min_length=1)


class PackageScope(_StrictContractModel):
    market: str = Field(..., min_length=1)
    asset_scope: str = Field(..., min_length=1)
    asset_class: str = Field(..., min_length=1)
    account_scope: str = Field(..., min_length=1)
    currency: str = Field(..., min_length=1)
    symbol_namespace: str = Field(..., min_length=1)


class PackageInputs(_StrictContractModel):
    market_snapshot_id: str = Field(..., min_length=1)
    holdings_snapshot_id: str = Field(..., min_length=1)
    cash_snapshot_id: str = Field(..., min_length=1)
    reconcile_id: str = Field(..., min_length=1)


class TargetPosition(_StrictContractModel):
    symbol: str = Field(..., min_length=1)
    target_weight: float = Field(..., ge=0.0, le=1.0)
    target_qty: int | None = Field(default=None, ge=0)
    current_qty: int | None = Field(default=None, ge=0)
    reference_price: float | None = Field(default=None, ge=0)


class PackageAction(_StrictContractModel):
    action_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    market: str = Field(..., min_length=1)
    asset_class: str = Field(..., min_length=1)
    action_type: ActionType
    action_status: ActionStatus = "proposed"
    current_qty: int = Field(..., ge=0)
    target_qty: int = Field(..., ge=0)
    delta_qty: int
    suggested_qty: int = Field(..., ge=0)
    target_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    reference_price: float = Field(..., ge=0)
    reference_price_basis: str = Field(..., min_length=1)
    estimated_amount: float | None = Field(default=None, ge=0.0)
    reason_code: str = Field(..., min_length=1)
    reason_tags: list[str] = Field(...)
    reason_codes: list[str] = Field(default_factory=list)
    blocked: bool = Field(...)
    blocked_reason: str = ""
    expires_at: str = Field(..., min_length=1)


class RiskFlag(_StrictContractModel):
    code: str = Field(..., min_length=1)
    severity: RiskSeverity
    message: str = Field(..., min_length=1)


class PackageValidation(_StrictContractModel):
    status: ValidationStatus
    failure_reason_codes: list[str] = Field(default_factory=list)
    stale: bool = False
    drifted: bool = False


class DailyPositionAdjustmentPackage(_StrictContractModel):
    header: PackageHeader
    source: PackageSource
    clock: PackageClock
    scope: PackageScope
    inputs: PackageInputs
    package_status: PackageStatus
    target_positions: list[TargetPosition] = Field(...)
    action_sheet: list[PackageAction] = Field(...)
    risk_flags: list[RiskFlag] = Field(...)
    validation: PackageValidation

    @model_validator(mode="after")
    def _validate_status_contract(self) -> "DailyPositionAdjustmentPackage":
        if self.package_status == "ready" and not self.action_sheet:
            raise ValueError("ready package requires at least one action")
        if self.package_status in {"blocked", "invalid"} and not self.validation.failure_reason_codes:
            raise ValueError("blocked/invalid package requires failure_reason_codes")
        if self.validation.status == "passed" and self.validation.failure_reason_codes:
            raise ValueError("passed validation must not include failure_reason_codes")
        if self.validation.status in {"blocked", "invalid"} and not self.validation.failure_reason_codes:
            raise ValueError("blocked/invalid validation requires failure_reason_codes")
        return self


def validate_daily_position_adjustment_package(payload: dict) -> DailyPositionAdjustmentPackage:
    return DailyPositionAdjustmentPackage.model_validate(payload)


__all__ = [
    "PACKAGE_SCHEMA_VERSION",
    "DailyPositionAdjustmentPackage",
    "PackageAction",
    "PackageClock",
    "PackageHeader",
    "PackageInputs",
    "PackageScope",
    "PackageSource",
    "PackageValidation",
    "RiskFlag",
    "TargetPosition",
    "validate_daily_position_adjustment_package",
]
