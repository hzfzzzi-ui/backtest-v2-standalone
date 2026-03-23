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


def _append_reason(reason: str, suffix: str) -> str:
    text = str(reason or "").strip()
    if not text:
        return suffix
    token = f"+{suffix}"
    if text.endswith(token) or token in text:
        return text
    return f"{text}{token}"


def _normalize_refresh_membership(refresh_membership: pd.DataFrame | None) -> pd.DataFrame:
    if refresh_membership is None or refresh_membership.empty:
        return pd.DataFrame(
            columns=["index_code", "refresh_date", "symbol", "constituent_start_date", "snapshot_trade_date"]
        )
    out = refresh_membership.copy()
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.lower().str.strip()
    if "refresh_date" in out.columns:
        out["refresh_date"] = pd.to_datetime(out["refresh_date"], errors="coerce").dt.normalize()
    if "constituent_start_date" in out.columns:
        out["constituent_start_date"] = pd.to_datetime(out["constituent_start_date"], errors="coerce").dt.normalize()
    if "snapshot_trade_date" in out.columns:
        out["snapshot_trade_date"] = pd.to_datetime(out["snapshot_trade_date"], errors="coerce").dt.normalize()
    for column in ("source", "event_type"):
        if column in out.columns:
            out[column] = out[column].astype(str).str.strip()
    out = out.dropna(subset=["symbol", "refresh_date"]).reset_index(drop=True)
    return out


def audit_membership_history(
    membership_history: pd.DataFrame,
    *,
    refresh_membership: pd.DataFrame | None = None,
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
            "refresh_sidecar_present": False,
            "refresh_membership_rows": 0,
            "refresh_event_count": 0,
            "zero_diff_refresh_event_count": 0,
            "covered_refresh_event_count": 0,
            "provider_floor_date": None,
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
    refresh_history = _normalize_refresh_membership(refresh_membership)

    refresh_membership_rows = int(len(refresh_history.index))
    refresh_event_dates = (
        sorted({ts.date().isoformat() for ts in refresh_history["refresh_date"].dropna().tolist()})
        if "refresh_date" in refresh_history.columns
        else []
    )
    refresh_event_count = int(len(refresh_event_dates))
    boundary_dates = {ts.date().isoformat() for ts in history["start_date"].dropna().tolist()}
    boundary_dates.update({ts.date().isoformat() for ts in history["end_date"].dropna().tolist() if pd.notna(ts)})
    zero_diff_refresh_event_count = int(sum(1 for item in refresh_event_dates if item not in boundary_dates))
    non_static_refresh = refresh_history
    if "source" in refresh_history.columns:
        non_static_refresh = refresh_history.loc[
            ~refresh_history["source"].astype(str).str.lower().str.contains("static", na=False)
        ].reset_index(drop=True)
    provider_dates: list[pd.Timestamp] = []
    if not non_static_refresh.empty:
        if "snapshot_trade_date" in non_static_refresh.columns:
            provider_dates.extend(
                [ts for ts in non_static_refresh["snapshot_trade_date"].dropna().tolist() if pd.notna(ts)]
            )
        if not provider_dates and "refresh_date" in non_static_refresh.columns:
            provider_dates.extend(
                [ts for ts in non_static_refresh["refresh_date"].dropna().tolist() if pd.notna(ts)]
            )
    provider_floor_ts = min(provider_dates) if provider_dates else None
    provider_floor_date = provider_floor_ts.date().isoformat() if provider_floor_ts is not None else None

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
        reason = _append_reason(reason, "missing_calendar_metadata")
    if provisional_calendar_lineage and quality == "pit_verified":
        quality = "approximate"
        reason = _append_reason(reason, "provisional_calendar_lineage")
    if require_calendar_metadata and refresh_history.empty and quality == "pit_verified":
        quality = "approximate"
        reason = _append_reason(reason, "missing_refresh_sidecar")

    covers_required_start: bool | None = None
    if required_start is not None:
        start_ts = pd.Timestamp(required_start)
        if provider_floor_ts is not None and start_ts < provider_floor_ts:
            reason = _append_reason(reason, "provider_floor_uncovered_start")
        covers_required_start = bool(
            (
                history["start_date"].le(start_ts)
                & (history["end_date"].isna() | history["end_date"].gt(start_ts))
            ).any()
        )
        if not covers_required_start and quality == "pit_verified":
            quality = "approximate"
            if provider_floor_ts is not None and start_ts < provider_floor_ts:
                reason = _append_reason(reason, "provider_floor_uncovered_start")
            else:
                reason = _append_reason(reason, "missing_start_coverage")

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
            reason = _append_reason(reason, "missing_end_coverage")

    covered_refresh_event_count = 0
    if refresh_event_dates:
        covered_start_ts = pd.Timestamp(required_start) if required_start is not None else None
        if provider_floor_ts is not None and (covered_start_ts is None or covered_start_ts < provider_floor_ts):
            covered_start_ts = provider_floor_ts
        covered_end_ts = pd.Timestamp(required_end) if required_end is not None else None
        covered_refresh_event_count = int(
            sum(
                1
                for refresh_date in refresh_event_dates
                if (covered_start_ts is None or pd.Timestamp(refresh_date) >= covered_start_ts)
                and (covered_end_ts is None or pd.Timestamp(refresh_date) <= covered_end_ts)
            )
        )

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
        "refresh_sidecar_present": bool(not refresh_history.empty),
        "refresh_membership_rows": refresh_membership_rows,
        "refresh_event_count": refresh_event_count,
        "zero_diff_refresh_event_count": zero_diff_refresh_event_count,
        "covered_refresh_event_count": covered_refresh_event_count,
        "provider_floor_date": provider_floor_date,
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
