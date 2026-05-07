from __future__ import annotations

import pandas as pd

from backend.research.stock_alpha_factor_catalog import build_stock_alpha_factor_catalog
from backend.research.stock_alpha_factor_snapshots import build_stock_alpha_factor_score_snapshot, build_stock_alpha_factor_snapshots


def _price_history() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=70)
    rows: list[dict[str, object]] = []
    bases = {
        "sh600000": 10.0,
        "sz000001": 12.0,
        "sh601318": 14.0,
    }
    slopes = {
        "sh600000": 0.08,
        "sz000001": 0.05,
        "sh601318": 0.03,
    }
    for symbol, base in bases.items():
        slope = slopes[symbol]
        for idx, dt in enumerate(dates):
            close = base + slope * idx
            rows.append(
                {
                    "date": dt,
                    "symbol": symbol,
                    "close": close,
                    "high": close * 1.01,
                    "amount": 1.0e8 + idx * 1.0e6,
                }
            )
    return pd.DataFrame(rows)


def test_build_stock_alpha_factor_catalog_has_expected_first_wave_factors() -> None:
    catalog = build_stock_alpha_factor_catalog()
    ids = [item["factor_id"] for item in catalog]
    assert ids == [
        "breakout_distance",
        "residual_strength",
        "trend_quality",
        "volatility_penalty",
        "liquidity_quality",
    ]


def test_build_stock_alpha_factor_snapshots_emits_required_columns() -> None:
    snapshots = build_stock_alpha_factor_snapshots(
        _price_history(),
        factor_ids=["breakout_distance", "trend_quality"],
    )
    assert set(
        [
            "date",
            "symbol",
            "factor_id",
            "raw_value",
            "normalized_value",
            "rank_value",
            "availability_flag",
            "asof_timestamp",
        ]
    ).issubset(snapshots.columns)
    assert sorted(snapshots["factor_id"].unique().tolist()) == ["breakout_distance", "trend_quality"]
    assert snapshots["availability_flag"].any()


def test_build_stock_alpha_factor_score_snapshot_combines_normalized_values() -> None:
    snapshots = build_stock_alpha_factor_snapshots(
        _price_history(),
        factor_ids=["breakout_distance", "residual_strength"],
    )
    score = build_stock_alpha_factor_score_snapshot(
        snapshots,
        factor_ids=["breakout_distance", "residual_strength"],
        factor_weights={"breakout_distance": 1.0, "residual_strength": 1.0},
    )
    assert set(["date", "symbol", "score_id", "score_value", "availability_flag", "asof_timestamp"]).issubset(score.columns)
    assert score["score_id"].nunique() == 1
