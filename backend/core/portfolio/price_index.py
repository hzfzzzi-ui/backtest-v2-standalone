from __future__ import annotations

from datetime import date

import pandas as pd


def build_backtest_price_indices(
    *,
    history: pd.DataFrame,
    trading_days: list[date],
) -> tuple[dict[tuple[date, str], float], dict[tuple[date, str], float]]:
    """Build execution open lookup plus valuation close lookup."""
    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"]).dt.normalize()
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    open_idx: dict[tuple[date, str], float] = {}
    for row in hist.itertuples(index=False):
        d = pd.Timestamp(row.date).date()
        s = str(row.symbol).lower()
        open_idx[(d, s)] = float(row.open)

    if hist.empty or not trading_days:
        return open_idx, {}

    cal = pd.DatetimeIndex(pd.to_datetime([pd.Timestamp(d).normalize() for d in trading_days]))
    close_wide = (
        hist.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
        .sort_index()
        .reindex(cal)
        .ffill()
    )
    last_dates = hist.groupby("symbol", sort=False)["date"].max()
    for sym, last_dt in last_dates.items():
        close_wide.loc[close_wide.index > pd.Timestamp(last_dt), str(sym).lower()] = pd.NA

    close_idx: dict[tuple[date, str], float] = {}
    stacked = close_wide.stack()
    stacked = stacked[stacked.notna()]
    for (dt, sym), value in stacked.items():
        close_idx[(pd.Timestamp(dt).date(), str(sym).lower())] = float(value)
    return open_idx, close_idx
