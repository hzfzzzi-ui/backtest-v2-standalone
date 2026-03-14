from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.core.analytics.symbol_performance import build_symbol_performance


def test_build_symbol_performance_marks_to_market_closed_position_drawdown() -> None:
    trades_df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600000",
                "side": "BUY",
                "qty": 100,
                "value": 1000.0,
                "commission": 0.0,
                "stamp_tax": 0.0,
                "slippage": 0.0,
            },
            {
                "date": "2024-01-04",
                "symbol": "sh600000",
                "side": "SELL",
                "qty": 100,
                "value": 1200.0,
                "commission": 0.0,
                "stamp_tax": 0.0,
                "slippage": 0.0,
            },
        ]
    )
    daily_close_df = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "sh600000", "close": 10.0},
            {"date": "2024-01-03", "symbol": "sh600000", "close": 8.0},
            {"date": "2024-01-04", "symbol": "sh600000", "close": 12.0},
        ]
    )

    out = build_symbol_performance(
        trades_df=trades_df,
        last_close_map={"sh600000": 12.0},
        last_date=date(2024, 1, 4),
        daily_close_df=daily_close_df,
    )

    row = out.iloc[0]
    assert row["symbol"] == "sh600000"
    assert row["return_pct"] == pytest.approx(0.2)
    assert row["max_drawdown"] == pytest.approx(-0.2)
    assert row["realized_pnl"] == pytest.approx(200.0)
    assert pd.isna(row["valuation_price"])
    assert row["last_valuation_date"] == ""


def test_build_symbol_performance_keeps_open_position_valuation_fields() -> None:
    trades_df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "sh600001",
                "side": "BUY",
                "qty": 100,
                "value": 1000.0,
                "commission": 0.0,
                "stamp_tax": 0.0,
                "slippage": 0.0,
            }
        ]
    )
    daily_close_df = pd.DataFrame(
        [
            {"trade_date": "2024-01-02", "symbol": "sh600001", "close": 10.0},
            {"trade_date": "2024-01-03", "symbol": "sh600001", "close": 11.0},
        ]
    )

    out = build_symbol_performance(
        trades_df=trades_df,
        last_close_map={"sh600001": 11.0},
        last_date=date(2024, 1, 3),
        daily_close_df=daily_close_df,
    )

    row = out.iloc[0]
    assert row["symbol"] == "sh600001"
    assert row["return_pct"] == pytest.approx(0.1)
    assert row["max_drawdown"] == pytest.approx(0.0)
    assert row["unrealized_approx_pnl"] == pytest.approx(100.0)
    assert row["valuation_price"] == pytest.approx(11.0)
    assert row["last_valuation_date"] == "2024-01-03"
