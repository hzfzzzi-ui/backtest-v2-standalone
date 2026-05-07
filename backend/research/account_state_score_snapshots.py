from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.core.data.mapping import normalize_index_symbol
from backend.research.account_state_score_catalog import list_account_state_score_ids


_REQUIRED_COLUMNS = {"date", "symbol", "close"}


def _ensure_required_columns(frame: pd.DataFrame) -> None:
    missing = sorted(_REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"account state score snapshot missing columns: {', '.join(missing)}")


def _sigmoid(values: pd.Series, *, scale: float) -> pd.Series:
    clipped = np.clip(values.astype(float), -10.0, 10.0)
    return 1.0 / (1.0 + np.exp(-scale * clipped))


def _asof_timestamp(date_text: str) -> str:
    return f"{date_text}T15:00:00+08:00"


def _derive_state(wide: pd.DataFrame) -> pd.Series:
    defense = wide["defense_score"].astype(float)
    recovery = wide["recovery_score"].astype(float)
    risk_on = wide["risk_on_score"].astype(float)
    derived = np.full(len(wide), "TRANS_DOWN", dtype=object)
    derived = np.where(
        (defense >= 0.60) & (defense >= recovery) & (defense >= risk_on),
        "RISK_OFF",
        derived,
    )
    derived = np.where(
        (risk_on >= 0.60) & (risk_on >= recovery) & (risk_on > defense),
        "BULL",
        derived,
    )
    derived = np.where(
        (recovery >= 0.50) & (recovery >= defense) & (recovery > risk_on),
        "TRANS_UP",
        derived,
    )
    return pd.Series(derived, index=wide.index, dtype="object")


def build_account_state_score_snapshots(
    benchmark_history: pd.DataFrame,
    *,
    benchmark_symbol: str,
    score_ids: list[str] | None = None,
) -> pd.DataFrame:
    frame = benchmark_history.copy()
    _ensure_required_columns(frame)
    symbol = normalize_index_symbol(str(benchmark_symbol or "").strip())
    if not symbol:
        raise ValueError("benchmark_symbol is required for account state score snapshots")
    frame["symbol"] = frame["symbol"].astype(str).map(lambda value: normalize_index_symbol(str(value).strip()))
    frame = frame.loc[frame["symbol"] == symbol].copy()
    if frame.empty:
        raise ValueError(f"no benchmark history found for symbol={benchmark_symbol}")
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date").reset_index(drop=True)

    close = frame["close"].astype(float)
    ma20 = close.rolling(20, min_periods=20).mean()
    ma60 = close.rolling(60, min_periods=60).mean()
    ma120 = close.rolling(120, min_periods=120).mean()
    rolling_high60 = close.rolling(60, min_periods=60).max()

    long_trend_raw = close.div(ma120) - 1.0
    short_trend_raw = close.div(ma20) - 1.0
    medium_slope_raw = ma20.div(ma60) - 1.0
    drawdown60_raw = close.div(rolling_high60) - 1.0

    raw_values = pd.DataFrame(
        {
            "date": frame["date"].dt.strftime("%Y-%m-%d"),
            "risk_on_score": 0.45 * long_trend_raw + 0.35 * medium_slope_raw + 0.20 * short_trend_raw,
            "recovery_score": 0.55 * short_trend_raw + 0.45 * medium_slope_raw - 0.35 * np.maximum(long_trend_raw, 0.0),
            "defense_score": 0.55 * (-long_trend_raw) + 0.25 * (-medium_slope_raw) + 0.20 * (-drawdown60_raw),
        }
    )
    requested_ids = [str(item).strip().lower() for item in list(score_ids or []) if str(item).strip()]
    selected_ids = requested_ids or list_account_state_score_ids()

    normalized = pd.DataFrame({"date": raw_values["date"]})
    normalized["risk_on_score"] = _sigmoid(raw_values["risk_on_score"], scale=18.0)
    normalized["recovery_score"] = _sigmoid(raw_values["recovery_score"], scale=20.0)
    normalized["defense_score"] = _sigmoid(raw_values["defense_score"], scale=18.0)

    availability = (
        long_trend_raw.notna()
        & short_trend_raw.notna()
        & medium_slope_raw.notna()
        & drawdown60_raw.notna()
    )
    normalized["derived_state"] = _derive_state(normalized.loc[:, ["risk_on_score", "recovery_score", "defense_score"]])

    rows: list[dict[str, Any]] = []
    for score_id in selected_ids:
        if score_id not in raw_values.columns:
            raise KeyError(f"unknown account state score in snapshot request: {score_id}")
        for idx, row in raw_values.loc[:, ["date", score_id]].iterrows():
            date_text = str(row["date"])
            rows.append(
                sanitize_json(
                    {
                        "date": date_text,
                        "score_id": score_id,
                        "scope": "account",
                        "raw_value": float(row[score_id]) if pd.notna(row[score_id]) else None,
                        "normalized_value": (
                            float(normalized.loc[idx, score_id]) if pd.notna(normalized.loc[idx, score_id]) else None
                        ),
                        "availability_flag": bool(availability.iloc[idx]),
                        "asof_timestamp": _asof_timestamp(date_text),
                        "source_trace": json.dumps(
                            {
                                "benchmark_symbol": symbol,
                                "inputs": ["close"],
                                "components": {
                                    "risk_on_score": ["long_trend_raw", "medium_slope_raw", "short_trend_raw"],
                                    "recovery_score": ["short_trend_raw", "medium_slope_raw", "long_trend_raw"],
                                    "defense_score": ["long_trend_raw", "medium_slope_raw", "drawdown60_raw"],
                                }.get(score_id, []),
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        "derived_state": str(normalized.loc[idx, "derived_state"]) if availability.iloc[idx] else None,
                    }
                )
            )
    return pd.DataFrame(rows)


def build_account_state_combo_score_snapshot(
    score_snapshot: pd.DataFrame,
    *,
    score_ids: list[str],
    score_weights: dict[str, float],
    combo_score_id: str = "account_state_combo_score",
) -> pd.DataFrame:
    subset = score_snapshot.loc[score_snapshot["score_id"].isin(score_ids)].copy()
    if subset.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "score_id",
                "scope",
                "raw_value",
                "normalized_value",
                "availability_flag",
                "asof_timestamp",
                "source_trace",
                "derived_state",
            ]
        )
    pivot = subset.pivot_table(index="date", columns="score_id", values="normalized_value", aggfunc="first")
    available_scores = [score_id for score_id in score_ids if score_id in pivot.columns]
    weights = np.array([float(score_weights.get(score_id, 0.0)) for score_id in available_scores], dtype=float)
    if np.allclose(weights.sum(), 0.0):
        weights = np.ones(len(available_scores), dtype=float)
    normalized_weights = weights / float(weights.sum())
    combo_norm = pivot.loc[:, available_scores].mul(normalized_weights, axis=1).sum(axis=1)
    combo_raw = combo_norm * 2.0 - 1.0

    derived_lookup = (
        subset.loc[:, ["date", "derived_state"]]
        .drop_duplicates(subset=["date"])
        .set_index("date")["derived_state"]
        .to_dict()
    )
    asof_lookup = (
        subset.loc[:, ["date", "asof_timestamp"]]
        .drop_duplicates(subset=["date"])
        .set_index("date")["asof_timestamp"]
        .to_dict()
    )
    availability_lookup = subset.groupby("date")["availability_flag"].all().to_dict()

    rows = [
        sanitize_json(
            {
                "date": str(date_text),
                "score_id": combo_score_id,
                "scope": "account",
                "raw_value": float(combo_raw.loc[date_text]),
                "normalized_value": float(combo_norm.loc[date_text]),
                "availability_flag": bool(availability_lookup.get(date_text, False)),
                "asof_timestamp": str(asof_lookup.get(date_text) or _asof_timestamp(str(date_text))),
                "source_trace": json.dumps(
                    {
                        "components": available_scores,
                        "weights": {score_id: float(score_weights.get(score_id, 0.0)) for score_id in available_scores},
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "derived_state": str(derived_lookup.get(date_text) or ""),
            }
        )
        for date_text in combo_norm.index
    ]
    return pd.DataFrame(rows)
