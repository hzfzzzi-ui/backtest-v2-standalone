from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


@dataclass(slots=True)
class OhlcMatrices:
    dates: np.ndarray
    symbols: list[str]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    tradable: np.ndarray


def build_ohlc_matrices_from_history(
    history: pd.DataFrame,
    trading_days: list[date],
) -> OhlcMatrices:
    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    dates = pd.to_datetime([pd.Timestamp(d).normalize() for d in trading_days])
    symbols = sorted(hist["symbol"].dropna().astype(str).unique().tolist())
    t = len(dates)
    n = len(symbols)
    sym_to_col = {s: i for i, s in enumerate(symbols)}
    date_to_row = {d: i for i, d in enumerate(dates)}

    open_m = np.full((t, n), np.nan, dtype=float)
    high_m = np.full((t, n), np.nan, dtype=float)
    low_m = np.full((t, n), np.nan, dtype=float)
    close_m = np.full((t, n), np.nan, dtype=float)
    volume_m = np.full((t, n), np.nan, dtype=float)
    tradable = np.zeros((t, n), dtype=bool)

    for row in hist.itertuples(index=False):
        d = pd.Timestamp(row.date).normalize()
        s = str(row.symbol)
        r = date_to_row.get(d)
        c = sym_to_col.get(s)
        if r is None or c is None:
            continue
        open_m[r, c] = float(getattr(row, "open", np.nan))
        high_m[r, c] = float(getattr(row, "high", np.nan))
        low_m[r, c] = float(getattr(row, "low", np.nan))
        close_m[r, c] = float(getattr(row, "close", np.nan))
        vol = getattr(row, "volume", np.nan)
        volume_m[r, c] = float(vol) if pd.notna(vol) else np.nan
        tradable[r, c] = bool(pd.notna(close_m[r, c]) and close_m[r, c] > 0 and pd.notna(open_m[r, c]) and open_m[r, c] > 0)

    return OhlcMatrices(
        dates=dates.to_numpy(),
        symbols=symbols,
        open=open_m,
        high=high_m,
        low=low_m,
        close=close_m,
        volume=volume_m,
        tradable=tradable,
    )


def build_ohlc_matrices(
    provider: Any,
    symbols: list[str],
    start: date,
    end: date,
    cache: dict[tuple[Any, ...], OhlcMatrices] | None = None,
) -> OhlcMatrices:
    key = ("ohlc_mx", tuple(sorted([str(s).lower() for s in symbols])), str(start), str(end))
    if cache is not None and key in cache:
        return cache[key]
    history = provider.load_ohlcv_daily(symbols, start, end, source="stocks")
    cal = provider.load_trading_calendar_cn(start, end)
    days = [d.date() for d in cal]
    out = build_ohlc_matrices_from_history(history, days)
    if cache is not None:
        cache[key] = out
    return out

