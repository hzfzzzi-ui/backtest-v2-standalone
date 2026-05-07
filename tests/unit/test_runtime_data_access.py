from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from backend.core.data import market_data_access
from backend.core.tools import runtime_data_access


def _install_market_data_access_stub(monkeypatch) -> None:
    monkeypatch.setattr(
        market_data_access,
        "build_market_data_access",
        lambda access: SimpleNamespace(),
    )


def test_resolve_validation_universe_uses_shared_filter_path(monkeypatch) -> None:
    _install_market_data_access_stub(monkeypatch)
    provider = SimpleNamespace(
        load_ohlcv_daily=lambda symbols, start, end, source="stocks": pd.DataFrame(
            {"symbol": ["sh600000"], "date": [pd.Timestamp(start)], "close": [10.0]}
        ),
        load_st_history=lambda symbols, start, end: pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        load_security_master=lambda symbols: pd.DataFrame(columns=["symbol", "list_date", "delist_date"]),
    )
    access = runtime_data_access.RuntimeDataAccess(
        bt_root=Path("C:/tmp"),
        cfg_obj=SimpleNamespace(db="db", db_runtime="runtime"),
        cfg_path=Path("C:/tmp/config.json"),
        provider=provider,
    )

    monkeypatch.setattr(runtime_data_access, "load_runtime_data_access", lambda bt_root=None, asset_scope=None: access)
    monkeypatch.setattr(runtime_data_access, "resolve_universe_timing", lambda mode, start, end: (start, False))
    monkeypatch.setattr(
        runtime_data_access,
        "resolve_universe_by_mode",
        lambda **kwargs: (["sh600000", "sz000001"], {"raw_count": 2}),
    )
    monkeypatch.setattr(
        runtime_data_access,
        "build_candidates_from_ohlcv",
        lambda history, filter_asof, st_history=None, security_master=None, turnover_rate_field="turnover_rate_f": pd.DataFrame({"symbol": ["sh600000"]}),
    )
    monkeypatch.setattr(
        runtime_data_access,
        "apply_universe_filters",
        lambda candidates, filter_cfg: (candidates, None, {"st": 1}),
    )

    snapshot = runtime_data_access.resolve_validation_universe(
        bt_root=Path("C:/tmp"),
        universe_mode="CUSTOM",
        symbols=["sh600000", "sz000001"],
        industries=[],
        universe_limit=None,
        start=pd.Timestamp("2024-01-02").date(),
        end=pd.Timestamp("2024-01-31").date(),
        exclude_st=True,
        exclude_suspended=True,
        min_list_days=120,
        min_avg_turnover_20d=1e8,
        min_avg_turnover_rate_20d=0.0,
        turnover_rate_field="turnover_rate_f",
        price_min=0.0,
        price_max=99999.0,
        limit_rule="ignore",
    )

    assert snapshot.resolved_symbols == ["sh600000"]
    assert snapshot.resolved_meta["excluded_counts"] == {"st": 1}
    assert snapshot.resolved_meta["tradable_symbols"] == 1
    assert snapshot.resolved_meta["after_filters_symbols"] == 1
    assert snapshot.resolved_meta["asset_scope"] == "cn_a_equity"
    assert snapshot.resolved_meta["asset_profile_id"] == "cn_a_equity_mainline"
    assert snapshot.resolved_meta["market_profile_id"] == "cn_a_mainland_equity_market"


def test_resolve_validation_universe_supports_cn_etf_catalog_snapshot(monkeypatch) -> None:
    _install_market_data_access_stub(monkeypatch)
    provider = SimpleNamespace(
        load_cn_etf_catalog=lambda symbols: pd.DataFrame(
            [
                {
                    "ts_code": "512100.SH",
                    "symbol": "sh512100",
                    "batch_id": "first_wave",
                    "name": "中证1000ETF",
                }
            ]
        ),
        load_cn_etf_coverage=lambda symbols: pd.DataFrame(
            [
                {
                    "ts_code": "512100.SH",
                    "coverage_start": "2016-11-04",
                    "coverage_end": "2026-03-20",
                    "daily_table": "pams_cn_etf_daily",
                    "price_series_semantics": "executable_price_only_not_total_return",
                }
            ]
        ),
    )
    access = runtime_data_access.RuntimeDataAccess(
        bt_root=Path("C:/tmp"),
        cfg_obj=SimpleNamespace(db="db", db_runtime="runtime"),
        cfg_path=Path("C:/tmp/config.json"),
        provider=provider,
    )

    monkeypatch.setattr(runtime_data_access, "load_runtime_data_access", lambda bt_root=None, asset_scope=None: access)
    monkeypatch.setattr(runtime_data_access, "resolve_universe_timing", lambda mode, start, end: (start, False))
    monkeypatch.setattr(
        runtime_data_access,
        "resolve_universe_by_mode",
        lambda **kwargs: (
            ["sh512100"],
            {
                "raw_count": 1,
                "etf_batch": "cn_etf_single_asset_template",
                "etf_symbols": ["512100.SH"],
            },
        ),
    )

    snapshot = runtime_data_access.resolve_validation_universe(
        bt_root=Path("C:/tmp"),
        asset_scope="cn_etf",
        universe_mode="CUSTOM",
        symbols=["512100.SH"],
        industries=[],
        universe_limit=None,
        start=pd.Timestamp("2024-01-02").date(),
        end=pd.Timestamp("2024-01-31").date(),
        exclude_st=True,
        exclude_suspended=True,
        min_list_days=120,
        min_avg_turnover_20d=0.0,
        min_avg_turnover_rate_20d=0.0,
        turnover_rate_field="turnover_rate_f",
        price_min=0.0,
        price_max=99999.0,
        limit_rule="ignore",
    )

    assert snapshot.resolved_symbols == ["sh512100"]
    assert snapshot.dynamic_all_a_entry is False
    assert snapshot.universe_filters_raw == {}
    assert snapshot.resolved_meta["asset_scope"] == "cn_etf"
    assert snapshot.resolved_meta["coverage_start"] == "2016-11-04"
    assert snapshot.resolved_meta["coverage_end"] == "2026-03-20"
    assert snapshot.resolved_meta["daily_table"] == "pams_cn_etf_daily"
    assert snapshot.resolved_meta["price_series_semantics"] == "executable_price_only_not_total_return"


def test_resolve_validation_universe_requires_turnover_rate_field_when_filter_enabled(monkeypatch) -> None:
    _install_market_data_access_stub(monkeypatch)
    provider = SimpleNamespace(
        load_ohlcv_daily=lambda symbols, start, end, source="stocks": pd.DataFrame(
            {"symbol": ["sh600000"], "date": [pd.Timestamp(start)], "close": [10.0]}
        ),
        load_st_history=lambda symbols, start, end: pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        load_security_master=lambda symbols: pd.DataFrame(columns=["symbol", "list_date", "delist_date"]),
    )
    access = runtime_data_access.RuntimeDataAccess(
        bt_root=Path("C:/tmp"),
        cfg_obj=SimpleNamespace(db="db", db_runtime="runtime"),
        cfg_path=Path("C:/tmp/config.json"),
        provider=provider,
    )

    monkeypatch.setattr(runtime_data_access, "load_runtime_data_access", lambda bt_root=None, asset_scope=None: access)
    monkeypatch.setattr(runtime_data_access, "resolve_universe_timing", lambda mode, start, end: (start, False))
    monkeypatch.setattr(
        runtime_data_access,
        "resolve_universe_by_mode",
        lambda **kwargs: (["sh600000"], {"raw_count": 1}),
    )

    try:
        runtime_data_access.resolve_validation_universe(
            bt_root=Path("C:/tmp"),
            universe_mode="CUSTOM",
            symbols=["sh600000"],
            industries=[],
            universe_limit=None,
            start=pd.Timestamp("2024-01-02").date(),
            end=pd.Timestamp("2024-01-31").date(),
            exclude_st=True,
            exclude_suspended=True,
            min_list_days=120,
            min_avg_turnover_20d=0.0,
            min_avg_turnover_rate_20d=1.0,
            turnover_rate_field="turnover_rate_f",
            price_min=0.0,
            price_max=99999.0,
            limit_rule="ignore",
        )
    except ValueError as exc:
        assert "turnover rate filter field unavailable" in str(exc)
    else:
        raise AssertionError("expected ValueError when turnover rate filter field is missing")


def test_resolve_validation_universe_filters_star_market_for_dynamic_all_a(monkeypatch) -> None:
    _install_market_data_access_stub(monkeypatch)
    provider = SimpleNamespace(
        load_ohlcv_daily=lambda symbols, start, end, source="stocks": pd.DataFrame(),
        load_st_history=lambda symbols, start, end: pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        load_security_master=lambda symbols: pd.DataFrame(columns=["symbol", "list_date", "delist_date"]),
    )
    access = runtime_data_access.RuntimeDataAccess(
        bt_root=Path("C:/tmp"),
        cfg_obj=SimpleNamespace(db="db", db_runtime="runtime"),
        cfg_path=Path("C:/tmp/config.json"),
        provider=provider,
    )

    monkeypatch.setattr(runtime_data_access, "load_runtime_data_access", lambda bt_root=None, asset_scope=None: access)
    monkeypatch.setattr(runtime_data_access, "resolve_universe_timing", lambda mode, start, end: (start, True))
    monkeypatch.setattr(
        runtime_data_access,
        "resolve_universe_by_mode",
        lambda **kwargs: (["600000.SH", "688001.SH"], {"raw_count": 2}),
    )

    snapshot = runtime_data_access.resolve_validation_universe(
        bt_root=Path("C:/tmp"),
        universe_mode="ALL_A",
        symbols=[],
        industries=[],
        universe_limit=None,
        start=pd.Timestamp("2024-01-02").date(),
        end=pd.Timestamp("2024-01-31").date(),
        exclude_st=True,
        exclude_suspended=True,
        min_list_days=120,
        min_avg_turnover_20d=1e8,
        min_avg_turnover_rate_20d=0.0,
        turnover_rate_field="turnover_rate_f",
        price_min=0.0,
        price_max=99999.0,
        limit_rule="ignore",
        exclude_star_market=True,
    )

    assert snapshot.resolved_symbols == ["600000.SH"]
    assert snapshot.resolved_meta["excluded_counts"] == {"EXCLUDE_STAR_MARKET": 1}
    assert snapshot.resolved_meta["tradable_symbols"] == 1
    assert snapshot.resolved_meta["filters_config"]["exclude_star_market"] is True


def test_load_runtime_data_access_rejects_unsupported_asset_scope() -> None:
    try:
        runtime_data_access.load_runtime_data_access(Path("C:/tmp"), asset_scope="us_equity")
    except runtime_data_access.UnsupportedAssetScopeError as exc:
        assert "us_equity" in str(exc)
    else:
        raise AssertionError("expected UnsupportedAssetScopeError for non-CN asset scope")


def test_resolve_trade_st_flags_uses_ts_symbols_and_skips_current_name_fallback(monkeypatch) -> None:
    trades_df = pd.DataFrame(
        [
            {"date": "2016-08-29", "symbol": "sz000793", "side": "BUY"},
        ]
    )
    executed: dict[str, object] = {}

    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            executed["query"] = query
            executed["params"] = params

        def fetchall(self):
            return [("000793.SZ", pd.Timestamp("2025-03-18"), None)]

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(runtime_data_access, "_connect_runtime_db", lambda access: _FakeConn())
    flags = runtime_data_access.resolve_trade_st_flags(
        trades_df,
        {"sz000793": "ST华闻"},
        access=SimpleNamespace(),
    )

    assert executed["params"] == (["000793.SZ"], pd.Timestamp("2016-08-29").date(), pd.Timestamp("2016-08-29").date())
    assert flags == {"2016-08-29|sz000793": "-"}
