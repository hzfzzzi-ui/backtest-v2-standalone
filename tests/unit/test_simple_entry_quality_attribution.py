from __future__ import annotations

import pandas as pd

from backend.research.simple_entry_quality_attribution import (
    _entry_features,
    _path_metrics,
    accel_bucket,
    drawdown60_bucket,
    entry_risk_labels,
    entry_risk_tier,
    ret120_bucket,
    risk_tier_multiplier,
)


def test_buckets_are_plain_and_stable() -> None:
    assert ret120_bucket(0.15) == "<20%"
    assert ret120_bucket(0.60) == "40-80%"
    assert ret120_bucket(1.20) == ">=80%"
    assert accel_bucket(0.30, 0.60) == "recent_fast"
    assert drawdown60_bucket(-0.25) == "deep<-20%"
    assert drawdown60_bucket(-0.01) == "near_high"


def test_path_metrics_labels_future_return_mfe_and_mae() -> None:
    closes = pd.Series([10.0, 11.0, 9.0, 12.0, 8.0, 13.0])

    metrics = _path_metrics(closes, 0, horizons=(3,))

    assert round(metrics["fwd_ret_3"], 6) == 0.2
    assert round(metrics["mfe_3"], 6) == 0.2
    assert round(metrics["mae_3"], 6) == -0.1


def test_entry_features_use_history_and_output_future_labels() -> None:
    dates = pd.bdate_range("2020-01-01", periods=140)
    frame = pd.DataFrame(
        {
            "symbol": ["sz300001"] * len(dates),
            "date": dates,
            "adj_close": [10.0 + i * 0.1 for i in range(len(dates))],
            "turnover": [200_000_000.0] * len(dates),
        }
    )

    features = _entry_features(frame, dates[120])

    assert features["ret120"] > 1.0
    assert features["ma120_distance"] > 0
    assert features["avg_turnover20"] == 200_000_000.0
    assert "fwd_ret_20" in features


def test_entry_risk_labels_are_descriptive_and_entry_time_only() -> None:
    row = {
        "membership_bucket": "csi1000_new",
        "ma_distance_bucket": ">=50%",
        "vol20_bucket": ">=6%",
        "ret120_bucket": ">=80%",
        "accel_bucket": "very_recent",
        "fwd_ret_60": 1.0,
        "realized_return": 1.0,
    }

    labels = entry_risk_labels(row)

    assert labels == [
        "high_extension",
        "high_volatility",
        "late_acceleration",
        "csi1000_high_extension",
    ]
    assert entry_risk_tier(len(labels)) == "3_plus_extreme"


def test_risk_tier_multiplier_keeps_fixed_mapping() -> None:
    assert risk_tier_multiplier("0_low") == 1.0
    assert risk_tier_multiplier("1_watch") == 0.8
    assert risk_tier_multiplier("2_high") == 0.5
    assert round(risk_tier_multiplier("3_plus_extreme"), 6) == round(1.0 / 3.0, 6)
    assert risk_tier_multiplier("unknown") == 1.0
