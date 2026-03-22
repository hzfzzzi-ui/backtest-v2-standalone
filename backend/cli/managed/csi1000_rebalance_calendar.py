from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CALENDAR_PATH = REPO_ROOT / "data_cache" / "csi1000_rebalance_calendar.csv"


@dataclass(frozen=True)
class RebalanceCalendarEntry:
    effective_date: str
    event_type: str
    source: str
    version: str
    generated_at: str = ""
    source_url: str = ""
    source_note: str = ""


def _summarize_single_value(values: set[str]) -> str | None:
    if not values:
        return None
    if len(values) == 1:
        return next(iter(values))
    return "mixed"


def load_rebalance_calendar(path: Path) -> list[RebalanceCalendarEntry]:
    entries: list[RebalanceCalendarEntry] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            effective_date = str(raw.get("effective_date") or "").strip()
            if not effective_date:
                continue
            dt.date.fromisoformat(effective_date)
            entries.append(
                RebalanceCalendarEntry(
                    effective_date=effective_date,
                    event_type=str(raw.get("event_type") or "scheduled").strip().lower() or "scheduled",
                    source=str(raw.get("source") or "").strip(),
                    version=str(raw.get("version") or "").strip(),
                    generated_at=str(raw.get("generated_at") or "").strip(),
                    source_url=str(raw.get("source_url") or "").strip(),
                    source_note=str(raw.get("source_note") or "").strip(),
                )
            )
    if not entries:
        raise RuntimeError(f"rebalance calendar is empty: {path}")
    entries.sort(key=lambda entry: entry.effective_date)
    return entries


def validate_rebalance_calendar(
    entries: list[RebalanceCalendarEntry],
    *,
    required_start: dt.date | None = None,
    required_end: dt.date | None = None,
) -> dict[str, Any]:
    if not entries:
        raise RuntimeError("rebalance calendar is empty")
    if required_start and required_end and required_start > required_end:
        raise ValueError("required_start > required_end")

    effective_dates = [dt.date.fromisoformat(entry.effective_date) for entry in entries]
    if effective_dates != sorted(effective_dates):
        raise RuntimeError("rebalance calendar is not sorted by effective_date")
    if len(effective_dates) != len(set(effective_dates)):
        raise RuntimeError("duplicate effective_date in rebalance calendar")

    first_effective_date = effective_dates[0]
    last_effective_date = effective_dates[-1]
    covers_required_start = required_start is None or first_effective_date <= required_start
    covers_required_end = required_end is None or first_effective_date <= required_end

    if not covers_required_start and required_start is not None:
        raise RuntimeError(
            "coverage gap before required_start="
            f"{required_start.isoformat()}: first_effective_date={first_effective_date.isoformat()}"
        )
    if not covers_required_end and required_end is not None:
        raise RuntimeError(
            "coverage gap before required_end="
            f"{required_end.isoformat()}: first_effective_date={first_effective_date.isoformat()}"
        )

    source_values = {entry.source for entry in entries if entry.source}
    version_values = {entry.version for entry in entries if entry.version}
    generated_values = {entry.generated_at for entry in entries if entry.generated_at}
    event_types = sorted({entry.event_type for entry in entries if entry.event_type})

    return {
        "event_count": len(entries),
        "first_effective_date": first_effective_date.isoformat(),
        "last_effective_date": last_effective_date.isoformat(),
        "source": _summarize_single_value(source_values),
        "version": _summarize_single_value(version_values),
        "generated_at": _summarize_single_value(generated_values),
        "event_types": event_types,
        "covers_required_start": covers_required_start,
        "covers_required_end": covers_required_end,
    }
