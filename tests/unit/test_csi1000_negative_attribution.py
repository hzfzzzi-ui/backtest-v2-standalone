from __future__ import annotations

import pandas as pd

from backend.research.csi1000_negative_attribution import (
    INDEX_CSI1000,
    _build_exit_events,
    _candidate_funnel,
    classify_membership,
    normalize_symbol,
    to_ts_code,
)


def test_symbol_normalization_and_ts_code() -> None:
    assert normalize_symbol("300076.SZ") == "sz300076"
    assert normalize_symbol("SH600000") == "sh600000"
    assert to_ts_code("sz300076") == "300076.SZ"
    assert to_ts_code("sh600000") == "600000.SH"


def test_classify_membership_uses_asof_interval() -> None:
    intervals = {
        "sz300076": [
            (pd.Timestamp("2016-01-01"), pd.Timestamp("2016-12-31"), INDEX_CSI1000),
        ]
    }
    assert classify_membership("sz300076", "2016-07-01", intervals) == "csi1000_new"
    assert classify_membership("sz300076", "2017-01-01", intervals) == "unclassified"


def test_build_exit_events_allocates_fifo_pnl() -> None:
    trades = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-01"),
                "symbol": "sz300001",
                "side": "BUY",
                "qty": 100.0,
                "net_amount": 1000.0,
                "commission": 1.0,
                "stamp_tax": 0.0,
                "slippage": 0.0,
                "reason_code": "BREAKOUT_HIGH",
            },
            {
                "date": pd.Timestamp("2024-01-10"),
                "symbol": "sz300001",
                "side": "SELL",
                "qty": 100.0,
                "net_amount": 900.0,
                "commission": 1.0,
                "stamp_tax": 1.0,
                "slippage": 1.0,
                "reason_code": "ATR_STOP_LOSS",
            },
        ]
    )
    features = pd.DataFrame(
        [
            {
                "symbol": "sz300001",
                "membership_bucket": "csi1000_new",
                "industry_l1": "电子",
                "liquidity_bucket": "100-200m",
                "market_cap_bucket": "50-100yi",
                "rank_pct_bucket": "top_10pct",
            }
        ]
    )

    events = _build_exit_events(trades, features)

    assert len(events) == 1
    assert events.loc[0, "realized_pnl"] == -100.0
    assert events.loc[0, "membership_bucket"] == "csi1000_new"
    assert events.loc[0, "exit_reason"] == "ATR_STOP_LOSS"


def test_candidate_funnel_counts_buy_rows_separately_from_rejected_candidates() -> None:
    candidates = pd.DataFrame(
        [
            {
                "symbol": "sz300001",
                "membership_bucket": "csi1000_new",
                "selected_flag": False,
                "cash_blocked_flag": True,
                "rank_pct": 0.2,
            },
            {
                "symbol": "sz300002",
                "membership_bucket": "csi1000_new",
                "selected_flag": False,
                "cash_blocked_flag": True,
                "rank_pct": 0.4,
            },
        ]
    )
    selected = pd.DataFrame(
        [
            {
                "symbol": "sz300003",
                "membership_bucket": "csi1000_new",
            }
        ]
    )

    funnel = _candidate_funnel(candidates, "membership_bucket", selected)

    assert funnel.loc[0, "candidate_rows"] == 2
    assert funnel.loc[0, "buy_rows"] == 1
    assert funnel.loc[0, "selected_rows_with_buys"] == 1
