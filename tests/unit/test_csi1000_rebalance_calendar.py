from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from backend.cli.managed.csi1000_rebalance_calendar import (
    load_rebalance_calendar,
    validate_rebalance_calendar,
)


def _write_calendar(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "effective_date",
                "event_type",
                "source",
                "version",
                "generated_at",
                "source_url",
                "source_note",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_load_and_validate_rebalance_calendar_success(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.csv"
    _write_calendar(
        calendar_path,
        [
            {
                "effective_date": "2016-03-01",
                "event_type": "scheduled",
                "source": "csindex_seed_schedule",
                "version": "seed-v1",
                "generated_at": "2026-03-11T00:00:00+08:00",
                "source_url": "",
                "source_note": "",
            },
            {
                "effective_date": "2016-09-01",
                "event_type": "scheduled",
                "source": "csindex_seed_schedule",
                "version": "seed-v1",
                "generated_at": "2026-03-11T00:00:00+08:00",
                "source_url": "",
                "source_note": "",
            },
        ],
    )

    entries = load_rebalance_calendar(calendar_path)
    summary = validate_rebalance_calendar(
        entries,
        required_start=date(2016, 3, 1),
        required_end=date(2016, 10, 1),
    )

    assert len(entries) == 2
    assert summary["version"] == "seed-v1"
    assert summary["source"] == "csindex_seed_schedule"
    assert summary["generated_at"] == "2026-03-11T00:00:00+08:00"
    assert summary["covers_required_start"] is True
    assert summary["covers_required_end"] is True


def test_validate_rebalance_calendar_rejects_duplicate_effective_dates(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.csv"
    _write_calendar(
        calendar_path,
        [
            {
                "effective_date": "2016-03-01",
                "event_type": "scheduled",
                "source": "csindex_seed_schedule",
                "version": "seed-v1",
                "generated_at": "",
                "source_url": "",
                "source_note": "",
            },
            {
                "effective_date": "2016-03-01",
                "event_type": "ad_hoc",
                "source": "csindex_seed_schedule",
                "version": "seed-v1",
                "generated_at": "",
                "source_url": "",
                "source_note": "",
            },
        ],
    )

    entries = load_rebalance_calendar(calendar_path)
    try:
        validate_rebalance_calendar(entries)
    except RuntimeError as exc:
        assert "duplicate effective_date" in str(exc)
    else:
        raise AssertionError("expected duplicate effective_date validation error")


def test_validate_rebalance_calendar_detects_required_start_gap(tmp_path: Path) -> None:
    calendar_path = tmp_path / "calendar.csv"
    _write_calendar(
        calendar_path,
        [
            {
                "effective_date": "2016-09-01",
                "event_type": "scheduled",
                "source": "csindex_seed_schedule",
                "version": "seed-v1",
                "generated_at": "",
                "source_url": "",
                "source_note": "",
            },
        ],
    )

    entries = load_rebalance_calendar(calendar_path)
    try:
        validate_rebalance_calendar(entries, required_start=date(2016, 3, 1))
    except RuntimeError as exc:
        assert "coverage gap" in str(exc)
    else:
        raise AssertionError("expected coverage gap validation error")
