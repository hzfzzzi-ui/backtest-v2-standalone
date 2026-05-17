from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip("pyarrow")
from backend.core.data.cached_provider import CachedDataProvider


class _InnerProvider:
    def __init__(self) -> None:
        self.catalog_calls: list[list[str] | None] = []
        self.coverage_calls: list[list[str] | None] = []

    def load_cn_etf_catalog(self, symbols: list[str] | None = None) -> pd.DataFrame:
        self.catalog_calls.append(symbols)
        return pd.DataFrame([{"ts_code": "512100.SH", "symbol": "sh512100"}])

    def load_cn_etf_coverage(self, symbols: list[str] | None = None) -> pd.DataFrame:
        self.coverage_calls.append(symbols)
        return pd.DataFrame([{"ts_code": "512100.SH", "coverage_start": "2016-11-04"}])


def test_cached_provider_delegates_cn_etf_catalog_and_coverage() -> None:
    inner = _InnerProvider()
    provider = object.__new__(CachedDataProvider)
    provider._inner = inner

    catalog = provider.load_cn_etf_catalog(["512100.SH"])
    coverage = provider.load_cn_etf_coverage(["512100.SH"])

    assert inner.catalog_calls == [["512100.SH"]]
    assert inner.coverage_calls == [["512100.SH"]]
    assert catalog.iloc[0]["symbol"] == "sh512100"
    assert coverage.iloc[0]["coverage_start"] == "2016-11-04"


class _Source:
    def __init__(self, table: str, mapping_key: str | None = None) -> None:
        self._table = table
        self._mapping_key = mapping_key or table

    def resolved_stocks_table(self) -> str:
        return self._table

    def resolved_stocks_mapping_table(self) -> str:
        return self._mapping_key


class _CacheInnerProvider:
    def __init__(self, table: str, mapping_key: str | None = None) -> None:
        key = mapping_key or table
        self._source = _Source(table, key)
        self._db = SimpleNamespace(host="localhost", port=5432, dbname="pams", user="pams", password="")
        self._schema = {
            key: {
                "date": "date",
                "symbol": "symbol",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "amount": "amount",
            }
        }
        self.calls: list[dict[str, object]] = []
        self._audit: list[dict[str, object]] = []

    @property
    def query_audit(self) -> list[dict]:
        return list(self._audit)

    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        normalized = sorted(str(symbol).lower() for symbol in symbols)
        self.calls.append({"symbols": normalized, "start": start, "end": end, "source": source})
        self._audit.append(
            {
                "provider": "postgres",
                "source": source,
                "table": self._source.resolved_stocks_table(),
                "symbol_count": len(normalized),
            }
        )
        return pd.DataFrame(
            [
                {
                    "date": pd.Timestamp(start),
                    "symbol": symbol,
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 100.0,
                    "amount": 100.0,
                }
                for symbol in normalized
            ]
        )


def _patch_signature(monkeypatch: pytest.MonkeyPatch, row_count: int = 1) -> None:
    monkeypatch.setattr(
        CachedDataProvider,
        "_current_db_signature",
        lambda self: {
            "resolved_table": self._resolved_table,
            "mapping_key": self._mapping_key,
            "row_count": row_count,
            "max_trade_date": "2026-05-08",
            "max_created_at": None,
            "suspended_rows": 0,
            "schema_columns": ["date", "symbol", "open", "close"],
        },
    )


def test_table_cache_paths_are_scoped_by_resolved_table(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OHLCV_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("OHLCV_CACHE_MODE", "table")
    _patch_signature(monkeypatch)

    stock_provider = CachedDataProvider(_CacheInnerProvider("pams_ohlcv_daily_v2"))
    etf_provider = CachedDataProvider(_CacheInnerProvider("pams_cn_etf_daily"))

    assert stock_provider._table_cache_path != etf_provider._table_cache_path
    assert "pams_ohlcv_daily_v2" in stock_provider._table_cache_path.name
    assert "pams_cn_etf_daily" in etf_provider._table_cache_path.name


def test_slice_cache_reuses_same_window_and_symbol_set(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OHLCV_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("OHLCV_CACHE_MODE", raising=False)
    _patch_signature(monkeypatch)

    inner = _CacheInnerProvider("pams_ohlcv_daily_v2")
    provider = CachedDataProvider(inner)
    start = date(2020, 1, 1)
    end = date(2020, 1, 3)

    first = provider.load_ohlcv_daily(["600000.SH", "000001.SZ"], start, end, source="stocks")
    second = provider.load_ohlcv_daily(["sz000001", "sh600000"], start, end, source="stocks")

    assert len(inner.calls) == 1
    pd.testing.assert_frame_equal(first, second, check_dtype=False)
    cache_events = [item for item in provider.query_audit if item.get("provider") == "ohlcv_cache"]
    assert [item["cache_hit"] for item in cache_events] == [False, True]


def test_cn_etf_slice_cache_normalizes_symbols_like_postgres_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OHLCV_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("OHLCV_CACHE_MODE", raising=False)
    _patch_signature(monkeypatch)

    inner = _CacheInnerProvider("pams_cn_etf_daily")
    provider = CachedDataProvider(inner)
    start = date(2020, 1, 1)
    end = date(2020, 1, 3)

    provider.load_ohlcv_daily(["512100.SH"], start, end, source="stocks")
    provider.load_ohlcv_daily(["sh512100"], start, end, source="stocks")

    assert len(inner.calls) == 1
    assert inner.calls[0]["symbols"] == ["sh512100"]
