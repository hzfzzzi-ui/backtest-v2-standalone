from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from backend.research.stock_alpha_factor_catalog import list_stock_alpha_factor_ids


def _rolling_group_stat(
    series: pd.Series,
    groups: pd.Series,
    *,
    window: int,
    min_periods: int,
    func: str,
) -> pd.Series:
    rolled = getattr(
        series.groupby(groups).rolling(window=window, min_periods=min_periods),
        func,
    )()
    return rolled.reset_index(level=0, drop=True)


def _cross_sectional_zscore(series: pd.Series) -> pd.Series:
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    if not np.isfinite(std) or std <= 0:
        return pd.Series(np.zeros(len(series), dtype=float), index=series.index)
    return (series - mean) / std


def _prepare_price_history(price_history: pd.DataFrame) -> pd.DataFrame:
    frame = price_history.copy()
    if "date" not in frame.columns or "symbol" not in frame.columns:
        raise ValueError("price_history must contain date and symbol columns")
    frame["date"] = pd.to_datetime(frame["date"])
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    for col in ("close", "high", "amount"):
        if col not in frame.columns:
            raise ValueError(f"price_history must contain column '{col}'")
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    return frame


def build_stock_alpha_factor_snapshots(
    price_history: pd.DataFrame,
    *,
    factor_ids: Sequence[str] | None = None,
) -> pd.DataFrame:
    frame = _prepare_price_history(price_history)
    selected = [str(item).strip().lower() for item in list(factor_ids or list_stock_alpha_factor_ids()) if str(item).strip()]
    if not selected:
        raise ValueError("factor_ids cannot be empty")
    unknown = sorted(set(selected) - set(list_stock_alpha_factor_ids()))
    if unknown:
        raise ValueError(f"unknown stock alpha factors: {', '.join(unknown)}")

    by_symbol = frame["symbol"]
    close = frame["close"]
    high = frame["high"]
    amount = frame["amount"]

    prev_close_20 = close.groupby(by_symbol).shift(20)
    ret_20 = close / prev_close_20 - 1.0
    ret_1 = close.groupby(by_symbol).pct_change()
    vol_20 = _rolling_group_stat(ret_1, by_symbol, window=20, min_periods=10, func="std")
    prev_high_45 = _rolling_group_stat(high.groupby(by_symbol).shift(1), by_symbol, window=45, min_periods=20, func="max")
    amount_avg_20 = _rolling_group_stat(amount.groupby(by_symbol).shift(1), by_symbol, window=20, min_periods=10, func="mean")

    raw_map: dict[str, pd.Series] = {
        "breakout_distance": close / prev_high_45 - 1.0,
        "residual_strength": ret_20 - ret_20.groupby(frame["date"]).transform("median"),
        "trend_quality": ret_20 / (vol_20 * np.sqrt(20.0)),
        "volatility_penalty": -vol_20,
        "liquidity_quality": np.log1p(amount_avg_20.clip(lower=0.0)),
    }

    snapshots: list[pd.DataFrame] = []
    for factor_id in selected:
        raw = pd.to_numeric(raw_map[factor_id], errors="coerce")
        item = frame.loc[:, ["date", "symbol"]].copy()
        item["factor_id"] = factor_id
        item["raw_value"] = raw
        item["availability_flag"] = raw.notna()
        item["normalized_value"] = raw.groupby(frame["date"]).transform(_cross_sectional_zscore)
        item["rank_value"] = raw.groupby(frame["date"]).rank(method="average", pct=True)
        item.loc[~item["availability_flag"], ["normalized_value", "rank_value"]] = np.nan
        item["asof_timestamp"] = item["date"].dt.strftime("%Y-%m-%dT15:00:00+08:00")
        snapshots.append(item)

    out = pd.concat(snapshots, axis=0, ignore_index=True)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.loc[
        :,
        [
            "date",
            "symbol",
            "factor_id",
            "raw_value",
            "normalized_value",
            "rank_value",
            "availability_flag",
            "asof_timestamp",
        ],
    ].sort_values(["date", "symbol", "factor_id"]).reset_index(drop=True)


def build_stock_alpha_factor_score_snapshot(
    factor_snapshot: pd.DataFrame,
    *,
    factor_ids: Sequence[str],
    factor_weights: dict[str, float] | None = None,
    score_id: str = "stock_alpha_factor_score",
) -> pd.DataFrame:
    selected = [str(item).strip().lower() for item in list(factor_ids or []) if str(item).strip()]
    if not selected:
        raise ValueError("factor_ids cannot be empty for factor score")
    frame = factor_snapshot.copy()
    frame["factor_id"] = frame["factor_id"].astype(str).str.lower()
    subset = frame.loc[frame["factor_id"].isin(selected)].copy()
    if subset.empty:
        raise ValueError("no factor snapshot rows found for requested factor_ids")
    weights = {key: float(value) for key, value in dict(factor_weights or {}).items()}
    if not weights:
        weights = {factor_id: 1.0 for factor_id in selected}

    pivot = subset.pivot_table(
        index=["date", "symbol"],
        columns="factor_id",
        values="normalized_value",
        aggfunc="first",
    )
    for factor_id in selected:
        if factor_id not in pivot.columns:
            pivot[factor_id] = np.nan
    weight_sum = sum(abs(weights.get(factor_id, 0.0)) for factor_id in selected)
    if weight_sum <= 0:
        raise ValueError("factor_weights must contain at least one non-zero weight")
    weighted = sum(pivot[factor_id].fillna(0.0) * float(weights.get(factor_id, 0.0)) for factor_id in selected) / weight_sum
    coverage = pivot[selected].notna().any(axis=1)
    out = weighted.rename("score_value").reset_index()
    out["score_id"] = score_id
    out["availability_flag"] = coverage.to_numpy()
    out["asof_timestamp"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%dT15:00:00+08:00")
    return out.loc[:, ["date", "symbol", "score_id", "score_value", "availability_flag", "asof_timestamp"]]
