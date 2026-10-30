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

    def fetchall(self) -> list[tuple[str]]:
        sql, params = self.executed[-1]
        assert "pg_attribute" in sql and params
        table = str(params[0]).removeprefix("public.")
        return [(name,) for name in refresh_cn_etf_daily._REQUIRED_COLUMNS[table]]

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

    def query(self, api_name: str, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        assert api_name == "fund_adj"
        assert ts_code == "512100.SH"
        assert start_date == "20210104"
        assert end_date == "20210105"
        return pd.DataFrame(
            [
                {"trade_date": "20210105", "adj_factor": 0.5},
                {"trade_date": "20210104", "adj_factor": 1.0},
            ]
        )

    def fund_div(self, ts_code: str) -> pd.DataFrame:
        assert ts_code == "512100.SH"
        return pd.DataFrame(
            [
                {
                    "ann_date": "20201231",
                    "record_date": "20210104",
                    "ex_date": "20210105",
                    "pay_date": "20210106",
                    "earpay_date": None,
                    "net_ex_date": "20210105",
                    "div_cash": 0.03,
                    "div_proc": "实施",
                }
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
    assert summary["dividend_rows_inserted"] == 1
    assert summary["symbols"] == ["512100.SH"]
    assert summary["per_symbol"] == [
        {
            "ts_code": "512100.SH",
            "symbol": "sh512100",
            "rows": 2,
            "coverage_start": "2021-01-04",
            "coverage_end": "2021-01-05",
            "dividend_events": 1,
        }
    ]
    daily_inserts = [
        params for sql, params in fake_conn.cursor_obj.executed if params and "INSERT INTO public.pams_cn_etf_daily" in sql
    ]
    assert len(daily_inserts) == 2
    assert daily_inserts[0][10] == 1.0
    assert daily_inserts[0][11] == "none"
    assert daily_inserts[0][12] == refresh_cn_etf_daily.PRICE_SERIES_SEMANTICS
    assert daily_inserts[1][10] == 0.5
    coverage_insert = [
        params
        for sql, params in fake_conn.cursor_obj.executed
        if params and "INSERT INTO public.cn_etf_data_coverage_daily" in sql
    ][0]
    dividend_insert = [
        params
        for sql, params in fake_conn.cursor_obj.executed
        if params and "INSERT INTO public.pit_cn_etf_dividend_events" in sql
    ][0]
    assert coverage_insert[0] == "512100.SH"
    assert coverage_insert[7] == refresh_cn_etf_daily.DAILY_TABLE
    assert coverage_insert[8] == refresh_cn_etf_daily.PRICE_SERIES_SEMANTICS
    assert dividend_insert[1] == "512100.SH"
    assert dividend_insert[2] == "sh512100"
    assert dividend_insert[7].isoformat() == "2021-01-05"
    assert dividend_insert[8].isoformat() == "2021-01-06"
    assert dividend_insert[12] == 0.03
    assert fake_conn.committed is True
    assert (tmp_path / "summary.json").exists()
