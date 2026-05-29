from __future__ import annotations

from datetime import date

import backend.core.data as data_pkg
import pandas as pd

from backend.core.config.models import DataSourceConfig
from backend.core.data.market_data_access import (
    CALENDAR_VERSION,
    DIRECT_CANONICAL_CACHE_VERSION,
    MarketDataAccess,
)


class _FakeProvider:
    def __init__(self) -> None:
        self._audit: list[dict] = []

    @property
    def query_audit(self) -> list[dict]:
        return list(self._audit)

    def _append_audit(self, table: str, source: str) -> None:
        self._audit.append({"table": table, "source": source})

    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        self._append_audit("pams_ohlcv_daily_v2", source)
        return pd.DataFrame(
            {
                "date": [pd.Timestamp(start)],
                "symbol": [symbols[0]],
                "open": [10.0],
                "high": [11.0],
                "low": [9.5],
                "close": [10.5],
                "volume": [1000.0],
                "amount": [10500.0],
                "adj_factor": [1.0],
                "is_suspended": [False],
            }
        )

    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        self._append_audit("pit_index_daily", "benchmark")
        return pd.DataFrame(
            {
                "date": [pd.Timestamp(start)],
                "symbol": [benchmark_symbol],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [10000.0],
                "amount": [1005000.0],
                "adj_factor": [1.0],
                "is_suspended": [False],
            }
        )

    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        self._append_audit("pams_ohlcv_daily_v2", "calendar")
        return pd.DatetimeIndex([pd.Timestamp(start), pd.Timestamp(end)])

    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        self._append_audit("pit_index_constituents", "index_constituent_history")
        return pd.DataFrame(
            {
                "index_code": [index_code],
                "symbol": ["sh600000"],
                "start_date": [pd.Timestamp(start)],
                "end_date": [pd.NaT],
            }
        )

    def load_industry_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        self._append_audit("pit_industry_history", "industry_history")
        return pd.DataFrame(
            {
                "ts_code": ["sh600000"],
                "start_date": [pd.Timestamp(start)],
                "end_date": [pd.NaT],
                "standard": ["sw_l1"],
                "industry_l1": ["银行"],
                "industry_l2": ["国有大行"],
            }
        )

    def load_security_master(self, symbols: list[str]) -> pd.DataFrame:
        self._append_audit("pit_security_master", "security_master")
        return pd.DataFrame(
            {
                "symbol": ["sh600000"],
                "name": ["浦发银行"],
                "list_date": [pd.Timestamp("1999-11-10")],
                "delist_date": [pd.NaT],
            }
        )

    def _resolved_stocks_mapping(self) -> dict[str, str]:
        return {"date": "trade_date"}


def _make_access(provider: _FakeProvider) -> MarketDataAccess:
    access = object.__new__(MarketDataAccess)
    access._provider = provider
    access._canonical_data_source = type("CanonicalSource", (), {"resolved_stocks_table": lambda self: "pams_ohlcv_daily_v2"})()
    access._runtime_access = None
    return access


def test_price_history_audit_uses_fixed_contract_fields() -> None:
    access = _make_access(_FakeProvider())

    result = access.load_price_history(
        symbols=["sh600000"],
        start=date(2026, 3, 1),
        end=date(2026, 3, 31),
    )

    assert list(result.frame.columns) == [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "adj_factor",
        "is_suspended",
    ]
    assert result.audit.canonical_objects == ["pams_ohlcv_daily_v2"]
    assert result.audit.cache_hit is False
    assert result.audit.cache_version == DIRECT_CANONICAL_CACHE_VERSION
    assert result.audit.window_start == "2026-03-01"
    assert result.audit.window_end == "2026-03-31"


def test_market_data_access_builds_canonical_data_source_from_runtime_config() -> None:
    source = DataSourceConfig(
        data_role="v2_runtime",
        stocks_table="legacy_ohlcv",
        v2_canonical_stocks_table="canonical_market_ohlcv_daily",
        v2_runtime_stocks_table="canonical_market_ohlcv_runtime",
        v2_schema_mapping_table="canonical_market_ohlcv_daily",
    )

    canonical = MarketDataAccess._build_canonical_data_source(source)

    assert canonical.resolved_data_role() == "v2_canonical"
    assert canonical.resolved_stocks_table() == "canonical_market_ohlcv_daily"
    assert canonical.resolved_stocks_mapping_table() == "canonical_market_ohlcv_daily"
    assert canonical.stocks_table == "canonical_market_ohlcv_daily"


def test_trading_calendar_contract_returns_minimal_fields() -> None:
    access = _make_access(_FakeProvider())

    result = access.load_trading_calendar(
        start=date(2026, 3, 3),
        end=date(2026, 3, 4),
    )

    assert list(result.frame.columns) == ["trade_date", "is_trading_day", "calendar_version"]
    assert result.frame["is_trading_day"].tolist() == [True, True]
    assert set(result.frame["calendar_version"].tolist()) == {CALENDAR_VERSION}


def test_trading_calendar_index_helper_returns_datetimeindex() -> None:
    access = _make_access(_FakeProvider())

    result = access.load_trading_calendar_index(
        start=date(2026, 3, 3),
        end=date(2026, 3, 4),
    )

    assert isinstance(result, pd.DatetimeIndex)
    assert result.tolist() == [pd.Timestamp("2026-03-03"), pd.Timestamp("2026-03-04")]


def test_backend_core_data_exports_market_data_access_surface() -> None:
    assert data_pkg.MarketDataAccess is MarketDataAccess
    assert data_pkg.build_market_data_access.__name__ == "build_market_data_access"
    assert data_pkg.load_market_data_access.__name__ == "load_market_data_access"


def test_security_master_snapshot_fills_required_contract_fields() -> None:
    access = _make_access(_FakeProvider())

    result = access.load_security_master_snapshot(
        as_of_date=date(2026, 3, 20),
        symbols=["600000.SH"],
    )

    row = result.frame.iloc[0].to_dict()
    assert row["symbol"] == "sh600000"
    assert row["ts_code"] == "600000.SH"
    assert row["name"] == "浦发银行"
    assert row["market"] == "CN_A"
    assert row["exchange"] == "SH"
    assert row["security_type"] == "stock"
    assert row["asset_scope"] == "cn_a_equity"
    assert bool(row["is_active_at_asof"]) is True
