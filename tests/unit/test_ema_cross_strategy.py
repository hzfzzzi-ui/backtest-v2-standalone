from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.core.core.models import Position
from backend.core.strategies.ema_cross import EMACrossStrategy


def _mk_history(symbol: str, closes: list[float], start: date) -> pd.DataFrame:
    rows: list[dict] = []
    for i, c in enumerate(closes):
        d = start + timedelta(days=i)
        rows.append(
            {
                "date": pd.Timestamp(d),
                "symbol": symbol,
                "open": float(c),
                "high": float(c) * 1.01,
                "low": float(c) * 0.99,
                "close": float(c),
            }
        )
    return pd.DataFrame(rows)


def test_ema_cross_buy_signal_has_trend_meta() -> None:
    start = date(2026, 1, 1)
    day = start + timedelta(days=7)
    history = _mk_history("AAA", [10, 10, 10, 10, 10, 10, 15, 18], start)

    strategy = EMACrossStrategy(fast=3, slow=5, order_size=1000)
    signals = strategy.generate_signals(day, history, positions={})
    buys = [s for s in signals if str(s.side.value).upper() == "BUY"]

    assert len(buys) == 1
    sig = buys[0]
    assert sig.reason_code == "EMA_CROSS_UP"
    assert (sig.meta or {}).get("signal_class") == "TREND"
    assert (sig.meta or {}).get("ma_type") == "EMA"


def test_ema_cross_sell_signal_when_position_exists() -> None:
    start = date(2026, 1, 1)
    day = start + timedelta(days=7)
    history = _mk_history("AAA", [18, 17, 16, 15, 14, 13, 12, 11], start)
    positions = {"AAA": Position(symbol="AAA", total_qty=1000, sellable_qty=1000, avg_cost=15.0)}

    strategy = EMACrossStrategy(fast=3, slow=5, order_size=1000)
    signals = strategy.generate_signals(day, history, positions=positions)
    sells = [s for s in signals if str(s.side.value).upper() == "SELL"]

    assert len(sells) == 1
    sig = sells[0]
    assert sig.reason_code == "EMA_CROSS_DOWN"
    assert sig.qty == 1000
