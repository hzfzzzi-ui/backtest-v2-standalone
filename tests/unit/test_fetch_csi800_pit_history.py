from __future__ import annotations

import pandas as pd

from backend.scripts.fetch_csi800_pit_history import build_trade_date_snapshots, reconstruct_changes


def test_build_trade_date_snapshots_uses_change_dates_and_skips_partial_rows() -> None:
    frame = pd.DataFrame(
        [{"symbol": f"{i:06d}.SZ", "trade_date": pd.Timestamp("2025-07-31")} for i in range(800)]
        + [{"symbol": f"{i:06d}.SZ", "trade_date": pd.Timestamp("2025-08-01")} for i in range(800)]
        + [{"symbol": f"{i:06d}.SZ", "trade_date": pd.Timestamp("2025-08-04")} for i in range(799)]
        + [{"symbol": f"{i:06d}.SZ", "trade_date": pd.Timestamp("2025-08-05")} for i in range(1, 800)]
        + [{"symbol": "900000.SH", "trade_date": pd.Timestamp("2025-08-05")}]
    )

    snapshots, usable_dates, skipped = build_trade_date_snapshots(frame)
    changes = reconstruct_changes(snapshots)

    assert usable_dates == ["2025-07-31", "2025-08-01", "2025-08-05"]
    assert [item[0] for item in snapshots] == ["2025-07-31", "2025-08-05"]
    assert skipped == [{"trade_date": "2025-08-04", "count": 799}]
    assert any(row["symbol"] == "000000.SZ" and row["out_date"] == "2025-08-05" for row in changes)
    assert any(row["symbol"] == "900000.SH" and row["in_date"] == "2025-08-05" for row in changes)
    assert all(row["source"] == "tushare_csi800_history" for row in changes)
