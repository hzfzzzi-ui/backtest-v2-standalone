from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.portfolio.portfolio_builder import build_backtest_price_indices, compute_nav_snapshot


def test_build_backtest_price_indices_ffill_gaps_but_not_after_last_bar() -> None:
    history = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-01-05"), "symbol": "AAA", "open": 10.0, "close": 10.0},
            {"date": pd.Timestamp("2026-01-07"), "symbol": "AAA", "open": 12.0, "close": 12.0},
        ]
    )
    trading_days = [
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
        date(2026, 1, 8),
    ]

    open_idx, close_idx = build_backtest_price_indices(history=history, trading_days=trading_days)

    assert open_idx[(date(2026, 1, 5), "aaa")] == 10.0
    assert open_idx[(date(2026, 1, 7), "aaa")] == 12.0
    assert (date(2026, 1, 6), "aaa") not in open_idx

    assert close_idx[(date(2026, 1, 5), "aaa")] == 10.0
    assert close_idx[(date(2026, 1, 6), "aaa")] == 10.0
    assert close_idx[(date(2026, 1, 7), "aaa")] == 12.0
    assert (date(2026, 1, 8), "aaa") not in close_idx


def test_compute_nav_snapshot_uses_carried_close_on_missing_trade_day() -> None:
    history = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-01-05"), "symbol": "AAA", "open": 10.0, "close": 10.0},
            {"date": pd.Timestamp("2026-01-07"), "symbol": "AAA", "open": 12.0, "close": 12.0},
        ]
    )
    trading_days = [
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
    ]
    _, close_idx = build_backtest_price_indices(history=history, trading_days=trading_days)

    nav, market_value, pos_values = compute_nav_snapshot(
        cash=1_000.0,
        positions={"aaa": 100},
        close_idx=close_idx,
        day=date(2026, 1, 6),
    )

    assert market_value == 1_000.0
    assert nav == 2_000.0
    assert pos_values == [("aaa", 1_000.0)]
