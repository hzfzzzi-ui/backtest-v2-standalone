from __future__ import annotations

from datetime import date

import pandas as pd

from backend.cli.managed import update_pams_ohlcv_daily as managed_updater
from backend.scripts.update_pams_ohlcv_daily import (
    build_update_args,
    _compute_limit_prices,
    _load_cn_index_daily_tushare,
    _limit_pct_for_symbol,
    _normalize_cn_a_rows,
    _normalize_cn_index_rows,
    _normalize_daily_basic_frame,
)


def test_limit_pct_matches_existing_board_conventions() -> None:
    assert _limit_pct_for_symbol("sh600519", is_st=False) == 0.10
    assert _limit_pct_for_symbol("sz300750", is_st=False) == 0.20
    assert _limit_pct_for_symbol("sh688981", is_st=False) == 0.20
    assert _limit_pct_for_symbol("bj920002", is_st=False) == 0.30
    assert _limit_pct_for_symbol("sz000608", is_st=True) == 0.05
    assert _limit_pct_for_symbol("sz300344", is_st=True) == 0.20
    assert _limit_pct_for_symbol("sh688399", is_st=True) == 0.20


def test_compute_limit_prices_rounds_to_exchange_tick_size() -> None:
    assert _compute_limit_prices(10.0, "sz000609", is_st=True) == (10.5, 9.5)
    assert _compute_limit_prices(102.0, "bj920002", is_st=False) == (132.6, 71.4)
    assert _compute_limit_prices(3.63, "sz000608", is_st=True) == (3.81, 3.45)
    assert _compute_limit_prices(24.53, "sz002261", is_st=False) == (26.98, 22.08)
    assert _compute_limit_prices(6.93, "sz002797", is_st=False) == (7.62, 6.24)
    assert _compute_limit_prices(None, "sh600519", is_st=False) == (None, None)


def test_normalize_daily_basic_frame_merges_expected_fields() -> None:
    raw = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260310",
                "turnover_rate": "0.55",
                "turnover_rate_f": "0.60",
                "volume_ratio": "1.2",
                "float_share": "1000",
                "free_share": "800",
                "circ_mv": "12345",
            }
        ]
    )
    normalized = _normalize_daily_basic_frame(raw)
    assert normalized.loc[0, "symbol"] == "sh600519"
    assert normalized.loc[0, "trade_date"].isoformat() == "2026-03-10"
    assert float(normalized.loc[0, "turnover_rate_f"]) == 0.60
    assert float(normalized.loc[0, "circ_mv"]) == 12345.0


def test_normalize_cn_index_rows_preserves_existing_table_convention() -> None:
    raw = pd.DataFrame(
        [
            {
                "日期": "2026-03-10",
                "开盘": 4100.0,
                "最高": 4120.0,
                "最低": 4090.0,
                "收盘": 4110.0,
                "成交量": 123456.0,
            }
        ]
    )
    normalized, stats = _normalize_cn_index_rows("sh000001", raw, start=date(2026, 3, 1), end=date(2026, 3, 10))
    assert stats["rows"] == 1
    assert normalized.loc[0, "market"] == "CN_INDEX"
    assert int(normalized.loc[0, "volume"]) == 12345600
    assert float(normalized.loc[0, "turnover"]) == 0.0
    assert pd.isna(normalized.loc[0, "adj_factor"])


def test_load_cn_index_daily_tushare_adapts_to_existing_normalizer_shape() -> None:
    class _DummyPro:
        def index_daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": "000001.SH",
                        "trade_date": "20260313",
                        "open": 4117.5738,
                        "high": 4134.0794,
                        "low": 4086.8469,
                        "close": 4095.4485,
                        "vol": 792054764.0,
                        "amount": 1063918169.4,
                    }
                ]
            )

    raw = _load_cn_index_daily_tushare(_DummyPro(), "sh000001", start=date(2026, 3, 13), end=date(2026, 3, 13))
    normalized, stats = _normalize_cn_index_rows("sh000001", raw, start=date(2026, 3, 13), end=date(2026, 3, 13))
    assert stats["rows"] == 1
    assert normalized.loc[0, "trade_date"].isoformat() == "2026-03-13"
    assert int(normalized.loc[0, "volume"]) == 79205476400
    assert float(normalized.loc[0, "turnover"]) == 0.0


def test_normalize_cn_a_rows_builds_suspended_rows_from_adj_only_symbol() -> None:
    daily_raw = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260310",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "pre_close": 100.0,
                "vol": 10.0,
                "amount": 20.0,
            }
        ]
    )
    adj_raw = pd.DataFrame(
        [
            {"ts_code": "600519.SH", "trade_date": "20260310", "adj_factor": 1.0},
            {"ts_code": "300344.SZ", "trade_date": "20260310", "adj_factor": 2.0},
        ]
    )

    normalized, stats = _normalize_cn_a_rows(
        trade_date=date(2026, 3, 10),
        daily_raw=daily_raw,
        adj_raw=adj_raw,
        basic_raw=pd.DataFrame(),
        st_periods={"sz300344": [(date(2025, 1, 1), None)]},
        prev_close_map={"sh600519": 100.0, "sz300344": 9.8},
    )

    suspended = normalized[normalized["symbol"] == "sz300344"].reset_index(drop=True)
    assert stats["suspended_rows"] == 1
    assert len(suspended) == 1
    assert bool(suspended.loc[0, "is_suspended"]) is True
    assert float(suspended.loc[0, "close"]) == 9.8
    assert float(suspended.loc[0, "limit_up"]) == 11.76


def test_build_update_args_exposes_reusable_apply_entry() -> None:
    args = build_update_args(end="2026-03-14", output_dir="tmp-sync", apply=True)

    assert args.end == "2026-03-14"
    assert args.output_dir == "tmp-sync"
    assert args.apply is True


def test_run_update_keeps_cn_a_sync_when_cn_index_fetch_fails(monkeypatch, tmp_path) -> None:
    class _DummyPro:
        def daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20260311",
                        "open": 100.0,
                        "high": 101.0,
                        "low": 99.0,
                        "close": 100.5,
                        "pre_close": 100.0,
                        "vol": 10.0,
                        "amount": 20.0,
                    }
                ]
            )

        def adj_factor(self, **kwargs):
            return pd.DataFrame([{"ts_code": "600519.SH", "trade_date": "20260311", "adj_factor": 1.0}])

        def daily_basic(self, **kwargs):
            return pd.DataFrame()

        def index_daily(self, **kwargs):
            symbol = kwargs.get("ts_code", "")
            if symbol == "000001.SH":
                raise RuntimeError("index down: sh000001")
            return pd.DataFrame()

    monkeypatch.setattr(managed_updater, "_load_tushare_client", lambda token: _DummyPro())
    monkeypatch.setattr(managed_updater, "_load_existing_prev_close_map", lambda table, start: {"sh600519": 100.0})
    monkeypatch.setattr(managed_updater, "_load_st_periods", lambda start, end: {})
    monkeypatch.setattr(managed_updater, "_load_index_symbols", lambda table: ["sh000001"])
    monkeypatch.setattr(managed_updater, "_get_latest_trade_date", lambda table, market: None)
    monkeypatch.setattr(managed_updater, "_init_temp_table", lambda cur: None)
    monkeypatch.setattr(managed_updater, "_load_batch_into_temp", lambda cur, batch: None)
    monkeypatch.setattr(managed_updater, "_count_batch_state", lambda cur, table: (1, 0))
    monkeypatch.setattr(managed_updater, "_upsert_batch", lambda cur, table: 1)

    class _DummyConn:
        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(managed_updater, "_connect", lambda: _DummyConn())

    args = build_update_args(
        start="2026-03-11",
        end="2026-03-11",
        output_dir=str(tmp_path),
        apply=False,
        token="dummy-token",
    )
    summary = managed_updater.run_update(args)

    assert summary["cn_a_rows"] == 1
    assert summary["cn_index_rows"] == 0
    assert summary["rows_total"] == 1
    assert "CN_INDEX fetch failed for sh000001" in " ".join(summary["notes"])
    assert summary["index_symbol_stats"][0]["error"] == "index down: sh000001"
