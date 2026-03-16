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


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    as_of_date: date | None = None
    buy_candidates: tuple[str, ...] = ()
    sell_candidates: tuple[str, ...] = ()
    hold_overrides: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    ranking_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "buy_candidates", _freeze_symbols(self.buy_candidates))
        object.__setattr__(self, "sell_candidates", _freeze_symbols(self.sell_candidates))
        object.__setattr__(self, "hold_overrides", _freeze_symbols(self.hold_overrides))
        object.__setattr__(self, "risk_flags", _freeze_symbols(self.risk_flags))
        object.__setattr__(self, "ranking_payload", _freeze_mapping(self.ranking_payload))

    def to_payload(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date.isoformat() if isinstance(self.as_of_date, date) else None,
            "buy_candidates": list(self.buy_candidates),
            "sell_candidates": list(self.sell_candidates),
            "hold_overrides": list(self.hold_overrides),
            "risk_flags": list(self.risk_flags),
            "ranking_payload": dict(self.ranking_payload),
        }


@dataclass(frozen=True, slots=True)
class AccountingSnapshot:
    cash: float
    positions: Mapping[str, Any] = field(default_factory=dict)
    filled_orders: tuple[Mapping[str, Any], ...] = ()
    trade_rows: tuple[Mapping[str, Any], ...] = ()
    daily_marks: Mapping[str, Any] = field(default_factory=dict)
    counters: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cash", float(self.cash))
        object.__setattr__(self, "positions", _freeze_mapping(self.positions))
        object.__setattr__(self, "filled_orders", _freeze_mapping_sequence(self.filled_orders))
        object.__setattr__(self, "trade_rows", _freeze_mapping_sequence(self.trade_rows))
        object.__setattr__(self, "daily_marks", _freeze_mapping(self.daily_marks))
        object.__setattr__(self, "counters", _freeze_counts(self.counters))

    def to_payload(self) -> dict[str, Any]:
        return {
            "cash": float(self.cash),
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
