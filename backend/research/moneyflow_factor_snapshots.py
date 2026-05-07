from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from backend.research.moneyflow_factor_catalog import list_moneyflow_factor_ids


def _cross_sectional_zscore(series: pd.Series) -> pd.Series:
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    if not np.isfinite(std) or std <= 0:
        return pd.Series(np.zeros(len(series), dtype=float), index=series.index)
    return (series - mean) / std


def _prepare_monthly_panel(monthly_panel: pd.DataFrame) -> pd.DataFrame:
    frame = monthly_panel.copy()
    required = {"month", "symbol", "monthly_divergence_rate", "monthly_factor_valid"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"monthly_panel missing required columns: {', '.join(missing)}")
    frame["month"] = pd.to_datetime(frame["month"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame["monthly_divergence_rate"] = pd.to_numeric(frame["monthly_divergence_rate"], errors="coerce")
    frame["monthly_factor_valid"] = frame["monthly_factor_valid"].fillna(False).astype(bool)
    return frame.sort_values(["month", "symbol"]).reset_index(drop=True)


def build_moneyflow_factor_snapshots(
    monthly_panel: pd.DataFrame,
    *,
    factor_ids: Sequence[str] | None = None,
) -> pd.DataFrame:
    frame = _prepare_monthly_panel(monthly_panel)
    selected = [str(item).strip().lower() for item in list(factor_ids or list_moneyflow_factor_ids()) if str(item).strip()]
    if not selected:
        raise ValueError("factor_ids cannot be empty")
    unknown = sorted(set(selected) - set(list_moneyflow_factor_ids()))
    if unknown:
        raise ValueError(f"unknown moneyflow factors: {', '.join(unknown)}")

    raw_map: dict[str, pd.Series] = {
        "monthly_divergence_rate": frame["monthly_divergence_rate"],
    }
    snapshots: list[pd.DataFrame] = []
    for factor_id in selected:
        raw = pd.to_numeric(raw_map[factor_id], errors="coerce")
        availability = frame["monthly_factor_valid"] & raw.notna()
        ranked_source = raw.where(availability)
        item = frame.loc[:, ["month", "symbol"]].copy()
        item["factor_id"] = factor_id
        item["raw_value"] = raw
        item["availability_flag"] = availability
        item["normalized_value"] = ranked_source.groupby(frame["month"]).transform(_cross_sectional_zscore)
        item["rank_value"] = ranked_source.groupby(frame["month"]).rank(method="average", pct=True)
        item.loc[~item["availability_flag"], ["normalized_value", "rank_value"]] = np.nan
        item["asof_timestamp"] = item["month"].dt.strftime("%Y-%m-%dT15:00:00+08:00")
        item["date"] = item["month"].dt.strftime("%Y-%m-%d")
        snapshots.append(item)

    out = pd.concat(snapshots, axis=0, ignore_index=True)
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


def build_moneyflow_factor_score_snapshot(
    factor_snapshot: pd.DataFrame,
    *,
    factor_ids: Sequence[str],
    factor_weights: dict[str, float] | None = None,
    score_id: str = "moneyflow_factor_score",
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
    weighted = sum(
        pivot[factor_id].fillna(0.0) * float(weights.get(factor_id, 0.0))
        for factor_id in selected
    ) / weight_sum
    coverage = pivot[selected].notna().any(axis=1)
    out = weighted.rename("score_value").reset_index()
    out["score_id"] = score_id
    out["availability_flag"] = coverage.to_numpy()
    out["asof_timestamp"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%dT15:00:00+08:00")
    return out.loc[:, ["date", "symbol", "score_id", "score_value", "availability_flag", "asof_timestamp"]]
