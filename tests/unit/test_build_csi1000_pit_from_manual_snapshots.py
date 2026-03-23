from __future__ import annotations

import csv
from pathlib import Path

from backend.scripts.build_csi1000_pit_from_manual_snapshots import (
    build_snapshots_from_manifest,
    reconstruct_changes,
    summarize_build,
)


def _write_snapshot_csv(path: Path, header: str, symbols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([header])
        for symbol in symbols:
            writer.writerow([symbol])


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "effective_date",
                "snapshot_path",
                "source",
                "event_type",
                "version",
                "snapshot_trade_date",
                "rebalance_calendar_source",
                "rebalance_calendar_generated_at",
                "source_url",
                "source_note",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_manual_snapshot_builder_reconstructs_changes(tmp_path: Path) -> None:
    snap1 = tmp_path / "snapshots" / "2016-03-01.csv"
    snap2 = tmp_path / "snapshots" / "2016-09-01.csv"
    _write_snapshot_csv(snap1, "证券代码", ["000001", "000002", "600000"])
    _write_snapshot_csv(snap2, "证券代码", ["000001", "600000", "600001"])

    manifest = tmp_path / "manifest.csv"
    _write_manifest(
        manifest,
        [
            {
                "effective_date": "2016-03-01",
                "snapshot_path": "snapshots/2016-03-01.csv",
                "source": "csindex_notice",
                "event_type": "scheduled",
                "version": "manual-v1",
                "snapshot_trade_date": "2016-03-01",
                "rebalance_calendar_source": "csindex_seed_schedule",
                "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                "source_url": "https://example.com/a",
                "source_note": "first",
            },
            {
                "effective_date": "2016-09-01",
                "snapshot_path": "snapshots/2016-09-01.csv",
                "source": "csindex_notice",
                "event_type": "scheduled",
                "version": "manual-v1",
                "snapshot_trade_date": "2016-09-01",
                "rebalance_calendar_source": "csindex_seed_schedule",
                "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                "source_url": "https://example.com/b",
                "source_note": "second",
            },
        ],
    )

    snapshots = build_snapshots_from_manifest(manifest, expected_count=3, strict_count=True)
    assert [spec.effective_date for spec, _ in snapshots] == ["2016-03-01", "2016-09-01"]
    assert snapshots[0][1] == ["000001.SZ", "000002.SZ", "600000.SH"]

    changes = reconstruct_changes(snapshots)
    by_symbol = {(row["symbol"], row["in_date"], row["out_date"]) for row in changes}
    assert ("000001.SZ", "2016-03-01", "") in by_symbol
    assert ("600000.SH", "2016-03-01", "") in by_symbol
    assert ("000002.SZ", "2016-03-01", "2016-09-01") in by_symbol
    assert ("600001.SH", "2016-09-01", "") in by_symbol
    open_row = next(row for row in changes if row["symbol"] == "000001.SZ" and row["out_date"] == "")
    assert open_row["event_type"] == "scheduled"
    assert open_row["rebalance_calendar_version"] == "manual-v1"
    assert open_row["rebalance_calendar_source"] == "csindex_seed_schedule"
    assert open_row["rebalance_calendar_generated_at"] == "2026-03-11T00:00:00+08:00"


def test_manual_snapshot_builder_detects_count_mismatch(tmp_path: Path) -> None:
    snap1 = tmp_path / "2016-03-01.csv"
    _write_snapshot_csv(snap1, "code", ["000001", "000002"])
    manifest = tmp_path / "manifest.csv"
    _write_manifest(
        manifest,
        [{
            "effective_date": "2016-03-01",
            "snapshot_path": "2016-03-01.csv",
            "source": "csindex_notice",
            "event_type": "scheduled",
            "version": "manual-v1",
            "snapshot_trade_date": "",
            "rebalance_calendar_source": "csindex_seed_schedule",
            "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
            "source_url": "",
            "source_note": "",
        }],
    )

    try:
        build_snapshots_from_manifest(manifest, expected_count=3, strict_count=True)
    except RuntimeError as exc:
        assert "snapshot count mismatch" in str(exc)
    else:
        raise AssertionError("expected count mismatch to raise")


def test_manual_snapshot_builder_summary_includes_lineage_metadata(tmp_path: Path) -> None:
    snap1 = tmp_path / "snapshots" / "2016-03-01.csv"
    snap2 = tmp_path / "snapshots" / "2016-09-01.csv"
    _write_snapshot_csv(snap1, "code", ["000001", "000002", "600000"])
    _write_snapshot_csv(snap2, "code", ["000001", "600000", "600001"])

    manifest = tmp_path / "manifest.csv"
    _write_manifest(
        manifest,
        [
            {
                "effective_date": "2016-03-01",
                "snapshot_path": "snapshots/2016-03-01.csv",
                "source": "csindex_official_manual",
                "event_type": "scheduled",
                "version": "official-v1",
                "snapshot_trade_date": "2016-03-01",
                "rebalance_calendar_source": "csindex_notice",
                "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                "source_url": "https://example.com/a",
                "source_note": "first",
            },
            {
                "effective_date": "2016-09-01",
                "snapshot_path": "snapshots/2016-09-01.csv",
                "source": "csindex_official_manual",
                "event_type": "scheduled",
                "version": "official-v1",
                "snapshot_trade_date": "2016-09-01",
                "rebalance_calendar_source": "csindex_notice",
                "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                "source_url": "https://example.com/b",
                "source_note": "second",
            },
        ],
    )

    snapshots = build_snapshots_from_manifest(manifest, expected_count=3, strict_count=True)
    changes = reconstruct_changes(snapshots)
    summary = summarize_build(
        manifest,
        snapshots,
        changes,
        expected_count=3,
        strict_count=True,
        snapshots_csv=tmp_path / "csi1000_pit_manual_snapshots.csv",
        changes_csv=tmp_path / "csi1000_pit_manual_changes.csv",
    )

    assert summary["snapshot_count"] == 2
    assert summary["source"] == "csindex_official_manual"
    assert summary["rebalance_calendar_version"] == "official-v1"
    assert summary["rebalance_calendar_source"] == "csindex_notice"
    assert summary["rebalance_calendar_generated_at"] == "2026-03-11T00:00:00+08:00"
    assert summary["provider_floor_date"] == "2016-03-01"
    assert summary["source_url_count"] == 2
