from __future__ import annotations

import pandas as pd

from backend.research.csi1000_negative_attribution import INDEX_CSI1000, INDEX_CSI800
from backend.research.simple_csi1000_trend_rebuild import (
    SimpleTrendConfig,
    _candidate_entry_risk_tier,
    _metrics,
    add_simple_trend_features,
    build_market_gate,
    build_membership_intervals,
    run_backtest_from_frames,
    select_rebalance_target,
)


def test_membership_intervals_support_classification() -> None:
    membership = pd.DataFrame(
        [
            {
                "index_code": INDEX_CSI1000,
                "symbol": "300001.SZ",
                "start_date": pd.Timestamp("2020-01-01"),
                "end_date": pd.Timestamp("2020-12-31"),
            }
        ]
    )

    intervals = build_membership_intervals(membership)

    assert intervals["sz300001"][0][2] == INDEX_CSI1000


def test_select_rebalance_target_uses_plain_trend_rank() -> None:
    cfg = SimpleTrendConfig(start="2020-01-01", end="2020-12-31", max_positions=1, keep_rank=2)
    features = pd.DataFrame(
        [
            {
                "symbol": "sz300001",
                "eligible_base": True,
                "ret120": 0.30,
                "ret60": 0.10,
                "avg_turnover20": 200_000_000,
            },
            {
                "symbol": "sh600001",
                "eligible_base": True,
                "ret120": 0.20,
                "ret60": 0.50,
                "avg_turnover20": 300_000_000,
            },
            {
                "symbol": "sz300002",
                "eligible_base": False,
                "ret120": 0.80,
                "ret60": 0.80,
                "avg_turnover20": 500_000_000,
            },
        ]
    )

    target, candidates = select_rebalance_target(features, {"sz300001", "sh600001", "sz300002"}, cfg)

    assert target["symbol"].tolist() == ["sz300001"]
    assert candidates["rank"].tolist() == [1, 2]


def test_metrics_include_drawdown_and_cagr() -> None:
    nav = pd.DataFrame(
        [
            {"date": "2020-01-01", "nav": 1.0, "daily_return": 0.0, "positions": 0, "turnover": 0.0},
            {"date": "2020-01-02", "nav": 1.1, "daily_return": 0.1, "positions": 1, "turnover": 1.0},
            {"date": "2020-01-03", "nav": 0.99, "daily_return": -0.1, "positions": 1, "turnover": 0.0},
        ]
    )

    metrics = _metrics(nav)

    assert metrics["total_return"] < 0
    assert metrics["max_drawdown"] < 0
    assert "cagr" in metrics


def test_run_backtest_from_frames_rebalances_weekly_with_csi1000() -> None:
    dates = pd.bdate_range("2020-01-01", periods=150)
    rows = []
    for i, date in enumerate(dates):
        rows.append(
            {
                "symbol": "sz300001",
                "date": date,
                "adj_close": 10 + i * 0.1,
                "turnover": 200_000_000,
                "is_suspended": False,
            }
        )
        rows.append(
            {
                "symbol": "sh600001",
                "date": date,
                "adj_close": 10 + i * 0.05,
                "turnover": 200_000_000,
                "is_suspended": False,
            }
        )
    prices = pd.DataFrame(rows)
    membership = pd.DataFrame(
        [
            {
                "index_code": INDEX_CSI1000,
                "symbol": "300001.SZ",
                "start_date": pd.Timestamp("2019-01-01"),
                "end_date": pd.Timestamp("2099-12-31"),
            },
            {
                "index_code": INDEX_CSI800,
                "symbol": "600001.SH",
                "start_date": pd.Timestamp("2019-01-01"),
                "end_date": pd.Timestamp("2099-12-31"),
            },
        ]
    )
    cfg = SimpleTrendConfig(start="2020-01-01", end="2020-07-31", max_positions=1, min_avg_turnover=100_000_000)

    result = run_backtest_from_frames(prices, membership, cfg)

    holdings = result["holdings"]
    assert not holdings.empty
    assert holdings["symbol"].eq("sz300001").any()
    assert result["perf"]["trade_rows"] > 0


def test_run_backtest_keeps_existing_holding_inside_keep_rank() -> None:
    dates = pd.bdate_range("2020-01-01", periods=140)
    rows = []
    for symbol, slope in [("sz300001", 0.10), ("sh600001", 0.09), ("sz300002", 0.08)]:
        for i, date in enumerate(dates):
            rows.append(
                {
                    "symbol": symbol,
                    "date": date,
                    "adj_close": 10 + i * slope,
                    "turnover": 200_000_000,
                    "is_suspended": False,
                }
            )
    prices = pd.DataFrame(rows)
    membership = pd.DataFrame(
        [
            {
                "index_code": INDEX_CSI1000,
                "symbol": symbol,
                "start_date": pd.Timestamp("2019-01-01"),
                "end_date": pd.Timestamp("2099-12-31"),
            }
            for symbol in ["300001.SZ", "600001.SH", "300002.SZ"]
        ]
    )
    cfg = SimpleTrendConfig(
        start="2020-01-01",
        end="2020-07-31",
        max_positions=1,
        keep_rank=2,
        min_avg_turnover=100_000_000,
    )

    result = run_backtest_from_frames(prices, membership, cfg)
    sells = result["trades"].loc[result["trades"]["side"].eq("SELL")]

    assert sells.empty


def test_add_simple_trend_features_keeps_only_mature_positive_trend_eligible() -> None:
    dates = pd.bdate_range("2020-01-01", periods=130)
    prices = pd.DataFrame(
        {
            "symbol": ["sz300001"] * len(dates),
            "date": dates,
            "adj_close": [10 + i * 0.1 for i in range(len(dates))],
            "turnover": [200_000_000] * len(dates),
            "is_suspended": [False] * len(dates),
        }
    )
    cfg = SimpleTrendConfig(start="2020-01-01", end="2020-07-31")

    features = add_simple_trend_features(prices, cfg)

    assert bool(features.iloc[-1]["eligible_base"]) is True


def test_market_2of3_filter_turns_off_when_only_one_index_is_above_ma() -> None:
    dates = pd.bdate_range("2020-01-01", periods=130)
    rows = []
    for code, slope in [("000300.SH", 0.10), ("000905.SH", -0.02), ("000852.SH", -0.03)]:
        for i, date in enumerate(dates):
            rows.append({"index_code": code, "date": date, "close": 100 + i * slope})
    cfg = SimpleTrendConfig(
        start="2020-01-01",
        end="2020-07-31",
        variant="market_2of3_ma120",
        market_filter_ma_window=120,
        market_filter_min_on=2,
    )

    gate = build_market_gate(pd.DataFrame(rows), cfg)

    assert bool(gate.iloc[-1]["market_gate_on"]) is False
    assert int(gate.iloc[-1]["market_positive_count"]) == 1


def test_entry_risk_scaled_tier_uses_entry_time_buckets() -> None:
    tier = _candidate_entry_risk_tier(
        pd.Series(
            {
                "ret20": 0.40,
                "ret120": 1.00,
                "ma120_distance": 0.60,
                "vol20": 0.07,
            }
        ),
        "csi1000_new",
    )

    assert tier == "3_plus_extreme"
