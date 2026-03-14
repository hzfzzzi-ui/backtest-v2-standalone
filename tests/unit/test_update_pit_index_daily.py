from __future__ import annotations

import pandas as pd

from backend.scripts.update_pit_index_daily import _filter_incremental_rows, _internal_to_ts_index_code


def test_internal_to_ts_index_code_maps_cn_index_symbol() -> None:
    assert _internal_to_ts_index_code("sh000300") == "000300.SH"
    assert _internal_to_ts_index_code("sz399001") == "399001.SZ"


def test_filter_incremental_rows_keeps_only_dates_after_current_max() -> None:
    frame = pd.DataFrame(
        [
            {"index_code": "000300.SH", "trade_date": pd.Timestamp("2026-02-13").date(), "open": 1},
            {"index_code": "000300.SH", "trade_date": pd.Timestamp("2026-02-24").date(), "open": 2},
            {"index_code": "399001.SZ", "trade_date": pd.Timestamp("2026-02-12").date(), "open": 3},
            {"index_code": "399001.SZ", "trade_date": pd.Timestamp("2026-02-24").date(), "open": 4},
        ]
    )

    out = _filter_incremental_rows(
        frame,
        before_max={"000300.SH": pd.Timestamp("2026-02-13").date(), "399001.SZ": pd.Timestamp("2026-02-11").date()},
        start=None,
    )

    assert out["index_code"].tolist() == ["399001.SZ", "000300.SH", "399001.SZ"]
    assert [item.isoformat() for item in out["trade_date"].tolist()] == ["2026-02-12", "2026-02-24", "2026-02-24"]
