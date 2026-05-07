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
    "execution_contract": "execution_contract.json",
    "trades": "portfolio_trades.csv",
    "orders": "orders.csv",
    "daily": "portfolio_daily.csv",
    "candidate_signals": "candidate_signals.csv",
    "cash_blocked_buys_recent": "cash_blocked_buys_recent.csv",
    "alpha_funnel": "alpha_funnel.csv",
    "score_diagnostics": "score_diagnostics.csv",
    "symbol_performance": "symbol_performance.csv",
    "stage_summary": "stage_summary.json",
    "execution_lineage_ledger": "execution_lineage_ledger.csv",
    "regime_audit_summary": "regime_audit_summary.json",
    "regime_transition_debug": "regime_transition_debug.csv",
    "regime_audit_report": "regime_audit_report.md",
    "attribution_audit": "attribution_audit.json",
}

COUNTER_CANONICAL_FIELDS: tuple[str, ...] = (
    "raw_signal",
    "blocked",
    "orders",
    "skipped",
    "closed_trades",
)

MISSING_FIELD_KEYS: dict[str, str] = {
    "nav": "missing_nav_source",
    "funnel": "missing_funnel_source",
    "reason_codes": "missing_reason_code_source",
    "atr_trigger_counters": "missing_atr_trigger_counters",
    "symbol_performance": "missing_symbol_performance_source",
}


def resolve_artifact_path(root: Path, key: str, preferred_rel: str | None = None) -> Path:
    """Resolve an artifact path using the canonical filename contract."""
    if preferred_rel:
        p = (root / str(preferred_rel)).resolve()
        if p.exists():
            return p
    canonical = str(ARTIFACT_FILENAMES.get(key, "") or "").strip()
    return (root / canonical).resolve()


def normalize_counters(raw: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    """Return counters using the canonical field set only."""
    src = dict(raw or {})
    out = {key: src.get(key, 0) for key in COUNTER_CANONICAL_FIELDS}
    for key in COUNTER_CANONICAL_FIELDS:
        out[key] = out.get(key, 0)
    return out, 0
