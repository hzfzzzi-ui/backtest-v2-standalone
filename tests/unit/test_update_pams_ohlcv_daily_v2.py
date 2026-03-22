from __future__ import annotations

from datetime import date

import pandas as pd

from backend.cli.managed import pams_ohlcv_daily_v2_common as v2_common
from backend.cli.managed import update_pams_ohlcv_daily_v2 as updater


class _DummyAkCache:
    def __init__(self, value: float | None = None, source: str | None = None) -> None:
        self.value = value
        self.source = source or ("akshare_stock_zh_a_hist" if value is not None else None)

    def get(self, symbol: str, trade_date: date, market_phase: str) -> tuple[float | None, str | None]:
        _ = (symbol, trade_date, market_phase)
        return self.value, self.source


def test_resolve_turnover_rate_fallback_priority() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2026, 3, 16),
        symbol="sh600000",
        market_phase="sh",
        basic_row={"turnover_rate": 0.66, "float_share": 1000.0},
        prev_state=v2_common.PrevState(),
        row_status="traded",
        volume=100000,
        ak_cache=_DummyAkCache(0.77),
        exceptions=exceptions,
        ts_code="600000.SH",
    )
    assert value == 0.66
    assert source == "tushare_daily_basic"
    assert confidence == 3
    assert exceptions == []

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2026, 3, 16),
        symbol="sh600000",
        market_phase="sh",
        basic_row={},
        prev_state=v2_common.PrevState(),
        row_status="traded",
        volume=100000,
        ak_cache=_DummyAkCache(0.77),
        exceptions=exceptions,
        ts_code="600000.SH",
    )
    assert value == 0.77
    assert source == "akshare_stock_zh_a_hist"
    assert confidence == 2

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2026, 3, 16),
        symbol="sh600000",
        market_phase="sh",
        basic_row={"float_share": 1000.0},
        prev_state=v2_common.PrevState(),
        row_status="traded",
        volume=100000,
        ak_cache=_DummyAkCache(None),
        exceptions=exceptions,
        ts_code="600000.SH",
    )
    assert round(value, 6) == 1.0
    assert source == "formula_from_float_share"
    assert confidence == 1


def test_resolve_turnover_rate_imputed_zero_uses_mapping_failure_for_bj_pre() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2020, 1, 2),
        symbol="bj920047",
        market_phase="bj_pre_20211115",
        basic_row={},
        prev_state=v2_common.PrevState(),
        row_status="source_unresolved",
        volume=0,
        ak_cache=_DummyAkCache(None),
        exceptions=exceptions,
        ts_code="920047.BJ",
    )

    assert value == 0.0
    assert source == "imputed_zero"
    assert confidence == 0
    assert exceptions[-1]["issue_type"] == "turnover_rate_imputed_zero"
    assert exceptions[-1]["cause_class"] == "mapping_failure"


def test_resolve_turnover_rate_rejects_zero_from_lineage_when_traded() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2020, 1, 2),
        symbol="bj920047",
        market_phase="bj_pre_20211115",
        basic_row={},
        prev_state=v2_common.PrevState(),
        row_status="traded",
        volume=10000,
        ak_cache=_DummyAkCache(0.0, "akshare_stock_zh_a_hist_lineage"),
        exceptions=exceptions,
        ts_code="920047.BJ",
    )

    assert value == 0.0
    assert source == "imputed_zero"
    assert confidence == 0
    assert "ak_source=akshare_stock_zh_a_hist_lineage" in str(exceptions[-1]["issue_detail"])


def test_resolve_turnover_rate_uses_prev_float_share_when_basic_missing() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2020, 1, 2),
        symbol="bj920047",
        market_phase="bj_pre_20211115",
        basic_row={},
        prev_state=v2_common.PrevState(float_share=2000.0),
        row_status="traded",
        volume=100000,
        ak_cache=_DummyAkCache(None),
        exceptions=exceptions,
        ts_code="920047.BJ",
    )

    assert round(value, 6) == 0.5
    assert source == "formula_from_prev_float_share"
    assert confidence == 1
    assert exceptions == []


def test_build_trade_date_rows_keeps_zero_gap_and_records_eligible_no_source() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "600000.SH",
                "symbol": "sh600000",
                "exchange": "SH",
                "list_date": date(2000, 1, 1),
                "delist_date": None,
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"sh600000": v2_common.PrevState(close=10.0, adj_factor=1.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2026, 3, 16),
        eligible_frame=eligible,
        daily_frame=pd.DataFrame(columns=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "symbol"]),
        adj_frame=pd.DataFrame(columns=["ts_code", "trade_date", "adj_factor", "symbol"]),
        basic_frame=pd.DataFrame(columns=["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS, "symbol"]),
        suspend_frame=pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type", "symbol"]),
        limit_frame=pd.DataFrame(columns=["ts_code", "trade_date", "up_limit", "down_limit", "symbol"]),
        st_periods={},
        prev_state=prev_state,
        ak_cache=_DummyAkCache(None),  # type: ignore[arg-type]
        bj_pre_evidence_dates={},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["market_phase"] == "sh"
    assert row["row_status"] == "source_unresolved"
    assert bool(row["is_suspended"]) is False
    assert float(row["pre_close"]) == 10.0
    assert row["pre_close_source"] == "prev_close_carry"
    assert int(row["pre_close_confidence"]) == 2
    assert float(row["open"]) == 10.0
    assert float(row["high"]) == 10.0
    assert float(row["low"]) == 10.0
    assert float(row["close"]) == 10.0
    assert int(row["volume"]) == 0
    assert float(row["turnover"]) == 0.0
    assert float(row["turnover_rate"]) == 0.0
    assert row["turnover_rate_source"] == "imputed_zero"
    assert int(row["turnover_rate_confidence"]) == 0
    assert row["adj_factor_source"] == "prev_adj_factor_carry"
    assert int(row["adj_factor_confidence"]) == 2
    assert stats["eligible_symbol_count"] == 1
    assert stats["built_symbol_count"] == 1
    assert stats["eligible_no_source_rows"] == 1
    assert any(item["issue_type"] == "eligible_no_source" for item in exceptions)
    assert any(item["cause_class"] == "missing_in_all_sources" for item in exceptions if item["issue_type"] == "eligible_no_source")


def test_build_trade_date_rows_skips_bj_pre_without_raw_evidence() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "920047.BJ",
                "symbol": "bj920047",
                "exchange": "BJ",
                "list_date": date(2010, 4, 22),
                "delist_date": None,
                "market_type": "CN_A",
            }
        ]
    )

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2010, 4, 23),
        eligible_frame=eligible,
        daily_frame=pd.DataFrame(columns=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "symbol"]),
        adj_frame=pd.DataFrame(columns=["ts_code", "trade_date", "adj_factor", "symbol"]),
        basic_frame=pd.DataFrame(columns=["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS, "symbol"]),
        suspend_frame=pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type", "symbol"]),
        limit_frame=pd.DataFrame(columns=["ts_code", "trade_date", "up_limit", "down_limit", "symbol"]),
        st_periods={},
        prev_state={},
        ak_cache=_DummyAkCache(None),  # type: ignore[arg-type]
        bj_pre_evidence_dates={"bj920047": {date(2010, 4, 22)}},
        build_run_id="test_run",
    )

    assert frame.empty
    assert stats["eligible_symbol_count"] == 1
    assert stats["built_symbol_count"] == 0
    assert stats["skipped_bj_pre_no_evidence_rows"] == 1
    assert stats["eligible_no_source_rows"] == 0
    assert exceptions == []
