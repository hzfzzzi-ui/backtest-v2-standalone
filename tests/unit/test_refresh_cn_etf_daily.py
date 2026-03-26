from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.cli.managed import refresh_cn_etf_daily
from backend.core.data.cn_etf_catalog import CnEtfCatalogEntry


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        self.executed.append((sql, params))

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()
        self.committed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakePro:
    def fund_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        assert ts_code == "512100.SH"
        assert start_date == "20210104"
        assert end_date == "20210105"
        return pd.DataFrame(
            [
                {
                    "trade_date": "20210105",
                    "open": 1.1,
                    "high": 1.2,
                    "low": 1.0,
                    "close": 1.15,
                    "vol": 1000,
                    "amount": 2000,
                },
                {
                    "trade_date": "20210104",
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.05,
                    "vol": 900,
                    "amount": 1800,
                },
            ]
        )


def test_run_refresh_writes_daily_rows_and_coverage(monkeypatch, tmp_path: Path) -> None:
    fake_conn = _FakeConnection()
    entry = CnEtfCatalogEntry(
        "512100.SH",
        "sh512100",
        "中证1000ETF",
        "SSE",
        "first_wave",
        "small_cap_equity",
    )

    monkeypatch.setattr(refresh_cn_etf_daily.common, "connect", lambda: fake_conn)
    monkeypatch.setattr(refresh_cn_etf_daily.common, "load_tushare_client", lambda token: _FakePro())
    monkeypatch.setattr(refresh_cn_etf_daily, "list_seeded_entries", lambda: (entry,))

    summary = refresh_cn_etf_daily.run_refresh(
        token="dummy",
        start="2021-01-04",
        end="2021-01-05",
        symbols_csv="512100.SH",
        summary_out=tmp_path / "summary.json",
    )

    assert summary["rows_inserted"] == 2
    assert summary["symbols"] == ["512100.SH"]
    assert summary["per_symbol"] == [
        {
            "ts_code": "512100.SH",
            "symbol": "sh512100",
            "rows": 2,
            "coverage_start": "2021-01-04",
            "coverage_end": "2021-01-05",
        }
    ]
    daily_inserts = [
        params for sql, params in fake_conn.cursor_obj.executed if params and "INSERT INTO public.pams_cn_etf_daily" in sql
    ]
    assert len(daily_inserts) == 2
    assert daily_inserts[0][10] == "none"
    assert daily_inserts[0][11] == refresh_cn_etf_daily.PRICE_SERIES_SEMANTICS
    coverage_insert = [
        params
        for sql, params in fake_conn.cursor_obj.executed
        if params and "INSERT INTO public.cn_etf_data_coverage_daily" in sql
    ][0]
    assert coverage_insert[0] == "512100.SH"
    assert coverage_insert[7] == refresh_cn_etf_daily.DAILY_TABLE
    assert coverage_insert[8] == refresh_cn_etf_daily.PRICE_SERIES_SEMANTICS
    assert fake_conn.committed is True
    assert (tmp_path / "summary.json").exists()
