from __future__ import annotations

from backend.scripts.build_csi800_formal_history import materialize_formal_rows
from backend.scripts.import_csi800_pit import PITRow


def test_materialize_formal_rows_keeps_seed_when_patch_absent() -> None:
    seed = [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2007-01-01", end_date=None, source="seed"),
    ]

    rows, patch_start, sources = materialize_formal_rows(seed, patch_rows=None)

    assert patch_start is None
    assert sources == ["seed"]
    assert rows == [
        PITRow(
            index_code="000906.SH",
            symbol="000001.SZ",
            start_date="2007-01-01",
            end_date=None,
            source="csi800_formal_history",
        )
    ]


def test_materialize_formal_rows_replaces_seed_tail_with_patch() -> None:
    seed = [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2007-01-01", end_date=None, source="seed"),
        PITRow(index_code="000906.SH", symbol="000002.SZ", start_date="2007-01-01", end_date=None, source="seed"),
    ]
    patch = [
        PITRow(index_code="000906.SH", symbol="000001.SZ", start_date="2025-08-29", end_date="2025-09-30", source="patch"),
        PITRow(index_code="000906.SH", symbol="000003.SZ", start_date="2025-08-29", end_date=None, source="patch"),
    ]

    rows, patch_start, sources = materialize_formal_rows(seed, patch_rows=patch)

    assert patch_start == "2025-08-29"
    assert sources == ["patch", "seed"]
    assert rows == [
        PITRow(
            index_code="000906.SH",
            symbol="000001.SZ",
            start_date="2007-01-01",
            end_date="2025-08-29",
            source="csi800_formal_history",
        ),
        PITRow(
            index_code="000906.SH",
            symbol="000001.SZ",
            start_date="2025-08-29",
            end_date="2025-09-30",
            source="csi800_formal_history",
        ),
        PITRow(
            index_code="000906.SH",
            symbol="000002.SZ",
            start_date="2007-01-01",
            end_date="2025-08-29",
            source="csi800_formal_history",
        ),
        PITRow(
            index_code="000906.SH",
            symbol="000003.SZ",
            start_date="2025-08-29",
            end_date=None,
            source="csi800_formal_history",
        ),
    ]
