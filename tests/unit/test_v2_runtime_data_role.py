from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.config.models import DBConfig, DataSourceConfig
from backend.core.data.pg_provider import PostgresDataProvider


def test_data_source_config_resolves_v2_runtime_table_and_mapping() -> None:
    cfg = DataSourceConfig(
        data_role="v2_runtime",
        stocks_table="pams_ohlcv_daily",
        v2_canonical_stocks_table="pams_ohlcv_daily_v2",
        v2_runtime_stocks_table="pams_ohlcv_daily_v2_runtime",
        v2_schema_mapping_table="pams_ohlcv_daily_v2",
    )

    assert cfg.resolved_data_role() == "v2_runtime"
    assert cfg.resolved_stocks_table() == "pams_ohlcv_daily_v2_runtime"
    assert cfg.resolved_stocks_mapping_table() == "pams_ohlcv_daily_v2"


def test_postgres_provider_load_ohlcv_daily_uses_resolved_runtime_table() -> None:
    provider = PostgresDataProvider.__new__(PostgresDataProvider)
    provider._audit = []
    provider._table_columns_cache = {}
    provider._db = DBConfig(host="localhost", port=5432, dbname="pams", user="pams", password="")
    provider._runtime = type("Runtime", (), {"statement_timeout_ms": 60000})()
    provider._source = DataSourceConfig(
        data_role="v2_runtime",
        stocks_table="pams_ohlcv_daily",
        v2_runtime_stocks_table="pams_ohlcv_daily_v2_runtime",
        v2_schema_mapping_table="pams_ohlcv_daily_v2",
    )
    provider._schema = {
        "pams_ohlcv_daily_v2": {
            "date": "trade_date",
            "symbol": "symbol",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "amount": "turnover",
            "limit_up": "limit_up",
            "limit_down": "limit_down",
            "is_suspended": "is_suspended",
            "adj_factor": "adj_factor",
            "turnover_rate": "turnover_rate",
            "turnover_rate_f": "turnover_rate_f",
            "volume_ratio": "volume_ratio",
            "float_share": "float_share",
            "free_share": "free_share",
            "circ_mv": "circ_mv",
        }
    }
    provider._get_table_columns = lambda table: {  # type: ignore[attr-defined]
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
        "adj_factor",
    }
    captured: dict[str, object] = {}

    def _fake_exec_df(query, params, audit_meta):
        captured["query"] = query
        captured["audit_meta"] = audit_meta
        captured["params"] = params
        provider._audit.append(dict(audit_meta))
        return pd.DataFrame(
            [
                {
                    "trade_date": "2026-03-16",
                    "symbol": "sh600000",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.9,
                    "close": 10.2,
                    "volume": 1000.0,
                    "turnover": 10000.0,
                    "adj_factor": 1.0,
                }
            ]
        )

    provider._exec_df = _fake_exec_df  # type: ignore[attr-defined]

    result = provider.load_ohlcv_daily(
        ["600000.SH"],
        date(2026, 3, 16),
        date(2026, 3, 16),
        source="test_source",
    )

    assert "FROM pams_ohlcv_daily_v2_runtime" in str(captured["query"])
    assert dict(captured["audit_meta"] or {}).get("table") == "pams_ohlcv_daily_v2_runtime"
    assert captured["params"] == (date(2026, 3, 16), date(2026, 3, 16), ["sh600000"])
    assert result["symbol"].tolist() == ["sh600000"]


def test_postgres_provider_load_cn_etf_dividend_events_casts_dates_to_text_and_coerces_invalid_values() -> None:
    provider = PostgresDataProvider.__new__(PostgresDataProvider)
    provider._audit = []
    provider._table_columns_cache = {}
    provider._db = DBConfig(host="localhost", port=5432, dbname="pams", user="pams", password="")
    provider._runtime = type("Runtime", (), {"statement_timeout_ms": 60000})()
    provider._source = DataSourceConfig(cn_etf_dividend_table="pit_cn_etf_dividend_events")
    provider._schema = {}
    provider._get_table_columns = lambda table: {  # type: ignore[attr-defined]
        "event_id",
        "ts_code",
        "symbol",
        "ann_date",
        "record_date",
        "ex_date",
        "pay_date",
        "earpay_date",
        "net_ex_date",
        "div_cash",
        "div_proc",
    }
    captured: dict[str, object] = {}

    def _fake_exec_df(query, params, audit_meta):
        captured["query"] = query
        captured["params"] = params
        captured["audit_meta"] = audit_meta
        return pd.DataFrame(
            [
                {
                    "event_id": "511010.SH|2013-06-03|2013-06-07|2013-05-31|0.28000000",
                    "ts_code": "511010.SH",
                    "symbol": "sh511010",
                    "ann_date": "2013-05-28",
                    "record_date": "2013-05-31",
                    "ex_date": "2013-06-03",
                    "pay_date": "2013-06-07",
                    "earpay_date": "48113-11-21",
                    "net_ex_date": "2013-06-03",
                    "div_cash": "0.28",
                    "div_proc": "实施",
                }
            ]
        )

    provider._exec_df = _fake_exec_df  # type: ignore[attr-defined]

    result = provider.load_cn_etf_dividend_events(
        ["511010.SH"],
        date(2013, 1, 1),
        date(2013, 12, 31),
    )

    assert "CAST(ex_date AS TEXT) AS ex_date" in str(captured["query"])
    assert "CAST(earpay_date AS TEXT) AS earpay_date" in str(captured["query"])
    assert captured["params"] == (date(2013, 12, 31), date(2013, 1, 1), ["sh511010"], ["511010.SH"])
    assert result["symbol"].tolist() == ["sh511010"]
    assert result["ts_code"].tolist() == ["511010.SH"]
    assert result["ex_date"].iloc[0].strftime("%Y-%m-%d") == "2013-06-03"
    assert pd.isna(result["earpay_date"].iloc[0])
    assert result["div_cash"].iloc[0] == 0.28
