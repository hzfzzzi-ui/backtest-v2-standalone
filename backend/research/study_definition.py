from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_REQUIRED_OUTPUTS = {"machine_bundle", "human_bundle", "baseline_append"}


class StudyValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StudyPatch:
    path: str
    value: Any

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "value": self.value}


@dataclass(frozen=True, slots=True)
class StudyVariant:
    name: str
    description: str = ""
    request_overrides: dict[str, Any] = field(default_factory=dict)
    config_patches: tuple[StudyPatch, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "request_overrides": dict(self.request_overrides),
            "config_patches": [patch.as_dict() for patch in self.config_patches],
        }


@dataclass(frozen=True, slots=True)
class StudyWindow:
    key: str
    role: str
    start: str
    end: str
    periods: dict[str, tuple[str, str]] = field(default_factory=dict)
    request_overrides: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "role": self.role,
            "start": self.start,
            "end": self.end,
            "periods": {name: [bounds[0], bounds[1]] for name, bounds in self.periods.items()},
            "request_overrides": dict(self.request_overrides),
        }


@dataclass(frozen=True, slots=True)
class StudyDefinition:
    study_id: str
    title: str
    baseline_id: str
    hypothesis: str
    change_scope: dict[str, Any]
    variants: tuple[StudyVariant, ...]
    windows: tuple[StudyWindow, ...]
    hard_gates: dict[str, Any]
    required_outputs: tuple[str, ...]
    request_template: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "title": self.title,
            "baseline_id": self.baseline_id,
            "hypothesis": self.hypothesis,
            "change_scope": dict(self.change_scope),
            "variants": [variant.as_dict() for variant in self.variants],
            "windows": [window.as_dict() for window in self.windows],
            "hard_gates": dict(self.hard_gates),
            "required_outputs": list(self.required_outputs),
            "request_template": dict(self.request_template),
            "metadata": dict(self.metadata),
        }


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise StudyValidationError(f"study field '{key}' is required")
    return value


def _parse_patch(row: dict[str, Any], *, variant_name: str) -> StudyPatch:
    path = str(row.get("path") or "").strip()
    if not path:
        raise StudyValidationError(f"variant '{variant_name}' has an empty config patch path")
    return StudyPatch(path=path, value=row.get("value"))


def _parse_variant(row: dict[str, Any]) -> StudyVariant:
    if not isinstance(row, dict):
        raise StudyValidationError("study variants must be objects")
    name = _require_text(row, "name")
    patches_raw = row.get("config_patches")
    if patches_raw is None:
        patches: tuple[StudyPatch, ...] = ()
    elif isinstance(patches_raw, list):
        patches = tuple(_parse_patch(item if isinstance(item, dict) else {}, variant_name=name) for item in patches_raw)
    else:
        raise StudyValidationError(f"variant '{name}' has invalid config_patches")
    request_overrides = row.get("request_overrides")
    if request_overrides is not None and not isinstance(request_overrides, dict):
        raise StudyValidationError(f"variant '{name}' has invalid request_overrides")
    return StudyVariant(
        name=name,
        description=str(row.get("description") or "").strip(),
        request_overrides=dict(request_overrides or {}),
        config_patches=patches,
    )


def _parse_periods(row: dict[str, Any], *, window_key: str) -> dict[str, tuple[str, str]]:
    periods_raw = row.get("periods")
    if periods_raw is None:
        return {}
    if not isinstance(periods_raw, dict):
        raise StudyValidationError(f"window '{window_key}' has invalid periods")
    periods: dict[str, tuple[str, str]] = {}
    for name, bounds in periods_raw.items():
        if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            start, end = str(bounds[0] or "").strip(), str(bounds[1] or "").strip()
            if start and end:
                periods[str(name)] = (start, end)
                continue
        raise StudyValidationError(f"window '{window_key}' period '{name}' must be a [start, end] pair")
    return periods


def _parse_window(row: dict[str, Any]) -> StudyWindow:
    if not isinstance(row, dict):
        raise StudyValidationError("study windows must be objects")
    key = _require_text(row, "key")
    request_overrides = row.get("request_overrides")
    if request_overrides is not None and not isinstance(request_overrides, dict):
        raise StudyValidationError(f"window '{key}' has invalid request_overrides")
    return StudyWindow(
        key=key,
        role=str(row.get("role") or "main").strip() or "main",
        start=_require_text(row, "start"),
        end=_require_text(row, "end"),
        periods=_parse_periods(row, window_key=key),
        request_overrides=dict(request_overrides or {}),
    )


def validate_study_payload(payload: dict[str, Any]) -> StudyDefinition:
    if not isinstance(payload, dict):
        raise StudyValidationError("study definition must be a mapping")
    study_id = _require_text(payload, "study_id")
    title = _require_text(payload, "title")
    baseline_id = _require_text(payload, "baseline_id")
    hypothesis = _require_text(payload, "hypothesis")

    change_scope = payload.get("change_scope")
    if not isinstance(change_scope, dict):
        raise StudyValidationError("study field 'change_scope' must be an object")
    hard_gates = payload.get("hard_gates")
    if not isinstance(hard_gates, dict):
        raise StudyValidationError("study field 'hard_gates' must be an object")
    request_template = payload.get("request_template")
    if request_template is not None and not isinstance(request_template, dict):
        raise StudyValidationError("study field 'request_template' must be an object when provided")
    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise StudyValidationError("study field 'metadata' must be an object when provided")

    variants_raw = payload.get("variants")
    if not isinstance(variants_raw, list) or not variants_raw:
        raise StudyValidationError("study field 'variants' must be a non-empty list")
    variants = tuple(_parse_variant(item) for item in variants_raw)
    variant_names = [variant.name for variant in variants]
    if len(set(variant_names)) != len(variant_names):
        raise StudyValidationError("study variant names must be unique")

    windows_raw = payload.get("windows")
    if not isinstance(windows_raw, list) or not windows_raw:
        raise StudyValidationError("study field 'windows' must be a non-empty list")
    windows = tuple(_parse_window(item) for item in windows_raw)
    window_keys = [window.key for window in windows]
    if len(set(window_keys)) != len(window_keys):
        raise StudyValidationError("study window keys must be unique")

    required_outputs_raw = payload.get("required_outputs")
    if not isinstance(required_outputs_raw, list) or not required_outputs_raw:
        raise StudyValidationError("study field 'required_outputs' must be a non-empty list")
    required_outputs = tuple(str(item or "").strip() for item in required_outputs_raw if str(item or "").strip())
    if not required_outputs:
        raise StudyValidationError("study field 'required_outputs' cannot be empty")
    unknown_outputs = sorted(set(required_outputs) - _REQUIRED_OUTPUTS)
    if unknown_outputs:
        raise StudyValidationError(f"unsupported required_outputs: {', '.join(unknown_outputs)}")

    return StudyDefinition(
        study_id=study_id,
        title=title,
        baseline_id=baseline_id,
        hypothesis=hypothesis,
        change_scope=dict(change_scope),
        variants=variants,
        windows=windows,
        hard_gates=dict(hard_gates),
        required_outputs=required_outputs,
        request_template=dict(request_template or {}),
        metadata=dict(metadata or {}),
    )
