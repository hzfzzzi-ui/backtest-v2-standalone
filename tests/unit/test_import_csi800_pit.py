from __future__ import annotations

from backend.scripts.import_csi800_pit import PITRow, _merge_rows, _read_csv, _select_rows_for_write


def test_merge_rows_trims_overlapping_old_rows_at_patch_boundary() -> None:
    existing = [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2007-01-01", end_date=None, source="old"),
        PITRow(index_code="000906.SH", symbol="000002.SZ", start_date="2024-01-01", end_date="2025-01-01", source="old"),
    ]
    patch = [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2025-07-31", end_date=None, source="new"),
    ]

    merged, patch_start = _merge_rows(existing, patch)

    assert patch_start == "2025-07-31"
    assert merged == [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2007-01-01", end_date="2025-07-31", source="old"),
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2025-07-31", end_date=None, source="new"),
        PITRow(index_code="000906.SH", symbol="000002.SZ", start_date="2024-01-01", end_date="2025-01-01", source="old"),
    ]


def test_read_csv_defaults_source_label_for_patch_rows(tmp_path) -> None:
    csv_path = tmp_path / "csi800_pit_changes.csv"
    csv_path.write_text(
        "\n".join(
            [
                "index_code,symbol,in_date,out_date",
                "000906.SH,000001.SZ,2025-07-31,",
            ]
        ),
        encoding="utf-8",
    )

    rows = _read_csv(csv_path)

    assert rows == [
        PITRow(
            index_code="000906.SH",
            symbol="000001.SZ",
            start_date="2025-07-31",
            end_date=None,
            source="tushare_csi800_monthly",
        )
    ]


def test_read_csv_defaults_source_label_for_history_rows(tmp_path) -> None:
    csv_path = tmp_path / "csi800_pit_history_changes.csv"
    csv_path.write_text(
        "\n".join(
            [
                "index_code,symbol,in_date,out_date",
                "000906.SH,000001.SZ,2025-07-31,",
            ]
        ),
        encoding="utf-8",
    )

    rows = _read_csv(csv_path)

    assert rows[0].source == "tushare_csi800_history"


def test_select_rows_for_write_can_replace_existing_history() -> None:
    existing = [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2007-01-01", end_date=None, source="old"),
    ]
    patch = [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2010-01-01", end_date=None, source="new"),
        PITRow(index_code="000906.SH", symbol="000002.SZ", start_date="2010-01-01", end_date=None, source="new"),
    ]

    rows, patch_start, mode = _select_rows_for_write(existing, patch, replace_existing=True)

    assert mode == "replace_existing"
    assert patch_start == "2010-01-01"
    assert rows == patch
