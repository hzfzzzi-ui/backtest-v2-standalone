from __future__ import annotations

from datetime import date
import pandas as pd

from backend.cli.managed import update_pams_ohlcv_daily_v2_raw as updater


def test_tushare_source_tables_land_in_raw_vendor_namespace() -> None:
    assert updater.SOURCE_TABLES == {
        "stock_basic": "raw_tushare_stock_basic",
        "trade_cal": "raw_tushare_trade_cal",
        "daily": "raw_tushare_daily",
        "adj_factor": "raw_tushare_adj_factor",
        "daily_basic": "raw_tushare_daily_basic",
        "suspend_d": "raw_tushare_suspend_d",
        "stk_limit": "raw_tushare_stk_limit",
        "moneyflow": "raw_tushare_moneyflow",
    }
    assert len(set(updater.SOURCE_TABLES.values())) == len(updater.SOURCE_TABLES)
    assert all(table.startswith("raw_tushare_") for table in updater.SOURCE_TABLES.values())


def test_query_with_retry_retries_then_succeeds(monkeypatch) -> None:
    calls = {"count": 0}

    def _fetch():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ConnectionError("temporary failure")
        return "ok"

    monkeypatch.setattr(updater.time, "sleep", lambda _: None)

    result = updater._query_with_retry(
        _fetch,
        label="daily",
        trade_date=date(2026, 3, 16),
        max_attempts=5,
        sleep_seconds=1,
    )

    assert result == "ok"
    assert calls["count"] == 3


def test_query_with_retry_soft_fails_network_error_for_stk_limit() -> None:
    events: list[dict[str, object]] = []

    def _fetch():
        raise ConnectionError("HTTPConnectionPool(host='api.waditu.com', port=80): Failed to resolve")

    result = updater._query_with_retry(
        _fetch,
        label="stk_limit",
        trade_date=date(2011, 4, 21),
        max_attempts=2,
        sleep_seconds=0,
        allow_soft_fail=True,
        soft_fail_events=events,
    )

    assert result is None
    assert len(events) == 1
    assert events[0]["label"] == "stk_limit"
    assert events[0]["trade_date"] == "2011-04-21"


def test_query_with_retry_soft_fails_network_error_for_moneyflow() -> None:
    events: list[dict[str, object]] = []

    def _fetch():
        raise ConnectionError("HTTPSConnectionPool(host='api.waditu.com', port=443): Temporary failure in name resolution")

    result = updater._query_with_retry(
        _fetch,
        label="moneyflow",
        trade_date=date(2016, 5, 17),
        max_attempts=2,
        sleep_seconds=0,
        allow_soft_fail=True,
        soft_fail_events=events,
    )

    assert result is None
    assert len(events) == 1
    assert events[0]["label"] == "moneyflow"
    assert events[0]["trade_date"] == "2016-05-17"


def test_fetch_trade_date_sources_soft_fails_only_stk_limit(monkeypatch) -> None:
    class _FakePro:
        def daily(self, **_kwargs):
            return pd.DataFrame(
                [{"ts_code": "600000.SH", "trade_date": "20110421", "open": 1, "high": 1, "low": 1, "close": 1, "pre_close": 1, "change": 0, "pct_chg": 0, "vol": 1, "amount": 1}]
            )

        def adj_factor(self, **_kwargs):
            return pd.DataFrame([{"ts_code": "600000.SH", "trade_date": "20110421", "adj_factor": 1.0}])

        def daily_basic(self, **_kwargs):
            return pd.DataFrame([{"ts_code": "600000.SH", "trade_date": "20110421", "turnover_rate": 1.0}])

        def suspend_d(self, **_kwargs):
            return pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"])

        def stk_limit(self, **_kwargs):
            raise ConnectionError("temporary failure in name resolution")

        def moneyflow(self, **_kwargs):
            return pd.DataFrame([{"ts_code": "600000.SH", "trade_date": "20110421", "net_mf_vol": 1.0, "net_mf_amount": 1.0}])

    monkeypatch.setattr(updater.time, "sleep", lambda _: None)
    events: list[dict[str, object]] = []

    result = updater._fetch_trade_date_sources(_FakePro(), date(2011, 4, 21), set(), soft_fail_events=events)

    assert len(events) == 1
    assert events[0]["label"] == "stk_limit"
    assert result["daily"].shape[0] == 1
    assert result["stk_limit"].empty


def test_fetch_trade_date_sources_soft_fails_only_moneyflow(monkeypatch) -> None:
    class _FakePro:
        def daily(self, **_kwargs):
            return pd.DataFrame(
                [{"ts_code": "600000.SH", "trade_date": "20160517", "open": 1, "high": 1, "low": 1, "close": 1, "pre_close": 1, "change": 0, "pct_chg": 0, "vol": 1, "amount": 1}]
            )

        def adj_factor(self, **_kwargs):
            return pd.DataFrame([{"ts_code": "600000.SH", "trade_date": "20160517", "adj_factor": 1.0}])

        def daily_basic(self, **_kwargs):
            return pd.DataFrame([{"ts_code": "600000.SH", "trade_date": "20160517", "turnover_rate": 1.0}])

        def suspend_d(self, **_kwargs):
            return pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"])

        def stk_limit(self, **_kwargs):
            return pd.DataFrame([{"ts_code": "600000.SH", "trade_date": "20160517", "up_limit": 2.0, "down_limit": 0.5}])

        def moneyflow(self, **_kwargs):
            raise ConnectionError("temporary failure in name resolution")

    monkeypatch.setattr(updater.time, "sleep", lambda _: None)
    events: list[dict[str, object]] = []

    result = updater._fetch_trade_date_sources(_FakePro(), date(2016, 5, 17), set(), soft_fail_events=events)

    assert len(events) == 1
    assert events[0]["label"] == "moneyflow"
    assert result["daily"].shape[0] == 1
    assert result["stk_limit"].shape[0] == 1
    assert result["moneyflow"].empty
