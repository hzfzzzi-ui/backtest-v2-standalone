from __future__ import annotations

from pathlib import Path
from typing import Any

# Canonical artifact filenames
ARTIFACT_FILENAMES: dict[str, str] = {
    "perf": "perf.json",
    "nav": "nav.csv",
    "funnel": "funnel.csv",
    "reason_codes": "reason_codes.csv",
    "config": "config.json",
    "run_meta": "run_meta.json",
    "trades": "portfolio_trades.csv",
    "daily": "portfolio_daily.csv",
    "symbol_performance": "symbol_performance.csv",
}

# Legacy file aliases accepted by readers during migration window.
ARTIFACT_LEGACY_ALIASES: dict[str, list[str]] = {
    "reason_codes": ["reason_code_counts.csv"],
}

COUNTER_CANONICAL_FIELDS: tuple[str, ...] = (
    "raw_signal",
    "blocked",
    "orders",
    "skipped",
    "closed_trades",
)

COUNTER_LEGACY_ALIASES: dict[str, tuple[str, ...]] = {
    "raw_signal": ("raw_signal_count",),
    "blocked": ("blocked_count",),
    "orders": ("orders_count",),
    "skipped": ("skipped_count",),
    "closed_trades": ("closed_trades_count",),
}

MISSING_FIELD_KEYS: dict[str, str] = {
    "nav": "missing_nav_source",
    "funnel": "missing_funnel_source",
    "reason_codes": "missing_reason_code_source",
    "atr_trigger_counters": "missing_atr_trigger_counters",
    "symbol_performance": "missing_symbol_performance_source",
}


def candidate_artifact_names(key: str) -> list[str]:
    canonical = ARTIFACT_FILENAMES.get(key)
    out: list[str] = []
    if canonical:
        out.append(canonical)
    out.extend(ARTIFACT_LEGACY_ALIASES.get(key, []))
    return out


def resolve_artifact_path(root: Path, key: str, preferred_rel: str | None = None) -> tuple[Path, bool]:
    """Resolve an artifact path with legacy fallback.

    Returns (path, used_legacy_alias).
    """
    if preferred_rel:
        p = (root / str(preferred_rel)).resolve()
        if p.exists():
            return p, False
    names = candidate_artifact_names(key)
    for idx, name in enumerate(names):
        p = (root / name).resolve()
        if p.exists():
            return p, idx > 0
    canonical = ARTIFACT_FILENAMES.get(key, "")
    return (root / canonical).resolve(), False


def normalize_counters(raw: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    """Return canonical counter keys and legacy alias hit count."""
    src = dict(raw or {})
    out = dict(src)
    legacy_hits = 0
    for canonical, aliases in COUNTER_LEGACY_ALIASES.items():
        if out.get(canonical) is not None:
            continue
        for alias in aliases:
            if alias in src:
                out[canonical] = src.get(alias)
                legacy_hits += 1
                break
    return out, legacy_hits
