from __future__ import annotations

import pandas as pd

from backend.core.core.models import DailySnapshot


def equity_curve_df(snaps: list[DailySnapshot]) -> pd.DataFrame:
    rows = [
        {
            "date": s.date.isoformat(),
            "cash_total": s.cash_total,
            "cash_available": s.cash_available,
            "market_value": s.market_value,
            "equity": s.equity,
            "realized_pnl": s.realized_pnl,
            "unrealized_pnl": s.unrealized_pnl,
        }
        for s in snaps
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["cummax_equity"] = df["equity"].cummax()
    df["drawdown_pct"] = (df["equity"] / df["cummax_equity"] - 1.0) * 100.0
    df.drop(columns=["cummax_equity"], inplace=True)
    return df
