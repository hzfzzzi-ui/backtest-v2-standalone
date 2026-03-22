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


def build_backtest_hfq_indices(
    *,
    history: pd.DataFrame,
    trading_days: list[date],
) -> tuple[dict[tuple[date, str], float], dict[tuple[date, str], float]]:
    """Build HFQ close and adj-factor indices for corporate-action-safe valuation."""
    hist = history.copy()
    if hist.empty or not trading_days or "adj_factor" not in hist.columns:
        return {}, {}

    hist["date"] = pd.to_datetime(hist["date"]).dt.normalize()
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist["close"] = pd.to_numeric(hist["close"], errors="coerce")
    hist["adj_factor"] = pd.to_numeric(hist["adj_factor"], errors="coerce")
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)
    hist["hfq_close"] = hist["close"] * hist["adj_factor"]

    cal = pd.DatetimeIndex(pd.to_datetime([pd.Timestamp(d).normalize() for d in trading_days]))
    hfq_wide = (
        hist.pivot_table(index="date", columns="symbol", values="hfq_close", aggfunc="last")
        .sort_index()
        .reindex(cal)
        .ffill()
    )
    adj_wide = (
        hist.pivot_table(index="date", columns="symbol", values="adj_factor", aggfunc="last")
        .sort_index()
        .reindex(cal)
        .ffill()
    )
    last_dates = hist.groupby("symbol", sort=False)["date"].max()
    for sym, last_dt in last_dates.items():
        sym_key = str(sym).lower()
        mask = hfq_wide.index > pd.Timestamp(last_dt)
        hfq_wide.loc[mask, sym_key] = pd.NA
        adj_wide.loc[mask, sym_key] = pd.NA

    hfq_close_idx: dict[tuple[date, str], float] = {}
    hfq_stacked = hfq_wide.stack()
    hfq_stacked = hfq_stacked[hfq_stacked.notna()]
    for (dt, sym), value in hfq_stacked.items():
        hfq_close_idx[(pd.Timestamp(dt).date(), str(sym).lower())] = float(value)

    adj_factor_idx: dict[tuple[date, str], float] = {}
    adj_stacked = adj_wide.stack()
    adj_stacked = adj_stacked[adj_stacked.notna()]
    for (dt, sym), value in adj_stacked.items():
        adj_factor_idx[(pd.Timestamp(dt).date(), str(sym).lower())] = float(value)

    return hfq_close_idx, adj_factor_idx
