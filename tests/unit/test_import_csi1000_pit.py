from __future__ import annotations

import csv
from pathlib import Path

from backend.scripts.import_csi1000_pit import (
    _build_refresh_sidecar_rows,
    _read_csv,
    _read_snapshots_csv,
    summarize_rows,
    summarize_snapshot_rows,
)


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


def _write_snapshots(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "effective_date",
                "symbol",
                "source",
                "event_type",
                "rebalance_calendar_version",
                "rebalance_calendar_source",
                "rebalance_calendar_generated_at",
                "snapshot_trade_date",
                "source_url",
                "source_note",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "effective_date": "2016-03-01",
                    "symbol": "000001.SZ",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                    "snapshot_trade_date": "2016-03-01",
                    "source_url": "",
                    "source_note": "",
                },
                {
                    "effective_date": "2016-03-01",
                    "symbol": "600000.SH",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                    "snapshot_trade_date": "2016-03-01",
                    "source_url": "",
                    "source_note": "",
                },
                {
                    "effective_date": "2016-09-01",
                    "symbol": "000001.SZ",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                    "snapshot_trade_date": "2016-09-01",
                    "source_url": "",
                    "source_note": "",
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


def test_snapshot_reader_and_sidecar_mapping_capture_provider_floor(tmp_path: Path) -> None:
    changes_path = tmp_path / "csi1000_pit_calendar_changes.csv"
    snapshots_path = tmp_path / "csi1000_pit_calendar_snapshots.csv"
    _write_changes(changes_path)
    _write_snapshots(snapshots_path)

    pit_rows = _read_csv(changes_path)
    snapshot_rows = _read_snapshots_csv(snapshots_path)
    snapshot_summary = summarize_snapshot_rows(snapshot_rows)
    refresh_rows = _build_refresh_sidecar_rows(pit_rows, snapshot_rows)

    assert snapshot_summary["rows"] == 3
    assert snapshot_summary["refresh_event_count"] == 2
    assert snapshot_summary["provider_floor_date"] == "2016-03-01"
    assert len(refresh_rows) == 3
    assert refresh_rows[0].constituent_start_date == "2016-03-01"
    assert refresh_rows[-1].refresh_date == "2016-09-01"
