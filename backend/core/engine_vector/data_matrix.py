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


def _build_st_lookup(
    st_df: pd.DataFrame,
    sym_to_col: dict[str, int],
) -> dict[int, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """Build per-symbol ST period lookup: {col_index: [(start, end), ...]}."""
    lookup: dict[int, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    if st_df.empty:
        return lookup
    for row in st_df.itertuples(index=False):
        ts_code = str(getattr(row, "ts_code", "")).strip()
        # Convert TS format (600000.SH) to internal (sh600000)
        if "." in ts_code:
            code, exch = ts_code.split(".", 1)
            internal = exch.lower() + code
        else:
            internal = ts_code.lower()
        c = sym_to_col.get(internal)
        if c is None:
            continue
        s_date = pd.Timestamp(getattr(row, "start_date"))
        e_val = getattr(row, "end_date", None)
        e_date = pd.Timestamp(e_val) if pd.notna(e_val) else pd.Timestamp("2099-12-31")
        if c not in lookup:
            lookup[c] = []
        lookup[c].append((s_date, e_date))
    return lookup


def _is_in_st(
    lookup: dict[int, list[tuple[pd.Timestamp, pd.Timestamp]]],
    col: int,
    dt: pd.Timestamp,
) -> bool:
    periods = lookup.get(col)
    if not periods:
        return False
    for s, e in periods:
        if s <= dt <= e:
            return True
    return False


def build_ohlc_matrices_from_history(
    history: pd.DataFrame,
    trading_days: list[date],
    st_history: pd.DataFrame | None = None,
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

    has_suspended = "is_suspended" in hist.columns
    st_lookup = _build_st_lookup(st_history, sym_to_col) if st_history is not None and not st_history.empty else {}

    # 向量化行/列索引构建
    hist["_row"] = hist["date"].dt.normalize().map(date_to_row)
    hist["_col"] = hist["symbol"].map(sym_to_col)
    valid_mask = hist["_row"].notna() & hist["_col"].notna()
    v = hist.loc[valid_mask]
    r_arr = v["_row"].to_numpy(dtype=int)
    c_arr = v["_col"].to_numpy(dtype=int)

    # 批量赋值
    open_m[r_arr, c_arr] = pd.to_numeric(v["open"], errors="coerce").to_numpy(dtype=float)
    high_m[r_arr, c_arr] = pd.to_numeric(v["high"], errors="coerce").to_numpy(dtype=float)
    low_m[r_arr, c_arr] = pd.to_numeric(v["low"], errors="coerce").to_numpy(dtype=float)
    close_m[r_arr, c_arr] = pd.to_numeric(v["close"], errors="coerce").to_numpy(dtype=float)
    volume_m[r_arr, c_arr] = pd.to_numeric(v["volume"], errors="coerce").to_numpy(dtype=float)

    # tradable 向量化：valid OHLC + has volume
    ok_price = (
        ~np.isnan(close_m[r_arr, c_arr]) & (close_m[r_arr, c_arr] > 0)
        & ~np.isnan(open_m[r_arr, c_arr]) & (open_m[r_arr, c_arr] > 0)
    )
    ok_volume = ~np.isnan(volume_m[r_arr, c_arr]) & (volume_m[r_arr, c_arr] > 0)
    tradable[r_arr, c_arr] = ok_price & ok_volume

    # suspended 过滤（向量化）
    if has_suspended:
        susp_vals = v["is_suspended"]
        is_susp = susp_vals.notna() & susp_vals.astype(bool)
        if is_susp.any():
            susp_r = r_arr[is_susp.to_numpy()]
            susp_c = c_arr[is_susp.to_numpy()]
            tradable[susp_r, susp_c] = False

    # ST 过滤（按区间清除）
    if st_lookup:
        for col_idx, periods in st_lookup.items():
            for s_date, e_date in periods:
                row_mask = (dates >= s_date) & (dates <= e_date)
                tradable[row_mask, col_idx] = False

    # 清理临时列
    hist.drop(columns=["_row", "_col"], inplace=True)

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
    enable_st_filter: bool = True,
) -> OhlcMatrices:
    key = ("ohlc_mx", tuple(sorted([str(s).lower() for s in symbols])), str(start), str(end))
    if cache is not None and key in cache:
        return cache[key]
    history = provider.load_ohlcv_daily(symbols, start, end, source="stocks")
    cal = provider.load_trading_calendar_cn(start, end)
    days = [d.date() for d in cal]

    st_history = None
    if enable_st_filter:
        try:
            st_history = provider.load_st_history(symbols, start, end)
        except Exception:
            st_history = None

    out = build_ohlc_matrices_from_history(history, days, st_history=st_history)
    if cache is not None:
        cache[key] = out
    return out

