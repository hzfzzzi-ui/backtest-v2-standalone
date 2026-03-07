from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class FeatureMatrices:
    fast_ma: np.ndarray
    slow_ma: np.ndarray
    trend_fast_ma: np.ndarray
    trend_slow_ma: np.ndarray
    atr14: np.ndarray
    strength_ma: np.ndarray
    rsi: np.ndarray
    sma20: np.ndarray
    sma60: np.ndarray
    high_max20: np.ndarray
    low_min10: np.ndarray


def _ewm_mean_matrix(values: np.ndarray, span: int) -> np.ndarray:
    """EWM（指数加权）均值矩阵 — DataFrame 级别并行计算。"""
    return pd.DataFrame(values).ewm(span=int(span), min_periods=int(span)).mean().to_numpy(dtype=float)


def _rsi_matrix(close: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothed RSI 矩阵，列式计算。"""
    p = int(period)
    t, n = close.shape
    out = np.full((t, n), np.nan, dtype=float)
    for c in range(n):
        s = pd.Series(close[:, c], dtype=float)
        valid = s.notna()
        if int(valid.sum()) <= p:
            continue
        sv = s[valid].reset_index(drop=True)
        delta = sv.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)
        avg_gain = gain.ewm(alpha=1.0 / p, min_periods=p, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / p, min_periods=p, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - 100.0 / (1.0 + rs)
        idx = np.where(valid.to_numpy())[0]
        out[idx, c] = rsi.to_numpy(dtype=float)
    return out


def adx_matrix(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """向量化 ADX(period) 矩阵 — Wilder 平滑，逐列计算。

    支持 2D (T, N) 和 1D (T,) 输入。
    """
    p = int(period)
    squeeze = False
    if high.ndim == 1:
        high = high[:, np.newaxis]
        low = low[:, np.newaxis]
        close = close[:, np.newaxis]
        squeeze = True

    t, n = close.shape
    out = np.full((t, n), np.nan, dtype=float)

    for c in range(n):
        h = pd.Series(high[:, c], dtype=float)
        l = pd.Series(low[:, c], dtype=float)
        cl = pd.Series(close[:, c], dtype=float)

        valid = h.notna() & l.notna() & cl.notna()
        if int(valid.sum()) < 2 * p + 1:
            continue

        # 提取有效子序列
        h_v = h[valid].reset_index(drop=True)
        l_v = l[valid].reset_index(drop=True)
        cl_v = cl[valid].reset_index(drop=True)
        vlen = len(h_v)

        prev_c = cl_v.shift(1)
        prev_h = h_v.shift(1)
        prev_l = l_v.shift(1)

        # True Range
        tr = pd.concat([
            h_v - l_v,
            (h_v - prev_c).abs(),
            (l_v - prev_c).abs(),
        ], axis=1).max(axis=1)

        # +DM / -DM
        up_move = h_v - prev_h
        down_move = prev_l - l_v
        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), dtype=float)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), dtype=float)

        # Wilder 平滑（递推式）
        smooth_tr = np.full(vlen, np.nan, dtype=float)
        smooth_pdm = np.full(vlen, np.nan, dtype=float)
        smooth_mdm = np.full(vlen, np.nan, dtype=float)

        # 初始值 = 前 period 天的 sum（跳过第 0 行的 NaN）
        if vlen < p + 1:
            continue
        smooth_tr[p] = tr.iloc[1:p + 1].sum()
        smooth_pdm[p] = plus_dm.iloc[1:p + 1].sum()
        smooth_mdm[p] = minus_dm.iloc[1:p + 1].sum()

        for j in range(p + 1, vlen):
            smooth_tr[j] = smooth_tr[j - 1] - smooth_tr[j - 1] / p + tr.iloc[j]
            smooth_pdm[j] = smooth_pdm[j - 1] - smooth_pdm[j - 1] / p + plus_dm.iloc[j]
            smooth_mdm[j] = smooth_mdm[j - 1] - smooth_mdm[j - 1] / p + minus_dm.iloc[j]

        with np.errstate(divide="ignore", invalid="ignore"):
            plus_di = 100.0 * smooth_pdm / smooth_tr
            minus_di = 100.0 * smooth_mdm / smooth_tr
            dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)

        # ADX: Wilder 平滑 DX
        adx_arr = np.full(vlen, np.nan, dtype=float)
        # 初始 ADX = DX[p:2p] 的均值
        if vlen < 2 * p:
            continue
        first_adx_vals = dx[p:2 * p]
        valid_dx = first_adx_vals[~np.isnan(first_adx_vals)]
        if len(valid_dx) == 0:
            continue
        adx_arr[2 * p - 1] = np.mean(valid_dx)
        for j in range(2 * p, vlen):
            if np.isnan(dx[j]):
                adx_arr[j] = adx_arr[j - 1]
            else:
                adx_arr[j] = (adx_arr[j - 1] * (p - 1) + dx[j]) / p

        # 写回到原始索引
        idx = np.where(valid.to_numpy())[0]
        out[idx, c] = adx_arr

    if squeeze:
        return out[:, 0]
    return out


def _rolling_mean_matrix(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling mean 矩阵 — DataFrame 级别并行计算。"""
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).mean().to_numpy(dtype=float)


def _rolling_max_matrix(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling max 矩阵 — DataFrame 级别并行计算。"""
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).max().to_numpy(dtype=float)


def _rolling_min_matrix(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling min 矩阵 — DataFrame 级别并行计算。"""
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).min().to_numpy(dtype=float)


def compute_feature_matrices(
    *,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    fast: int = 5,
    slow: int = 20,
    trend_fast: int = 120,
    trend_slow: int = 200,
    atr_n: int = 14,
    strength_ma: int = 120,
    ma_type: str = "SMA",
    rsi_period: int = 6,
    v2_trend_short_ma: int = 20,
    v2_trend_long_ma: int = 60,
    breakout_window: int = 20,
    low10_exit_window: int = 10,
) -> FeatureMatrices:
    # 信号用均线：根据 ma_type 选择 SMA 或 EMA
    _ma_fn = _ewm_mean_matrix if str(ma_type).upper() == "EMA" else _rolling_mean_matrix
    fast_ma = _ma_fn(close, int(fast))
    slow_ma = _ma_fn(close, int(slow))
    trend_fast_ma = _rolling_mean_matrix(close, int(trend_fast))
    trend_slow_ma = _rolling_mean_matrix(close, int(trend_slow))
    strength_ma_m = _rolling_mean_matrix(close, int(strength_ma))
    t, n = close.shape
    w_atr = int(atr_n)
    # True Range 向量化：numpy 广播一次完成全矩阵
    prev_close = np.empty_like(close)
    prev_close[0, :] = np.nan
    prev_close[1:, :] = close[:-1, :]
    tr_m = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
    )
    # Rolling mean — DataFrame 级别并行
    atr = pd.DataFrame(tr_m).rolling(w_atr, min_periods=w_atr).mean().to_numpy(dtype=float)
    rsi = _rsi_matrix(close, int(rsi_period)) if int(rsi_period) > 0 else np.full((t, n), np.nan, dtype=float)
    sma20 = _rolling_mean_matrix(close, int(v2_trend_short_ma))
    sma60 = _rolling_mean_matrix(close, int(v2_trend_long_ma))
    high_max20 = _rolling_max_matrix(high, int(breakout_window))
    low_min10 = _rolling_min_matrix(low, int(low10_exit_window))
    return FeatureMatrices(
        fast_ma=fast_ma,
        slow_ma=slow_ma,
        trend_fast_ma=trend_fast_ma,
        trend_slow_ma=trend_slow_ma,
        atr14=atr,
        strength_ma=strength_ma_m,
        rsi=rsi,
        sma20=sma20,
        sma60=sma60,
        high_max20=high_max20,
        low_min10=low_min10,
    )


def compute_sector_eligible(
    *,
    sector_data: dict[str, pd.DataFrame],
    industry_map: dict[str, str],
    symbols: list[str],
    dates: np.ndarray,
    window: int = 60,
    top_pct: float = 0.30,
) -> np.ndarray:
    """Build sector_eligible matrix (T, N) bool.

    Ranks SW L1 sectors by ``window``-day return, daily cross-sectional.
    Stocks whose sector is in top ``top_pct`` get True.

    Edge cases handled per spec:
    - First ``window`` days: gate disabled (all True)
    - Sector with no data on a day: excluded from ranking
    - Stock with no industry mapping: False (excluded)
    """
    from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP

    t = len(dates)
    n = len(symbols)
    eligible = np.ones((t, n), dtype=bool)  # default True (gate disabled)

    if not sector_data or not industry_map:
        return eligible

    # --- Step 1: Build sector close time series aligned to dates ---
    # Reverse map: L1 name → index_code
    name_to_code = dict(SW_L1_INDEX_MAP)
    all_codes = sorted(set(name_to_code.values()) & set(sector_data.keys()))
    if not all_codes:
        return eligible

    date_to_idx: dict[pd.Timestamp, int] = {}
    for i_d, d in enumerate(dates):
        date_to_idx[pd.Timestamp(d).normalize()] = i_d

    s_count = len(all_codes)
    code_to_sidx = {c: j for j, c in enumerate(all_codes)}
    sector_close = np.full((t, s_count), np.nan, dtype=float)

    for code in all_codes:
        df = sector_data[code]
        sidx = code_to_sidx[code]
        date_col = "trade_date" if "trade_date" in df.columns else "date"
        for row in df.itertuples(index=False):
            ts = pd.Timestamp(getattr(row, date_col)).normalize()
            tidx = date_to_idx.get(ts)
            if tidx is not None:
                sector_close[tidx, sidx] = float(row.close)

    # --- Step 2: Compute window-day returns ---
    sector_ret = np.full((t, s_count), np.nan, dtype=float)
    if window < t:
        prev = sector_close[:-window, :]
        curr = sector_close[window:, :]
        safe_prev = np.where(np.abs(prev) > 1e-8, prev, np.nan)
        sector_ret[window:, :] = (curr - prev) / safe_prev

    # --- Step 3: Daily cross-sectional rank → eligible sectors ---
    cutoff_k = max(1, int(np.ceil(s_count * top_pct)))

    # Build stock → sector column index mapping
    sym_to_sidx: dict[str, int] = {}
    for sym in symbols:
        sym_lower = sym.lower()
        l1_name = industry_map.get(sym_lower)
        if l1_name is None:
            continue
        idx_code = name_to_code.get(l1_name)
        if idx_code is None:
            continue
        sidx = code_to_sidx.get(idx_code)
        if sidx is not None:
            sym_to_sidx[sym] = sidx

    sym_col_map = {sym: col for col, sym in enumerate(symbols)}

    for i_day in range(t):
        if i_day < window:
            # Gate disabled for first `window` days — keep all True
            continue

        day_rets = sector_ret[i_day, :]
        valid_mask = ~np.isnan(day_rets)
        if int(np.sum(valid_mask)) < 2:
            # Not enough sectors to rank — keep all True
            continue

        # Rank: top_pct sectors by return (highest = best)
        valid_indices = np.where(valid_mask)[0]
        valid_returns = day_rets[valid_indices]
        sorted_order = np.argsort(-valid_returns)  # descending
        top_sector_set = set(valid_indices[sorted_order[:cutoff_k]])

        # Apply gate: stock eligible only if its sector is in top set
        for sym, col in sym_col_map.items():
            sidx = sym_to_sidx.get(sym)
            if sidx is None:
                eligible[i_day, col] = False
            elif sidx not in top_sector_set:
                eligible[i_day, col] = False
            # else: stays True

    return eligible
