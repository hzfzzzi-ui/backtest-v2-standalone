from __future__ import annotations

import pandas as pd

from backend.research.v4_fundamental_quality_shadow import (
    _quality_columns,
    compute_quality_score,
    load_buy_entries,
    quality_bucket,
)


def test_quality_column_aliases_are_plain_fundamental_components() -> None:
    columns = {"symbol", "ann_date", "end_date", "roe", "grossprofit_margin", "debt_ratio"}

    assert _quality_columns(columns) == {
        "roe": "roe",
        "gross_margin": "grossprofit_margin",
        "leverage": "debt_ratio",
    }


def test_quality_score_rewards_profitability_and_lower_leverage() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["sh600000", "sh600001", "sh600002"],
            "roe": [5.0, 20.0, 10.0],
            "gross_margin": [10.0, 40.0, 20.0],
            "leverage": [80.0, 20.0, 60.0],
        }
    )

    scored = compute_quality_score(frame)

    best = scored.sort_values("quality_score", ascending=False).iloc[0]
    worst = scored.sort_values("quality_score", ascending=True).iloc[0]
    assert best["symbol"] == "sh600001"
    assert worst["symbol"] == "sh600000"
    assert scored["quality_component_count"].tolist() == [3, 3, 3]


def test_quality_bucket_boundaries_are_stable() -> None:
    assert quality_bucket(None) == "missing"
    assert quality_bucket(0.10) == "q1_low"
    assert quality_bucket(0.30) == "q2_mid_low"
    assert quality_bucket(0.60) == "q3_mid_high"
    assert quality_bucket(0.90) == "q4_high"


def test_load_buy_entries_uses_signal_date_from_meta_json(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pd.DataFrame(
        [
            {
                "date": "2026-01-05",
                "symbol": "000001.SZ",
                "side": "BUY",
                "price": 10.0,
                "value": 1000.0,
                "reason_code": "BREAKOUT_HIGH",
                "meta_json": '{"signal_date":"2026-01-02","final_score_rank":2,"final_score_value":0.7}',
            },
            {
                "date": "2026-01-06",
                "symbol": "000002.SZ",
                "side": "SELL",
                "price": 11.0,
                "value": 1100.0,
                "reason_code": "STOP",
                "meta_json": "{}",
            },
        ]
    ).to_csv(source / "portfolio_trades.csv", index=False)

    entries = load_buy_entries(source, "2026-01-01", "2026-01-31")

    assert len(entries) == 1
    assert entries.loc[0, "symbol"] == "sz000001"
    assert entries.loc[0, "signal_date"] == pd.Timestamp("2026-01-02")
    assert entries.loc[0, "final_score_rank"] == 2
