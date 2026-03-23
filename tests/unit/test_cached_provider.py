from __future__ import annotations

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
