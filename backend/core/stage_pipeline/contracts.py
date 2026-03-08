from __future__ import annotations

from dataclasses import dataclass, field
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
