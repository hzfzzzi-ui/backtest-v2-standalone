from __future__ import annotations

import csv
from pathlib import Path

from backend.scripts.import_csi1000_pit import _read_csv, summarize_rows


def _write_changes(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "index_code",
                "symbol",
                "in_date",
                "out_date",
                "source",
                "event_type",
                "rebalance_calendar_version",
                "rebalance_calendar_source",
                "rebalance_calendar_generated_at",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "index_code": "000852.SH",
                    "symbol": "000001.SZ",
                    "in_date": "2016-03-01",
                    "out_date": "",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
                {
                    "index_code": "000852.SH",
                    "symbol": "600000.SH",
                    "in_date": "2016-03-01",
                    "out_date": "2016-09-01",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
            ]
        )


def test_import_csv_reader_and_summary_capture_calendar_metadata(tmp_path: Path) -> None:
    csv_path = tmp_path / "csi1000_pit_calendar_changes.csv"
    _write_changes(csv_path)

    rows = _read_csv(csv_path)
    summary = summarize_rows(rows)

    assert len(rows) == 2
    assert summary["rows"] == 2
    assert summary["distinct_symbols"] == 2
    assert summary["distinct_start_dates"] == 1
    assert summary["open_rows"] == 1
    assert summary["closed_rows"] == 1
    assert summary["membership_source"] == "tushare_csi1000_calendar"
    assert summary["rebalance_calendar_version"] == "seed-v1"
    assert summary["rebalance_calendar_source"] == "csindex_seed_schedule"
    assert summary["rebalance_calendar_generated_at"] == "2026-03-11T00:00:00+08:00"
