from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


_CALENDAR_METADATA_COLUMNS = (
    "rebalance_calendar_version",
    "rebalance_calendar_source",
    "rebalance_calendar_generated_at",
)
_PROVISIONAL_CALENDAR_KEYWORDS = ("approx", "proxy", "provisional", "monthly")


def _normalize_distinct_values(history: pd.DataFrame, column: str) -> list[str]:
    if column not in history.columns:
        return []
    values = {
        str(value).strip()
        for value in history[column].tolist()
        if str(value or "").strip()
    }
    return sorted(values)


def _pick_single(values: list[str], *, default: str | None = None) -> str | None:
    if not values:
        return default
    if len(values) == 1:
        return str(values[0])
    return "mixed"


def _calendar_metadata_complete(history: pd.DataFrame) -> bool:
    if history.empty:
        return False
    for column in _CALENDAR_METADATA_COLUMNS:
        if column not in history.columns:
            return False
        series = history[column].astype(str).str.strip()
        if bool((series == "").any()):
            return False
    return True


def _calendar_lineage_is_provisional(
    calendar_versions: list[str],
    calendar_sources: list[str],
) -> bool:
    combined = " ".join([*calendar_versions, *calendar_sources]).lower()
    return any(keyword in combined for keyword in _PROVISIONAL_CALENDAR_KEYWORDS)


def audit_membership_history(
    membership_history: pd.DataFrame,
    *,
    required_start: date | None = None,
    required_end: date | None = None,
    require_calendar_metadata: bool = False,
) -> dict[str, Any]:
    if membership_history is None or membership_history.empty:
        return {
            "membership_source": "unknown",
            "membership_sources": [],
            "membership_data_quality": "missing",
            "audit_status": "error",
            "audit_reason": "empty_membership_history",
            "membership_history_rows": 0,
            "distinct_symbols": 0,
            "distinct_start_dates": 0,
            "open_rows": 0,
            "closed_rows": 0,
            "min_start_date": None,
            "max_start_date": None,
            "min_end_date": None,
            "max_end_date": None,
            "covers_required_start": False if required_start is not None else None,
            "covers_required_end": False if required_end is not None else None,
            "event_types": [],
            "rebalance_calendar_version": None,
            "rebalance_calendar_source": None,
            "rebalance_calendar_generated_at": None,
            "calendar_metadata_complete": False,
            "calendar_metadata_required": bool(require_calendar_metadata),
        }

    history = membership_history.copy()
    history["symbol"] = history["symbol"].astype(str).str.lower()
    history["start_date"] = pd.to_datetime(history["start_date"], errors="coerce").dt.normalize()
    history["end_date"] = pd.to_datetime(history["end_date"], errors="coerce").dt.normalize()
    history = history.dropna(subset=["symbol", "start_date"]).reset_index(drop=True)

    row_count = int(len(history))
    distinct_symbols = int(history["symbol"].nunique())
    distinct_start_dates = int(history["start_date"].nunique())
    open_rows = int(history["end_date"].isna().sum())
    closed_rows = int(row_count - open_rows)
    min_start = history["start_date"].min()
    max_start = history["start_date"].max()
    min_end = history["end_date"].min()
    max_end = history["end_date"].max()

    sources = _normalize_distinct_values(history, "source")
    source_label = _pick_single(sources, default="unknown") or "unknown"
    event_types = _normalize_distinct_values(history, "event_type")
    calendar_versions = _normalize_distinct_values(history, "rebalance_calendar_version")
    calendar_sources = _normalize_distinct_values(history, "rebalance_calendar_source")
    calendar_generated_values = _normalize_distinct_values(history, "rebalance_calendar_generated_at")
    metadata_complete = _calendar_metadata_complete(history)
    provisional_calendar_lineage = _calendar_lineage_is_provisional(calendar_versions, calendar_sources)

    lower_sources = [item.lower() for item in sources]
    rows_eq_symbols = row_count == distinct_symbols
    single_start = distinct_start_dates <= 1
    all_open = open_rows == row_count
    shape_static = rows_eq_symbols and single_start and all_open
    has_pit_shape = distinct_start_dates > 1 or closed_rows > 0

    all_static_sources = bool(lower_sources) and all("static" in item for item in lower_sources)
    has_static_sources = any("static" in item for item in lower_sources)
    has_approx_sources = any(("monthly" in item) or ("approx" in item) for item in lower_sources)

    if all_static_sources or shape_static:
        quality = "static_fallback"
        reason = "source_static" if all_static_sources else "single_start_date_all_open"
    elif has_approx_sources:
        quality = "approximate"
        reason = "source_monthly_or_approximate"
    elif has_pit_shape:
        quality = "pit_verified"
        reason = "multi_start_dates_or_closed_rows"
    else:
        quality = "approximate"
        reason = "insufficient_history_shape"

    if has_static_sources and quality == "pit_verified":
        quality = "approximate"
        reason = f"{reason}+mixed_static_source"

    if require_calendar_metadata and not metadata_complete and quality == "pit_verified":
        quality = "approximate"
        reason = f"{reason}+missing_calendar_metadata"
    if provisional_calendar_lineage and quality == "pit_verified":
        quality = "approximate"
        reason = f"{reason}+provisional_calendar_lineage"

    covers_required_start: bool | None = None
    if required_start is not None:
        start_ts = pd.Timestamp(required_start)
        covers_required_start = bool(
            (
                history["start_date"].le(start_ts)
                & (history["end_date"].isna() | history["end_date"].gt(start_ts))
            ).any()
        )
        if not covers_required_start and quality == "pit_verified":
            quality = "approximate"
            reason = f"{reason}+missing_start_coverage"

    covers_required_end: bool | None = None
    if required_end is not None:
        end_ts = pd.Timestamp(required_end)
        covers_required_end = bool(
            (
                history["start_date"].le(end_ts)
                & (history["end_date"].isna() | history["end_date"].gt(end_ts))
            ).any()
        )
        if not covers_required_end and quality == "pit_verified":
            quality = "approximate"
            reason = f"{reason}+missing_end_coverage"

    if quality == "pit_verified":
        status = "ok"
    elif quality == "approximate":
        status = "warn"
    elif quality == "static_fallback":
        status = "blocked"
    else:
        status = "error"

    return {
        "membership_source": source_label,
        "membership_sources": sources,
        "membership_data_quality": quality,
        "audit_status": status,
        "audit_reason": reason,
        "membership_history_rows": row_count,
        "distinct_symbols": distinct_symbols,
        "distinct_start_dates": distinct_start_dates,
        "open_rows": open_rows,
        "closed_rows": closed_rows,
        "min_start_date": (str(min_start.date()) if pd.notna(min_start) else None),
        "max_start_date": (str(max_start.date()) if pd.notna(max_start) else None),
        "min_end_date": (str(min_end.date()) if pd.notna(min_end) else None),
        "max_end_date": (str(max_end.date()) if pd.notna(max_end) else None),
        "covers_required_start": covers_required_start,
        "covers_required_end": covers_required_end,
        "event_types": event_types,
        "rebalance_calendar_version": _pick_single(calendar_versions),
        "rebalance_calendar_source": _pick_single(calendar_sources),
        "rebalance_calendar_generated_at": _pick_single(calendar_generated_values),
        "calendar_metadata_complete": bool(metadata_complete),
        "calendar_metadata_required": bool(require_calendar_metadata),
        "calendar_lineage_provisional": bool(provisional_calendar_lineage),
    }


def should_block_static_fallback(
    *,
    universe_mode: str,
    membership_mode: str,
    membership_data_quality: str,
    allow_low_fidelity_history: bool,
) -> bool:
    if allow_low_fidelity_history:
        return False
    if str(membership_mode or "").strip().upper() != "PIT_DYNAMIC":
        return False
    if str(universe_mode or "").strip().upper() != "CSI1000":
        return False
    return str(membership_data_quality or "").strip().lower() == "static_fallback"
