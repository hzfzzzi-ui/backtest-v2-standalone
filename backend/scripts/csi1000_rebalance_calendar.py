from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


ALLOWED_EVENT_TYPES = {"scheduled", "ad_hoc"}
DEFAULT_MAX_SCHEDULED_GAP_DAYS = 380
DEFAULT_CALENDAR_PATH = Path(__file__).resolve().parents[2] / "data_cache" / "csi1000_rebalance_calendar.csv"


@dataclass(frozen=True, slots=True)
class RebalanceCalendarEntry:
    effective_date: str
    event_type: str
    source: str
    version: str
    generated_at: str = ""
    source_url: str = ""
    source_note: str = ""

    @property
    def effective_date_value(self) -> date:
        return date.fromisoformat(self.effective_date)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _pick_single(values: list[str], *, default: str = "unknown") -> str:
    unique = sorted({str(value).strip() for value in values if str(value).strip()})
    if not unique:
        return default
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def load_rebalance_calendar(path: str | Path | None = None) -> list[RebalanceCalendarEntry]:
    calendar_path = Path(path).resolve() if path is not None else DEFAULT_CALENDAR_PATH.resolve()
    if not calendar_path.exists():
        raise FileNotFoundError(f"rebalance calendar not found: {calendar_path}")

    with calendar_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = {str(name or "").strip() for name in (reader.fieldnames or [])}
        required = {"effective_date", "event_type", "source", "version"}
        missing = sorted(required - fieldnames)
        if missing:
            raise RuntimeError(
                f"rebalance calendar missing required columns: {missing}; path={calendar_path}"
            )

        rows: list[RebalanceCalendarEntry] = []
        for raw in reader:
            effective_date = _normalize_text(raw.get("effective_date"))
            if not effective_date:
                continue
            event_type = _normalize_text(raw.get("event_type")).lower()
            source = _normalize_text(raw.get("source"))
            version = _normalize_text(raw.get("version"))
            if event_type not in ALLOWED_EVENT_TYPES:
                raise RuntimeError(
                    f"invalid event_type={event_type!r} at effective_date={effective_date}; "
                    f"allowed={sorted(ALLOWED_EVENT_TYPES)}"
                )
            if not source or not version:
                raise RuntimeError(
                    f"rebalance calendar row missing source/version at effective_date={effective_date}"
                )
            date.fromisoformat(effective_date)
            rows.append(
                RebalanceCalendarEntry(
                    effective_date=effective_date,
                    event_type=event_type,
                    source=source,
                    version=version,
                    generated_at=_normalize_text(raw.get("generated_at")),
                    source_url=_normalize_text(raw.get("source_url")),
                    source_note=_normalize_text(raw.get("source_note")),
                )
            )

    if not rows:
        raise RuntimeError(f"rebalance calendar has no valid rows: {calendar_path}")
    return rows


def summarize_rebalance_calendar(entries: list[RebalanceCalendarEntry]) -> dict[str, Any]:
    if not entries:
        return {
            "event_count": 0,
            "scheduled_event_count": 0,
            "ad_hoc_event_count": 0,
            "earliest_effective_date": None,
            "latest_effective_date": None,
            "version": "unknown",
            "source": "unknown",
        }
    scheduled_count = sum(1 for entry in entries if entry.event_type == "scheduled")
    ad_hoc_count = sum(1 for entry in entries if entry.event_type == "ad_hoc")
    dates = sorted(entry.effective_date for entry in entries)
    return {
        "event_count": len(entries),
        "scheduled_event_count": scheduled_count,
        "ad_hoc_event_count": ad_hoc_count,
        "earliest_effective_date": dates[0],
        "latest_effective_date": dates[-1],
        "version": _pick_single([entry.version for entry in entries]),
        "source": _pick_single([entry.source for entry in entries]),
        "generated_at": _pick_single([entry.generated_at for entry in entries], default=""),
    }


def validate_rebalance_calendar(
    entries: list[RebalanceCalendarEntry],
    *,
    required_start: date | None = None,
    required_end: date | None = None,
    max_scheduled_gap_days: int = DEFAULT_MAX_SCHEDULED_GAP_DAYS,
) -> dict[str, Any]:
    if not entries:
        raise RuntimeError("rebalance calendar is empty")

    ordered = [entry.effective_date_value for entry in entries]
    if ordered != sorted(ordered):
        raise RuntimeError("rebalance calendar effective_date values must be strictly ascending")

    duplicates = sorted({entry.effective_date for entry in entries if ordered.count(entry.effective_date_value) > 1})
    if duplicates:
        raise RuntimeError(f"rebalance calendar contains duplicate effective_date rows: {duplicates}")

    earliest = ordered[0]
    latest = ordered[-1]

    if required_start is not None and earliest > required_start:
        raise RuntimeError(
            f"rebalance calendar coverage gap: earliest_effective_date={earliest.isoformat()} "
            f"is later than required_start={required_start.isoformat()}"
        )

    if required_end is not None:
        eligible = [item for item in ordered if item <= required_end]
        if not eligible:
            raise RuntimeError(
                f"rebalance calendar coverage gap: no effective_date on or before required_end={required_end.isoformat()}"
            )

    scheduled_dates = [entry.effective_date_value for entry in entries if entry.event_type == "scheduled"]
    gap_warnings: list[dict[str, Any]] = []
    if scheduled_dates:
        for prev, nxt in zip(scheduled_dates, scheduled_dates[1:]):
            gap_days = (nxt - prev).days
            if gap_days > int(max_scheduled_gap_days):
                raise RuntimeError(
                    f"rebalance calendar scheduled gap too large: prev={prev.isoformat()} next={nxt.isoformat()} "
                    f"gap_days={gap_days} max_allowed={int(max_scheduled_gap_days)}"
                )
            gap_warnings.append({"prev": prev.isoformat(), "next": nxt.isoformat(), "gap_days": gap_days})

    return summarize_rebalance_calendar(entries) | {
        "max_scheduled_gap_days": int(max_scheduled_gap_days),
        "scheduled_gaps": gap_warnings,
        "covers_required_start": bool(required_start is None or earliest <= required_start),
        "covers_required_end": bool(required_end is None or any(item <= required_end for item in ordered)),
    }
