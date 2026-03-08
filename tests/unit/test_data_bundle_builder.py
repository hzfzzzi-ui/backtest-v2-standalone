from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from backend.core.config.models import (
    BacktestConfig,
    DBConfig,
    DBRuntimeConfig,
    DataScopeConfig,
    DataSourceConfig,
    StrategyConfig,
    UniverseConfig,
)
from backend.core.data.provider import DataProvider
from backend.core.tools.data_bundle_builder import build_data_bundle


class _FakeProvider(DataProvider):
    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        rows = [
            {"date": pd.Timestamp("2024-01-02"), "symbol": "sh600000", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2, "volume": 1000, "amount": 10000, "adj_factor": 1.0},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "sh600000", "open": 10.3, "high": 10.7, "low": 10.0, "close": 10.4, "volume": 1100, "amount": 11000, "adj_factor": 1.1},
            {"date": pd.Timestamp("2024-01-02"), "symbol": "sz000001", "open": 8.0, "high": 8.2, "low": 7.9, "close": 8.1, "volume": 900, "amount": 9000, "adj_factor": 1.0},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "sz000001", "open": 8.1, "high": 8.4, "low": 8.0, "close": 8.3, "volume": 950, "amount": 9500, "adj_factor": 1.05},
        ]
        return pd.DataFrame(rows)

    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        return pd.DatetimeIndex([pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")])

    def get_previous_trading_day_cn(self, start: date) -> date | None:
        return date(2024, 1, 1)

    def load_instrument_rules(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(columns=["symbol"])

    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": pd.Timestamp("2024-01-02"), "symbol": benchmark_symbol, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1, "amount": 1},
                {"date": pd.Timestamp("2024-01-03"), "symbol": benchmark_symbol, "open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1, "volume": 1, "amount": 1},
            ]
        )

    def load_st_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"])

    def load_sector_indices(self, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"index_code": "801010.SI", "trade_date": pd.Timestamp("2024-01-02"), "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
                {"index_code": "801010.SI", "trade_date": pd.Timestamp("2024-01-03"), "open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1},
            ]
        )

    def load_industry_mapping(self, symbols: list[str]) -> dict[str, str]:
        return {"sh600000": "Bank", "sz000001": "Bank"}

    def load_security_master(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"symbol": "sh600000", "list_date": "2010-01-01", "delist_date": None},
                {"symbol": "sz000001", "list_date": "2010-01-01", "delist_date": None},
            ]
        )

    @property
    def query_audit(self) -> list[dict]:
        return []


def _cfg() -> BacktestConfig:
    return BacktestConfig(
        db=DBConfig(host="localhost", port=5432, dbname="pams", user="pams", password="secret"),
        db_runtime=DBRuntimeConfig(),
        universe=UniverseConfig(
            symbols=["600000.SH", "000001.SZ"],
            benchmark="000300.SH",
            start=date(2024, 1, 2),
            end=date(2024, 1, 3),
        ),
        data_source=DataSourceConfig(),
        schema_mapping={},
        data_scope=DataScopeConfig(),
        strategy=StrategyConfig(name="breakout_trend"),
        initial_capital=1000000.0,
    )


def test_build_data_bundle_preloads_data_and_summary() -> None:
    bundle = build_data_bundle(
        cfg_obj=_cfg(),
        cfg_merged={"universe": {}},
        overrides={"universe_mode": "CUSTOM", "price_adj": "hfq"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_FakeProvider(),
        default_experiment_symbols=["600000.SH"],
    )

    assert bundle.symbols == ["sh600000", "sz000001"]
    assert bundle.price_adj_mode == "hfq"
    assert len(bundle.raw_history) == 4
    assert len(bundle.signal_history) == 4
    assert bundle.summary["symbols_count"] == 2
    assert bundle.summary["benchmark_rows"] == 2
    assert bundle.summary["trading_days"] == 2
    assert bundle.summary["industry_map_count"] == 2
