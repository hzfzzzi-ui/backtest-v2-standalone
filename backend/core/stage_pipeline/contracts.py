from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, Mapping, Sequence


def _freeze_mapping(raw: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return MappingProxyType(dict(raw or {}))


def _freeze_counts(raw: Mapping[str, Any] | None = None) -> Mapping[str, int]:
    return MappingProxyType({str(key): int(value or 0) for key, value in dict(raw or {}).items()})


def _freeze_symbols(raw: Sequence[str] | None = None) -> tuple[str, ...]:
    return tuple(str(item) for item in list(raw or ()))


def _freeze_warnings(raw: Sequence[str] | None = None) -> tuple[str, ...]:
    return tuple(str(item) for item in list(raw or ()))


def _freeze_reason_codes(raw: Sequence[str] | None = None) -> tuple[str, ...]:
    return tuple(str(item) for item in list(raw or ()) if str(item))


def _freeze_mapping_sequence(raw: Sequence[Mapping[str, Any]] | None = None) -> tuple[Mapping[str, Any], ...]:
    return tuple(_freeze_mapping(item) for item in list(raw or ()))


def _freeze_pipeline_modules(raw: Mapping[str, Sequence[str]] | None = None) -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType(
        {
            str(key): tuple(str(item) for item in list(value or ()))
            for key, value in dict(raw or {}).items()
        }
    )


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_required_int(value: Any, *, field_name: str, minimum: int | None = None) -> int:
    out = _coerce_optional_int(value)
    if out is None:
        raise ValueError(f"{field_name} is required")
    if minimum is not None and out < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return int(out)


def _coerce_required_float(value: Any, *, field_name: str) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{field_name} is required")
    try:
        return float(value)
    except Exception as exc:
        raise ValueError(f"{field_name} must be a float") from exc


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if out != out:
        return None
    return float(out)


@dataclass(frozen=True, slots=True)
class ActionIntentAction:
    action_index: int
    symbol: str
    side: str
    priority: int
    reason_codes: tuple[str, ...] = ()
    suggested_size_value: float = 0.0
    suggested_size_unit: str = ""
    suggested_size_basis: str = ""
    source_intent_id: str = ""
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        symbol = str(self.symbol or "").strip().lower()
        side = str(self.side or "").strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        action_index = _coerce_required_int(self.action_index, field_name="action_index", minimum=1)
        priority = _coerce_required_int(self.priority, field_name="priority", minimum=1)
        suggested_size_value = _coerce_required_float(self.suggested_size_value, field_name="suggested_size_value")
        suggested_size_unit = str(self.suggested_size_unit or "").strip().lower()
        suggested_size_basis = str(self.suggested_size_basis or "").strip().lower()
        if not 0.0 <= suggested_size_value <= 1.0:
            raise ValueError("suggested_size_value must be within [0, 1]")
        if side == "BUY":
            if suggested_size_unit != "weight":
                raise ValueError("BUY suggested_size_unit must be weight")
            if suggested_size_basis != "subsystem_budget_relative":
                raise ValueError("BUY suggested_size_basis must be subsystem_budget_relative")
        else:
            if suggested_size_unit != "ratio":
                raise ValueError("SELL suggested_size_unit must be ratio")
            if suggested_size_basis != "sellable_qty_relative":
                raise ValueError("SELL suggested_size_basis must be sellable_qty_relative")
        object.__setattr__(self, "action_index", action_index)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "priority", priority)
        object.__setattr__(self, "reason_codes", _freeze_reason_codes(self.reason_codes))
        object.__setattr__(self, "suggested_size_value", float(suggested_size_value))
        object.__setattr__(self, "suggested_size_unit", suggested_size_unit)
        object.__setattr__(self, "suggested_size_basis", suggested_size_basis)
        object.__setattr__(self, "source_intent_id", str(self.source_intent_id or "").strip())
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "action_index": int(self.action_index),
            "symbol": self.symbol,
            "side": self.side,
            "priority": int(self.priority),
            "reason_codes": list(self.reason_codes),
            "suggested_size_value": float(self.suggested_size_value),
            "suggested_size_unit": self.suggested_size_unit,
            "suggested_size_basis": self.suggested_size_basis,
            "source_intent_id": self.source_intent_id,
            "notes": dict(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ActionIntentContract:
    contract_version: str = "action_intent_v1"
    as_of_date: date | None = None
    owner_system: str = ""
    actions: tuple[ActionIntentAction, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_version", str(self.contract_version or "action_intent_v1"))
        owner_system = str(self.owner_system or "").strip()
        if not owner_system:
            raise ValueError("owner_system is required")
        frozen_actions: list[ActionIntentAction] = []
        seen_symbol_sides: set[tuple[str, str]] = set()
        seen_symbols: dict[str, str] = {}
        last_sort_key: tuple[int, int] | None = None
        for item in list(self.actions or ()):
            action = item if isinstance(item, ActionIntentAction) else ActionIntentAction(**dict(item or {}))
            sort_key = (int(action.priority), int(action.action_index))
            if last_sort_key is not None and sort_key < last_sort_key:
                raise ValueError("actions must be pre-sorted by priority then action_index")
            last_sort_key = sort_key
            same_side_key = (action.symbol, action.side)
            if same_side_key in seen_symbol_sides:
                raise ValueError("duplicate action for same symbol/side is not allowed")
            prior_side = seen_symbols.get(action.symbol)
            if prior_side and prior_side != action.side:
                raise ValueError("same symbol cannot include both BUY and SELL in one action_intent_v1")
            seen_symbol_sides.add(same_side_key)
            seen_symbols[action.symbol] = action.side
            frozen_actions.append(action)
        object.__setattr__(self, "owner_system", owner_system)
        object.__setattr__(self, "actions", tuple(frozen_actions))

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "as_of_date": self.as_of_date.isoformat() if isinstance(self.as_of_date, date) else None,
            "owner_system": self.owner_system,
            "actions": [item.to_payload() for item in self.actions],
        }


@dataclass(frozen=True, slots=True)
class SubsystemBudgetContract:
    contract_version: str = "subsystem_budget_v1"
    as_of_date: date | None = None
    owner_system: str = ""
    budget_value: float = 0.0
    budget_unit: str = "weight"
    budget_basis: str = "portfolio_relative"
    strategic_floor_cap: float | None = None
    tactical_overlay_cap: float | None = None
    deployment_pace: str = ""
    allow_new_risk: bool = True
    force_reduce_only: bool = False
    hard_block_flags: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_version", str(self.contract_version or "subsystem_budget_v1"))
        owner_system = str(self.owner_system or "").strip()
        if not owner_system:
            raise ValueError("owner_system is required")
        budget_value = _coerce_required_float(self.budget_value, field_name="budget_value")
        if not 0.0 <= budget_value <= 1.0:
            raise ValueError("budget_value must be within [0, 1]")
        budget_unit = str(self.budget_unit or "").strip().lower()
        budget_basis = str(self.budget_basis or "").strip().lower()
        if budget_unit != "weight":
            raise ValueError("budget_unit must be weight")
        if budget_basis != "portfolio_relative":
            raise ValueError("budget_basis must be portfolio_relative")
        strategic_floor_cap = _coerce_optional_float(self.strategic_floor_cap)
        tactical_overlay_cap = _coerce_optional_float(self.tactical_overlay_cap)
        deployment_pace = str(self.deployment_pace or "").strip().lower()
        if strategic_floor_cap is not None and not 0.0 <= strategic_floor_cap <= 1.0:
            raise ValueError("strategic_floor_cap must be within [0, 1]")
        if tactical_overlay_cap is not None and not 0.0 <= tactical_overlay_cap <= 1.0:
            raise ValueError("tactical_overlay_cap must be within [0, 1]")
        object.__setattr__(self, "owner_system", owner_system)
        object.__setattr__(self, "budget_value", float(budget_value))
        object.__setattr__(self, "budget_unit", budget_unit)
        object.__setattr__(self, "budget_basis", budget_basis)
        object.__setattr__(self, "strategic_floor_cap", strategic_floor_cap)
        object.__setattr__(self, "tactical_overlay_cap", tactical_overlay_cap)
        object.__setattr__(self, "deployment_pace", deployment_pace)
        object.__setattr__(self, "allow_new_risk", _coerce_bool(self.allow_new_risk))
        object.__setattr__(self, "force_reduce_only", _coerce_bool(self.force_reduce_only))
        object.__setattr__(self, "hard_block_flags", _freeze_reason_codes(self.hard_block_flags))
        object.__setattr__(self, "reason_codes", _freeze_reason_codes(self.reason_codes))
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "as_of_date": self.as_of_date.isoformat() if isinstance(self.as_of_date, date) else None,
            "owner_system": self.owner_system,
            "budget_value": float(self.budget_value),
            "budget_unit": self.budget_unit,
            "budget_basis": self.budget_basis,
            "strategic_floor_cap": self.strategic_floor_cap,
            "tactical_overlay_cap": self.tactical_overlay_cap,
            "deployment_pace": self.deployment_pace,
            "allow_new_risk": bool(self.allow_new_risk),
            "force_reduce_only": bool(self.force_reduce_only),
            "hard_block_flags": list(self.hard_block_flags),
            "reason_codes": list(self.reason_codes),
            "notes": dict(self.notes),
        }


@dataclass(frozen=True, slots=True)
class RiskOverrideContract:
    contract_version: str = "risk_override_v1"
    as_of_date: date | None = None
    override_owner: str = "global_portfolio_governor"
    scope: str = ""
    action: str = ""
    target_symbol: str = ""
    reason_codes: tuple[str, ...] = ()
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_version", str(self.contract_version or "risk_override_v1"))
        override_owner = str(self.override_owner or "").strip()
        scope = str(self.scope or "").strip().lower()
        action = str(self.action or "").strip().upper()
        target_symbol = str(self.target_symbol or "").strip().lower()
        if not override_owner:
            raise ValueError("override_owner is required")
        if scope not in {"portfolio", "symbol"}:
            raise ValueError("scope must be portfolio or symbol")
        if action not in {"FORCE_EXIT", "REDUCE_ONLY"}:
            raise ValueError("action must be FORCE_EXIT or REDUCE_ONLY")
        if scope == "symbol" and not target_symbol:
            raise ValueError("target_symbol is required for symbol scope")
        if scope == "portfolio":
            target_symbol = ""
        object.__setattr__(self, "override_owner", override_owner)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "target_symbol", target_symbol)
        object.__setattr__(self, "reason_codes", _freeze_reason_codes(self.reason_codes))
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "as_of_date": self.as_of_date.isoformat() if isinstance(self.as_of_date, date) else None,
            "override_owner": self.override_owner,
            "scope": self.scope,
            "action": self.action,
            "target_symbol": self.target_symbol,
            "reason_codes": list(self.reason_codes),
            "notes": dict(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ExecutionAuditRecord:
    action_index: int
    owner_system: str
    symbol: str
    side: str
    requested_size_value: float
    requested_size_unit: str
    requested_size_basis: str
    outcome: str
    reason_codes: tuple[str, ...] = ()
    blocked_by_override: bool = False
    clipped_to_sellable: bool = False
    rounded_to_lot: bool = False
    skipped_for_priority: bool = False
    final_qty: int | None = None
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        action_index = _coerce_required_int(self.action_index, field_name="action_index", minimum=1)
        owner_system = str(self.owner_system or "").strip()
        symbol = str(self.symbol or "").strip().lower()
        side = str(self.side or "").strip().upper()
        outcome = str(self.outcome or "").strip().lower()
        requested_size_value = _coerce_required_float(self.requested_size_value, field_name="requested_size_value")
        if not owner_system:
            raise ValueError("owner_system is required")
        if not symbol:
            raise ValueError("symbol is required")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if outcome not in {"accepted", "blocked", "overridden", "clipped", "rounded", "skipped", "rejected"}:
            raise ValueError("outcome is invalid")
        object.__setattr__(self, "action_index", action_index)
        object.__setattr__(self, "owner_system", owner_system)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "requested_size_value", float(requested_size_value))
        object.__setattr__(self, "requested_size_unit", str(self.requested_size_unit or "").strip().lower())
        object.__setattr__(self, "requested_size_basis", str(self.requested_size_basis or "").strip().lower())
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "reason_codes", _freeze_reason_codes(self.reason_codes))
        object.__setattr__(self, "blocked_by_override", _coerce_bool(self.blocked_by_override))
        object.__setattr__(self, "clipped_to_sellable", _coerce_bool(self.clipped_to_sellable))
        object.__setattr__(self, "rounded_to_lot", _coerce_bool(self.rounded_to_lot))
        object.__setattr__(self, "skipped_for_priority", _coerce_bool(self.skipped_for_priority))
        object.__setattr__(self, "final_qty", _coerce_optional_int(self.final_qty))
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "action_index": int(self.action_index),
            "owner_system": self.owner_system,
            "symbol": self.symbol,
            "side": self.side,
            "requested_size_value": float(self.requested_size_value),
            "requested_size_unit": self.requested_size_unit,
            "requested_size_basis": self.requested_size_basis,
            "outcome": self.outcome,
            "reason_codes": list(self.reason_codes),
            "blocked_by_override": bool(self.blocked_by_override),
            "clipped_to_sellable": bool(self.clipped_to_sellable),
            "rounded_to_lot": bool(self.rounded_to_lot),
            "skipped_for_priority": bool(self.skipped_for_priority),
            "final_qty": self.final_qty,
            "notes": dict(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ExecutionAuditContract:
    contract_version: str = "execution_audit_v1"
    as_of_date: date | None = None
    records: tuple[ExecutionAuditRecord, ...] = ()
    summary: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_version", str(self.contract_version or "execution_audit_v1"))
        frozen_records: list[ExecutionAuditRecord] = []
        last_sort_key: tuple[int, str, str] | None = None
        for item in list(self.records or ()):
            record = item if isinstance(item, ExecutionAuditRecord) else ExecutionAuditRecord(**dict(item or {}))
            sort_key = (int(record.action_index), record.symbol, record.outcome)
            if last_sort_key is not None and sort_key < last_sort_key:
                raise ValueError("records must be stable-sorted by action_index")
            last_sort_key = sort_key
            frozen_records.append(record)
        summary = dict(self.summary or {})
        if not summary:
            summary = {
                "accepted_count": sum(1 for item in frozen_records if item.outcome == "accepted"),
                "blocked_count": sum(1 for item in frozen_records if item.outcome == "blocked"),
                "overridden_count": sum(1 for item in frozen_records if item.outcome == "overridden"),
                "clipped_count": sum(1 for item in frozen_records if item.clipped_to_sellable),
                "rounded_count": sum(1 for item in frozen_records if item.rounded_to_lot),
                "skipped_count": sum(1 for item in frozen_records if item.skipped_for_priority),
            }
        object.__setattr__(self, "records", tuple(frozen_records))
        object.__setattr__(self, "summary", _freeze_counts(summary))

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "as_of_date": self.as_of_date.isoformat() if isinstance(self.as_of_date, date) else None,
            "records": [item.to_payload() for item in self.records],
            "summary": dict(self.summary),
        }


@dataclass(frozen=True, slots=True)
class RuntimePlan:
    runtime_config: Mapping[str, Any] = field(default_factory=dict)
    execution_overrides: Mapping[str, Any] = field(default_factory=dict)
    strategy_route: str = ""
    provider_ref: str = ""
    data_bundle_refs: Mapping[str, Any] = field(default_factory=dict)
    execution_assumptions: Mapping[str, Any] = field(default_factory=dict)
    risk_controls: Mapping[str, Any] = field(default_factory=dict)
    pipeline_modules: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_config", _freeze_mapping(self.runtime_config))
        object.__setattr__(self, "execution_overrides", _freeze_mapping(self.execution_overrides))
        object.__setattr__(self, "strategy_route", str(self.strategy_route or ""))
        object.__setattr__(self, "provider_ref", str(self.provider_ref or ""))
        object.__setattr__(self, "data_bundle_refs", _freeze_mapping(self.data_bundle_refs))
        object.__setattr__(self, "execution_assumptions", _freeze_mapping(self.execution_assumptions))
        object.__setattr__(self, "risk_controls", _freeze_mapping(self.risk_controls))
        object.__setattr__(self, "pipeline_modules", _freeze_pipeline_modules(self.pipeline_modules))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None = None) -> "RuntimePlan":
        data = dict(raw or {})
        return cls(
            runtime_config=data.get("runtime_config") if isinstance(data.get("runtime_config"), Mapping) else {},
            execution_overrides=data.get("execution_overrides") if isinstance(data.get("execution_overrides"), Mapping) else {},
            strategy_route=str(data.get("strategy_route") or ""),
            provider_ref=str(data.get("provider_ref") or ""),
            data_bundle_refs=data.get("data_bundle_refs") if isinstance(data.get("data_bundle_refs"), Mapping) else {},
            execution_assumptions=(
                data.get("execution_assumptions")
                if isinstance(data.get("execution_assumptions"), Mapping)
                else {}
            ),
            risk_controls=data.get("risk_controls") if isinstance(data.get("risk_controls"), Mapping) else {},
            pipeline_modules=data.get("pipeline_modules") if isinstance(data.get("pipeline_modules"), Mapping) else {},
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "runtime_config": dict(self.runtime_config),
            "execution_overrides": dict(self.execution_overrides),
            "strategy_route": self.strategy_route,
            "provider_ref": self.provider_ref,
            "data_bundle_refs": dict(self.data_bundle_refs),
            "execution_assumptions": dict(self.execution_assumptions),
            "risk_controls": dict(self.risk_controls),
            "pipeline_modules": {key: list(value) for key, value in self.pipeline_modules.items()},
        }


# 兼容摘要结构，仅供迁移期 payload / 调试链使用，不作为正式共享执行边界合同
@dataclass(frozen=True, slots=True)
class CandidateBoundaryItem:
    symbol: str
    owner_system: str = ""
    score: float | None = None
    reason_codes: tuple[str, ...] = ()
    priority: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", str(self.symbol or "").strip().lower())
        object.__setattr__(self, "owner_system", str(self.owner_system or "").strip())
        object.__setattr__(self, "score", None if self.score is None else float(self.score))
        object.__setattr__(self, "reason_codes", _freeze_reason_codes(self.reason_codes))
        object.__setattr__(self, "priority", _coerce_optional_int(self.priority))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None = None) -> "CandidateBoundaryItem":
        data = dict(raw or {})
        return cls(
            symbol=str(data.get("symbol") or ""),
            owner_system=str(data.get("owner_system") or ""),
            score=data.get("score"),
            reason_codes=tuple(str(item) for item in list(data.get("reason_codes") or ())),
            priority=data.get("priority"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "owner_system": self.owner_system,
            "score": self.score,
            "reason_codes": list(self.reason_codes),
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class CandidateBoundaryContract:
    contract_version: str = "candidate_boundary_v1"
    decision_date: date | None = None
    boundary_mode: str = ""
    selected_candidates: tuple[CandidateBoundaryItem, ...] = ()
    owner_system_slot_caps: Mapping[str, int] = field(default_factory=dict)
    owner_system_available_slots: Mapping[str, int] = field(default_factory=dict)
    owner_system_candidate_counts: Mapping[str, int] = field(default_factory=dict)
    owner_system_selected_counts: Mapping[str, int] = field(default_factory=dict)
    reject_reason_counts: Mapping[str, int] = field(default_factory=dict)
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_version", str(self.contract_version or "candidate_boundary_v1"))
        object.__setattr__(self, "boundary_mode", str(self.boundary_mode or "").strip())
        frozen_candidates = []
        for item in list(self.selected_candidates or ()):
            frozen_candidates.append(item if isinstance(item, CandidateBoundaryItem) else CandidateBoundaryItem.from_mapping(item))
        object.__setattr__(self, "selected_candidates", tuple(frozen_candidates))
        object.__setattr__(self, "owner_system_slot_caps", _freeze_counts(self.owner_system_slot_caps))
        object.__setattr__(self, "owner_system_available_slots", _freeze_counts(self.owner_system_available_slots))
        object.__setattr__(self, "owner_system_candidate_counts", _freeze_counts(self.owner_system_candidate_counts))
        object.__setattr__(self, "owner_system_selected_counts", _freeze_counts(self.owner_system_selected_counts))
        object.__setattr__(self, "reject_reason_counts", _freeze_counts(self.reject_reason_counts))
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "decision_date": self.decision_date.isoformat() if isinstance(self.decision_date, date) else None,
            "boundary_mode": self.boundary_mode,
            "selected_candidates": [item.to_payload() for item in self.selected_candidates],
            "owner_system_slot_caps": dict(self.owner_system_slot_caps),
            "owner_system_available_slots": dict(self.owner_system_available_slots),
            "owner_system_candidate_counts": dict(self.owner_system_candidate_counts),
            "owner_system_selected_counts": dict(self.owner_system_selected_counts),
            "reject_reason_counts": dict(self.reject_reason_counts),
            "notes": dict(self.notes),
        }


# 迁移期内部结构，仅供 stage 内部和 compat payload 使用
@dataclass(frozen=True, slots=True)
class CandidatePlanItem:
    symbol: str
    owner_system: str = ""
    score: float | None = None
    reason_codes: tuple[str, ...] = ()
    priority: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", str(self.symbol or "").strip().lower())
        object.__setattr__(self, "owner_system", str(self.owner_system or "").strip())
        object.__setattr__(self, "score", None if self.score is None else float(self.score))
        object.__setattr__(self, "reason_codes", _freeze_reason_codes(self.reason_codes))
        object.__setattr__(self, "priority", _coerce_optional_int(self.priority))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None = None) -> "CandidatePlanItem":
        data = dict(raw or {})
        return cls(
            symbol=str(data.get("symbol") or ""),
            owner_system=str(data.get("owner_system") or ""),
            score=data.get("score"),
            reason_codes=tuple(str(item) for item in list(data.get("reason_codes") or ())),
            priority=data.get("priority"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "owner_system": self.owner_system,
            "score": self.score,
            "reason_codes": list(self.reason_codes),
            "priority": self.priority,
        }


# 迁移期内部结构，仅供 stage 内部和 compat payload 使用
@dataclass(frozen=True, slots=True)
class CandidatePlanContract:
    contract_version: str = "candidate_plan_v1"
    decision_date: date | None = None
    plan_mode: str = ""
    planned_candidates: tuple[CandidatePlanItem, ...] = ()
    planned_rotation_sell_symbols: tuple[str, ...] = ()
    reject_reason_counts: Mapping[str, int] = field(default_factory=dict)
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_version", str(self.contract_version or "candidate_plan_v1"))
        object.__setattr__(self, "plan_mode", str(self.plan_mode or "").strip())
        frozen_candidates = []
        for item in list(self.planned_candidates or ()):
            frozen_candidates.append(item if isinstance(item, CandidatePlanItem) else CandidatePlanItem.from_mapping(item))
        object.__setattr__(self, "planned_candidates", tuple(frozen_candidates))
        object.__setattr__(self, "planned_rotation_sell_symbols", _freeze_symbols(self.planned_rotation_sell_symbols))
        object.__setattr__(self, "reject_reason_counts", _freeze_counts(self.reject_reason_counts))
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "decision_date": self.decision_date.isoformat() if isinstance(self.decision_date, date) else None,
            "plan_mode": self.plan_mode,
            "planned_candidates": [item.to_payload() for item in self.planned_candidates],
            "planned_rotation_sell_symbols": list(self.planned_rotation_sell_symbols),
            "reject_reason_counts": dict(self.reject_reason_counts),
            "notes": dict(self.notes),
        }


@dataclass(frozen=True, slots=True)
class TargetBookItem:
    symbol: str
    target_weight: float
    owner_system: str = ""
    reason_codes: tuple[str, ...] = ()
    priority: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", str(self.symbol or "").strip().lower())
        object.__setattr__(self, "target_weight", float(self.target_weight))
        object.__setattr__(self, "owner_system", str(self.owner_system or "").strip())
        object.__setattr__(self, "reason_codes", _freeze_reason_codes(self.reason_codes))
        object.__setattr__(self, "priority", _coerce_optional_int(self.priority))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None = None) -> "TargetBookItem":
        data = dict(raw or {})
        return cls(
            symbol=str(data.get("symbol") or ""),
            target_weight=float(data.get("target_weight") or 0.0),
            owner_system=str(data.get("owner_system") or ""),
            reason_codes=tuple(str(item) for item in list(data.get("reason_codes") or ())),
            priority=data.get("priority"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "target_weight": float(self.target_weight),
            "owner_system": self.owner_system,
            "reason_codes": list(self.reason_codes),
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class TargetBookContract:
    contract_version: str = "target_book_v1"
    decision_date: date | None = None
    execution_date: date | None = None
    execution_timing: str = "next_open"
    portfolio_constraints: Mapping[str, Any] = field(default_factory=dict)
    targets: tuple[TargetBookItem, ...] = ()
    blocking_result: Mapping[str, Any] = field(default_factory=dict)
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_version", str(self.contract_version or "target_book_v1"))
        object.__setattr__(self, "execution_timing", str(self.execution_timing or "next_open"))
        object.__setattr__(self, "portfolio_constraints", _freeze_mapping(self.portfolio_constraints))
        frozen_targets = []
        for item in list(self.targets or ()):
            frozen_targets.append(item if isinstance(item, TargetBookItem) else TargetBookItem.from_mapping(item))
        object.__setattr__(self, "targets", tuple(frozen_targets))
        object.__setattr__(self, "blocking_result", _freeze_mapping(self.blocking_result))
        object.__setattr__(self, "notes", _freeze_mapping(self.notes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "decision_date": self.decision_date.isoformat() if isinstance(self.decision_date, date) else None,
            "execution_date": self.execution_date.isoformat() if isinstance(self.execution_date, date) else None,
            "execution_timing": self.execution_timing,
            "portfolio_constraints": dict(self.portfolio_constraints),
            "targets": [item.to_payload() for item in self.targets],
            "blocking_result": dict(self.blocking_result),
            "notes": dict(self.notes),
        }


@dataclass(frozen=True, slots=True)
class AccountingSnapshot:
    cash: float
    dividend_receivable: float = 0.0
    positions: Mapping[str, Any] = field(default_factory=dict)
    filled_orders: tuple[Mapping[str, Any], ...] = ()
    trade_rows: tuple[Mapping[str, Any], ...] = ()
    daily_marks: Mapping[str, Any] = field(default_factory=dict)
    counters: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cash", float(self.cash))
        object.__setattr__(self, "dividend_receivable", float(self.dividend_receivable))
        object.__setattr__(self, "positions", _freeze_mapping(self.positions))
        object.__setattr__(self, "filled_orders", _freeze_mapping_sequence(self.filled_orders))
        object.__setattr__(self, "trade_rows", _freeze_mapping_sequence(self.trade_rows))
        object.__setattr__(self, "daily_marks", _freeze_mapping(self.daily_marks))
        object.__setattr__(self, "counters", _freeze_counts(self.counters))

    def to_payload(self) -> dict[str, Any]:
        return {
            "cash": float(self.cash),
            "dividend_receivable": float(self.dividend_receivable),
            "positions": dict(self.positions),
            "filled_orders": [dict(item) for item in self.filled_orders],
            "trade_rows": [dict(item) for item in self.trade_rows],
            "daily_marks": dict(self.daily_marks),
            "counters": dict(self.counters),
        }


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticsInput:
    route_id: str = ""
    candidates_count: int = 0
    selected_count: int = 0
    positions_before_sell: int = 0
    positions_after_sell: int = 0
    buy_slots: int = 0
    raw_buy_signal_count: int = 0
    raw_alpha_signal_count: int = 0
    composed_buy_signal_count: int = 0
    composed_sell_signal_count: int = 0
    raw_buy_candidate_count: int = 0
    raw_after_held_filter_count: int = 0
    raw_after_slot_filter_count: int | None = None
    raw_after_cash_lot_count: int | None = None
    benchmark_regime_on: bool = False
    strong_risk_on: bool = False
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    debug_plan: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", str(self.route_id or ""))
        object.__setattr__(self, "candidates_count", int(self.candidates_count))
        object.__setattr__(self, "selected_count", int(self.selected_count))
        object.__setattr__(self, "positions_before_sell", int(self.positions_before_sell))
        object.__setattr__(self, "positions_after_sell", int(self.positions_after_sell))
        object.__setattr__(self, "buy_slots", int(self.buy_slots))
        object.__setattr__(self, "raw_buy_signal_count", int(self.raw_buy_signal_count))
        object.__setattr__(self, "raw_alpha_signal_count", int(self.raw_alpha_signal_count))
        object.__setattr__(self, "composed_buy_signal_count", int(self.composed_buy_signal_count))
        object.__setattr__(self, "composed_sell_signal_count", int(self.composed_sell_signal_count))
        object.__setattr__(self, "raw_buy_candidate_count", int(self.raw_buy_candidate_count))
        object.__setattr__(self, "raw_after_held_filter_count", int(self.raw_after_held_filter_count))
        object.__setattr__(self, "raw_after_slot_filter_count", _coerce_optional_int(self.raw_after_slot_filter_count))
        object.__setattr__(self, "raw_after_cash_lot_count", _coerce_optional_int(self.raw_after_cash_lot_count))
        object.__setattr__(self, "benchmark_regime_on", _coerce_bool(self.benchmark_regime_on))
        object.__setattr__(self, "strong_risk_on", _coerce_bool(self.strong_risk_on))
        object.__setattr__(self, "diagnostics", _freeze_mapping(self.diagnostics))
        object.__setattr__(self, "debug_plan", _freeze_mapping(self.debug_plan))

    def to_payload(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "candidates_count": int(self.candidates_count),
            "selected_count": int(self.selected_count),
            "positions_before_sell": int(self.positions_before_sell),
            "positions_after_sell": int(self.positions_after_sell),
            "buy_slots": int(self.buy_slots),
            "raw_buy_signal_count": int(self.raw_buy_signal_count),
            "raw_alpha_signal_count": int(self.raw_alpha_signal_count),
            "composed_buy_signal_count": int(self.composed_buy_signal_count),
            "composed_sell_signal_count": int(self.composed_sell_signal_count),
            "raw_buy_candidate_count": int(self.raw_buy_candidate_count),
            "raw_after_held_filter_count": int(self.raw_after_held_filter_count),
            "raw_after_slot_filter_count": self.raw_after_slot_filter_count,
            "raw_after_cash_lot_count": self.raw_after_cash_lot_count,
            "benchmark_regime_on": bool(self.benchmark_regime_on),
            "strong_risk_on": bool(self.strong_risk_on),
            "diagnostics": dict(self.diagnostics),
            "debug_plan": dict(self.debug_plan),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None = None) -> "RuntimeDiagnosticsInput":
        data = dict(raw or {})
        return cls(
            route_id=str(data.get("route_id") or ""),
            candidates_count=int(data.get("candidates_count") or 0),
            selected_count=int(data.get("selected_count") or 0),
            positions_before_sell=int(data.get("positions_before_sell") or 0),
            positions_after_sell=int(data.get("positions_after_sell") or 0),
            buy_slots=int(data.get("buy_slots") or 0),
            raw_buy_signal_count=int(data.get("raw_buy_signal_count") or 0),
            raw_alpha_signal_count=int(data.get("raw_alpha_signal_count") or 0),
            composed_buy_signal_count=int(data.get("composed_buy_signal_count") or 0),
            composed_sell_signal_count=int(data.get("composed_sell_signal_count") or 0),
            raw_buy_candidate_count=int(data.get("raw_buy_candidate_count") or 0),
            raw_after_held_filter_count=int(data.get("raw_after_held_filter_count") or 0),
            raw_after_slot_filter_count=data.get("raw_after_slot_filter_count"),
            raw_after_cash_lot_count=data.get("raw_after_cash_lot_count"),
            benchmark_regime_on=bool(data.get("benchmark_regime_on", False)),
            strong_risk_on=bool(data.get("strong_risk_on", False)),
            diagnostics=data.get("diagnostics") if isinstance(data.get("diagnostics"), Mapping) else {},
            debug_plan=data.get("debug_plan") if isinstance(data.get("debug_plan"), Mapping) else {},
        )

    @classmethod
    def from_json(cls, raw: str | None) -> "RuntimeDiagnosticsInput | None":
        text = str(raw or "").strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        if not isinstance(payload, Mapping):
            return None
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class StageInputs:
    candidate_symbols: tuple[str, ...] = ()
    holding_symbols: tuple[str, ...] = ()
    buy_symbols: tuple[str, ...] = ()
    sell_symbols: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)
    reason_counts: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_symbols", _freeze_symbols(self.candidate_symbols))
        object.__setattr__(self, "holding_symbols", _freeze_symbols(self.holding_symbols))
        object.__setattr__(self, "buy_symbols", _freeze_symbols(self.buy_symbols))
        object.__setattr__(self, "sell_symbols", _freeze_symbols(self.sell_symbols))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))
        object.__setattr__(self, "reason_counts", _freeze_counts(self.reason_counts))
        object.__setattr__(self, "warnings", _freeze_warnings(self.warnings))


@dataclass(frozen=True, slots=True)
class StageOutputs:
    stage_key: str
    enabled: bool = True
    candidate_symbols: tuple[str, ...] = ()
    holding_symbols: tuple[str, ...] = ()
    buy_symbols: tuple[str, ...] = ()
    sell_symbols: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)
    reason_counts: Mapping[str, int] = field(default_factory=dict)
    summary_fragment: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_key", str(self.stage_key))
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "candidate_symbols", _freeze_symbols(self.candidate_symbols))
        object.__setattr__(self, "holding_symbols", _freeze_symbols(self.holding_symbols))
        object.__setattr__(self, "buy_symbols", _freeze_symbols(self.buy_symbols))
        object.__setattr__(self, "sell_symbols", _freeze_symbols(self.sell_symbols))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))
        object.__setattr__(self, "reason_counts", _freeze_counts(self.reason_counts))
        object.__setattr__(self, "summary_fragment", _freeze_mapping(self.summary_fragment))
        object.__setattr__(self, "warnings", _freeze_warnings(self.warnings))

    @classmethod
    def neutral(
        cls,
        stage_key: str,
        stage_inputs: StageInputs | None = None,
        *,
        summary_fragment: Mapping[str, Any] | None = None,
        warnings: Sequence[str] | None = None,
    ) -> "StageOutputs":
        stage_inputs = stage_inputs or StageInputs()
        fragment = {"mode": "neutral"}
        fragment.update(dict(summary_fragment or {}))
        return cls(
            stage_key=stage_key,
            enabled=False,
            candidate_symbols=stage_inputs.candidate_symbols,
            holding_symbols=stage_inputs.holding_symbols,
            buy_symbols=stage_inputs.buy_symbols,
            sell_symbols=stage_inputs.sell_symbols,
            payload=stage_inputs.payload,
            reason_counts=stage_inputs.reason_counts,
            summary_fragment=fragment,
            warnings=tuple(stage_inputs.warnings) + _freeze_warnings(warnings),
        )
