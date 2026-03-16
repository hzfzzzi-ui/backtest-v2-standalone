"""Shared matrix helpers for breakout signal providers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_max_matrix(values: np.ndarray, window: int) -> np.ndarray:
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).max().to_numpy(dtype=float)


def rolling_min_matrix(values: np.ndarray, window: int) -> np.ndarray:
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).min().to_numpy(dtype=float)


def rolling_any(mask: np.ndarray, window: int) -> np.ndarray:
    rolled = pd.DataFrame(mask.astype(float)).rolling(int(window), min_periods=1).max().to_numpy(dtype=float)
    return rolled > 0


def return_matrix(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    w = int(window)
    if w <= 0 or values.shape[0] <= w:
        return out
    prev = values[:-w, :]
    curr = values[w:, :]
    safe_prev = np.where(prev > 1e-8, prev, np.nan)
    out[w:, :] = curr / safe_prev - 1.0
    return out


def return_series(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    w = int(window)
    if w <= 0 or values.shape[0] <= w:
        return out
    prev = values[:-w]
    curr = values[w:]
    safe_prev = np.where(prev > 1e-8, prev, np.nan)
    out[w:] = curr / safe_prev - 1.0
    return out


def row_rank_pct(values: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    row_count = int(values.shape[0])
    for i in range(row_count):
        row = values[i, :]
        row_valid = valid_mask[i, :] & ~np.isnan(row)
        idx = np.flatnonzero(row_valid)
        count = int(idx.size)
        if count == 0:
            continue
        if count == 1:
            out[i, idx[0]] = 0.5
            continue
        order = np.argsort(row[idx], kind="mergesort")
        ranks = np.empty(count, dtype=float)
        denom = float(max(count - 1, 1))
        ranks[order] = np.arange(count, dtype=float) / denom
        out[i, idx] = ranks
    return out


def row_bucket_code(values: np.ndarray, valid_mask: np.ndarray, bucket_count: int) -> tuple[np.ndarray, np.ndarray]:
    rank_pct = row_rank_pct(values, valid_mask)
    buckets = np.full(values.shape, -1, dtype=int)
    if int(bucket_count) < 2:
        return rank_pct, buckets
    valid = valid_mask & ~np.isnan(rank_pct)
    if not np.any(valid):
        return rank_pct, buckets
    ranked_valid = np.floor(rank_pct[valid] * float(bucket_count)).astype(int)
    ranked_valid = np.clip(ranked_valid, 0, int(bucket_count) - 1)
    buckets[valid] = ranked_valid
    return rank_pct, buckets


def weighted_score(components: list[tuple[np.ndarray, float]], shape: tuple[int, int]) -> np.ndarray:
    score = np.zeros(shape, dtype=float)
    weight_sum = np.zeros(shape, dtype=float)
    for matrix, weight in components:
        if float(weight) <= 0:
            continue
        valid = ~np.isnan(matrix)
        score[valid] += matrix[valid] * float(weight)
        weight_sum[valid] += float(weight)
    out = np.full(shape, np.nan, dtype=float)
    ok = weight_sum > 1e-12
    out[ok] = score[ok] / weight_sum[ok]
    return out


def normalize_industry_history(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    for col in ("ts_code", "industry_l1", "industry_l2", "standard"):
        if col not in out.columns:
            out[col] = None
    out["ts_code"] = out["ts_code"].astype(str).str.lower()
    out["industry_l1"] = out["industry_l1"].astype(str)
    out["industry_l2"] = out["industry_l2"].astype(str)
    out["standard"] = out["standard"].astype(str)
    out["start_date"] = pd.to_datetime(out["start_date"], errors="coerce").dt.normalize()
    if "end_date" in out.columns:
        out["end_date"] = pd.to_datetime(out["end_date"], errors="coerce").dt.normalize()
    else:
        out["end_date"] = pd.NaT
    out = out.dropna(subset=["ts_code", "start_date", "industry_l1"])
    return out.sort_values(["ts_code", "start_date"]).reset_index(drop=True)


def build_industry_assignment_matrices(
    *,
    industry_map: dict[str, str] | None,
    industry_history: pd.DataFrame | None,
    sector_data: dict[str, pd.DataFrame] | None,
    symbols: list[str],
    dates: np.ndarray,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    if not symbols or len(dates) == 0:
        return None, None
    if not industry_map and (industry_history is None or industry_history.empty):
        return None, None

    row_count = int(len(dates))
    col_count = int(len(symbols))
    name_matrix = np.empty((row_count, col_count), dtype=object)
    name_matrix[:, :] = None
    index_code_matrix = np.empty((row_count, col_count), dtype=object)
    index_code_matrix[:, :] = None

    symbol_to_col = {str(sym).lower(): idx for idx, sym in enumerate(symbols)}

    hist = normalize_industry_history(industry_history)
    if hist.empty:
        if not industry_map:
            return None, None
        from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP

        for sym, industry_name in dict(industry_map).items():
            col_idx = symbol_to_col.get(str(sym).lower())
            if col_idx is None or industry_name is None:
                continue
            sector_name = str(industry_name)
            name_matrix[:, col_idx] = sector_name
            code = SW_L1_INDEX_MAP.get(sector_name)
            if code is not None:
                index_code_matrix[:, col_idx] = code
        return name_matrix, index_code_matrix

    date_index = pd.DatetimeIndex(pd.to_datetime(dates, errors="coerce")).normalize()
    if date_index.empty:
        return None, None
    date_start = date_index[0]
    date_end = date_index[-1]
    hist = hist[hist["ts_code"].isin(symbol_to_col.keys())].copy()
    hist = hist[(hist["start_date"] <= date_end) & (hist["end_date"].isna() | (hist["end_date"] > date_start))]
    if hist.empty:
        return None, None

    from backend.core.universe.ingest_universe import resolve_sw_index_code_from_industry_code

    code_available_start_idx: dict[str, int] = {}
    for code, df in (sector_data or {}).items():
        if df is None or df.empty:
            continue
        date_col = "trade_date" if "trade_date" in df.columns else "date"
        if date_col not in df.columns:
            continue
        code_dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if code_dates.empty:
            continue
        code_available_start_idx[str(code).upper()] = int(date_index.searchsorted(code_dates.min().normalize(), side="left"))

    for sym, group in hist.groupby("ts_code", sort=False):
        col_idx = symbol_to_col.get(str(sym).lower())
        if col_idx is None:
            continue
        prev_code: str | None = None
        for row in group.itertuples(index=False):
            start_ts = pd.Timestamp(getattr(row, "start_date")).normalize()
            end_raw = getattr(row, "end_date", pd.NaT)
            end_ts = None if pd.isna(end_raw) else pd.Timestamp(end_raw).normalize()
            start_idx = int(date_index.searchsorted(start_ts, side="left"))
            end_idx = int(date_index.searchsorted(end_ts, side="left")) if end_ts is not None else row_count
            if start_idx >= row_count or start_idx >= end_idx:
                continue
            name_matrix[start_idx:end_idx, col_idx] = str(getattr(row, "industry_l1"))

            primary_code = resolve_sw_index_code_from_industry_code(getattr(row, "industry_l2", ""))
            if primary_code is None:
                continue
            primary_code = str(primary_code).upper()
            available_start_idx = code_available_start_idx.get(primary_code)

            if available_start_idx is None:
                if prev_code is not None:
                    index_code_matrix[start_idx:end_idx, col_idx] = prev_code
                prev_code = primary_code
                continue

            bridge_end_idx = min(end_idx, max(start_idx, int(available_start_idx)))
            if bridge_end_idx > start_idx and prev_code is not None:
                index_code_matrix[start_idx:bridge_end_idx, col_idx] = prev_code
            fill_start_idx = max(start_idx, int(available_start_idx))
            if fill_start_idx < end_idx:
                index_code_matrix[fill_start_idx:end_idx, col_idx] = primary_code
            prev_code = primary_code
    return name_matrix, index_code_matrix


def normalize_history_like(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.lower()
    return out.sort_values(["date", "symbol"]).reset_index(drop=True)


_rolling_any = rolling_any
_return_matrix = return_matrix
_return_series = return_series
_row_rank_pct = row_rank_pct
_weighted_score = weighted_score
_rolling_max_matrix = rolling_max_matrix
_rolling_min_matrix = rolling_min_matrix
_normalize_history_like = normalize_history_like
_build_industry_assignment_matrices = build_industry_assignment_matrices


def aligned_numeric_matrix(
    frame: pd.DataFrame,
    *,
    dates: np.ndarray,
    symbols: list[str],
    column: str,
) -> np.ndarray:
    shape = (len(dates), len(symbols))
    if frame.empty or column not in frame.columns or not symbols:
        return np.full(shape, np.nan, dtype=float)
    date_index = pd.to_datetime(pd.Index(dates)).normalize()
    pivot = (
        frame.pivot_table(index="date", columns="symbol", values=column, aggfunc="last")
        .reindex(index=date_index, columns=symbols)
    )
    return pivot.to_numpy(dtype=float)


_aligned_numeric_matrix = aligned_numeric_matrix

def _compute_conditional_tiebreak_matrices(
    *,
    raw_history: pd.DataFrame | None,
    dates: np.ndarray,
    symbols: list[str],
    tradable: np.ndarray,
    adj_close: np.ndarray,
    breakout_quality_score: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    shape = adj_close.shape
    neutral = np.full(shape, 0.5, dtype=float)
    recent_limit_hit_3d = np.zeros(shape, dtype=bool)
    near_limit_up = np.zeros(shape, dtype=bool)
    normalized = _normalize_history_like(raw_history)
    if normalized.empty or not symbols:
        return neutral.copy(), neutral.copy(), neutral.copy(), neutral.copy(), recent_limit_hit_3d, near_limit_up

    amount = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="amount")
    if np.isnan(amount).all():
        turnover = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="turnover")
        volume = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="volume")
        close_raw = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="close")
        amount = np.where(~np.isnan(turnover), turnover, close_raw * volume)
    else:
        close_raw = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="close")
    high_raw = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="high")
    limit_up = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="limit_up")
    circ_mv = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="circ_mv")
    turnover_rate_f = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="turnover_rate_f")
    turnover_rate = _aligned_numeric_matrix(normalized, dates=dates, symbols=symbols, column="turnover_rate")

    turnover_proxy = np.where(~np.isnan(turnover_rate_f), turnover_rate_f, turnover_rate)
    inst_mcap_proxy = circ_mv.copy()
    fallback_mask = np.isnan(inst_mcap_proxy) & (turnover_proxy > 1e-8)
    inst_mcap_proxy[fallback_mask] = amount[fallback_mask] * 100.0 / turnover_proxy[fallback_mask]
    amount20 = pd.DataFrame(amount).rolling(20, min_periods=15).mean().to_numpy(dtype=float)

    valid_limit = ~np.isnan(limit_up) & (limit_up > 1e-8)
    near_limit_up = valid_limit & (
        ((high_raw / limit_up) >= 0.995)
        | ((close_raw / limit_up) >= 0.985)
    )
    limit_hit_up = valid_limit & (
        ((high_raw / limit_up) >= 0.999)
        | ((close_raw / limit_up) >= 0.999)
    )
    recent_limit_hit_3d = _rolling_any(limit_hit_up, 3)

    adj_ret40 = _return_matrix(adj_close, 40)
    adj_daily_ret = np.full(shape, np.nan, dtype=float)
    if shape[0] > 1:
        prev_close = adj_close[:-1, :]
        curr_close = adj_close[1:, :]
        safe_prev = np.where(prev_close > 1e-8, prev_close, np.nan)
        adj_daily_ret[1:, :] = curr_close / safe_prev - 1.0
    vol20 = pd.DataFrame(adj_daily_ret).rolling(20, min_periods=15).std().to_numpy(dtype=float)

    inst_valid = tradable & ~np.isnan(inst_mcap_proxy) & ~np.isnan(amount20)
    inst_rank_size = _row_rank_pct(inst_mcap_proxy, inst_valid)
    inst_rank_liq = _row_rank_pct(amount20, inst_valid)
    inst_proxy_score = _weighted_score(
        [(inst_rank_size, 0.5), (inst_rank_liq, 0.5)],
        shape=shape,
    )
    inst_proxy_score = np.where(np.isnan(inst_proxy_score), 0.5, inst_proxy_score)

    factor_leader_score = np.full(shape, 0.5, dtype=float)
    style_valid = tradable & ~np.isnan(inst_mcap_proxy) & ~np.isnan(amount20) & ~np.isnan(vol20) & ~np.isnan(adj_ret40)
    row_count = int(shape[0])
    for i in range(row_count):
        idx = np.flatnonzero(style_valid[i, :])
        count = int(idx.size)
        if count < 3:
            continue
        size_vals = inst_mcap_proxy[i, idx]
        liq_vals = amount20[i, idx]
        vol_vals = vol20[i, idx]
        ret_vals = adj_ret40[i, idx]
        size_cut = float(np.nanmedian(size_vals))
        liq_cut = float(np.nanmedian(liq_vals))
        vol_cut = float(np.nanmedian(vol_vals))
        bucket_codes = (
            (size_vals >= size_cut).astype(int) * 4
            + (liq_vals >= liq_cut).astype(int) * 2
            + (vol_vals <= vol_cut).astype(int)
        )
        unique_codes = np.unique(bucket_codes)
        bucket_scores: dict[int, float] = {}
        if unique_codes.size == 1:
            bucket_scores[int(unique_codes[0])] = 0.5
        else:
            bucket_ret = np.array(
                [float(np.nanmean(ret_vals[bucket_codes == code])) for code in unique_codes],
                dtype=float,
            )
            order = np.argsort(bucket_ret, kind="mergesort")
            ranks = np.empty(unique_codes.size, dtype=float)
            ranks[order] = np.arange(unique_codes.size, dtype=float) / float(max(unique_codes.size - 1, 1))
            bucket_scores = {int(code): float(rank) for code, rank in zip(unique_codes, ranks)}
        factor_leader_score[i, idx] = np.array(
            [bucket_scores.get(int(code), 0.5) for code in bucket_codes],
            dtype=float,
        )

    supportive_score = _weighted_score(
        [(factor_leader_score, 0.5), (inst_proxy_score, 0.5)],
        shape=shape,
    )
    supportive_score = np.where(np.isnan(supportive_score), 0.5, supportive_score)
    crowding_score = np.full(shape, 0.5, dtype=float)
    crowding_mask = near_limit_up | recent_limit_hit_3d
    crowding_score[crowding_mask] = supportive_score[crowding_mask]

    quality_safe = np.where(np.isnan(breakout_quality_score), 0.5, breakout_quality_score)
    conditional_tiebreak_score = _weighted_score(
        [
            (quality_safe, 0.40),
            (factor_leader_score, 0.30),
            (inst_proxy_score, 0.20),
            (crowding_score, 0.10),
        ],
        shape=shape,
    )
    conditional_tiebreak_score = np.where(np.isnan(conditional_tiebreak_score), 0.5, conditional_tiebreak_score)
    return (
        conditional_tiebreak_score,
        factor_leader_score,
        inst_proxy_score,
        crowding_score,
        recent_limit_hit_3d,
        near_limit_up,
    )


def _compute_industry_second_stage_matrices(
    *,
    tradable: np.ndarray,
    adj_close: np.ndarray,
    industry_map: dict[str, str] | None,
    industry_name_matrix: np.ndarray | None,
    symbols: list[str],
    breakout_margin_raw: np.ndarray,
    breakout_quality_score: np.ndarray,
    recent_limit_hit_3d: np.ndarray,
    near_limit_up: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    shape = adj_close.shape
    neutral = np.full(shape, 0.5, dtype=float)
    if not symbols or (industry_name_matrix is None and not industry_map):
        return neutral.copy(), neutral.copy(), neutral.copy(), neutral.copy(), neutral.copy()

    ret10 = _return_matrix(adj_close, 10)
    ret20 = _return_matrix(adj_close, 20)
    ret40 = _return_matrix(adj_close, 40)
    ma20 = pd.DataFrame(adj_close).rolling(20, min_periods=15).mean().to_numpy(dtype=float)
    distance_to_ma20 = np.full(shape, np.nan, dtype=float)
    valid_ma20 = ~np.isnan(adj_close) & ~np.isnan(ma20) & (ma20 > 1e-8)
    distance_to_ma20[valid_ma20] = adj_close[valid_ma20] / ma20[valid_ma20] - 1.0

    adj_daily_ret = np.full(shape, np.nan, dtype=float)
    if shape[0] > 1:
        prev_close = adj_close[:-1, :]
        curr_close = adj_close[1:, :]
        safe_prev = np.where(prev_close > 1e-8, prev_close, np.nan)
        adj_daily_ret[1:, :] = curr_close / safe_prev - 1.0
    vol20 = pd.DataFrame(adj_daily_ret).rolling(20, min_periods=15).std().to_numpy(dtype=float)
    vol60 = pd.DataFrame(adj_daily_ret).rolling(60, min_periods=40).std().to_numpy(dtype=float)
    vol_expansion = np.full(shape, np.nan, dtype=float)
    valid_vol = ~np.isnan(vol20) & ~np.isnan(vol60) & (vol60 > 1e-8)
    vol_expansion[valid_vol] = vol20[valid_vol] / vol60[valid_vol] - 1.0

    industry_rank_pct = _compute_industry_rank_pct_matrix(
        stock_ret=ret40,
        tradable=tradable,
        industry_map=industry_map if isinstance(industry_map, dict) else None,
        industry_name_matrix=industry_name_matrix,
        symbols=symbols,
    )
    industry_top_flag = np.zeros(shape, dtype=float)
    valid_rank = ~np.isnan(industry_rank_pct)
    industry_top_flag[valid_rank] = (industry_rank_pct[valid_rank] >= 0.7).astype(float)
    persistence_10d = pd.DataFrame(industry_top_flag).rolling(10, min_periods=5).mean().to_numpy(dtype=float)

    industry_labels_static: np.ndarray | None = None
    if industry_name_matrix is None and industry_map:
        industry_labels_static = np.array(
            [industry_map.get(str(sym).lower()) for sym in symbols],
            dtype=object,
        )

    breadth_level = np.full(shape, np.nan, dtype=float)
    industry_breadth_by_day: dict[str, np.ndarray] = {}
    row_count, col_count = shape
    for row_idx in range(int(row_count)):
        labels = industry_name_matrix[row_idx, :] if industry_name_matrix is not None else industry_labels_static
        if labels is None:
            continue
        row_groups: dict[str, list[int]] = {}
        for col_idx in range(int(col_count)):
            if not bool(tradable[row_idx, col_idx]):
                continue
            label = labels[col_idx]
            if label is None or (isinstance(label, float) and np.isnan(label)):
                continue
            if not np.isfinite(ret20[row_idx, col_idx]):
                continue
            row_groups.setdefault(str(label), []).append(col_idx)
        for label, cols in row_groups.items():
            if not cols:
                continue
            vals = ret20[row_idx, cols]
            breadth = float(np.nanmean(vals > 0.0))
            if not np.isfinite(breadth):
                continue
            breadth_level[row_idx, cols] = breadth
            series = industry_breadth_by_day.get(label)
            if series is None:
                series = np.full(row_count, np.nan, dtype=float)
                industry_breadth_by_day[label] = series
            series[row_idx] = breadth

    breadth_change_10d = np.full(shape, np.nan, dtype=float)
    for label, series in industry_breadth_by_day.items():
        diff = pd.Series(series).diff(10).to_numpy(dtype=float)
        if industry_name_matrix is not None:
            mask = industry_name_matrix == label
        else:
            mask = np.tile(industry_labels_static == label, (row_count, 1))
        if np.any(mask):
            breadth_change_10d[mask] = np.broadcast_to(diff.reshape(-1, 1), shape)[mask]

    quality_safe = np.where(np.isnan(breakout_quality_score), 0.5, breakout_quality_score)
    hot_margin_score = _row_rank_pct(-breakout_margin_raw, tradable)
    hot_ret10_score = _row_rank_pct(-ret10, tradable)
    hot_ma20_score = _row_rank_pct(-distance_to_ma20, tradable)
    not_hot_score = _weighted_score(
        [
            (hot_margin_score, 0.40),
            (hot_ret10_score, 0.30),
            (hot_ma20_score, 0.30),
        ],
        shape=shape,
    )
    not_hot_score = np.where(np.isnan(not_hot_score), 0.5, not_hot_score)

    vol_cool_score = _row_rank_pct(-vol_expansion, tradable)
    uncrowded_binary = np.ones(shape, dtype=float)
    uncrowded_binary[recent_limit_hit_3d] -= 0.5
    uncrowded_binary[near_limit_up] -= 0.5
    uncrowded_binary = np.clip(uncrowded_binary, 0.0, 1.0)
    uncrowded_score = _weighted_score(
        [
            (vol_cool_score, 0.60),
            (uncrowded_binary, 0.40),
        ],
        shape=shape,
    )
    uncrowded_score = np.where(np.isnan(uncrowded_score), 0.5, uncrowded_score)

    breadth_timing_score = _row_rank_pct(-breadth_change_10d, tradable)
    breadth_timing_score = np.where(np.isnan(breadth_timing_score), 0.5, breadth_timing_score)
    persistence_safe = np.where(np.isnan(persistence_10d), 0.5, persistence_10d)

    industry_second_stage_score = _weighted_score(
        [
            (quality_safe, 0.20),
            (not_hot_score, 0.25),
            (uncrowded_score, 0.20),
            (breadth_timing_score, 0.15),
            (persistence_safe, 0.20),
        ],
        shape=shape,
    )
    industry_second_stage_score = np.where(np.isnan(industry_second_stage_score), 0.5, industry_second_stage_score)
    return (
        industry_second_stage_score,
        not_hot_score,
        uncrowded_score,
        breadth_timing_score,
        persistence_safe,
    )


def _build_sector_feature_matrices(
    *,
    sector_data: dict[str, pd.DataFrame] | None,
    industry_map: dict[str, str] | None,
    industry_name_matrix: np.ndarray | None,
    industry_index_code_matrix: np.ndarray | None,
    symbols: list[str],
    dates: np.ndarray,
    short_window: int,
    long_window: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sector_ret_short = np.full((len(dates), len(symbols)), np.nan, dtype=float)
    sector_ret_long = np.full((len(dates), len(symbols)), np.nan, dtype=float)
    sector_trend = np.full((len(dates), len(symbols)), np.nan, dtype=float)
    if not sector_data or not symbols or (
        industry_name_matrix is None and industry_index_code_matrix is None and not industry_map
    ):
        return sector_ret_short, sector_ret_long, sector_trend

    from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP

    name_to_code = dict(SW_L1_INDEX_MAP)
    available_codes = sorted(set(str(k).upper() for k in sector_data.keys()))
    if not available_codes:
        return sector_ret_short, sector_ret_long, sector_trend

    date_to_idx = {pd.Timestamp(d).normalize(): i for i, d in enumerate(dates)}
    code_to_col = {code: idx for idx, code in enumerate(available_codes)}
    sector_close = np.full((len(dates), len(available_codes)), np.nan, dtype=float)

    for code in available_codes:
        df = sector_data.get(code)
        if df is None or df.empty:
            continue
        date_col = "trade_date" if "trade_date" in df.columns else "date"
        if date_col not in df.columns or "close" not in df.columns:
            continue
        col_idx = code_to_col[code]
        for row in df.itertuples(index=False):
            ts = pd.Timestamp(getattr(row, date_col)).normalize()
            row_idx = date_to_idx.get(ts)
            if row_idx is None:
                continue
            try:
                sector_close[row_idx, col_idx] = float(getattr(row, "close"))
            except Exception:
                continue

    sector_ret_short_raw = _return_matrix(sector_close, int(short_window))
    sector_ret_long_raw = _return_matrix(sector_close, int(long_window))
    sector_ma20 = pd.DataFrame(sector_close).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
    sector_ma60 = pd.DataFrame(sector_close).rolling(60, min_periods=60).mean().to_numpy(dtype=float)
    sector_trend_raw = np.where(
        (~np.isnan(sector_close)) & (~np.isnan(sector_ma20)) & (~np.isnan(sector_ma60)),
        ((sector_close > sector_ma20).astype(float) + (sector_ma20 > sector_ma60).astype(float)) / 2.0,
        np.nan,
    )

    if industry_index_code_matrix is not None:
        sector_col_matrix = np.full(industry_index_code_matrix.shape, -1, dtype=int)
        for code in available_codes:
            col_idx = code_to_col.get(code)
            if col_idx is None:
                continue
            mask = industry_index_code_matrix == code
            if np.any(mask):
                sector_col_matrix[mask] = int(col_idx)
        valid = sector_col_matrix >= 0
        if np.any(valid):
            row_idx, sym_idx = np.where(valid)
            sector_cols = sector_col_matrix[valid]
            sector_ret_short[valid] = sector_ret_short_raw[row_idx, sector_cols]
            sector_ret_long[valid] = sector_ret_long_raw[row_idx, sector_cols]
            sector_trend[valid] = sector_trend_raw[row_idx, sector_cols]
        return sector_ret_short, sector_ret_long, sector_trend

    if industry_name_matrix is not None:
        sector_col_matrix = np.full(industry_name_matrix.shape, -1, dtype=int)
        for sector_name, code in name_to_code.items():
            col_idx = code_to_col.get(code)
            if col_idx is None:
                continue
            mask = industry_name_matrix == sector_name
            if np.any(mask):
                sector_col_matrix[mask] = int(col_idx)
        valid = sector_col_matrix >= 0
        if np.any(valid):
            row_idx, sym_idx = np.where(valid)
            sector_cols = sector_col_matrix[valid]
            sector_ret_short[valid] = sector_ret_short_raw[row_idx, sector_cols]
            sector_ret_long[valid] = sector_ret_long_raw[row_idx, sector_cols]
            sector_trend[valid] = sector_trend_raw[row_idx, sector_cols]
        return sector_ret_short, sector_ret_long, sector_trend

    sym_to_sector_col: dict[str, int] = {}
    for sym in symbols:
        sector_name = industry_map.get(str(sym).lower()) if industry_map else None
        code = name_to_code.get(str(sector_name)) if sector_name is not None else None
        if code is None:
            continue
        col_idx = code_to_col.get(code)
        if col_idx is not None:
            sym_to_sector_col[str(sym)] = col_idx

    for sym_idx, sym in enumerate(symbols):
        sector_col = sym_to_sector_col.get(str(sym))
        if sector_col is None:
            continue
        sector_ret_short[:, sym_idx] = sector_ret_short_raw[:, sector_col]
        sector_ret_long[:, sym_idx] = sector_ret_long_raw[:, sector_col]
        sector_trend[:, sym_idx] = sector_trend_raw[:, sector_col]
    return sector_ret_short, sector_ret_long, sector_trend


def _compute_industry_rank_pct_matrix(
    *,
    stock_ret: np.ndarray,
    tradable: np.ndarray,
    industry_map: dict[str, str] | None,
    industry_name_matrix: np.ndarray | None,
    symbols: list[str],
) -> np.ndarray:
    industry_rank_pct = np.full(stock_ret.shape, np.nan, dtype=float)
    if not symbols or (industry_name_matrix is None and not industry_map):
        return industry_rank_pct

    if industry_name_matrix is not None:
        row_count, col_count = stock_ret.shape
        for row_idx in range(int(row_count)):
            labels = industry_name_matrix[row_idx, :]
            row_industry_to_cols: dict[str, list[int]] = {}
            for col_idx in range(int(col_count)):
                label = labels[col_idx]
                if label is None or (isinstance(label, float) and np.isnan(label)):
                    continue
                row_industry_to_cols.setdefault(str(label), []).append(int(col_idx))
            for cols in row_industry_to_cols.values():
                col_arr = np.asarray(cols, dtype=int)
                group_ret = stock_ret[row_idx : row_idx + 1, col_arr]
                group_valid = tradable[row_idx : row_idx + 1, col_arr] & ~np.isnan(group_ret)
                group_rank = _row_rank_pct(group_ret, group_valid)
                industry_rank_pct[row_idx : row_idx + 1, col_arr] = group_rank
        return industry_rank_pct

    industry_to_cols: dict[str, list[int]] = {}
    for col, sym in enumerate(symbols):
        industry_name = industry_map.get(str(sym).lower())
        if industry_name is None:
            continue
        industry_to_cols.setdefault(str(industry_name), []).append(col)

    for cols in industry_to_cols.values():
        if not cols:
            continue
        col_idx = np.asarray(cols, dtype=int)
        group_ret = stock_ret[:, col_idx]
        group_valid = tradable[:, col_idx] & ~np.isnan(group_ret)
        group_rank = _row_rank_pct(group_ret, group_valid)
        industry_rank_pct[:, col_idx] = group_rank
    return industry_rank_pct


def _compute_industry_excess_to_median_matrix(
    *,
    stock_ret: np.ndarray,
    tradable: np.ndarray,
    industry_map: dict[str, str] | None,
    industry_name_matrix: np.ndarray | None,
    symbols: list[str],
) -> np.ndarray:
    industry_excess = np.full(stock_ret.shape, np.nan, dtype=float)
    if not symbols or (industry_name_matrix is None and not industry_map):
        return industry_excess

    if industry_name_matrix is not None:
        row_count, col_count = stock_ret.shape
        for row_idx in range(int(row_count)):
            labels = industry_name_matrix[row_idx, :]
            row_industry_to_cols: dict[str, list[int]] = {}
            for col_idx in range(int(col_count)):
                label = labels[col_idx]
                if label is None or (isinstance(label, float) and np.isnan(label)):
                    continue
                row_industry_to_cols.setdefault(str(label), []).append(int(col_idx))
            for cols in row_industry_to_cols.values():
                col_arr = np.asarray(cols, dtype=int)
                group_ret = stock_ret[row_idx, col_arr]
                valid_mask = tradable[row_idx, col_arr] & ~np.isnan(group_ret)
                if not bool(np.any(valid_mask)):
                    continue
                median_value = float(np.median(group_ret[valid_mask]))
                industry_excess[row_idx, col_arr[valid_mask]] = group_ret[valid_mask] - median_value
        return industry_excess

    industry_to_cols: dict[str, list[int]] = {}
    for col, sym in enumerate(symbols):
        industry_name = industry_map.get(str(sym).lower())
        if industry_name is None:
            continue
        industry_to_cols.setdefault(str(industry_name), []).append(col)

    row_count = int(stock_ret.shape[0])
    for cols in industry_to_cols.values():
        if not cols:
            continue
        col_idx = np.asarray(cols, dtype=int)
        group_ret = stock_ret[:, col_idx]
        group_valid = tradable[:, col_idx] & ~np.isnan(group_ret)
        group_excess = np.full(group_ret.shape, np.nan, dtype=float)
        for row_idx in range(row_count):
            valid_mask = group_valid[row_idx, :]
            if not bool(np.any(valid_mask)):
                continue
            median_value = float(np.median(group_ret[row_idx, valid_mask]))
            group_excess[row_idx, valid_mask] = group_ret[row_idx, valid_mask] - median_value
        industry_excess[:, col_idx] = group_excess
    return industry_excess


def _compute_residual_ranking_matrices(
    *,
    close: np.ndarray,
    bench_close: np.ndarray,
    tradable: np.ndarray,
    residual_window: int,
    residual_benchmark_weight: float,
    residual_industry_weight: float,
    sector_data: dict[str, pd.DataFrame] | None,
    industry_map: dict[str, str] | None,
    industry_history: pd.DataFrame | None,
    symbols: list[str],
    dates: np.ndarray,
    sector_strength_window_short: int,
    sector_strength_window_long: int,
    industry_relative_mode: str = "sector_proxy",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    stock_ret = _return_matrix(close, int(residual_window))
    bench_ret = _return_series(bench_close, int(residual_window))
    bench_ret_m = np.repeat(bench_ret.reshape(-1, 1), close.shape[1], axis=1)
    industry_name_matrix, industry_index_code_matrix = _build_industry_assignment_matrices(
        industry_map=industry_map if isinstance(industry_map, dict) else None,
        industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
        sector_data=sector_data if isinstance(sector_data, dict) else None,
        symbols=symbols,
        dates=dates,
    )
    sector_ret_short, sector_ret_long, sector_trend = _build_sector_feature_matrices(
        sector_data=sector_data,
        industry_map=industry_map,
        industry_name_matrix=industry_name_matrix,
        industry_index_code_matrix=industry_index_code_matrix,
        symbols=symbols,
        dates=dates,
        short_window=int(sector_strength_window_short),
        long_window=int(max(sector_strength_window_long, residual_window)),
    )
    residual_vs_bench = stock_ret - bench_ret_m
    sector_proxy_residual = stock_ret - sector_ret_long
    industry_excess_median = _compute_industry_excess_to_median_matrix(
        stock_ret=stock_ret,
        tradable=tradable,
        industry_map=industry_map if isinstance(industry_map, dict) else None,
        industry_name_matrix=industry_name_matrix,
        symbols=symbols,
    )
    sector_beta_tailwind = sector_ret_long - bench_ret_m
    industry_mode = str(industry_relative_mode or "sector_proxy").strip().lower()
    if industry_mode == "industry_rank_pct":
        strict_industry_rank_pct = _compute_industry_rank_pct_matrix(
            stock_ret=stock_ret,
            tradable=tradable,
            industry_map=industry_map if isinstance(industry_map, dict) else None,
            industry_name_matrix=industry_name_matrix,
            symbols=symbols,
        )
        residual_vs_sector = np.where(
            np.isnan(strict_industry_rank_pct),
            np.nan,
            strict_industry_rank_pct - 0.5,
        )
        bench_component_score = _row_rank_pct(residual_vs_bench, tradable)
        residual_score = _weighted_score(
            [
                (bench_component_score, float(residual_benchmark_weight)),
                (strict_industry_rank_pct, float(residual_industry_weight)),
            ],
            shape=close.shape,
        )
        residual_raw = _weighted_score(
            [
                (
                    np.where(np.isnan(bench_component_score), np.nan, bench_component_score - 0.5),
                    float(residual_benchmark_weight),
                ),
                (residual_vs_sector, float(residual_industry_weight)),
            ],
            shape=close.shape,
        )
    elif industry_mode == "industry_excess_median":
        residual_vs_sector = industry_excess_median
        residual_raw = _weighted_score(
            [
                (residual_vs_bench, float(residual_benchmark_weight)),
                (residual_vs_sector, float(residual_industry_weight)),
            ],
            shape=close.shape,
        )
        residual_score = _row_rank_pct(residual_raw, tradable)
    else:
        residual_vs_sector = sector_proxy_residual
        residual_raw = _weighted_score(
            [
                (residual_vs_bench, float(residual_benchmark_weight)),
                (residual_vs_sector, float(residual_industry_weight)),
            ],
            shape=close.shape,
        )
        residual_score = _row_rank_pct(residual_raw, tradable)
    return (
        residual_raw,
        residual_score,
        residual_vs_bench,
        residual_vs_sector,
        sector_ret_short,
        sector_ret_long,
        sector_trend,
        sector_proxy_residual,
        industry_excess_median,
        sector_beta_tailwind,
    )


