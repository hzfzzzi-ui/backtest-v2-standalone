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
    "trades_alias": "trades.csv",
    "orders": "orders.csv",
    "daily": "portfolio_daily.csv",
    "candidate_signals": "candidate_signals.csv",
    "alpha_funnel": "alpha_funnel.csv",
    "score_diagnostics": "score_diagnostics.csv",
    "symbol_performance": "symbol_performance.csv",
    "stage_summary": "stage_summary.json",
}

ARTIFACT_LEGACY_ALIASES: dict[str, tuple[str, ...]] = {
    "reason_codes": ("reason_code_counts.csv",),
    "trades": ("trades.csv",),
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
    canonical = str(ARTIFACT_FILENAMES.get(key, "") or "").strip()
    names: list[str] = []
    if canonical:
        names.append(canonical)
    for alias in ARTIFACT_LEGACY_ALIASES.get(key, ()):
        alias_name = str(alias or "").strip()
        if alias_name and alias_name not in names:
            names.append(alias_name)
    return names


def resolve_artifact_path(root: Path, key: str, preferred_rel: str | None = None) -> Path:
    """Resolve an artifact path using the canonical filename contract."""
    if preferred_rel:
        p = (root / str(preferred_rel)).resolve()
        if p.exists():
            return p
    for candidate in candidate_artifact_names(key):
        p = (root / candidate).resolve()
        if p.exists():
            return p
    canonical = str(ARTIFACT_FILENAMES.get(key, "") or "").strip()
    return (root / canonical).resolve()


def normalize_counters(raw: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    """Return counters using the canonical field set and report legacy alias hits."""
    src = dict(raw or {})
    out = dict(src)
    hits = 0
    for aliases in COUNTER_LEGACY_ALIASES.values():
        for alias in aliases:
            out.pop(alias, None)
    for key, aliases in COUNTER_LEGACY_ALIASES.items():
        if key in src:
            continue
        for alias in aliases:
            if alias in src:
                out[key] = src.get(alias)
                hits += 1
                break
    for key in COUNTER_CANONICAL_FIELDS:
        out.setdefault(key, 0)
    return out, hits
