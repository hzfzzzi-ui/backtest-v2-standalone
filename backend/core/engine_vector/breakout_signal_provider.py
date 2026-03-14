"""Breakout Trend 信号提供者。

V2 Stage 6: close > max(high[-20:]) 突破入场信号。
使用 SignalProvider 协议，可被引擎统一循环调用。
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.candidate_index import build_daily_candidate_index
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
    evaluate_engine_exits,
)


def _rolling_max_matrix(values: np.ndarray, window: int) -> np.ndarray:
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).max().to_numpy(dtype=float)


def _rolling_min_matrix(values: np.ndarray, window: int) -> np.ndarray:
    return pd.DataFrame(values).rolling(int(window), min_periods=int(window)).min().to_numpy(dtype=float)


def _rolling_any(mask: np.ndarray, window: int) -> np.ndarray:
    rolled = pd.DataFrame(mask.astype(float)).rolling(int(window), min_periods=1).max().to_numpy(dtype=float)
    return rolled > 0


def _return_matrix(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    w = int(window)
    if w <= 0 or values.shape[0] <= w:
        return out
    prev = values[:-w, :]
    curr = values[w:, :]
    safe_prev = np.where(prev > 1e-8, prev, np.nan)
    out[w:, :] = curr / safe_prev - 1.0
    return out


def _return_series(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full(values.shape, np.nan, dtype=float)
    w = int(window)
    if w <= 0 or values.shape[0] <= w:
        return out
    prev = values[:-w]
    curr = values[w:]
    safe_prev = np.where(prev > 1e-8, prev, np.nan)
    out[w:] = curr / safe_prev - 1.0
    return out


def _row_rank_pct(values: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
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


def _row_bucket_code(values: np.ndarray, valid_mask: np.ndarray, bucket_count: int) -> tuple[np.ndarray, np.ndarray]:
    rank_pct = _row_rank_pct(values, valid_mask)
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


def _weighted_score(
    components: list[tuple[np.ndarray, float]],
    shape: tuple[int, int],
) -> np.ndarray:
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


def _normalize_industry_history(frame: pd.DataFrame | None) -> pd.DataFrame:
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


def _build_industry_assignment_matrices(
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

    hist = _normalize_industry_history(industry_history)
    # 严格 PIT: 只要有历史区间，就不再预填最新行业 fallback。
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


def _normalize_history_like(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.lower()
    return out.sort_values(["date", "symbol"]).reset_index(drop=True)


def _aligned_numeric_matrix(
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


class BreakoutTrendProvider:
    """20-Day High Breakout 信号提供者。

    买入信号: close[t] > high_max20[t-1]  (昨日 20 日最高价突破)
    卖出信号: 由 evaluate_engine_exits 统一评估
    """

    def __init__(self) -> None:
        # fill hooks（统一循环传给 _process_pending_fills）
        self.extra_clear_dicts: list[dict] = []
        self.last_sell_day: dict[str, date] | None = None
        self.entry_day: dict[str, date] = {}
        self.entry_bar_index: dict[str, int] = {}
        self.entry_breakout_floor_raw: dict[str, float] = {}
        self.entry_day_overwrite: bool = True
        self.peak_state_on_buy: dict[str, float] | None = None

        # 内部状态（precompute 后填充）
        self._mx: Any = None
        self._feats: Any = None
        self._breakout_up: np.ndarray = np.array([])
        self._breakout_up_short: np.ndarray = np.array([])
        self._breakout_up_long: np.ndarray = np.array([])
        self._dual_breakout_slow_gate_ok: np.ndarray = np.array([])
        self._high_max_short: np.ndarray = np.array([])
        self._high_max_long: np.ndarray = np.array([])
        self._high_max_main: np.ndarray = np.array([])
        self._v2_trend_ok: np.ndarray = np.array([])
        self._entry_confirm_ok: np.ndarray = np.array([])
        self._entry_delay_ok: np.ndarray = np.array([])
        self._entry_above_slow_ma: np.ndarray = np.array([])
        self._entry_slow_ma_slope_pos: np.ndarray = np.array([])
        self._cand_idx: Any = None
        self._bench_close: np.ndarray = np.array([])
        self._risk_on: np.ndarray = np.array([])
        self._strong_risk_on: np.ndarray = np.array([])
        self._breakout_buy: np.ndarray = np.array([])
        self._pullback_pb1: np.ndarray = np.array([])
        self._pullback_pb2: np.ndarray = np.array([])
        self._pullback_pb3: np.ndarray = np.array([])
        self._pullback_tight1: np.ndarray = np.array([])
        self._pullback_tight2: np.ndarray = np.array([])
        self._pullback_raw_selected: np.ndarray = np.array([])
        self._pullback_overlap: np.ndarray = np.array([])
        self._pullback_buy: np.ndarray = np.array([])
        self._breakout_margin_raw: np.ndarray = np.array([])
        self._breakout_fade_raw: np.ndarray = np.array([])
        self._breakout_open_gap_raw: np.ndarray = np.array([])
        self._residual_strength_raw: np.ndarray = np.array([])
        self._residual_vs_bench_raw: np.ndarray = np.array([])
        self._residual_vs_sector_raw: np.ndarray = np.array([])
        self._sector_proxy_residual_raw: np.ndarray = np.array([])
        self._industry_median_excess_raw: np.ndarray = np.array([])
        self._sector_beta_tailwind_raw: np.ndarray = np.array([])
        self._residual_window_effective: np.ndarray = np.array([])
        self._residual_benchmark_weight_effective: np.ndarray = np.array([])
        self._residual_industry_weight_effective: np.ndarray = np.array([])
        self._industry_relative_mode_effective: np.ndarray = np.array([], dtype=object)
        self._breakout_margin_score: np.ndarray = np.array([])
        self._breakout_quality_score: np.ndarray = np.array([])
        self._breakout_quality_pass: np.ndarray = np.array([])
        self._residual_strength_score: np.ndarray = np.array([])
        self._sector_strength_score: np.ndarray = np.array([])
        self._volume_price_quality_score: np.ndarray = np.array([])
        self._conditional_tiebreak_score: np.ndarray = np.array([])
        self._conditional_factor_leader_score: np.ndarray = np.array([])
        self._conditional_institution_proxy_score: np.ndarray = np.array([])
        self._conditional_crowding_score: np.ndarray = np.array([])
        self._conditional_recent_limit_hit_3d: np.ndarray = np.array([])
        self._conditional_near_limit_up: np.ndarray = np.array([])
        self._industry_second_stage_score: np.ndarray = np.array([])
        self._industry_second_stage_not_hot_score: np.ndarray = np.array([])
        self._industry_second_stage_uncrowded_score: np.ndarray = np.array([])
        self._industry_second_stage_breadth_timing_score: np.ndarray = np.array([])
        self._industry_second_stage_persistence_10d: np.ndarray = np.array([])
        self._industry_second_stage_active: np.ndarray = np.array([], dtype=bool)
        self._leadership_route_score: np.ndarray = np.array([])
        self._leadership_route_rank: np.ndarray = np.array([])
        self._leadership_route_bucket: np.ndarray = np.array([], dtype=int)
        self._final_score: np.ndarray = np.array([])
        self._sym_to_col: dict[str, int] = {}
        self._ec: ExitConfig = ExitConfig()
        self._peak_close_state: dict[str, float] = {}
        self._risk_off_partial_state: dict[str, bool] = {}

        # strategy 参数
        self._breakout_window: int = 20
        self._enable_dual_breakout: bool = False
        self._breakout_window_short: int = 20
        self._breakout_window_long: int = 55
        self._dual_breakout_mode: str = "or"
        self._dual_breakout_gate_ma_window: int = 120
        self._dual_breakout_gate_slope_lookback: int = 10
        self._breakout_entry_buffer_pct: float = 0.0
        self._entry_confirm_mode: str = "none"
        self._entry_delay_mode: str = "none"
        self._enable_entry_above_slow_ma: bool = False
        self._enable_entry_slow_ma_slope: bool = False
        self._entry_slope_lookback: int = 5
        self._enable_atr_stop: bool = False
        self._enable_atr_trail: bool = False
        self._atr_stop_k: float = 2.0
        self._atr_trail_k: float = 3.0
        self._order_size: int = 1000
        self._max_hold_days: int = 0
        self._min_hold_days: int = 0
        self._cooldown_days: int = 0
        self._enable_risk_off_exit: bool = False
        self._risk_off_exit_mode: str = "risk_on_off"
        self._risk_off_exit_partial_pct: float = 1.0
        self._risk_off_exit_partial_mode: str = "all_states"
        self._risk_off_exit_partial_only_if_profitable: bool = False
        self._risk_off_exit_trans_down_max_positions: int = 0
        self._risk_off_exit_trans_down_min_residual_score: float = 0.0
        self._enable_profit_decay_exit: bool = False
        self._profit_decay_exit_profit_pct: float = 0.15
        self._profit_decay_exit_min_hold_bars: int = 10
        self._profit_decay_exit_residual_score_threshold: float = 0.35
        self._min_hold_exempt_set: set[str] = set()
        self._base_order_value: float = 0.0
        self._enable_pullback_candidates: bool = False
        self._pullback_variant_mode: str = "pb_reclaim_ma20"
        self._pullback_touch_lookback: int = 12
        self._pullback_reclaim_window: int = 3
        self._pullback_ma20_touch_band_pct: float = 0.01
        self._pullback_low_lookback: int = 10
        self._pullback_low_band_pct: float = 0.02
        self._pullback_box_window: int = 5
        self._pullback_box_range_pct_max: float = 0.08
        self._enable_residual_ranking: bool = False
        self._residual_window: int = 60
        self._residual_benchmark_weight: float = 0.5
        self._residual_industry_weight: float = 0.5
        self._industry_relative_mode: str = "sector_proxy"
        self._industry_relative_regime_mode: str = "off"
        self._residual_weight_regime_mode: str = "off"
        self._residual_benchmark_weight_fallback: float = 0.5
        self._residual_industry_weight_fallback: float = 0.5
        self._ranking_mode: str = "none"
        self._leadership_route_bucket_count: int = 3
        self._breakout_quality_gate_min_score: float = 0.55
        self._breakout_quality_margin_cap_pct: float = 0.08
        self._breakout_quality_fade_cap_pct: float = 0.035
        self._breakout_quality_open_gap_cap_pct: float = 0.04
        self._residual_window_regime_mode: str = "off"
        self._residual_window_fallback: int = 60
        self._residual_window_regime_fast_ma: int = 120
        self._residual_window_regime_slow_ma: int = 200
        self._source_aware_residual_mode: str = "off"
        self._residual_refine_mode: str = "off"
        self._residual_refine_weight: float = 0.0
        self._industry_second_stage_min_industry_score: float = 0.85
        self._enable_sector_quality_ranking: bool = False
        self._sector_strength_window_short: int = 20
        self._sector_strength_window_long: int = 60
        self._volume_quality_window: int = 20
        self._residual_weight: float = 0.5
        self._sector_weight: float = 0.3
        self._quality_weight: float = 0.2

        # 累计计数器
        self.total_buy_signals: int = 0
        self.min_hold_block_count: int = 0
        self.cooldown_block_count: int = 0
        self.entry_above_slow_ma_block_count: int = 0
        self.entry_slope_block_count: int = 0
        self.precompute_seconds: float = 0.0
        self.diag_reason_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # precompute
    # ------------------------------------------------------------------

    def precompute(
        self,
        *,
        history: pd.DataFrame,
        benchmark: pd.DataFrame,
        raw_history: pd.DataFrame | None,
        trading_days: list[date],
        strategy: Any,
        **kwargs: Any,
    ) -> None:
        import time as _time

        exit_cfg = kwargs.get("exit_cfg") or ExitConfig()
        st_history = kwargs.get("st_history")
        membership_history = kwargs.get("membership_history")
        strength_ma = int(kwargs.get("strength_ma", 120))
        self._base_order_value = float(kwargs.get("base_order_value", 0.0))

        self._ec = exit_cfg
        pre_t0 = _time.perf_counter()

        # -- strategy 参数提取 --
        self._breakout_window = int(getattr(strategy, "breakout_window", 20))
        self._enable_dual_breakout = bool(getattr(strategy, "enable_dual_breakout", False))
        self._breakout_window_short = int(getattr(strategy, "breakout_window_short", 20))
        self._breakout_window_long = int(getattr(strategy, "breakout_window_long", max(self._breakout_window, 55)))
        self._dual_breakout_mode = str(getattr(strategy, "dual_breakout_mode", "or") or "or").strip().lower()
        self._dual_breakout_gate_ma_window = int(getattr(strategy, "dual_breakout_gate_ma_window", 120))
        self._dual_breakout_gate_slope_lookback = int(getattr(strategy, "dual_breakout_gate_slope_lookback", 10))
        self._breakout_entry_buffer_pct = float(getattr(strategy, "breakout_entry_buffer_pct", 0.0))
        self._entry_confirm_mode = str(getattr(strategy, "entry_confirm_mode", "none") or "none").strip().lower()
        self._entry_delay_mode = str(getattr(strategy, "entry_delay_mode", "none") or "none").strip().lower()
        self._enable_entry_above_slow_ma = bool(getattr(strategy, "enable_entry_above_slow_ma", False))
        self._enable_entry_slow_ma_slope = bool(getattr(strategy, "enable_entry_slow_ma_slope", False))
        self._entry_slope_lookback = int(getattr(strategy, "entry_slope_lookback", 5))
        self._enable_atr_stop = bool(getattr(strategy, "enable_atr_stop", False))
        self._enable_atr_trail = bool(getattr(strategy, "enable_atr_trail", False))
        self._atr_stop_k = float(kwargs.get("atr_stop_k", getattr(strategy, "atr_stop_k", 2.0)))
        self._atr_trail_k = float(getattr(strategy, "atr_trail_k", 3.0))
        self._order_size = int(getattr(strategy, "order_size", 1000))
        regime_ma = int(getattr(strategy, "regime_ma", 60))
        self._max_hold_days = int(getattr(strategy, "max_hold_days", 0))
        self._min_hold_days = int(getattr(strategy, "min_hold_days", 0))
        self._cooldown_days = int(getattr(strategy, "cooldown_days", 0))
        self._min_hold_exempt_set = set(getattr(strategy, "min_hold_exempt_reasons", []) or [])
        self._enable_risk_off_exit = bool(getattr(strategy, "enable_risk_off_exit", False))
        self._risk_off_exit_mode = str(getattr(strategy, "risk_off_exit_mode", "risk_on_off") or "risk_on_off").strip().lower()
        self._risk_off_exit_partial_pct = float(getattr(strategy, "risk_off_exit_partial_pct", 1.0) or 1.0)
        self._risk_off_exit_partial_mode = str(getattr(strategy, "risk_off_exit_partial_mode", "all_states") or "all_states").strip().lower()
        self._risk_off_exit_partial_only_if_profitable = bool(getattr(strategy, "risk_off_exit_partial_only_if_profitable", False))
        self._risk_off_exit_trans_down_max_positions = int(getattr(strategy, "risk_off_exit_trans_down_max_positions", 0) or 0)
        self._risk_off_exit_trans_down_min_residual_score = float(getattr(strategy, "risk_off_exit_trans_down_min_residual_score", 0.0) or 0.0)
        self._enable_profit_decay_exit = bool(getattr(strategy, "enable_profit_decay_exit", False))
        self._profit_decay_exit_profit_pct = float(getattr(strategy, "profit_decay_exit_profit_pct", 0.15) or 0.15)
        self._profit_decay_exit_min_hold_bars = int(getattr(strategy, "profit_decay_exit_min_hold_bars", 10) or 10)
        self._profit_decay_exit_residual_score_threshold = float(
            getattr(strategy, "profit_decay_exit_residual_score_threshold", 0.35) or 0.35
        )
        self._enable_pullback_candidates = bool(getattr(strategy, "enable_pullback_candidates", False))
        self._pullback_variant_mode = str(getattr(strategy, "pullback_variant_mode", "pb_reclaim_ma20") or "pb_reclaim_ma20").strip().lower()
        self._pullback_touch_lookback = int(getattr(strategy, "pullback_touch_lookback", 12))
        self._pullback_reclaim_window = int(getattr(strategy, "pullback_reclaim_window", 3))
        self._pullback_ma20_touch_band_pct = float(getattr(strategy, "pullback_ma20_touch_band_pct", 0.01))
        self._pullback_low_lookback = int(getattr(strategy, "pullback_low_lookback", 10))
        self._pullback_low_band_pct = float(getattr(strategy, "pullback_low_band_pct", 0.02))
        self._pullback_box_window = int(getattr(strategy, "pullback_box_window", 5))
        self._pullback_box_range_pct_max = float(getattr(strategy, "pullback_box_range_pct_max", 0.08))
        self._enable_residual_ranking = bool(getattr(strategy, "enable_residual_ranking", False))
        self._residual_window = int(getattr(strategy, "residual_window", 60))
        self._residual_benchmark_weight = float(getattr(strategy, "residual_benchmark_weight", 0.5) or 0.0)
        self._residual_industry_weight = float(getattr(strategy, "residual_industry_weight", 0.5) or 0.0)
        self._residual_weight_regime_mode = str(
            getattr(strategy, "residual_weight_regime_mode", "off") or "off"
        ).strip().lower()
        residual_benchmark_weight_fallback = getattr(
            strategy,
            "residual_benchmark_weight_fallback",
            self._residual_benchmark_weight,
        )
        residual_industry_weight_fallback = getattr(
            strategy,
            "residual_industry_weight_fallback",
            self._residual_industry_weight,
        )
        self._residual_benchmark_weight_fallback = float(
            self._residual_benchmark_weight
            if residual_benchmark_weight_fallback is None
            else residual_benchmark_weight_fallback
        )
        self._residual_industry_weight_fallback = float(
            self._residual_industry_weight
            if residual_industry_weight_fallback is None
            else residual_industry_weight_fallback
        )
        if self._residual_benchmark_weight_fallback < 0.0:
            self._residual_benchmark_weight_fallback = float(self._residual_benchmark_weight)
        if self._residual_industry_weight_fallback < 0.0:
            self._residual_industry_weight_fallback = float(self._residual_industry_weight)
        self._ranking_mode = str(getattr(strategy, "ranking_mode", "none") or "none").strip().lower()
        self._leadership_route_bucket_count = max(
            2,
            int(getattr(strategy, "leadership_route_bucket_count", 3) or 3),
        )
        self._breakout_quality_gate_min_score = float(getattr(strategy, "breakout_quality_gate_min_score", 0.55) or 0.55)
        self._breakout_quality_margin_cap_pct = float(getattr(strategy, "breakout_quality_margin_cap_pct", 0.08) or 0.08)
        self._breakout_quality_fade_cap_pct = float(getattr(strategy, "breakout_quality_fade_cap_pct", 0.035) or 0.035)
        self._breakout_quality_open_gap_cap_pct = float(getattr(strategy, "breakout_quality_open_gap_cap_pct", 0.04) or 0.04)
        self._residual_window_regime_mode = str(
            getattr(strategy, "residual_window_regime_mode", "off") or "off"
        ).strip().lower()
        self._residual_window_fallback = int(
            getattr(strategy, "residual_window_fallback", self._residual_window) or self._residual_window
        )
        self._residual_window_regime_fast_ma = int(
            getattr(strategy, "residual_window_regime_fast_ma", 120) or 120
        )
        self._residual_window_regime_slow_ma = int(
            getattr(strategy, "residual_window_regime_slow_ma", 200) or 200
        )
        self._industry_relative_mode = str(
            getattr(strategy, "industry_relative_mode", "sector_proxy") or "sector_proxy"
        ).strip().lower()
        self._industry_relative_regime_mode = str(
            getattr(strategy, "industry_relative_regime_mode", "off") or "off"
        ).strip().lower()
        self._source_aware_residual_mode = str(getattr(strategy, "source_aware_residual_mode", "off") or "off").strip().lower()
        self._residual_refine_mode = str(getattr(strategy, "residual_refine_mode", "off") or "off").strip().lower()
        self._residual_refine_weight = float(getattr(strategy, "residual_refine_weight", 0.0) or 0.0)
        self._industry_second_stage_min_industry_score = float(
            getattr(strategy, "industry_second_stage_min_industry_score", 0.85) or 0.0
        )
        self._enable_sector_quality_ranking = bool(getattr(strategy, "enable_sector_quality_ranking", False))
        self._sector_strength_window_short = int(getattr(strategy, "sector_strength_window_short", 20))
        self._sector_strength_window_long = int(getattr(strategy, "sector_strength_window_long", 60))
        self._volume_quality_window = int(getattr(strategy, "volume_quality_window", 20))
        self._residual_weight = float(getattr(strategy, "residual_weight", 0.5))
        self._sector_weight = float(getattr(strategy, "sector_weight", 0.3))
        self._quality_weight = float(getattr(strategy, "quality_weight", 0.2))

        enable_v2_trend_filter = bool(getattr(strategy, "enable_v2_trend_filter", True))
        v2_trend_short_ma = int(getattr(strategy, "v2_trend_short_ma", 20))
        v2_trend_long_ma = int(getattr(strategy, "v2_trend_long_ma", 60))
        sector_data = kwargs.get("sector_data")
        industry_map = kwargs.get("industry_map")
        industry_history = kwargs.get("industry_history")

        # -- OHLC + feature 矩阵 --
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

        _uf = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
        _min_price = float(_uf.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0)
        _min_list_days = int(_uf.get("min_list_days", 0) or 0)
        _min_avg_turnover_20d = float(_uf.get("min_avg_turnover_20d", 0.0) or 0.0)
        self._mx = build_ohlc_matrices_from_history(
            hist,
            trading_days,
            st_history=st_history,
            membership_history=membership_history,
            min_price=_min_price,
            min_list_days=_min_list_days,
            min_avg_turnover_20d=_min_avg_turnover_20d,
        )
        mx = self._mx
        t, n = mx.close.shape
        if n == 0:
            raise ValueError("history has no symbols")

        self._feats = compute_feature_matrices(
            close=mx.close, high=mx.high, low=mx.low,
            fast=5, slow=20,
            trend_fast=120, trend_slow=200,
            atr_n=14, strength_ma=strength_ma,
            v2_trend_short_ma=v2_trend_short_ma,
            v2_trend_long_ma=v2_trend_long_ma,
            breakout_window=max(self._breakout_window, self._breakout_window_short, self._breakout_window_long),
        )
        feats = self._feats

        # -- benchmark 数组 --
        bench = benchmark.copy()
        bench["date"] = pd.to_datetime(bench["date"])
        bench = bench.sort_values("date")
        bench_close_s = pd.to_numeric(bench["close"], errors="coerce")
        bench_ma_s = bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()
        bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
        bmap_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma_s)}
        self._bench_close = np.array([bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_ma = np.array([bmap_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._risk_on = np.ones(t, dtype=bool)
        valid_bench = ~np.isnan(self._bench_close) & ~np.isnan(bench_ma)
        self._risk_on[valid_bench] = self._bench_close[valid_bench] > bench_ma[valid_bench]
        strong_fast_ma = max(2, int(self._residual_window_regime_fast_ma))
        strong_slow_ma = max(strong_fast_ma + 1, int(self._residual_window_regime_slow_ma))
        bench_fast_ma_s = bench_close_s.rolling(strong_fast_ma, min_periods=strong_fast_ma).mean()
        bench_slow_ma_s = bench_close_s.rolling(strong_slow_ma, min_periods=strong_slow_ma).mean()
        bmap_fast_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_fast_ma_s)}
        bmap_slow_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_slow_ma_s)}
        bench_fast_ma = np.array([bmap_fast_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        bench_slow_ma = np.array([bmap_slow_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in mx.dates], dtype=float)
        self._strong_risk_on = np.zeros(t, dtype=bool)
        valid_strong = ~np.isnan(bench_fast_ma) & ~np.isnan(bench_slow_ma)
        self._strong_risk_on[valid_strong] = bench_fast_ma[valid_strong] > bench_slow_ma[valid_strong]

        # -- breakout signal matrix: close[t] > high_max(window)[t-1] * (1+buffer) --
        def _rolling_high_max(arr: np.ndarray, window: int) -> np.ndarray:
            w = max(2, int(window))
            return pd.DataFrame(arr).rolling(w, min_periods=w).max().to_numpy(dtype=float)

        self._high_max_short = _rolling_high_max(mx.high, self._breakout_window_short)
        self._high_max_long = _rolling_high_max(mx.high, self._breakout_window_long)
        self._high_max_main = _rolling_high_max(mx.high, self._breakout_window)
        self._breakout_up_short = np.zeros((t, n), dtype=bool)
        self._breakout_up_long = np.zeros((t, n), dtype=bool)
        self._breakout_up = np.zeros((t, n), dtype=bool)
        self._breakout_margin_raw = np.full((t, n), np.nan, dtype=float)
        self._breakout_fade_raw = np.full((t, n), np.nan, dtype=float)
        self._breakout_open_gap_raw = np.full((t, n), np.nan, dtype=float)
        self._dual_breakout_slow_gate_ok = np.ones((t, n), dtype=bool)
        if t > 1:
            curr_close = mx.close[1:, :]
            _buf = max(0.0, float(self._breakout_entry_buffer_pct))

            prev_hmax_short = self._high_max_short[:-1, :]
            prev_hmax_long = self._high_max_long[:-1, :]
            valid_short = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_short)
            valid_long = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_long)
            self._breakout_up_short[1:, :] = (curr_close > (prev_hmax_short * (1.0 + _buf))) & valid_short
            self._breakout_up_long[1:, :] = (curr_close > (prev_hmax_long * (1.0 + _buf))) & valid_long
            breakout_ref = np.full((t, n), np.nan, dtype=float)
            if self._enable_dual_breakout:
                breakout_ref[1:, :] = prev_hmax_short
            elif int(self._breakout_window) == int(self._breakout_window_short):
                breakout_ref[1:, :] = prev_hmax_short
            elif int(self._breakout_window) == int(self._breakout_window_long):
                breakout_ref[1:, :] = prev_hmax_long
            else:
                breakout_ref[1:, :] = self._high_max_main[:-1, :]
            breakout_ref = breakout_ref * (1.0 + _buf)
            valid_breakout_ref = ~np.isnan(mx.close) & ~np.isnan(breakout_ref) & (breakout_ref > 1e-8)
            self._breakout_margin_raw[valid_breakout_ref] = (
                mx.close[valid_breakout_ref] / breakout_ref[valid_breakout_ref] - 1.0
            )
            prev_close = np.full((t, n), np.nan, dtype=float)
            prev_close[1:, :] = mx.close[:-1, :]
            valid_open_gap = ~np.isnan(mx.open) & ~np.isnan(prev_close) & (prev_close > 1e-8)
            self._breakout_open_gap_raw[valid_open_gap] = np.maximum(
                mx.open[valid_open_gap] / prev_close[valid_open_gap] - 1.0,
                0.0,
            )
            valid_fade = ~np.isnan(mx.high) & ~np.isnan(mx.close) & (mx.close > 1e-8)
            self._breakout_fade_raw[valid_fade] = np.maximum(
                mx.high[valid_fade] / mx.close[valid_fade] - 1.0,
                0.0,
            )

            if self._dual_breakout_mode == "slow_gate_fast_trigger":
                gate_window = max(2, int(self._dual_breakout_gate_ma_window))
                gate_lb = max(1, int(self._dual_breakout_gate_slope_lookback))
                slow_gate_ma = pd.DataFrame(mx.close).rolling(gate_window, min_periods=gate_window).mean().to_numpy(dtype=float)
                slow_gate_prev = np.full((t, n), np.nan, dtype=float)
                if t > gate_lb:
                    slow_gate_prev[gate_lb:, :] = slow_gate_ma[:-gate_lb, :]
                self._dual_breakout_slow_gate_ok = (
                    ~np.isnan(mx.close)
                    & ~np.isnan(slow_gate_ma)
                    & ~np.isnan(slow_gate_prev)
                    & (mx.close > slow_gate_ma)
                    & (slow_gate_ma > slow_gate_prev)
                )

            if self._enable_dual_breakout:
                if self._dual_breakout_mode == "slow_gate_fast_trigger":
                    self._breakout_up = self._breakout_up_short & self._dual_breakout_slow_gate_ok
                else:
                    self._breakout_up = self._breakout_up_short | self._breakout_up_long
            else:
                if int(self._breakout_window) == int(self._breakout_window_short):
                    self._breakout_up = self._breakout_up_short.copy()
                elif int(self._breakout_window) == int(self._breakout_window_long):
                    self._breakout_up = self._breakout_up_long.copy()
                else:
                    prev_hmax_main = self._high_max_main[:-1, :]
                    valid_main = ~np.isnan(curr_close) & ~np.isnan(prev_hmax_main)
                    self._breakout_up[1:, :] = (curr_close > (prev_hmax_main * (1.0 + _buf))) & valid_main

        # -- entry confirmation matrix --
        self._entry_confirm_ok = np.ones((t, n), dtype=bool)
        _eps = 1e-8
        if self._entry_confirm_mode == "close_strength":
            spread = mx.high - mx.low
            close_pos = np.where(spread > _eps, (mx.close - mx.low) / spread, np.nan)
            self._entry_confirm_ok = (~np.isnan(close_pos)) & (close_pos > 0.6)
        elif self._entry_confirm_mode == "volume_confirm":
            vol_ma20 = pd.DataFrame(mx.volume).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            self._entry_confirm_ok = (~np.isnan(mx.volume)) & (~np.isnan(vol_ma20)) & (mx.volume > vol_ma20)
        elif self._entry_confirm_mode == "volume_ratio_confirm":
            vol_ma20 = pd.DataFrame(mx.volume).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            vol_ma20_prev = np.empty_like(vol_ma20)
            vol_ma20_prev[:] = np.nan
            if t > 1:
                vol_ma20_prev[1:, :] = vol_ma20[:-1, :]
            self._entry_confirm_ok = (~np.isnan(mx.volume)) & (~np.isnan(vol_ma20_prev)) & (mx.volume > (vol_ma20_prev * 1.5))
        elif self._entry_confirm_mode == "volatility_confirm":
            prev_close = np.empty_like(mx.close)
            prev_close[:] = np.nan
            if t > 1:
                prev_close[1:, :] = mx.close[:-1, :]
            tr1 = mx.high - mx.low
            tr2 = np.abs(mx.high - prev_close)
            tr3 = np.abs(mx.low - prev_close)
            tr = np.fmax(tr1, np.fmax(tr2, tr3))
            atr20 = pd.DataFrame(tr).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
            self._entry_confirm_ok = (~np.isnan(tr)) & (~np.isnan(atr20)) & (tr > (atr20 * 0.8))
        elif self._entry_confirm_mode not in {"none", ""}:
            self._entry_confirm_mode = "none"

        # -- entry delay confirmation matrix --
        self._entry_delay_ok = self._breakout_up.copy()
        if self._entry_delay_mode == "t1_confirm":
            _prev = np.zeros_like(self._breakout_up, dtype=bool)
            if t > 1:
                _prev[1:, :] = self._breakout_up[:-1, :]
            self._entry_delay_ok = self._breakout_up & _prev
        elif self._entry_delay_mode == "t2_confirm":
            _prev2 = np.zeros_like(self._breakout_up, dtype=bool)
            if t > 2:
                _prev2[2:, :] = self._breakout_up[:-2, :]
            self._entry_delay_ok = self._breakout_up & _prev2
        elif self._entry_delay_mode == "pullback_confirm":
            self._entry_delay_ok = np.zeros((t, n), dtype=bool)
            if t > 1:
                prev_breakout = self._breakout_up[:-1, :]
                level = self._high_max_main[:-1, :]
                low_touch = (~np.isnan(mx.low[1:, :])) & (~np.isnan(level)) & (mx.low[1:, :] <= level)
                close_reclaim = (~np.isnan(mx.close[1:, :])) & (~np.isnan(level)) & (mx.close[1:, :] > level)
                self._entry_delay_ok[1:, :] = prev_breakout & low_touch & close_reclaim
        elif self._entry_delay_mode not in {"none", ""}:
            self._entry_delay_mode = "none"

        self._entry_above_slow_ma = np.ones((t, n), dtype=bool)
        if self._enable_entry_above_slow_ma:
            self._entry_above_slow_ma = (
                ~np.isnan(mx.close)
                & ~np.isnan(feats.sma60)
                & (mx.close > feats.sma60)
            )

        self._entry_slow_ma_slope_pos = np.ones((t, n), dtype=bool)
        if self._enable_entry_slow_ma_slope:
            lb = max(1, int(self._entry_slope_lookback))
            self._entry_slow_ma_slope_pos[:] = False
            if t > lb:
                slow_ma_diff = np.full((t, n), np.nan, dtype=float)
                slow_ma_diff[lb:, :] = feats.sma60[lb:, :] - feats.sma60[:-lb, :]
                self._entry_slow_ma_slope_pos = (
                    ~np.isnan(slow_ma_diff)
                    & (slow_ma_diff > 0.0)
                )

        # -- V2 个股趋势过滤 --
        self._v2_trend_ok = np.ones((t, n), dtype=bool)
        if enable_v2_trend_filter:
            self._v2_trend_ok = (
                ~np.isnan(mx.close)
                & ~np.isnan(feats.sma20)
                & ~np.isnan(feats.sma60)
                & (mx.close > feats.sma60)
                & (feats.sma20 > feats.sma60)
            )

        # -- Momentum 前置过滤: 60日动量 top N% --
        momentum_top_pct = float(getattr(strategy, "momentum_top_pct", 0.0))
        momentum_window = 60
        self._momentum_ok = np.ones((t, n), dtype=bool)
        if momentum_top_pct > 0:
            # 60日收益率 = close[t] / close[t-60] - 1
            mom = np.full((t, n), np.nan, dtype=float)
            if t > momentum_window:
                prev_close = mx.close[:-momentum_window, :]
                curr_close = mx.close[momentum_window:, :]
                safe_prev = np.where(prev_close > 1e-8, prev_close, np.nan)
                mom[momentum_window:, :] = curr_close / safe_prev - 1.0
            # 每日排名, 只取 top N%
            self._momentum_ok = np.zeros((t, n), dtype=bool)
            for _di in range(t):
                row = mom[_di, :]
                valid_mask = ~np.isnan(row) & mx.tradable[_di, :]
                valid_count = int(np.sum(valid_mask))
                if valid_count == 0:
                    continue
                topk = max(1, int(valid_count * momentum_top_pct))
                # 找 top-K 的阈值
                valid_vals = row[valid_mask]
                threshold = np.partition(valid_vals, -topk)[-topk]
                self._momentum_ok[_di, :] = valid_mask & (row >= threshold)

        # -- 综合买入候选矩阵 --
        trend_base = (
            ~np.isnan(mx.close)
            & ~np.isnan(feats.sma20)
            & ~np.isnan(feats.sma60)
            & (mx.close > feats.sma60)
            & (feats.sma20 > feats.sma60)
        )
        reclaim_window = max(2, int(self._pullback_reclaim_window))
        touch_lookback = max(2, int(self._pullback_touch_lookback))
        pb_high = _rolling_max_matrix(mx.high, reclaim_window)
        pb_high_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            pb_high_prev[1:, :] = pb_high[:-1, :]
        ma20_touch = (
            ~np.isnan(mx.low)
            & ~np.isnan(feats.sma20)
            & (mx.low <= (feats.sma20 * (1.0 + max(0.0, float(self._pullback_ma20_touch_band_pct)))))
        )
        recent_ma20_touch = _rolling_any(ma20_touch, touch_lookback)
        self._pullback_pb1 = (
            trend_base
            & recent_ma20_touch
            & ~np.isnan(pb_high_prev)
            & (mx.close > pb_high_prev)
            & (mx.close > feats.sma20)
        )

        low_window = max(3, int(self._pullback_low_lookback))
        low_min = _rolling_min_matrix(mx.low, low_window)
        low_min_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            low_min_prev[1:, :] = low_min[:-1, :]
        self._pullback_pb2 = (
            trend_base
            & ~np.isnan(low_min_prev)
            & (mx.low <= low_min_prev * (1.0 + max(0.0, float(self._pullback_low_band_pct))))
            & (mx.close > mx.open)
            & ~np.isnan(pb_high_prev)
            & (mx.close > pb_high_prev)
        )

        box_window = max(3, int(self._pullback_box_window))
        box_high = _rolling_max_matrix(mx.high, box_window)
        box_low = _rolling_min_matrix(mx.low, box_window)
        box_high_prev = np.full((t, n), np.nan, dtype=float)
        box_low_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            box_high_prev[1:, :] = box_high[:-1, :]
            box_low_prev[1:, :] = box_low[:-1, :]
        box_range_pct = np.full((t, n), np.nan, dtype=float)
        valid_box = ~np.isnan(box_high_prev) & ~np.isnan(box_low_prev) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        box_range_pct[valid_box] = (box_high_prev[valid_box] - box_low_prev[valid_box]) / mx.close[valid_box]
        self._pullback_pb3 = (
            trend_base
            & ~np.isnan(box_range_pct)
            & (box_range_pct <= max(0.0, float(self._pullback_box_range_pct_max)))
            & ~np.isnan(box_high_prev)
            & (mx.close > box_high_prev)
        )

        high120 = _rolling_max_matrix(mx.high, 120)
        high120_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            high120_prev[1:, :] = high120[:-1, :]
        sma60_prev10 = np.full((t, n), np.nan, dtype=float)
        if t > 10:
            sma60_prev10[10:, :] = feats.sma60[:-10, :]
        ret20 = _return_matrix(mx.close, 20)
        close_pos = np.full((t, n), np.nan, dtype=float)
        day_range = mx.high - mx.low
        valid_close_pos = ~np.isnan(day_range) & (day_range > 1e-8) & ~np.isnan(mx.close) & ~np.isnan(mx.low)
        close_pos[valid_close_pos] = (mx.close[valid_close_pos] - mx.low[valid_close_pos]) / day_range[valid_close_pos]
        vol_ma20 = pd.DataFrame(mx.volume).rolling(20, min_periods=20).mean().to_numpy(dtype=float)
        vol_ratio20 = np.full((t, n), np.nan, dtype=float)
        valid_vol20 = ~np.isnan(mx.volume) & ~np.isnan(vol_ma20) & (vol_ma20 > 1e-8)
        vol_ratio20[valid_vol20] = mx.volume[valid_vol20] / vol_ma20[valid_vol20]
        high20 = _rolling_max_matrix(mx.high, 20)
        high20_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            high20_prev[1:, :] = high20[:-1, :]
        pullback_depth = np.full((t, n), np.nan, dtype=float)
        valid_depth = ~np.isnan(high20_prev) & (high20_prev > 1e-8) & ~np.isnan(mx.close)
        pullback_depth[valid_depth] = (high20_prev[valid_depth] - mx.close[valid_depth]) / high20_prev[valid_depth]
        recent_low8 = _rolling_min_matrix(mx.low, 8)
        low_structure_ok = ~np.isnan(recent_low8) & ~np.isnan(feats.sma60) & (recent_low8 >= (feats.sma60 * 0.98))
        tight_reclaim_high = _rolling_max_matrix(mx.high, 5)
        tight_reclaim_high_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            tight_reclaim_high_prev[1:, :] = tight_reclaim_high[:-1, :]
        trend_tight = (
            trend_base
            & ~np.isnan(sma60_prev10)
            & (feats.sma60 > sma60_prev10)
            & ~np.isnan(high120_prev)
            & (mx.close >= (high120_prev * 0.88))
            & ~np.isnan(ret20)
            & (ret20 > 0.03)
        )
        shallow_pullback = ~np.isnan(pullback_depth) & (pullback_depth >= 0.03) & (pullback_depth <= 0.12)
        restart_quality = (
            ~np.isnan(close_pos)
            & (close_pos >= 0.65)
            & ~np.isnan(vol_ratio20)
            & (vol_ratio20 >= 0.90)
            & (vol_ratio20 <= 2.50)
        )
        self._pullback_tight1 = (
            trend_tight
            & recent_ma20_touch
            & shallow_pullback
            & low_structure_ok
            & ~np.isnan(tight_reclaim_high_prev)
            & (mx.close > tight_reclaim_high_prev)
            & (mx.close > feats.sma20)
            & restart_quality
        )

        tight_box_window = 6
        tight_box_high = _rolling_max_matrix(mx.high, tight_box_window)
        tight_box_low = _rolling_min_matrix(mx.low, tight_box_window)
        tight_box_high_prev = np.full((t, n), np.nan, dtype=float)
        tight_box_low_prev = np.full((t, n), np.nan, dtype=float)
        if t > 1:
            tight_box_high_prev[1:, :] = tight_box_high[:-1, :]
            tight_box_low_prev[1:, :] = tight_box_low[:-1, :]
        tight_box_range_pct = np.full((t, n), np.nan, dtype=float)
        valid_tight_box = ~np.isnan(tight_box_high_prev) & ~np.isnan(tight_box_low_prev) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        tight_box_range_pct[valid_tight_box] = (tight_box_high_prev[valid_tight_box] - tight_box_low_prev[valid_tight_box]) / mx.close[valid_tight_box]
        self._pullback_tight2 = (
            trend_tight
            & shallow_pullback
            & ~np.isnan(tight_box_range_pct)
            & (tight_box_range_pct <= 0.05)
            & ~np.isnan(tight_box_low_prev)
            & ~np.isnan(feats.sma20)
            & (tight_box_low_prev >= (feats.sma20 * 0.97))
            & ~np.isnan(tight_box_high_prev)
            & (mx.close > tight_box_high_prev)
            & restart_quality
        )

        if self._enable_pullback_candidates:
            variant_mode = str(self._pullback_variant_mode or "pb_reclaim_ma20").lower()
            if variant_mode in {"pb_reversal_near_low", "pb2"}:
                self._pullback_raw_selected = self._pullback_pb2.copy()
            elif variant_mode in {"pb_tight_box", "pb_tight_box_break", "tight_box"}:
                self._pullback_raw_selected = self._pullback_tight2.copy()
            elif variant_mode in {"pb_reclaim_ma20_plus_box", "pb1_pb3"}:
                self._pullback_raw_selected = self._pullback_pb1 | self._pullback_pb3
            elif variant_mode in {"pb_tight_combo", "tight_combo", "pb_tight"}:
                self._pullback_raw_selected = self._pullback_tight1 | self._pullback_tight2
            elif variant_mode in {"pb_tight_reclaim", "tight_reclaim"}:
                self._pullback_raw_selected = self._pullback_tight1.copy()
            elif variant_mode == "all":
                self._pullback_raw_selected = self._pullback_pb1 | self._pullback_pb2 | self._pullback_pb3
            else:
                self._pullback_raw_selected = self._pullback_pb1.copy()
        else:
            self._pullback_raw_selected = np.zeros((t, n), dtype=bool)

        (
            self._residual_strength_raw,
            self._residual_strength_score,
            self._residual_vs_bench_raw,
            self._residual_vs_sector_raw,
            sector_ret_short,
            sector_ret_long,
            sector_trend,
            self._sector_proxy_residual_raw,
            self._industry_median_excess_raw,
            self._sector_beta_tailwind_raw,
        ) = _compute_residual_ranking_matrices(
            close=mx.close,
            bench_close=self._bench_close,
            tradable=mx.tradable,
            residual_window=int(self._residual_window),
            residual_benchmark_weight=float(self._residual_benchmark_weight),
            residual_industry_weight=float(self._residual_industry_weight),
            sector_data=sector_data if isinstance(sector_data, dict) else None,
            industry_map=industry_map if isinstance(industry_map, dict) else None,
            industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
            symbols=mx.symbols,
            dates=mx.dates,
            sector_strength_window_short=int(self._sector_strength_window_short),
            sector_strength_window_long=int(self._sector_strength_window_long),
            industry_relative_mode=str(self._industry_relative_mode),
        )
        self._residual_window_effective = np.full(t, int(self._residual_window), dtype=int)
        self._residual_benchmark_weight_effective = np.full(
            t,
            float(self._residual_benchmark_weight),
            dtype=float,
        )
        self._residual_industry_weight_effective = np.full(
            t,
            float(self._residual_industry_weight),
            dtype=float,
        )
        self._industry_relative_mode_effective = np.full(t, str(self._industry_relative_mode), dtype=object)
        fallback_window = int(self._residual_window)
        if self._residual_window_regime_mode == "strong_risk_on":
            fallback_window = int(self._residual_window_fallback)
        fallback_benchmark_weight = float(self._residual_benchmark_weight)
        fallback_industry_weight = float(self._residual_industry_weight)
        if self._residual_weight_regime_mode == "strong_risk_on":
            fallback_benchmark_weight = float(self._residual_benchmark_weight_fallback)
            fallback_industry_weight = float(self._residual_industry_weight_fallback)
        fallback_industry_relative_mode = str(self._industry_relative_mode)
        if self._industry_relative_regime_mode == "strong_risk_on":
            fallback_industry_relative_mode = "sector_proxy"
        fallback_window_changed = fallback_window != int(self._residual_window)
        fallback_weight_changed = (
            abs(fallback_benchmark_weight - float(self._residual_benchmark_weight)) > 1e-12
            or abs(fallback_industry_weight - float(self._residual_industry_weight)) > 1e-12
        )
        fallback_industry_mode_changed = fallback_industry_relative_mode != str(self._industry_relative_mode)
        if self._enable_residual_ranking and (
            fallback_window_changed or fallback_weight_changed or fallback_industry_mode_changed
        ):
            (
                fallback_raw,
                fallback_score,
                fallback_vs_bench_raw,
                fallback_vs_sector_raw,
                _,
                _,
                _,
                fallback_sector_proxy_raw,
                fallback_industry_median_excess_raw,
                fallback_sector_beta_tailwind_raw,
            ) = _compute_residual_ranking_matrices(
                close=mx.close,
                bench_close=self._bench_close,
                tradable=mx.tradable,
                residual_window=int(fallback_window),
                residual_benchmark_weight=float(fallback_benchmark_weight),
                residual_industry_weight=float(fallback_industry_weight),
                sector_data=sector_data if isinstance(sector_data, dict) else None,
                industry_map=industry_map if isinstance(industry_map, dict) else None,
                industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
                symbols=mx.symbols,
                dates=mx.dates,
                sector_strength_window_short=int(self._sector_strength_window_short),
                sector_strength_window_long=int(self._sector_strength_window_long),
                industry_relative_mode=str(fallback_industry_relative_mode),
            )
            fallback_mask = ~self._strong_risk_on
            if bool(np.any(fallback_mask)):
                self._residual_strength_raw[fallback_mask, :] = fallback_raw[fallback_mask, :]
                self._residual_strength_score[fallback_mask, :] = fallback_score[fallback_mask, :]
                self._residual_vs_bench_raw[fallback_mask, :] = fallback_vs_bench_raw[fallback_mask, :]
                self._residual_vs_sector_raw[fallback_mask, :] = fallback_vs_sector_raw[fallback_mask, :]
                self._sector_proxy_residual_raw[fallback_mask, :] = fallback_sector_proxy_raw[fallback_mask, :]
                self._industry_median_excess_raw[fallback_mask, :] = fallback_industry_median_excess_raw[fallback_mask, :]
                self._sector_beta_tailwind_raw[fallback_mask, :] = fallback_sector_beta_tailwind_raw[fallback_mask, :]
                self._residual_window_effective[fallback_mask] = int(fallback_window)
                self._residual_benchmark_weight_effective[fallback_mask] = float(fallback_benchmark_weight)
                self._residual_industry_weight_effective[fallback_mask] = float(fallback_industry_weight)
                self._industry_relative_mode_effective[fallback_mask] = str(fallback_industry_relative_mode)

        sector_short_rank = _row_rank_pct(sector_ret_short, mx.tradable)
        sector_long_rank = _row_rank_pct(sector_ret_long, mx.tradable)
        self._sector_strength_score = _weighted_score(
            [(sector_short_rank, 0.4), (sector_long_rank, 0.4), (sector_trend, 0.2)],
            shape=(t, n),
        )

        vol_window = max(5, int(self._volume_quality_window))
        vol_ma = pd.DataFrame(mx.volume).rolling(vol_window, min_periods=vol_window).mean().to_numpy(dtype=float)
        vol_ratio = np.full((t, n), np.nan, dtype=float)
        valid_vol = ~np.isnan(mx.volume) & ~np.isnan(vol_ma) & (vol_ma > 1e-8)
        vol_ratio[valid_vol] = mx.volume[valid_vol] / vol_ma[valid_vol]
        vol_quality_raw = np.full((t, n), np.nan, dtype=float)
        valid_vr = ~np.isnan(vol_ratio) & (vol_ratio > 1e-8)
        vol_quality_raw[valid_vr] = -np.abs(np.log(vol_ratio[valid_vr] / 1.2))
        atr_pct = np.full((t, n), np.nan, dtype=float)
        valid_atr_pct = ~np.isnan(feats.atr14) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        atr_pct[valid_atr_pct] = feats.atr14[valid_atr_pct] / mx.close[valid_atr_pct]
        range_high = _rolling_max_matrix(mx.high, vol_window)
        range_low = _rolling_min_matrix(mx.low, vol_window)
        range_pct = np.full((t, n), np.nan, dtype=float)
        valid_range = ~np.isnan(range_high) & ~np.isnan(range_low) & ~np.isnan(mx.close) & (mx.close > 1e-8)
        range_pct[valid_range] = (range_high[valid_range] - range_low[valid_range]) / mx.close[valid_range]
        quality_raw = _weighted_score(
            [(vol_quality_raw, 0.5), (-atr_pct, 0.3), (-range_pct, 0.2)],
            shape=(t, n),
        )
        self._volume_price_quality_score = _row_rank_pct(quality_raw, mx.tradable)

        risk_on_m = np.repeat(self._risk_on.reshape(-1, 1), n, axis=1)
        common_gate = risk_on_m & mx.tradable & self._momentum_ok
        self._breakout_buy = self._entry_delay_ok & self._entry_confirm_ok & self._v2_trend_ok & common_gate
        pullback_gate = self._entry_confirm_ok & common_gate
        if enable_v2_trend_filter:
            pullback_gate = pullback_gate & self._v2_trend_ok
        self._pullback_raw_selected = self._pullback_raw_selected & pullback_gate
        self._pullback_overlap = self._pullback_raw_selected & self._breakout_buy
        self._pullback_buy = self._pullback_raw_selected & ~self._breakout_buy
        self._breakout_margin_score = np.full((t, n), np.nan, dtype=float)
        breakout_margin_mask = self._breakout_buy | self._pullback_overlap
        if bool(np.any(breakout_margin_mask)):
            breakout_margin_input = np.where(breakout_margin_mask, self._breakout_margin_raw, np.nan)
            self._breakout_margin_score = _row_rank_pct(breakout_margin_input, breakout_margin_mask)

        self._breakout_quality_score = np.full((t, n), np.nan, dtype=float)
        self._breakout_quality_pass = np.ones((t, n), dtype=bool)
        if bool(np.any(breakout_margin_mask)):
            margin_cap = max(1e-8, float(self._breakout_quality_margin_cap_pct))
            fade_cap = max(1e-8, float(self._breakout_quality_fade_cap_pct))
            gap_cap = max(1e-8, float(self._breakout_quality_open_gap_cap_pct))

            margin_quality_raw = np.full((t, n), np.nan, dtype=float)
            valid_margin_quality = breakout_margin_mask & ~np.isnan(self._breakout_margin_raw)
            margin_quality_raw[valid_margin_quality] = np.clip(
                1.0 - (self._breakout_margin_raw[valid_margin_quality] / margin_cap),
                0.0,
                1.0,
            )

            fade_quality_raw = np.full((t, n), np.nan, dtype=float)
            valid_fade_quality = breakout_margin_mask & ~np.isnan(self._breakout_fade_raw)
            fade_quality_raw[valid_fade_quality] = np.clip(
                1.0 - (self._breakout_fade_raw[valid_fade_quality] / fade_cap),
                0.0,
                1.0,
            )

            gap_quality_raw = np.full((t, n), np.nan, dtype=float)
            valid_gap_quality = breakout_margin_mask & ~np.isnan(self._breakout_open_gap_raw)
            gap_quality_raw[valid_gap_quality] = np.clip(
                1.0 - (self._breakout_open_gap_raw[valid_gap_quality] / gap_cap),
                0.0,
                1.0,
            )

            vp_quality_input = np.where(breakout_margin_mask, self._volume_price_quality_score, np.nan)
            self._breakout_quality_score = _weighted_score(
                [
                    (margin_quality_raw, 0.35),
                    (fade_quality_raw, 0.25),
                    (gap_quality_raw, 0.20),
                    (vp_quality_input, 0.20),
                ],
                shape=(t, n),
            )
            if self._ranking_mode == "quality_then_residual":
                gate_floor = min(1.0, max(0.0, float(self._breakout_quality_gate_min_score)))
                quality_gate_pass = breakout_margin_mask & ~np.isnan(self._breakout_quality_score) & (
                    self._breakout_quality_score >= gate_floor
                )
                self._breakout_quality_pass = np.where(breakout_margin_mask, quality_gate_pass, True)

        residual_component = self._residual_strength_score
        (
            self._conditional_tiebreak_score,
            self._conditional_factor_leader_score,
            self._conditional_institution_proxy_score,
            self._conditional_crowding_score,
            self._conditional_recent_limit_hit_3d,
            self._conditional_near_limit_up,
        ) = _compute_conditional_tiebreak_matrices(
            raw_history=raw_history,
            dates=mx.dates,
            symbols=mx.symbols,
            tradable=mx.tradable,
            adj_close=mx.close,
            breakout_quality_score=self._breakout_quality_score,
        )
        self._industry_second_stage_score = np.full((t, n), 0.5, dtype=float)
        self._industry_second_stage_not_hot_score = np.full((t, n), 0.5, dtype=float)
        self._industry_second_stage_uncrowded_score = np.full((t, n), 0.5, dtype=float)
        self._industry_second_stage_breadth_timing_score = np.full((t, n), 0.5, dtype=float)
        self._industry_second_stage_persistence_10d = np.full((t, n), 0.5, dtype=float)
        self._industry_second_stage_active = np.zeros((t, n), dtype=bool)
        if (
            self._enable_residual_ranking
            and self._residual_refine_mode in {"industry_second_stage", "industry_second_stage_tiebreak"}
            and (
                self._residual_refine_mode == "industry_second_stage_tiebreak"
                or self._residual_refine_weight > 1e-12
            )
        ):
            industry_name_matrix, _ = _build_industry_assignment_matrices(
                industry_map=industry_map if isinstance(industry_map, dict) else None,
                industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
                sector_data=sector_data if isinstance(sector_data, dict) else None,
                symbols=mx.symbols,
                dates=mx.dates,
            )
            (
                self._industry_second_stage_score,
                self._industry_second_stage_not_hot_score,
                self._industry_second_stage_uncrowded_score,
                self._industry_second_stage_breadth_timing_score,
                self._industry_second_stage_persistence_10d,
            ) = _compute_industry_second_stage_matrices(
                tradable=mx.tradable,
                adj_close=mx.close,
                industry_map=industry_map if isinstance(industry_map, dict) else None,
                industry_name_matrix=industry_name_matrix,
                symbols=mx.symbols,
                breakout_margin_raw=self._breakout_margin_raw,
                breakout_quality_score=self._breakout_quality_score,
                recent_limit_hit_3d=self._conditional_recent_limit_hit_3d,
                near_limit_up=self._conditional_near_limit_up,
            )
            min_industry_score = min(1.0, max(0.0, float(self._industry_second_stage_min_industry_score)))
            self._industry_second_stage_active = (
                mx.tradable
                & ~np.isnan(self._residual_strength_score)
                & (self._residual_strength_score >= min_industry_score)
            )
        self._leadership_route_score = _weighted_score(
            [
                (self._conditional_factor_leader_score, 0.5),
                (self._conditional_institution_proxy_score, 0.5),
            ],
            shape=(t, n),
        )
        self._leadership_route_score = np.where(np.isnan(self._leadership_route_score), 0.5, self._leadership_route_score)
        (
            self._leadership_route_rank,
            self._leadership_route_bucket,
        ) = _row_bucket_code(
            self._leadership_route_score,
            mx.tradable & ~np.isnan(self._leadership_route_score),
            int(self._leadership_route_bucket_count),
        )
        if (
            self._enable_residual_ranking
            and self._residual_refine_mode == "breakout_margin"
            and self._residual_refine_weight > 1e-12
        ):
            residual_component = _weighted_score(
                [
                    (self._residual_strength_score, 1.0),
                    (self._breakout_margin_score, float(self._residual_refine_weight)),
                ],
                shape=(t, n),
            )
        elif (
            self._enable_residual_ranking
            and self._residual_refine_mode == "conditional_tiebreak"
            and self._residual_refine_weight > 1e-12
        ):
            residual_component = _weighted_score(
                [
                    (self._residual_strength_score, 1.0),
                    (self._conditional_tiebreak_score, float(self._residual_refine_weight)),
                ],
                shape=(t, n),
            )
        elif (
            self._enable_residual_ranking
            and self._residual_refine_mode == "industry_second_stage"
            and self._residual_refine_weight > 1e-12
        ):
            second_stage_effective = np.where(
                self._industry_second_stage_active,
                self._industry_second_stage_score,
                np.nan,
            )
            residual_component = _weighted_score(
                [
                    (self._residual_strength_score, 1.0),
                    (second_stage_effective, float(self._residual_refine_weight)),
                ],
                shape=(t, n),
            )

        if self._enable_residual_ranking or self._enable_sector_quality_ranking:
            score_components: list[tuple[np.ndarray, float]] = []
            if self._enable_residual_ranking:
                score_components.append((residual_component, float(self._residual_weight)))
            if self._enable_sector_quality_ranking:
                score_components.append((self._sector_strength_score, float(self._sector_weight)))
                score_components.append((self._volume_price_quality_score, float(self._quality_weight)))
            self._final_score = _weighted_score(score_components, shape=(t, n))
        else:
            self._final_score = np.full((t, n), 0.5, dtype=float)
        if self._ranking_mode == "quality_then_residual" and self._enable_residual_ranking:
            self._final_score = np.where(self._breakout_quality_pass, self._residual_strength_score, np.nan)
        if self._ranking_mode == "leadership_then_residual" and self._enable_residual_ranking:
            residual_safe = np.where(np.isnan(self._residual_strength_score), 0.5, self._residual_strength_score)
            route_width = 1.0 / float(max(int(self._leadership_route_bucket_count), 1))
            bucket_base = np.where(
                self._leadership_route_bucket >= 0,
                self._leadership_route_bucket.astype(float) * route_width,
                np.nan,
            )
            self._final_score = bucket_base + residual_safe * (route_width * 0.999)
        if self._source_aware_residual_mode in {"pullback_only", "pullback_only_rank"} and self._enable_residual_ranking:
            residual_safe = np.where(np.isnan(self._residual_strength_score), 0.5, self._residual_strength_score)
            breakout_only = self._breakout_buy & ~self._pullback_overlap
            self._final_score[breakout_only] = 2.0
            self._final_score[self._pullback_overlap] = 2.1
            self._final_score[self._pullback_buy] = residual_safe[self._pullback_buy]
        buy_base = self._breakout_buy | self._pullback_buy
        if self._ranking_mode == "quality_then_residual":
            breakout_quality_scope = self._breakout_buy | self._pullback_overlap
            buy_base = (buy_base & ~breakout_quality_scope) | (
                buy_base & breakout_quality_scope & self._breakout_quality_pass
            )
        self._cand_idx = build_daily_candidate_index(buy_base)
        self._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}

        # -- fill hooks 初始化 --
        self._peak_close_state = {}
        self._risk_off_partial_state = {}
        self.entry_day = {}
        self.last_sell_day = {}
        self.entry_bar_index = {}
        self.entry_breakout_floor_raw = {}
        self.extra_clear_dicts = [
            self._peak_close_state,
            self._risk_off_partial_state,
            self.entry_bar_index,
            self.entry_breakout_floor_raw,
        ]
        self.peak_state_on_buy = self._peak_close_state

        self.precompute_seconds = float(_time.perf_counter() - pre_t0)

    def _evaluate_profit_decay_exits(
        self,
        *,
        day: date,
        day_idx: int,
        positions: dict[str, int],
        position_avg_cost: dict[str, float],
        close_idx: dict[tuple[date, str], float],
        exit_syms: set[str],
        exit_counts: ExitCounts,
    ) -> list[Signal]:
        if not self._enable_profit_decay_exit:
            return []

        mx = self._mx
        feats = self._feats
        exits: list[Signal] = []
        for sym, qty in list(positions.items()):
            if int(qty) <= 0 or sym in exit_syms:
                continue
            col = self._sym_to_col.get(sym)
            if col is None:
                continue
            raw_close = float(close_idx.get((day, sym), 0.0) or 0.0)
            avg_cost = float(position_avg_cost.get(sym, 0.0) or 0.0)
            if raw_close <= 0.0 or avg_cost <= 0.0:
                continue
            pnl_pct = raw_close / avg_cost - 1.0
            if pnl_pct < self._profit_decay_exit_profit_pct:
                continue
            entry_idx = self.entry_bar_index.get(sym)
            if entry_idx is None:
                continue
            bars_since_entry = int(day_idx) - int(entry_idx)
            if bars_since_entry < self._profit_decay_exit_min_hold_bars:
                continue
            residual_score = (
                float(self._residual_strength_score[day_idx, col])
                if self._residual_strength_score.size and not np.isnan(self._residual_strength_score[day_idx, col])
                else None
            )
            if residual_score is None or residual_score > self._profit_decay_exit_residual_score_threshold:
                continue
            close_val = float(mx.close[day_idx, col]) if not np.isnan(mx.close[day_idx, col]) else None
            sma20_val = float(feats.sma20[day_idx, col]) if not np.isnan(feats.sma20[day_idx, col]) else None
            if close_val is None or sma20_val is None or close_val >= sma20_val:
                continue

            exit_syms.add(sym)
            exit_counts.profit_decay_exit += 1
            exits.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=int(qty),
                    reason="PROFIT_DECAY_EXIT",
                    reason_code="PROFIT_DECAY_EXIT",
                    meta={
                        "triggered_rule": "PROFIT_DECAY_EXIT",
                        "avg_cost": avg_cost,
                        "pnl_pct": float(pnl_pct),
                        "bars_since_entry": int(bars_since_entry),
                        "residual_strength_score": float(residual_score),
                        "profit_decay_exit_profit_pct": float(self._profit_decay_exit_profit_pct),
                        "profit_decay_exit_min_hold_bars": int(self._profit_decay_exit_min_hold_bars),
                        "profit_decay_exit_residual_score_threshold": float(self._profit_decay_exit_residual_score_threshold),
                        "close": float(close_val),
                        "sma20": float(sma20_val),
                    },
                )
            )
        return exits

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        i = day_idx
        mx = self._mx
        feats = self._feats
        positions = ctx.positions
        position_avg_cost = ctx.position_avg_cost
        close_idx = ctx.close_idx
        nav = ctx.nav
        max_positions = ctx.max_positions
        base_order_value = ctx.base_order_value
        n = mx.close.shape[1]

        # ── 卖出信号: engine 级退出规则 ──
        def _get_atr(sym: str, d: date) -> float | None:
            col = self._sym_to_col.get(sym)
            if col is None:
                return None
            v = float(feats.atr14[i, col])
            return v if not np.isnan(v) else None

        def _check_ma20(sym: str) -> bool:
            col = self._sym_to_col.get(sym)
            if col is None:
                return False
            adj_c = float(mx.close[i, col])
            sma20_v = float(feats.sma20[i, col])
            if np.isnan(adj_c) or np.isnan(sma20_v):
                return False
            return adj_c < sma20_v

        def _check_low10(sym: str) -> bool:
            col = self._sym_to_col.get(sym)
            if col is None:
                return False
            adj_c = float(mx.close[i, col])
            low10_v = float(feats.low_min10[i, col])
            if np.isnan(adj_c) or np.isnan(low10_v):
                return False
            return adj_c < low10_v

        sell_sigs, exit_syms, exit_counts = evaluate_engine_exits(
            positions=positions,
            day=day,
            close_idx=close_idx,
            position_avg_cost=position_avg_cost,
            peak_state=self._peak_close_state,
            entry_day=self.entry_day,
            entry_bar_index=self.entry_bar_index,
            current_bar_index=i,
            entry_breakout_floor=self.entry_breakout_floor_raw,
            exit_cfg=self._ec,
            get_atr=_get_atr,
            risk_on=bool(self._risk_on[i]),
            enable_risk_off_exit=self._enable_risk_off_exit,
            risk_off_exit_mode=self._risk_off_exit_mode,
            risk_off_exit_partial_pct=self._risk_off_exit_partial_pct,
            risk_off_exit_partial_mode=self._risk_off_exit_partial_mode,
            risk_off_exit_partial_only_if_profitable=self._risk_off_exit_partial_only_if_profitable,
            risk_off_partial_state=self._risk_off_partial_state,
            market_state=str(getattr(ctx, "market_state", "") or ""),
            max_hold_days=self._max_hold_days,
            atr_stop_k=self._atr_stop_k,
            check_ma20_exit=_check_ma20,
            check_low10_exit=_check_low10,
        )
        sell_sigs.extend(
            self._evaluate_profit_decay_exits(
                day=day,
                day_idx=i,
                positions=positions,
                position_avg_cost=position_avg_cost,
                close_idx=close_idx,
                exit_syms=exit_syms,
                exit_counts=exit_counts,
            )
        )
        for _ss in sell_sigs:
            _rc = str(_ss.reason_code)
            self.diag_reason_counts[_rc] = int(self.diag_reason_counts.get(_rc, 0)) + 1

        # ── 买入信号 ──
        day_cands = self._cand_idx[i]
        buy_sigs: list[Signal] = []
        mf_score_map: dict[str, float] = {}
        strength_map: dict[str, float] = {}
        breakout_count = 0
        pullback_count = 0
        overlap_count = 0
        self.total_buy_signals += int(len(day_cands))

        # Keep score maps available for held symbols too, so downstream order planning
        # can compare incumbent holdings vs. new candidates without peeking into t+1 data.
        for held_sym, held_qty in dict(positions or {}).items():
            sym = str(held_sym).lower()
            if int(held_qty) <= 0:
                continue
            col = self._sym_to_col.get(sym)
            if col is None:
                continue
            final_score_held = (
                float(self._final_score[i, col])
                if self._final_score.size and not np.isnan(self._final_score[i, col])
                else None
            )
            residual_score_held = (
                float(self._residual_strength_score[i, col])
                if self._residual_strength_score.size and not np.isnan(self._residual_strength_score[i, col])
                else None
            )
            if final_score_held is not None:
                mf_score_map[sym] = float(final_score_held)
            if residual_score_held is not None or final_score_held is not None:
                strength_map[sym] = float(residual_score_held if residual_score_held is not None else final_score_held)

        for c in day_cands:
            sym = mx.symbols[int(c)]
            # 已持有跳过
            if sym in positions and int(positions[sym]) > 0:
                continue
            # min_hold 约束
            if self._min_hold_days > 0 and sym in self.entry_day:
                held = (day - self.entry_day[sym]).days
                if held < self._min_hold_days:
                    self.min_hold_block_count += 1
                    continue
            # cooldown 约束
            if self._cooldown_days > 0 and self.last_sell_day and sym in self.last_sell_day:
                since_sell = (day - self.last_sell_day[sym]).days
                if since_sell < self._cooldown_days:
                    self.cooldown_block_count += 1
                    continue
            if self._enable_entry_above_slow_ma and not bool(self._entry_above_slow_ma[i, c]):
                self.entry_above_slow_ma_block_count += 1
                continue
            if self._enable_entry_slow_ma_slope and not bool(self._entry_slow_ma_slope_pos[i, c]):
                self.entry_slope_block_count += 1
                continue

            close_val = float(mx.close[i, c]) if not np.isnan(mx.close[i, c]) else None
            raw_close_val = float(close_idx.get((day, sym), 0.0) or 0.0)
            slow_ma_val = float(feats.sma60[i, c]) if not np.isnan(feats.sma60[i, c]) else None
            atr_val = float(feats.atr14[i, c]) if not np.isnan(feats.atr14[i, c]) else None
            hmax_prev_main = float(self._high_max_main[i - 1, c]) if (i > 0 and not np.isnan(self._high_max_main[i - 1, c])) else None
            hmax_prev_short = float(self._high_max_short[i - 1, c]) if (i > 0 and not np.isnan(self._high_max_short[i - 1, c])) else None
            hmax_prev_long = float(self._high_max_long[i - 1, c]) if (i > 0 and not np.isnan(self._high_max_long[i - 1, c])) else None
            hit_short = bool(self._breakout_up_short[i, c]) if self._breakout_up_short.size else False
            hit_long = bool(self._breakout_up_long[i, c]) if self._breakout_up_long.size else False
            from_breakout = bool(self._breakout_buy[i, c]) if self._breakout_buy.size else False
            from_pullback = bool(self._pullback_buy[i, c]) if self._pullback_buy.size else False
            is_overlap = bool(self._pullback_overlap[i, c]) if self._pullback_overlap.size else False
            if from_breakout:
                breakout_count += 1
            if from_pullback:
                pullback_count += 1
            if is_overlap:
                overlap_count += 1
            breakout_margin_raw = float(self._breakout_margin_raw[i, c]) if self._breakout_margin_raw.size and not np.isnan(self._breakout_margin_raw[i, c]) else None
            breakout_margin_score = float(self._breakout_margin_score[i, c]) if self._breakout_margin_score.size and not np.isnan(self._breakout_margin_score[i, c]) else None
            breakout_fade_raw = float(self._breakout_fade_raw[i, c]) if self._breakout_fade_raw.size and not np.isnan(self._breakout_fade_raw[i, c]) else None
            breakout_open_gap_raw = float(self._breakout_open_gap_raw[i, c]) if self._breakout_open_gap_raw.size and not np.isnan(self._breakout_open_gap_raw[i, c]) else None
            breakout_quality_score = float(self._breakout_quality_score[i, c]) if self._breakout_quality_score.size and not np.isnan(self._breakout_quality_score[i, c]) else None
            breakout_quality_pass = bool(self._breakout_quality_pass[i, c]) if self._breakout_quality_pass.size else True
            residual_raw = float(self._residual_strength_raw[i, c]) if self._residual_strength_raw.size and not np.isnan(self._residual_strength_raw[i, c]) else None
            residual_score = float(self._residual_strength_score[i, c]) if self._residual_strength_score.size and not np.isnan(self._residual_strength_score[i, c]) else None
            sector_score = float(self._sector_strength_score[i, c]) if self._sector_strength_score.size and not np.isnan(self._sector_strength_score[i, c]) else None
            quality_score = float(self._volume_price_quality_score[i, c]) if self._volume_price_quality_score.size and not np.isnan(self._volume_price_quality_score[i, c]) else None
            conditional_tiebreak_score = float(self._conditional_tiebreak_score[i, c]) if self._conditional_tiebreak_score.size and not np.isnan(self._conditional_tiebreak_score[i, c]) else None
            conditional_factor_leader_score = float(self._conditional_factor_leader_score[i, c]) if self._conditional_factor_leader_score.size and not np.isnan(self._conditional_factor_leader_score[i, c]) else None
            conditional_institution_proxy_score = float(self._conditional_institution_proxy_score[i, c]) if self._conditional_institution_proxy_score.size and not np.isnan(self._conditional_institution_proxy_score[i, c]) else None
            conditional_crowding_score = float(self._conditional_crowding_score[i, c]) if self._conditional_crowding_score.size and not np.isnan(self._conditional_crowding_score[i, c]) else None
            industry_second_stage_score = float(self._industry_second_stage_score[i, c]) if self._industry_second_stage_score.size and not np.isnan(self._industry_second_stage_score[i, c]) else None
            industry_second_stage_not_hot_score = float(self._industry_second_stage_not_hot_score[i, c]) if self._industry_second_stage_not_hot_score.size and not np.isnan(self._industry_second_stage_not_hot_score[i, c]) else None
            industry_second_stage_uncrowded_score = float(self._industry_second_stage_uncrowded_score[i, c]) if self._industry_second_stage_uncrowded_score.size and not np.isnan(self._industry_second_stage_uncrowded_score[i, c]) else None
            industry_second_stage_breadth_timing_score = float(self._industry_second_stage_breadth_timing_score[i, c]) if self._industry_second_stage_breadth_timing_score.size and not np.isnan(self._industry_second_stage_breadth_timing_score[i, c]) else None
            industry_second_stage_persistence_10d = float(self._industry_second_stage_persistence_10d[i, c]) if self._industry_second_stage_persistence_10d.size and not np.isnan(self._industry_second_stage_persistence_10d[i, c]) else None
            industry_second_stage_active = bool(self._industry_second_stage_active[i, c]) if self._industry_second_stage_active.size else False
            leadership_route_score = float(self._leadership_route_score[i, c]) if self._leadership_route_score.size and not np.isnan(self._leadership_route_score[i, c]) else None
            leadership_route_rank = float(self._leadership_route_rank[i, c]) if self._leadership_route_rank.size and not np.isnan(self._leadership_route_rank[i, c]) else None
            leadership_route_bucket = int(self._leadership_route_bucket[i, c]) if self._leadership_route_bucket.size and int(self._leadership_route_bucket[i, c]) >= 0 else None
            final_score = float(self._final_score[i, c]) if self._final_score.size and not np.isnan(self._final_score[i, c]) else 0.5
            mf_score_map[sym] = float(final_score)
            strength_map[sym] = float(residual_score if residual_score is not None else final_score)
            pullback_variant = ""
            if self._pullback_tight1.size and bool(self._pullback_tight1[i, c]) and self._pullback_tight2.size and bool(self._pullback_tight2[i, c]):
                pullback_variant = "pb_tight_combo"
            elif self._pullback_tight1.size and bool(self._pullback_tight1[i, c]):
                pullback_variant = "pb_tight_reclaim"
            elif self._pullback_tight2.size and bool(self._pullback_tight2[i, c]):
                pullback_variant = "pb_tight_box"
            elif self._pullback_pb1.size and bool(self._pullback_pb1[i, c]):
                pullback_variant = "pb_reclaim_ma20"
            elif self._pullback_pb2.size and bool(self._pullback_pb2[i, c]):
                pullback_variant = "pb_reversal_near_low"
            elif self._pullback_pb3.size and bool(self._pullback_pb3[i, c]):
                pullback_variant = "pb_box_break"
            alpha_source = "breakout"
            reason = "BREAKOUT_DUAL_OR" if self._enable_dual_breakout else "BREAKOUT_HIGH"
            if self._enable_dual_breakout and self._dual_breakout_mode == "slow_gate_fast_trigger":
                reason = "BREAKOUT_SLOW_GATE_FAST_TRIGGER"
            reason_code = reason
            if is_overlap and from_breakout:
                alpha_source = "pullback_overlap"
                reason = "BREAKOUT_PULLBACK_CONFLUENCE"
                reason_code = "BREAKOUT_PULLBACK_CONFLUENCE"
            elif from_pullback:
                alpha_source = "pullback_only"
                reason = "PULLBACK_TREND"
                reason_code = "PULLBACK_TREND"
            else:
                pullback_variant = ""
            entry_breakout_floor_raw = None
            if (
                hmax_prev_main is not None
                and close_val is not None
                and close_val > 0.0
                and raw_close_val > 0.0
            ):
                entry_breakout_floor_raw = float(hmax_prev_main) * float(raw_close_val) / float(close_val)

            buy_sigs.append(Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=self._order_size,
                reason=reason,
                reason_code=reason_code,
                meta={
                    "close": close_val,
                    "slow_ma": slow_ma_val,
                    "atr_last": atr_val,
                    "alpha_source": alpha_source,
                    "overlap_flag": bool(is_overlap),
                    "pullback_variant": pullback_variant,
                    "breakout_margin_raw": breakout_margin_raw,
                    "breakout_margin_score": breakout_margin_score,
                    "breakout_fade_raw": breakout_fade_raw,
                    "breakout_open_gap_raw": breakout_open_gap_raw,
                    "breakout_quality_score": breakout_quality_score,
                    "breakout_quality_pass": bool(breakout_quality_pass),
                    "ranking_mode": str(self._ranking_mode),
                    "breakout_quality_gate_min_score": float(self._breakout_quality_gate_min_score),
                    "breakout_quality_margin_cap_pct": float(self._breakout_quality_margin_cap_pct),
                    "breakout_quality_fade_cap_pct": float(self._breakout_quality_fade_cap_pct),
                    "breakout_quality_open_gap_cap_pct": float(self._breakout_quality_open_gap_cap_pct),
                    "residual_vs_bench_raw": (
                        float(self._residual_vs_bench_raw[i, c])
                        if self._residual_vs_bench_raw.size and np.isfinite(self._residual_vs_bench_raw[i, c])
                        else None
                    ),
                    "residual_vs_sector_raw": (
                        float(self._residual_vs_sector_raw[i, c])
                        if self._residual_vs_sector_raw.size and np.isfinite(self._residual_vs_sector_raw[i, c])
                        else None
                    ),
                    "sector_proxy_residual_raw": (
                        float(self._sector_proxy_residual_raw[i, c])
                        if self._sector_proxy_residual_raw.size and np.isfinite(self._sector_proxy_residual_raw[i, c])
                        else None
                    ),
                    "industry_median_excess_raw": (
                        float(self._industry_median_excess_raw[i, c])
                        if self._industry_median_excess_raw.size and np.isfinite(self._industry_median_excess_raw[i, c])
                        else None
                    ),
                    "sector_beta_tailwind_raw": (
                        float(self._sector_beta_tailwind_raw[i, c])
                        if self._sector_beta_tailwind_raw.size and np.isfinite(self._sector_beta_tailwind_raw[i, c])
                        else None
                    ),
                    "residual_strength_raw": residual_raw,
                    "residual_strength_score": residual_score,
                    "residual_benchmark_weight": float(self._residual_benchmark_weight),
                    "residual_industry_weight": float(self._residual_industry_weight),
                    "industry_relative_mode": str(self._industry_relative_mode),
                    "industry_relative_regime_mode": str(self._industry_relative_regime_mode),
                    "residual_weight_regime_mode": str(self._residual_weight_regime_mode),
                    "residual_benchmark_weight_fallback": float(self._residual_benchmark_weight_fallback),
                    "residual_industry_weight_fallback": float(self._residual_industry_weight_fallback),
                    "residual_benchmark_weight_effective": float(self._residual_benchmark_weight_effective[i])
                    if self._residual_benchmark_weight_effective.size
                    else float(self._residual_benchmark_weight),
                    "residual_industry_weight_effective": float(self._residual_industry_weight_effective[i])
                    if self._residual_industry_weight_effective.size
                    else float(self._residual_industry_weight),
                    "industry_relative_mode_effective": str(self._industry_relative_mode_effective[i])
                    if self._industry_relative_mode_effective.size
                    else str(self._industry_relative_mode),
                    "residual_window_configured": int(self._residual_window),
                    "residual_window_effective": int(self._residual_window_effective[i]) if self._residual_window_effective.size else int(self._residual_window),
                    "residual_window_regime_mode": str(self._residual_window_regime_mode),
                    "residual_window_fallback": int(self._residual_window_fallback),
                    "residual_window_regime_fast_ma": int(self._residual_window_regime_fast_ma),
                    "residual_window_regime_slow_ma": int(self._residual_window_regime_slow_ma),
                    "residual_window_conditional_active": bool(
                        self._residual_window_regime_mode == "strong_risk_on"
                        and bool(self._strong_risk_on[i])
                        and int(self._residual_window_fallback) != int(self._residual_window)
                    ),
                    "residual_weight_conditional_active": bool(
                        self._residual_weight_regime_mode == "strong_risk_on"
                        and bool(self._strong_risk_on[i])
                        and (
                            abs(float(self._residual_benchmark_weight_fallback) - float(self._residual_benchmark_weight)) > 1e-12
                            or abs(float(self._residual_industry_weight_fallback) - float(self._residual_industry_weight)) > 1e-12
                        )
                    ),
                    "industry_relative_conditional_active": bool(
                        self._industry_relative_regime_mode == "strong_risk_on"
                        and bool(self._strong_risk_on[i])
                        and str(self._industry_relative_mode) != "sector_proxy"
                    ),
                    "sector_strength_score": sector_score,
                    "volume_price_quality_score": quality_score,
                    "final_score": final_score,
                    "source_aware_residual_mode": str(self._source_aware_residual_mode),
                    "residual_refine_mode": str(self._residual_refine_mode),
                    "residual_refine_weight": float(self._residual_refine_weight),
                    "industry_second_stage_min_industry_score": float(self._industry_second_stage_min_industry_score),
                    "conditional_tiebreak_score": conditional_tiebreak_score,
                    "conditional_factor_leader_score": conditional_factor_leader_score,
                    "conditional_institution_proxy_score": conditional_institution_proxy_score,
                    "conditional_crowding_score": conditional_crowding_score,
                    "conditional_recent_limit_hit_3d": bool(self._conditional_recent_limit_hit_3d[i, c]) if self._conditional_recent_limit_hit_3d.size else False,
                    "conditional_near_limit_up": bool(self._conditional_near_limit_up[i, c]) if self._conditional_near_limit_up.size else False,
                    "industry_second_stage_score": industry_second_stage_score,
                    "industry_second_stage_not_hot_score": industry_second_stage_not_hot_score,
                    "industry_second_stage_uncrowded_score": industry_second_stage_uncrowded_score,
                    "industry_second_stage_breadth_timing_score": industry_second_stage_breadth_timing_score,
                    "industry_second_stage_persistence_10d": industry_second_stage_persistence_10d,
                    "industry_second_stage_active": bool(industry_second_stage_active),
                    "leadership_route_score": leadership_route_score,
                    "leadership_route_rank": leadership_route_rank,
                    "leadership_route_bucket": leadership_route_bucket,
                    "leadership_route_bucket_count": int(self._leadership_route_bucket_count),
                    "breakout_window_main": int(self._breakout_window),
                    "high_max_main_prev": hmax_prev_main,
                    "breakout_window_short": int(self._breakout_window_short),
                    "breakout_window_long": int(self._breakout_window_long),
                    "dual_breakout_mode": str(self._dual_breakout_mode),
                    "dual_breakout_gate_ma_window": int(self._dual_breakout_gate_ma_window),
                    "dual_breakout_gate_slope_lookback": int(self._dual_breakout_gate_slope_lookback),
                    "breakout_entry_buffer_pct": float(self._breakout_entry_buffer_pct),
                    "entry_confirm_mode": str(self._entry_confirm_mode),
                    "entry_delay_mode": str(self._entry_delay_mode),
                    "entry_above_slow_ma": bool(self._entry_above_slow_ma[i, c]),
                    "slow_ma_slope_pos": bool(self._entry_slow_ma_slope_pos[i, c]),
                    "high_max_short_prev": hmax_prev_short,
                    "high_max_long_prev": hmax_prev_long,
                    "entry_breakout_floor_raw": entry_breakout_floor_raw,
                    "breakout_hit_short": hit_short,
                    "breakout_hit_long": hit_long,
                    "slow_gate_ok": bool(self._dual_breakout_slow_gate_ok[i, c]) if self._dual_breakout_slow_gate_ok.size else True,
                    "v2_trend_ok": bool(self._v2_trend_ok[i, c]),
                    "regime_on": bool(self._risk_on[i]),
                    "strong_risk_on": bool(self._strong_risk_on[i]),
                },
            ))

        return DaySignals(
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            exit_syms=exit_syms,
            strength_map=strength_map,
            mf_score_map=mf_score_map,
            mf_gate_on_today=False,
            strong_risk_on=bool(self._strong_risk_on[i]) if self._strong_risk_on.size else False,
            exit_counts=exit_counts,
            diagnostics={
                "raw_buy_signal_count": int(len(day_cands)),
                "breakout_candidates": int(max(breakout_count - overlap_count, 0)),
                "pullback_candidates": int(pullback_count),
                "pullback_overlap_candidates": int(overlap_count),
                "pullback_total_candidates": int(pullback_count + overlap_count),
                "buy_signals_generated": int(len(buy_sigs)),
                "strong_risk_on_today": bool(self._strong_risk_on[i]) if self._strong_risk_on.size else False,
                "residual_window_effective": int(self._residual_window_effective[i]) if self._residual_window_effective.size else int(self._residual_window),
                "residual_benchmark_weight_effective": float(self._residual_benchmark_weight_effective[i])
                if self._residual_benchmark_weight_effective.size
                else float(self._residual_benchmark_weight),
                "residual_industry_weight_effective": float(self._residual_industry_weight_effective[i])
                if self._residual_industry_weight_effective.size
                else float(self._residual_industry_weight),
                "residual_window_regime_fast_ma": int(self._residual_window_regime_fast_ma),
                "residual_window_regime_slow_ma": int(self._residual_window_regime_slow_ma),
            },
        )
