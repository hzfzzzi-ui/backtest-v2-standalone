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

    def load_industry_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"ts_code": "sh600000", "start_date": pd.Timestamp("2024-01-02"), "end_date": None, "industry_l1": "Bank"},
                {"ts_code": "sz000001", "start_date": pd.Timestamp("2024-01-02"), "end_date": None, "industry_l1": "Bank"},
            ]
        )

    def load_security_master(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"symbol": "sh600000", "list_date": "2010-01-01", "delist_date": None},
                {"symbol": "sz000001", "list_date": "2010-01-01", "delist_date": None},
            ]
        )

    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "index_code": index_code,
                    "symbol": "sh600000",
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
                {
                    "index_code": index_code,
                    "symbol": "sz000001",
                    "start_date": "2024-01-02",
                    "end_date": "2024-01-03",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
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
    assert bundle.summary["industry_history_rows"] == 2


def test_build_data_bundle_supports_pit_dynamic_membership() -> None:
    bundle = build_data_bundle(
        cfg_obj=_cfg(),
        cfg_merged={"universe": {"membership_mode": "PIT_DYNAMIC", "filters": {"price_min": 5.0}}},
        overrides={"universe_mode": "HS300_ZZ500", "price_adj": "hfq"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_FakeProvider(),
        default_experiment_symbols=["600000.SH"],
    )

    assert bundle.universe_meta["membership_mode"] == "PIT_DYNAMIC"
    assert bundle.universe_meta["historical_membership_dynamic"] is True
    assert bundle.universe_meta["filter_mode"] == "dynamic_membership_gate"
    assert bundle.summary["membership_mode"] == "PIT_DYNAMIC"
    assert bundle.summary["membership_history_rows"] == 2
    assert sorted(bundle.membership_history["symbol"].astype(str).tolist()) == ["sh600000", "sz000001"]


class _StarMarketDynamicProvider(_FakeProvider):
    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        rows = []
        normalized = {str(symbol).strip().lower() for symbol in symbols}
        if "sh600000" in normalized:
            rows.extend(
                [
                    {"date": pd.Timestamp("2024-01-02"), "symbol": "sh600000", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2, "volume": 1000, "amount": 10000, "adj_factor": 1.0},
                    {"date": pd.Timestamp("2024-01-03"), "symbol": "sh600000", "open": 10.3, "high": 10.7, "low": 10.0, "close": 10.4, "volume": 1100, "amount": 11000, "adj_factor": 1.1},
                ]
            )
        if "sh688001" in normalized:
            rows.extend(
                [
                    {"date": pd.Timestamp("2024-01-02"), "symbol": "sh688001", "open": 20.0, "high": 20.5, "low": 19.8, "close": 20.2, "volume": 1000, "amount": 20000, "adj_factor": 1.0},
                    {"date": pd.Timestamp("2024-01-03"), "symbol": "sh688001", "open": 20.3, "high": 20.7, "low": 20.0, "close": 20.4, "volume": 1100, "amount": 22000, "adj_factor": 1.1},
                ]
            )
        return pd.DataFrame(rows)

    def load_security_master(self, symbols: list[str]) -> pd.DataFrame:
        rows = []
        normalized = {str(symbol).strip().lower() for symbol in symbols}
        if "sh600000" in normalized:
            rows.append({"symbol": "sh600000", "list_date": "2010-01-01", "delist_date": None})
        if "sh688001" in normalized:
            rows.append({"symbol": "sh688001", "list_date": "2020-01-01", "delist_date": None})
        return pd.DataFrame(rows)

    def load_industry_mapping(self, symbols: list[str]) -> dict[str, str]:
        return {str(symbol).strip().lower(): "Bank" for symbol in symbols}

    def load_industry_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"ts_code": str(symbol).strip().lower(), "start_date": pd.Timestamp(start), "end_date": None, "industry_l1": "Bank"}
                for symbol in symbols
            ]
        )

    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "index_code": index_code,
                    "symbol": "sh600000",
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
                {
                    "index_code": index_code,
                    "symbol": "sh688001",
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
            ]
        )


def test_build_data_bundle_filters_star_market_symbols_for_dynamic_membership() -> None:
    bundle = build_data_bundle(
        cfg_obj=_cfg(),
        cfg_merged={"universe": {"membership_mode": "PIT_DYNAMIC", "filters": {"exclude_star_market": True, "price_min": 0.0}}},
        overrides={"universe_mode": "HS300_ZZ500", "price_adj": "hfq"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_StarMarketDynamicProvider(),
        default_experiment_symbols=["600000.SH"],
    )

    assert bundle.symbols == ["sh600000"]
    assert bundle.universe_meta["excluded_counts"] == {"EXCLUDE_STAR_MARKET": 1}
    assert bundle.universe_meta["tradable_symbols"] == 1
    assert sorted(bundle.membership_history["symbol"].astype(str).tolist()) == ["sh600000"]
    assert sorted(bundle.raw_history["symbol"].astype(str).unique().tolist()) == ["sh600000"]


def test_build_data_bundle_exposes_csi1000_calendar_lineage_metadata() -> None:
    bundle = build_data_bundle(
        cfg_obj=_cfg(),
        cfg_merged={"universe": {"membership_mode": "PIT_DYNAMIC"}},
        overrides={"universe_mode": "CSI1000", "price_adj": "hfq"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_FakeProvider(),
        default_experiment_symbols=["600000.SH"],
    )

    assert bundle.universe_meta["membership_data_quality"] == "pit_verified"
    assert bundle.universe_meta["rebalance_calendar_version"] == "seed-v1"
    assert bundle.universe_meta["rebalance_calendar_source"] == "csindex_seed_schedule"
    assert bundle.universe_meta["rebalance_calendar_generated_at"] == "2026-03-11T00:00:00+08:00"
    assert bundle.summary["rebalance_calendar_version"] == "seed-v1"
    assert bundle.summary["rebalance_calendar_source"] == "csindex_seed_schedule"


class _StaticFallbackProvider(_FakeProvider):
    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "index_code": index_code,
                    "symbol": "sh600000",
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "source": "akshare_csi1000_static_fallback",
                },
                {
                    "index_code": index_code,
                    "symbol": "sz000001",
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "source": "akshare_csi1000_static_fallback",
                },
            ]
        )


def test_build_data_bundle_blocks_static_fallback_csi1000_by_default() -> None:
    try:
        build_data_bundle(
            cfg_obj=_cfg(),
            cfg_merged={"universe": {"membership_mode": "PIT_DYNAMIC"}},
            overrides={"universe_mode": "CSI1000", "price_adj": "hfq"},
            rules_path=Path("instrument_rules_cn.csv"),
            provider=_StaticFallbackProvider(),
            default_experiment_symbols=["600000.SH"],
        )
    except ValueError as exc:
        message = str(exc)
        assert "static_fallback" in message
        assert "audit_reason=" in message
        assert "distinct_start_dates=1" in message
    else:
        raise AssertionError("expected CSI1000 static fallback gate to block")


class _ProvisionalCalendarProvider(_FakeProvider):
    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "index_code": index_code,
                    "symbol": "sh600000",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-03",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "provisional-20260311",
                    "rebalance_calendar_source": "tushare_index_weight_monthly_proxy",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
                {
                    "index_code": index_code,
                    "symbol": "sh600000",
                    "start_date": "2024-01-02",
                    "end_date": None,
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "provisional-20260311",
                    "rebalance_calendar_source": "tushare_index_weight_monthly_proxy",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
            ]
        )


def test_build_data_bundle_downgrades_provisional_calendar_lineage() -> None:
    bundle = build_data_bundle(
        cfg_obj=_cfg(),
        cfg_merged={"universe": {"membership_mode": "PIT_DYNAMIC", "allow_low_fidelity_history": True}},
        overrides={"universe_mode": "CSI1000", "price_adj": "hfq"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_ProvisionalCalendarProvider(),
        default_experiment_symbols=["600000.SH"],
    )

    assert bundle.universe_meta["membership_data_quality"] == "approximate"
    assert "provisional_calendar_lineage" in str(bundle.universe_meta["audit_reason"])
    assert bundle.universe_meta["calendar_lineage_provisional"] is True


def test_build_data_bundle_fails_fast_when_turnover_rate_filter_field_is_missing() -> None:
    try:
        build_data_bundle(
            cfg_obj=_cfg(),
            cfg_merged={
                "universe": {
                    "filters": {
                        "exclude_st": True,
                        "exclude_suspended": True,
                        "min_list_days": 120,
                        "min_avg_turnover_20d": 0.0,
                        "min_avg_turnover_rate_20d": 1.0,
                        "turnover_rate_field": "turnover_rate_f",
                        "price_min": 5.0,
                    }
                }
            },
            overrides={"universe_mode": "CUSTOM", "price_adj": "hfq"},
            rules_path=Path("instrument_rules_cn.csv"),
            provider=_FakeProvider(),
            default_experiment_symbols=["600000.SH"],
        )
    except ValueError as exc:
        assert "turnover rate filter field unavailable" in str(exc)
    else:
        raise AssertionError("expected ValueError when turnover rate field is unavailable")
