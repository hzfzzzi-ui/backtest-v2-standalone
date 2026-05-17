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
from backend.core.tools.data_bundle_builder import _prune_history_to_membership_intervals, build_data_bundle


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

    def load_index_constituent_refresh_membership(self, index_code: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "index_code": index_code,
                    "refresh_date": "2024-01-01",
                    "symbol": "sh600000",
                    "constituent_start_date": "2024-01-01",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "snapshot_trade_date": "2024-01-01",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
                {
                    "index_code": index_code,
                    "refresh_date": "2024-01-01",
                    "symbol": "sh688001",
                    "constituent_start_date": "2024-01-01",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "snapshot_trade_date": "2024-01-01",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
            ]
        )

    @property
    def query_audit(self) -> list[dict]:
        return []

    def load_cn_etf_catalog(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(columns=["ts_code", "symbol", "batch_id", "name"])

    def load_cn_etf_coverage(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(columns=["ts_code", "coverage_start", "coverage_end", "daily_table", "price_series_semantics"])


class _CompositePitProvider(_FakeProvider):
    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        rows = []
        normalized = {str(symbol).strip().lower() for symbol in symbols}
        template = {
            "sh600000": 10.0,
            "sz000001": 8.0,
            "sz300001": 20.0,
        }
        for symbol, base in template.items():
            if symbol not in normalized:
                continue
            rows.extend(
                [
                    {
                        "date": pd.Timestamp("2024-01-02"),
                        "symbol": symbol,
                        "open": base,
                        "high": base + 0.5,
                        "low": base - 0.2,
                        "close": base + 0.2,
                        "volume": 1000,
                        "amount": 10000,
                        "adj_factor": 1.0,
                    },
                    {
                        "date": pd.Timestamp("2024-01-03"),
                        "symbol": symbol,
                        "open": base + 0.3,
                        "high": base + 0.7,
                        "low": base,
                        "close": base + 0.4,
                        "volume": 1100,
                        "amount": 11000,
                        "adj_factor": 1.1,
                    },
                ]
            )
        return pd.DataFrame(rows)

    def load_security_master(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"symbol": str(symbol).strip().lower(), "list_date": "2010-01-01", "delist_date": None}
                for symbol in symbols
            ]
        )

    def load_industry_mapping(self, symbols: list[str]) -> dict[str, str]:
        return {str(symbol).strip().lower(): "Bank" for symbol in symbols}

    def load_industry_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ts_code": str(symbol).strip().lower(),
                    "start_date": pd.Timestamp(start),
                    "end_date": None,
                    "industry_l1": "Bank",
                }
                for symbol in symbols
            ]
        )

    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        index_code = str(index_code).strip().upper()
        if index_code == "000906.SH":
            return pd.DataFrame(
                [
                    {
                        "index_code": index_code,
                        "symbol": "sh600000",
                        "start_date": "2024-01-01",
                        "end_date": None,
                        "source": "tushare_csi800_formal",
                    },
                    {
                        "index_code": index_code,
                        "symbol": "sz000001",
                        "start_date": "2024-01-01",
                        "end_date": None,
                        "source": "tushare_csi800_formal",
                    },
                ]
            )
        return pd.DataFrame(
            [
                {
                    "index_code": index_code,
                    "symbol": "sz000001",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-03",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
                {
                    "index_code": index_code,
                    "symbol": "sz300001",
                    "start_date": "2024-01-02",
                    "end_date": None,
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
            ]
        )

    def load_index_constituent_refresh_membership(self, index_code: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "index_code": "000852.SH",
                    "refresh_date": "2024-01-01",
                    "symbol": "sz000001",
                    "constituent_start_date": "2024-01-01",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "snapshot_trade_date": "2024-01-01",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
                {
                    "index_code": "000852.SH",
                    "refresh_date": "2024-01-02",
                    "symbol": "sz300001",
                    "constituent_start_date": "2024-01-02",
                    "source": "tushare_csi1000_calendar",
                    "event_type": "scheduled",
                    "snapshot_trade_date": "2024-01-02",
                    "rebalance_calendar_version": "seed-v1",
                    "rebalance_calendar_source": "csindex_seed_schedule",
                    "rebalance_calendar_generated_at": "2026-03-11T00:00:00+08:00",
                },
            ]
        )


class _CompositeStaticFallbackProvider(_CompositePitProvider):
    def load_index_constituent_history(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        index_code = str(index_code).strip().upper()
        if index_code == "000906.SH":
            return super().load_index_constituent_history(index_code, start, end)
        return pd.DataFrame(
            [
                {
                    "index_code": index_code,
                    "symbol": "sz000001",
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "source": "akshare_csi1000_static_fallback",
                },
                {
                    "index_code": index_code,
                    "symbol": "sz300001",
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "source": "akshare_csi1000_static_fallback",
                },
            ]
        )

    def load_index_constituent_refresh_membership(self, index_code: str) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "index_code",
                "refresh_date",
                "symbol",
                "constituent_start_date",
                "source",
                "event_type",
                "snapshot_trade_date",
            ]
        )


class _AdjFactorStaleProvider(_FakeProvider):
    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        dates = [
            pd.Timestamp("2024-01-02"),
            pd.Timestamp("2024-01-03"),
            pd.Timestamp("2024-01-04"),
            pd.Timestamp("2024-01-05"),
            pd.Timestamp("2024-01-08"),
            pd.Timestamp("2024-01-09"),
            pd.Timestamp("2024-01-10"),
        ]
        adj_values = [1.0, 1.1, None, None, None, None, None]
        rows = []
        for idx, trade_date in enumerate(dates):
            rows.append(
                {
                    "date": trade_date,
                    "symbol": "sh600000",
                    "open": 10.0 + idx,
                    "high": 10.2 + idx,
                    "low": 9.9 + idx,
                    "close": 10.1 + idx,
                    "volume": 1000 + idx,
                    "amount": 10000 + idx,
                    "adj_factor": adj_values[idx],
                }
            )
        return pd.DataFrame(rows)

    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(
            [
                pd.Timestamp("2024-01-02"),
                pd.Timestamp("2024-01-03"),
                pd.Timestamp("2024-01-04"),
                pd.Timestamp("2024-01-05"),
                pd.Timestamp("2024-01-08"),
                pd.Timestamp("2024-01-09"),
                pd.Timestamp("2024-01-10"),
            ]
        )

    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        rows = []
        for idx, trade_date in enumerate(self.load_trading_calendar_cn(start, end)):
            rows.append(
                {
                    "date": trade_date,
                    "symbol": benchmark_symbol,
                    "open": 1.0 + idx * 0.01,
                    "high": 1.0 + idx * 0.01,
                    "low": 1.0 + idx * 0.01,
                    "close": 1.0 + idx * 0.01,
                    "volume": 1,
                    "amount": 1,
                }
            )
        return pd.DataFrame(rows)


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
    assert bundle.universe_meta["provider_floor_date"] == "2024-01-01"
    assert bundle.universe_meta["refresh_event_count"] == 1
    assert bundle.summary["rebalance_calendar_version"] == "seed-v1"
    assert bundle.summary["rebalance_calendar_source"] == "csindex_seed_schedule"


def test_build_data_bundle_supports_hs300_zz500_csi1000_dynamic_membership() -> None:
    bundle = build_data_bundle(
        cfg_obj=_cfg(),
        cfg_merged={"universe": {"membership_mode": "PIT_DYNAMIC"}},
        overrides={"universe_mode": "HS300_ZZ500_CSI1000", "price_adj": "hfq"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_CompositePitProvider(),
        default_experiment_symbols=["600000.SH"],
    )

    assert bundle.universe_meta["index_codes"] == ["000906.SH", "000852.SH"]
    assert set(bundle.membership_history["index_code"].astype(str).str.upper()) == {"000906.SH", "000852.SH"}
    assert bundle.universe_meta["union_symbol_count"] == 3
    assert bundle.universe_meta["csi1000_membership_data_quality"] == "pit_verified"
    assert bundle.universe_meta["csi1000_provider_floor_date"] == "2024-01-01"
    assert bundle.summary["index_codes"] == ["000906.SH", "000852.SH"]
    assert bundle.summary["csi1000_membership_data_quality"] == "pit_verified"
    assert sorted(bundle.symbols) == ["sh600000", "sz000001", "sz300001"]


def test_pit_interval_pushdown_prunes_rows_outside_membership_with_warmup() -> None:
    history = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-02"), "symbol": "sh600000", "close": 10.0},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "sh600000", "close": 10.1},
            {"date": pd.Timestamp("2024-01-02"), "symbol": "sz300001", "close": 20.0},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "sz300001", "close": 20.1},
        ]
    )
    membership = pd.DataFrame(
        [
            {"index_code": "000906.SH", "symbol": "sh600000", "start_date": "2024-01-02", "end_date": None},
            {"index_code": "000852.SH", "symbol": "sz300001", "start_date": "2024-01-03", "end_date": None},
        ]
    )

    pruned, audit = _prune_history_to_membership_intervals(
        history,
        membership,
        [date(2024, 1, 2), date(2024, 1, 3)],
        warmup_trading_days=0,
    )

    kept = sorted((str(row.symbol), str(pd.Timestamp(row.date).date())) for row in pruned.itertuples(index=False))
    assert kept == [
        ("sh600000", "2024-01-02"),
        ("sh600000", "2024-01-03"),
        ("sz300001", "2024-01-03"),
    ]
    assert audit["pit_interval_pushdown_enabled"] is True
    assert audit["pit_interval_pushdown_rows_before"] == 4
    assert audit["pit_interval_pushdown_rows_after"] == 3
    assert audit["pit_interval_pushdown_rows_dropped"] == 1

    warm_pruned, warm_audit = _prune_history_to_membership_intervals(
        history,
        membership,
        [date(2024, 1, 2), date(2024, 1, 3)],
        warmup_trading_days=1,
    )
    assert len(warm_pruned.index) == 4
    assert warm_audit["pit_interval_pushdown_rows_dropped"] == 0


def test_build_data_bundle_blocks_static_fallback_csi1000_inside_composite_pool() -> None:
    try:
        build_data_bundle(
            cfg_obj=_cfg(),
            cfg_merged={"universe": {"membership_mode": "PIT_DYNAMIC"}},
            overrides={"universe_mode": "HS300_ZZ500_CSI1000", "price_adj": "hfq"},
            rules_path=Path("instrument_rules_cn.csv"),
            provider=_CompositeStaticFallbackProvider(),
            default_experiment_symbols=["600000.SH"],
        )
    except ValueError as exc:
        message = str(exc)
        assert "csi1000" in message
        assert "static_fallback" in message
        assert "audit_reason=" in message
    else:
        raise AssertionError("expected composite CSI1000 static fallback gate to block")


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


class _EtfProvider(_FakeProvider):
    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": pd.Timestamp("2024-01-02"), "symbol": "sh512100", "open": 1.0, "high": 1.02, "low": 0.99, "close": 1.01, "volume": 10000, "amount": 100000, "turnover": 100000},
                {"date": pd.Timestamp("2024-01-03"), "symbol": "sh512100", "open": 1.01, "high": 1.03, "low": 1.0, "close": 1.02, "volume": 11000, "amount": 110000, "turnover": 110000},
            ]
        )

    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": pd.Timestamp("2024-01-02"), "symbol": "512100.SH", "open": 1.0, "high": 1.02, "low": 0.99, "close": 1.01, "volume": 10000, "amount": 100000},
                {"date": pd.Timestamp("2024-01-03"), "symbol": "512100.SH", "open": 1.01, "high": 1.03, "low": 1.0, "close": 1.02, "volume": 11000, "amount": 110000},
            ]
        )

    def load_cn_etf_catalog(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ts_code": "512100.SH",
                    "symbol": "sh512100",
                    "batch_id": "cn_etf_single_asset_template",
                    "name": "中证1000ETF",
                }
            ]
        )

    def load_cn_etf_coverage(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ts_code": "512100.SH",
                    "coverage_start": "2016-11-04",
                    "coverage_end": "2026-03-20",
                    "daily_table": "pams_cn_etf_daily",
                    "price_series_semantics": "executable_price_only_not_total_return",
                }
            ]
        )

    def load_cn_etf_dividend_events(self, symbols: list[str] | None, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "event_id": "512100.SH|2024-01-03|2024-01-04|2024-01-02|0.03000000",
                    "ts_code": "512100.SH",
                    "symbol": "sh512100",
                    "ann_date": pd.Timestamp("2023-12-31"),
                    "record_date": pd.Timestamp("2024-01-02"),
                    "ex_date": pd.Timestamp("2024-01-03"),
                    "pay_date": pd.Timestamp("2024-01-04"),
                    "earpay_date": pd.NaT,
                    "net_ex_date": pd.Timestamp("2024-01-03"),
                    "div_cash": 0.03,
                    "div_proc": "实施",
                }
            ]
        )


def test_build_data_bundle_supports_cn_etf_research_entry() -> None:
    cfg = _cfg()
    cfg.universe.symbols = ["512100.SH"]
    cfg.universe.benchmark = ""

    bundle = build_data_bundle(
        cfg_obj=cfg,
        cfg_merged={"asset_scope": "cn_etf", "universe": {"filters": {"price_min": 0.0, "price_max": 99999.0, "atr_pct_range": "0,100", "limit_rule": "ignore"}}},
        overrides={"asset_scope": "cn_etf", "universe_mode": "CUSTOM", "price_adj": "none"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_EtfProvider(),
        default_experiment_symbols=["512100.SH"],
    )

    assert bundle.symbols == ["sh512100"]
    assert bundle.price_adj_mode == "none"
    assert bundle.universe_meta["membership_mode"] == "DIRECT_SYMBOLS"
    assert bundle.universe_meta["membership_data_quality"] == "whitelist_verified"
    assert bundle.universe_meta["etf_symbols"] == ["512100.SH"]
    assert bundle.universe_meta["etf_batch"] == "cn_etf_single_asset_template"
    assert bundle.universe_meta["catalog_batch_id"] == "cn_etf_single_asset_template"
    assert bundle.universe_meta["etf_beta_phase1_summary"]["source_entry_type"] == "cn_etf_phase1_allocation_entry"
    assert bundle.universe_meta["etf_beta_phase1_summary"]["eligible_etfs"] == []
    assert bundle.universe_meta["etf_beta_phase1_summary"]["selected_etfs"] == []
    assert bundle.universe_meta["etf_beta_phase1_summary"]["out_of_scope_etfs"] == []
    assert bundle.summary["daily_table"] == "pams_cn_etf_daily"
    assert bundle.summary["price_series_semantics"] == "executable_price_only_not_total_return"
    assert bundle.summary["dividend_event_rows"] == 1
    assert bundle.summary["dividend_event_ex_start"] == "2024-01-03"
    assert bundle.summary["dividend_event_ex_end"] == "2024-01-03"
    assert len(bundle.dividend_events.index) == 1
    assert bundle.summary["etf_beta_source_entry_type"] == "cn_etf_phase1_allocation_entry"
    assert bundle.summary["etf_beta_eligible_count"] == 0
    assert bundle.summary["etf_beta_out_of_scope_count"] == 0
    assert bundle.summary["industry_map_count"] == 0
    assert bundle.summary["benchmark_rows"] == 2
    assert cfg.data_source.data_role == "v1"
    assert cfg.data_source.stocks_table == "pams_cn_etf_daily"


def test_build_data_bundle_exposes_adj_factor_stale_stats() -> None:
    cfg = _cfg()
    cfg.universe.symbols = ["600000.SH"]
    cfg.universe.end = date(2024, 1, 10)
    bundle = build_data_bundle(
        cfg_obj=cfg,
        cfg_merged={"universe": {}},
        overrides={"universe_mode": "CUSTOM", "price_adj": "hfq"},
        rules_path=Path("instrument_rules_cn.csv"),
        provider=_AdjFactorStaleProvider(),
        default_experiment_symbols=["600000.SH"],
    )

    assert bundle.adj_factor_stats["null_count"] == 5
    assert bundle.adj_factor_stats["symbols_with_missing_count"] == 1
    assert bundle.adj_factor_stats["max_consecutive_missing_after_valid_rows"] == 5
    assert bundle.adj_factor_stats["symbols_exceeding_warn_count"] == 1
    assert bundle.adj_factor_stats["symbols_exceeding_fail_count"] == 0
    assert bundle.summary["adj_factor_symbols_exceeding_warn_count"] == 1
