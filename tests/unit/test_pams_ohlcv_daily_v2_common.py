from __future__ import annotations

import pandas as pd

from backend.cli.managed import pams_ohlcv_daily_v2_common as common


def test_pick_akshare_hist_columns_supports_chinese_headers() -> None:
    frame = pd.DataFrame(columns=["日期", "开盘", "换手率"])

    date_col, turnover_col = common._pick_akshare_hist_columns(frame)

    assert date_col == "日期"
    assert turnover_col == "换手率"


def test_pick_akshare_hist_columns_supports_ascii_fallback_headers() -> None:
    frame = pd.DataFrame(columns=["date", "close", "turnover_rate"])

    date_col, turnover_col = common._pick_akshare_hist_columns(frame)

    assert date_col == "date"
    assert turnover_col == "turnover_rate"
