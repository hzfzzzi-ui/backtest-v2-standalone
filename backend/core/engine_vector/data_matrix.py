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


def _normalize_symbol_like(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "." in text:
        code, exch = text.split(".", 1)
        return f"{exch}{code}".lower()
    return text


def _build_st_lookup(
    st_df: pd.DataFrame,
    sym_to_col: dict[str, int],
) -> dict[int, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """Build per-symbol ST period lookup: {col_index: [(start, end), ...]}."""
    lookup: dict[int, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    if st_df.empty:
        return lookup
    for row in st_df.itertuples(index=False):
        internal = _normalize_symbol_like(getattr(row, "ts_code", ""))
        c = sym_to_col.get(internal)
        if c is None:
            continue
        s_date = pd.Timestamp(getattr(row, "start_date"))
        e_val = getattr(row, "end_date", None)
        e_date = pd.Timestamp(e_val) if pd.notna(e_val) else pd.Timestamp("2099-12-31")
        lookup.setdefault(c, []).append((s_date, e_date))
    return lookup


def _build_membership_lookup(
    membership_df: pd.DataFrame,
    sym_to_col: dict[str, int],
) -> dict[int, list[tuple[pd.Timestamp, pd.Timestamp | None]]]:
    lookup: dict[int, list[tuple[pd.Timestamp, pd.Timestamp | None]]] = {}
    if membership_df.empty:
        return lookup
    for row in membership_df.itertuples(index=False):
        internal = _normalize_symbol_like(getattr(row, "symbol", ""))
        c = sym_to_col.get(internal)
        if c is None:
            continue
        s_date = pd.Timestamp(getattr(row, "start_date"))
        e_val = getattr(row, "end_date", None)
        e_date = pd.Timestamp(e_val) if pd.notna(e_val) else None
        lookup.setdefault(c, []).append((s_date, e_date))
    return lookup


def _build_index_membership_mask(
    membership_df: pd.DataFrame,
    sym_to_col: dict[str, int],
    dates: pd.DatetimeIndex,
    *,
    index_code: str,
) -> np.ndarray:
    mask = np.zeros((len(dates), len(sym_to_col)), dtype=bool)
    if membership_df.empty or "index_code" not in membership_df.columns:
        return mask
    target = str(index_code or "").strip().upper()
    if not target:
        return mask
    for row in membership_df.itertuples(index=False):
        if str(getattr(row, "index_code", "") or "").strip().upper() != target:
            continue
        internal = _normalize_symbol_like(getattr(row, "symbol", ""))
        c = sym_to_col.get(internal)
        if c is None:
            continue
        s_date = pd.Timestamp(getattr(row, "start_date"))
        e_val = getattr(row, "end_date", None)
        e_date = pd.Timestamp(e_val) if pd.notna(e_val) else None
        if e_date is None:
            row_mask = dates >= s_date
        else:
            row_mask = (dates >= s_date) & (dates < e_date)
        mask[row_mask, c] = True
    return mask


def build_ohlc_matrices_from_history(
    history: pd.DataFrame,
    trading_days: list[date],
    st_history: pd.DataFrame | None = None,
    membership_history: pd.DataFrame | None = None,
    min_price: float = 0.0,
    min_list_days: int = 0,
    min_avg_turnover_20d: float = 0.0,
    csi1000_new_min_circ_mv_yi: float = 0.0,
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
    amount_m = np.full((t, n), np.nan, dtype=float)
    circ_mv_m = np.full((t, n), np.nan, dtype=float)
    tradable = np.zeros((t, n), dtype=bool)

    has_suspended = "is_suspended" in hist.columns
    has_is_st = "is_st" in hist.columns
    st_lookup = _build_st_lookup(st_history, sym_to_col) if st_history is not None and not st_history.empty else {}
    membership_lookup = (
        _build_membership_lookup(membership_history, sym_to_col)
        if membership_history is not None and not membership_history.empty
        else {}
    )

    hist["_row"] = hist["date"].dt.normalize().map(date_to_row)
    hist["_col"] = hist["symbol"].map(sym_to_col)
    valid_mask = hist["_row"].notna() & hist["_col"].notna()
    v = hist.loc[valid_mask]
    r_arr = v["_row"].to_numpy(dtype=int)
    c_arr = v["_col"].to_numpy(dtype=int)

    open_m[r_arr, c_arr] = pd.to_numeric(v["open"], errors="coerce").to_numpy(dtype=float)
    high_m[r_arr, c_arr] = pd.to_numeric(v["high"], errors="coerce").to_numpy(dtype=float)
    low_m[r_arr, c_arr] = pd.to_numeric(v["low"], errors="coerce").to_numpy(dtype=float)
    close_m[r_arr, c_arr] = pd.to_numeric(v["close"], errors="coerce").to_numpy(dtype=float)
    volume_m[r_arr, c_arr] = pd.to_numeric(v["volume"], errors="coerce").to_numpy(dtype=float)
    if "amount" in v.columns:
        amount_m[r_arr, c_arr] = pd.to_numeric(v["amount"], errors="coerce").to_numpy(dtype=float)
    elif "turnover" in v.columns:
        amount_m[r_arr, c_arr] = pd.to_numeric(v["turnover"], errors="coerce").to_numpy(dtype=float)
    else:
        amount_m[r_arr, c_arr] = close_m[r_arr, c_arr] * volume_m[r_arr, c_arr]
    if "circ_mv" in v.columns:
        circ_mv_m[r_arr, c_arr] = pd.to_numeric(v["circ_mv"], errors="coerce").to_numpy(dtype=float)

    ok_price = (
        ~np.isnan(close_m[r_arr, c_arr]) & (close_m[r_arr, c_arr] > 0)
        & ~np.isnan(open_m[r_arr, c_arr]) & (open_m[r_arr, c_arr] > 0)
    )
    ok_volume = ~np.isnan(volume_m[r_arr, c_arr]) & (volume_m[r_arr, c_arr] > 0)
    tradable[r_arr, c_arr] = ok_price & ok_volume

    if has_suspended:
        susp_vals = v["is_suspended"]
        is_susp = susp_vals.notna() & susp_vals.astype(bool)
        if is_susp.any():
            susp_r = r_arr[is_susp.to_numpy()]
            susp_c = c_arr[is_susp.to_numpy()]
            tradable[susp_r, susp_c] = False

    if has_is_st:
        st_vals = v["is_st"]
        is_st = st_vals.notna() & st_vals.astype(bool)
        if is_st.any():
            st_r = r_arr[is_st.to_numpy()]
            st_c = c_arr[is_st.to_numpy()]
            tradable[st_r, st_c] = False

    if min_price > 0:
        tradable &= ~(close_m < min_price) | np.isnan(close_m)

    if int(min_list_days) > 0 and t > 0 and n > 0:
        has_bar = ~np.isnan(close_m)
        first_idx = np.full(n, -1, dtype=int)
        for c in range(n):
            idxs = np.flatnonzero(has_bar[:, c])
            if idxs.size > 0:
                first_idx[c] = int(idxs[0])
        for c in range(n):
            fi = int(first_idx[c])
            if fi < 0:
                tradable[:, c] = False
                continue
            tradable[np.arange(t, dtype=int) < (fi + int(min_list_days) - 1), c] = False

    if float(min_avg_turnover_20d) > 0 and t > 0 and n > 0:
        amt20 = pd.DataFrame(amount_m).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
        tradable &= (~np.isnan(amt20)) & (amt20 >= float(min_avg_turnover_20d))

    if st_lookup:
        for col_idx, periods in st_lookup.items():
            for s_date, e_date in periods:
                row_mask = (dates >= s_date) & (dates <= e_date)
                tradable[row_mask, col_idx] = False

    if membership_lookup:
        membership_mask = np.zeros((t, n), dtype=bool)
        for col_idx, periods in membership_lookup.items():
            col_mask = np.zeros(t, dtype=bool)
            for s_date, e_date in periods:
                if e_date is None:
                    row_mask = dates >= s_date
                else:
                    row_mask = (dates >= s_date) & (dates < e_date)
                col_mask |= row_mask
            membership_mask[:, col_idx] = col_mask
        tradable &= membership_mask

    try:
        min_csi1000_new_circ_mv_yi = float(csi1000_new_min_circ_mv_yi or 0.0)
    except Exception:
        min_csi1000_new_circ_mv_yi = 0.0
    if min_csi1000_new_circ_mv_yi > 0 and membership_history is not None and not membership_history.empty:
        csi800_mask = _build_index_membership_mask(
            membership_history,
            sym_to_col,
            dates,
            index_code="000906.SH",
        )
        csi1000_mask = _build_index_membership_mask(
            membership_history,
            sym_to_col,
            dates,
            index_code="000852.SH",
        )
        csi1000_new_mask = csi1000_mask & ~csi800_mask
        if bool(csi1000_new_mask.any()):
            # circ_mv uses the Tushare daily_basic convention: 10k CNY.
            threshold_wan_cny = float(min_csi1000_new_circ_mv_yi) * 10000.0
            low_or_missing_mcap = np.isnan(circ_mv_m) | (circ_mv_m < threshold_wan_cny)
            tradable[csi1000_new_mask & low_or_missing_mcap] = False

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
    min_price: float = 0.0,
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

    out = build_ohlc_matrices_from_history(history, days, st_history=st_history, min_price=min_price)
    if cache is not None:
        cache[key] = out
    return out
