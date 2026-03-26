from __future__ import annotations

from pathlib import Path

from backend.cli.managed import refresh_cn_etf_catalog
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


def test_run_refresh_normalizes_nan_catalog_dates(monkeypatch, tmp_path: Path) -> None:
    fake_conn = _FakeConnection()
    entry = CnEtfCatalogEntry(
        "510300.SH",
        "sh510300",
        "沪深300ETF",
        "SSE",
        "first_wave",
        "broad_equity",
        list_date="20120405",
    )

    monkeypatch.setattr(refresh_cn_etf_catalog.common, "connect", lambda: fake_conn)
    monkeypatch.setattr(refresh_cn_etf_catalog, "list_seeded_entries", lambda: (entry,))
    monkeypatch.setattr(
        refresh_cn_etf_catalog,
        "_load_tushare_catalog_rows",
        lambda token: {
            "510300.SH": {
                "ts_code": "510300.SH",
                "name": "沪深300ETF联接",
                "list_date": float("nan"),
                "delist_date": float("nan"),
            }
        },
    )

    summary = refresh_cn_etf_catalog.run_refresh(token="dummy", summary_out=tmp_path / "summary.json")

    assert summary["upserted_rows"] == 1
    insert_params = [params for sql, params in fake_conn.cursor_obj.executed if params and "INSERT INTO public.pit_cn_etf_master" in sql][0]
    assert insert_params[2] == "沪深300ETF联接"
    assert insert_params[6] == "20120405"
    assert insert_params[7] is None
    assert fake_conn.committed is True
    assert (tmp_path / "summary.json").exists()
