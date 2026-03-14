from __future__ import annotations

import pandas as pd

from backend.core.universe.hs300_csi500 import (
    UniverseFilterConfig,
    apply_universe_filters,
    build_candidates_from_ohlcv,
)


def test_build_candidates_from_ohlcv_uses_pit_st_only() -> None:
    ohlcv = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2016-08-29"),
                "symbol": "sz000793",
                "open": 12.0,
                "high": 12.2,
                "low": 11.8,
                "close": 12.1,
                "volume": 1000,
                "amount": 12000,
            }
        ]
    )
    security_master = pd.DataFrame(
        [
            {
                "symbol": "sz000793",
                "name": "ST鍗庨椈",
                "list_date": "2010-01-04",
                "delist_date": None,
            }
        ]
    )

    out = build_candidates_from_ohlcv(
        ohlcv,
        pd.Timestamp("2016-08-29"),
        st_history=pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        security_master=security_master,
    )

    assert len(out) == 1
    assert bool(out.iloc[0]["is_st"]) is False
    assert out.iloc[0]["security_name"] == "ST鍗庨椈"


def test_build_candidates_from_ohlcv_emits_avg_turnover_rate_20d_when_full_window_available() -> None:
    rows = []
    for i in range(20):
        rows.append(
            {
                "date": pd.Timestamp("2024-01-02") + pd.Timedelta(days=i),
                "symbol": "sh600000",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000 + i,
                "amount": 10000 + i,
                "turnover_rate_f": 1.0 + i * 0.1,
            }
        )

    out = build_candidates_from_ohlcv(
        pd.DataFrame(rows),
        pd.Timestamp("2024-01-21"),
        turnover_rate_field="turnover_rate_f",
    )

    assert len(out) == 1
    assert round(float(out.iloc[0]["avg_turnover_rate_20d"]), 6) == round(sum(1.0 + i * 0.1 for i in range(20)) / 20.0, 6)


def test_build_candidates_from_ohlcv_marks_turnover_rate_missing_when_window_has_gap() -> None:
    rows = []
    for i in range(20):
        rows.append(
            {
                "date": pd.Timestamp("2024-01-02") + pd.Timedelta(days=i),
                "symbol": "sh600000",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000 + i,
                "amount": 10000 + i,
                "turnover_rate_f": None if i == 19 else 1.0,
            }
        )

    out = build_candidates_from_ohlcv(
        pd.DataFrame(rows),
        pd.Timestamp("2024-01-21"),
        turnover_rate_field="turnover_rate_f",
    )

    assert len(out) == 1
    assert pd.isna(out.iloc[0]["avg_turnover_rate_20d"])


def test_apply_universe_filters_excludes_missing_turnover_rate_when_enabled() -> None:
    candidates = pd.DataFrame(
        [
            {
                "date": "2024-01-21",
                "symbol": "sh600000",
                "in_hs300": True,
                "in_csi500": True,
                "is_st": False,
                "is_delisted": False,
                "is_suspended": False,
                "list_days": 300,
                "avg_turnover_20d": 2e8,
                "avg_turnover_rate_20d": pd.NA,
                "last_close": 10.0,
                "limit_lock": False,
            }
        ]
    )
    filtered, snapshot, excluded_counts = apply_universe_filters(
        candidates,
        UniverseFilterConfig(
            min_avg_turnover_20d=0.0,
            min_avg_turnover_rate_20d=1.0,
            turnover_rate_field="turnover_rate_f",
            min_price=0.0,
        ),
    )

    assert filtered.empty
    assert snapshot.iloc[0]["excluded_reason"] == "EXCLUDE_TURNOVER_RATE_UNAVAILABLE"
    assert excluded_counts == {"EXCLUDE_TURNOVER_RATE_UNAVAILABLE": 1}
