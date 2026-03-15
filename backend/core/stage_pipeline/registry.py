from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType
from typing import Any, Callable, Mapping


ALLOWED_BUILTIN_MODULE_KINDS: tuple[str, ...] = (
    "candidate_filters",
    "rankers",
    "gates",
    "exits",
    "sizers",
    "reporters",
)

BuiltinModuleFactory = Callable[[], Any]

_REGISTRY: dict[str, dict[str, BuiltinModuleFactory]] = defaultdict(dict)


def _normalize_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized not in ALLOWED_BUILTIN_MODULE_KINDS:
        raise ValueError(f"unsupported built-in module kind: {kind}")
    return normalized


def _normalize_name(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if not normalized:
        raise ValueError("built-in module name is required")
    return normalized


def register_builtin_module(kind: str, name: str, factory: BuiltinModuleFactory) -> None:
    normalized_kind = _normalize_kind(kind)
    normalized_name = _normalize_name(name)
    _REGISTRY[normalized_kind][normalized_name] = factory


def get_builtin_module_factory(kind: str, name: str) -> BuiltinModuleFactory:
    normalized_kind = _normalize_kind(kind)
    normalized_name = _normalize_name(name)
    try:
        return _REGISTRY[normalized_kind][normalized_name]
    except KeyError as exc:
        raise KeyError(f"built-in module not registered: {normalized_kind}/{normalized_name}") from exc


def registered_builtin_modules(kind: str | None = None) -> Mapping[str, Mapping[str, BuiltinModuleFactory]]:
    if kind is None:
        return MappingProxyType(
            {
                key: MappingProxyType(dict(value))
                for key, value in _REGISTRY.items()
            }
        )
    normalized_kind = _normalize_kind(kind)
    return MappingProxyType({normalized_kind: MappingProxyType(dict(_REGISTRY.get(normalized_kind, {})))})


def reset_builtin_module_registry() -> None:
    _REGISTRY.clear()
