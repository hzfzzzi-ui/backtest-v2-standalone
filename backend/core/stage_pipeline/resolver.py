from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .registry import ALLOWED_BUILTIN_MODULE_KINDS, get_builtin_module_factory


@dataclass(frozen=True, slots=True)
class ResolvedBuiltinModule:
    kind: str
    name: str
    module: Any


def _normalize_module_names(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str):
        value = str(raw).strip().lower()
        return (value,) if value else ()
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        values = [str(item).strip().lower() for item in raw]
        return tuple(value for value in values if value)
    return ()


def resolve_builtin_modules(config: Mapping[str, Any] | None = None) -> tuple[ResolvedBuiltinModule, ...]:
    raw = dict(config or {})
    resolved: list[ResolvedBuiltinModule] = []
    for kind in ALLOWED_BUILTIN_MODULE_KINDS:
        for name in _normalize_module_names(raw.get(kind)):
            factory = get_builtin_module_factory(kind, name)
            resolved.append(
                ResolvedBuiltinModule(
                    kind=kind,
                    name=name,
                    module=factory(),
                )
            )
    return tuple(resolved)
