from __future__ import annotations

from datetime import timedelta

import pandas as pd

from backend.core.services.market_snapshot_service import build_market_snapshot_from_frames


def _build_market_history() -> pd.DataFrame:
    dates = pd.bdate_range("2025-10-01", periods=90)
    rows: list[dict[str, object]] = []
    for idx, trade_date in enumerate(dates):
        symbol_specs = [
            ("sh600001", 10.0 + 0.12 * idx, 1.2e8 + 2.0e6 * idx, 1.1 + 0.01 * idx, 0.9 + 0.002 * idx, 9.0e9 + 3.0e7 * idx),
            ("sz000001", 18.0 - 0.05 * idx, 1.0e8 + 1.5e6 * idx, 0.9 + 0.004 * idx, 0.8 + 0.001 * idx, 7.0e9 + 2.0e7 * idx),
            ("sz300001", 14.0 + 0.08 * idx, 1.4e8 + 2.5e6 * idx, 1.4 + 0.006 * idx, 1.1 + 0.003 * idx, 8.5e9 + 2.5e7 * idx),
        ]
        for symbol, close, amount, turnover_rate_f, volume_ratio, circ_mv in symbol_specs:
            limit_up = close * 1.10
            limit_down = close * 0.90
            if trade_date == dates[-1] and symbol == "sh600001":
                limit_up = close
            if trade_date == dates[-1] and symbol == "sz000001":
                limit_down = close
            rows.append(
                {
                    "date": trade_date,
                    "symbol": symbol,
                    "close": close,
                    "amount": amount,
                    "limit_up": limit_up,
                    "limit_down": limit_down,
                    "turnover_rate_f": turnover_rate_f,
                    "turnover_rate": turnover_rate_f - 0.1,
                    "volume_ratio": volume_ratio,
                    "circ_mv": circ_mv,
                    "volume": 1_000_000 + idx * 1_000,
                    "is_suspended": False,
                }
            )
    return pd.DataFrame(rows)


def _build_index_histories(last_date: pd.Timestamp, include_csi1000: bool = False) -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range(last_date - pd.tseries.offsets.BDay(89), last_date)
    factors = {
        "000001.SH": 1.0,
        "399001.SZ": 1.2,
        "399006.SZ": 1.4,
        "000300.SH": 0.9,
        "000905.SH": 1.3,
    }
    if include_csi1000:
        factors["000852.SH"] = 1.5
    histories: dict[str, pd.DataFrame] = {}
    for symbol, factor in factors.items():
        rows = []
        for idx, trade_date in enumerate(dates):
            rows.append(
                {
                    "date": trade_date,
                    "symbol": symbol,
                    "close": 1000.0 + factor * idx * 5.0,
                    "amount": 1.0e11 + factor * idx * 1.0e9,
                    "volume": 1.0e9 + factor * idx * 1.0e7,
                }
            )
        histories[symbol] = pd.DataFrame(rows)
    return histories


def _build_sentiment_history(last_date: pd.Timestamp) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "as_of": last_date,
                "sent_state": "HOT",
                "sent_score": 82.0,
                "advancers": 2,
                "decliners": 1,
                "limit_up": 1,
                "limit_down": 0,
                "created_at": pd.Timestamp(last_date) + pd.Timedelta(hours=18),
            }
        ]
    )


def test_market_snapshot_builder_outputs_six_layers_and_sources() -> None:
    market_history = _build_market_history()
    requested_trade_date = pd.Timestamp(market_history["date"].max()).date()
    index_histories = _build_index_histories(pd.Timestamp(requested_trade_date), include_csi1000=False)
    sentiment_history = _build_sentiment_history(pd.Timestamp(requested_trade_date))

    snapshot = build_market_snapshot_from_frames(
        requested_trade_date=requested_trade_date,
        market_history=market_history,
        index_histories=index_histories,
        sentiment_history=sentiment_history,
        provider_query_audit=[],
    )

    assert snapshot["schema_version"] == "market_snapshot_v1"
    for layer in (
        "index_layer",
        "style_layer",
        "breadth_layer",
        "liquidity_layer",
        "sentiment_layer",
        "risk_layer",
    ):
        assert layer in snapshot
        assert snapshot[layer]["sources"]
        assert "coverage" in snapshot[layer]

    assert snapshot["breadth_layer"]["advancers_count"] == 2
    assert snapshot["sentiment_layer"]["sentiment_regime"] == "hot"
    assert snapshot["style_layer"]["style_rel_1000_vs_300"] is None
    warning_codes = {item["code"] for item in snapshot["warnings"]}
    assert "INDEX_HISTORY_MISSING" in warning_codes


def test_market_snapshot_builder_marks_stale_and_uses_prev_window_for_heat() -> None:
    market_history = _build_market_history()
    last_date = pd.Timestamp(market_history["date"].max())
    requested_trade_date = (last_date + timedelta(days=5)).date()
    index_histories = _build_index_histories(last_date, include_csi1000=True)
    sentiment_history = _build_sentiment_history(last_date)

    snapshot = build_market_snapshot_from_frames(
        requested_trade_date=requested_trade_date,
        market_history=market_history,
        index_histories=index_histories,
        sentiment_history=sentiment_history,
        provider_query_audit=[],
    )

    daily_amount = market_history.groupby("date")["amount"].sum().sort_index()
    expected_prev_ma20 = float(daily_amount.iloc[-21:-1].mean())
    expected_heat = float(daily_amount.iloc[-1] / expected_prev_ma20)

    assert abs(snapshot["liquidity_layer"]["market_amount_heat"] - expected_heat) < 1e-9
    warning_codes = {item["code"] for item in snapshot["warnings"]}
    assert "STALE_MARKET_PRICE_DATA" in warning_codes
