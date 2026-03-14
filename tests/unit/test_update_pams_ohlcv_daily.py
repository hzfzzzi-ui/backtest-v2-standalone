from __future__ import annotations

from datetime import date

import pandas as pd

from backend.scripts.update_pams_ohlcv_daily import (
    _compute_limit_prices,
    _limit_pct_for_symbol,
    _normalize_cn_a_rows,
    _normalize_cn_index_rows,
    _normalize_daily_basic_frame,
)


def test_limit_pct_matches_existing_board_conventions() -> None:
    assert _limit_pct_for_symbol("sh600519", is_st=False) == 0.10
    assert _limit_pct_for_symbol("sz300750", is_st=False) == 0.20
    assert _limit_pct_for_symbol("sh688981", is_st=False) == 0.20
    assert _limit_pct_for_symbol("bj920002", is_st=False) == 0.30
    assert _limit_pct_for_symbol("sz000608", is_st=True) == 0.05
    assert _limit_pct_for_symbol("sz300344", is_st=True) == 0.20
    assert _limit_pct_for_symbol("sh688399", is_st=True) == 0.20


def test_compute_limit_prices_rounds_to_exchange_tick_size() -> None:
    assert _compute_limit_prices(10.0, "sz000609", is_st=True) == (10.5, 9.5)
    assert _compute_limit_prices(102.0, "bj920002", is_st=False) == (132.6, 71.4)
    assert _compute_limit_prices(3.63, "sz000608", is_st=True) == (3.81, 3.45)
    assert _compute_limit_prices(24.53, "sz002261", is_st=False) == (26.98, 22.08)
    assert _compute_limit_prices(6.93, "sz002797", is_st=False) == (7.62, 6.24)
    assert _compute_limit_prices(None, "sh600519", is_st=False) == (None, None)


def test_normalize_daily_basic_frame_merges_expected_fields() -> None:
    raw = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260310",
                "turnover_rate": "0.55",
                "turnover_rate_f": "0.60",
                "volume_ratio": "1.2",
                "float_share": "1000",
                "free_share": "800",
                "circ_mv": "12345",
            }
        ]
    )
    normalized = _normalize_daily_basic_frame(raw)
    assert normalized.loc[0, "symbol"] == "sh600519"
    assert normalized.loc[0, "trade_date"].isoformat() == "2026-03-10"
    assert float(normalized.loc[0, "turnover_rate_f"]) == 0.60
    assert float(normalized.loc[0, "circ_mv"]) == 12345.0


def test_normalize_cn_index_rows_preserves_existing_table_convention() -> None:
    raw = pd.DataFrame(
        [
            {
                "日期": "2026-03-10",
                "开盘": 4100.0,
                "最高": 4120.0,
                "最低": 4090.0,
                "收盘": 4110.0,
                "成交量": 123456.0,
            }
        ]
    )
    normalized, stats = _normalize_cn_index_rows("sh000001", raw, start=date(2026, 3, 1), end=date(2026, 3, 10))
    assert stats["rows"] == 1
    assert normalized.loc[0, "market"] == "CN_INDEX"
    assert int(normalized.loc[0, "volume"]) == 12345600
    assert float(normalized.loc[0, "turnover"]) == 0.0
    assert pd.isna(normalized.loc[0, "adj_factor"])


def test_normalize_cn_a_rows_builds_suspended_rows_from_adj_only_symbol() -> None:
    daily_raw = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260310",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "pre_close": 100.0,
                "vol": 10.0,
                "amount": 20.0,
            }
        ]
    )
    adj_raw = pd.DataFrame(
        [
            {"ts_code": "600519.SH", "trade_date": "20260310", "adj_factor": 1.0},
            {"ts_code": "300344.SZ", "trade_date": "20260310", "adj_factor": 2.0},
        ]
    )

    normalized, stats = _normalize_cn_a_rows(
        trade_date=date(2026, 3, 10),
        daily_raw=daily_raw,
        adj_raw=adj_raw,
        basic_raw=pd.DataFrame(),
        st_periods={"sz300344": [(date(2025, 1, 1), None)]},
        prev_close_map={"sh600519": 100.0, "sz300344": 9.8},
    )

    suspended = normalized[normalized["symbol"] == "sz300344"].reset_index(drop=True)
    assert stats["suspended_rows"] == 1
    assert len(suspended) == 1
    assert bool(suspended.loc[0, "is_suspended"]) is True
    assert float(suspended.loc[0, "close"]) == 9.8
    assert float(suspended.loc[0, "limit_up"]) == 11.76
