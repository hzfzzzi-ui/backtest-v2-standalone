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


def test_apply_terminal_boundaries_prefers_code_transition_end_date() -> None:
    security_master = pd.DataFrame(
        [
            {
                "ts_code": "300114.SZ",
                "symbol": "sz300114",
                "exchange": "SZ",
                "list_date": date(2010, 8, 27),
                "delist_date": None,
                "market_type": "CN_A",
            }
        ]
    )

    frame = updater._apply_terminal_boundaries(
        security_master,
        {"sz300114": (date(2025, 2, 14), "official_cninfo_code_change_2025_028")},
    )

    assert frame.iloc[0]["effective_end_date"] == date(2025, 2, 14)
    assert frame.iloc[0]["effective_end_source"] == "pit_security_symbol_lineage"


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


def test_resolve_turnover_rate_imputed_zero_uses_daily_basic_gap_for_bj_pre() -> None:
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
    assert exceptions[-1]["cause_class"] == "bj_pre_daily_basic_gap"
    assert "basic_turnover=None" in str(exceptions[-1]["issue_detail"])


def test_resolve_turnover_rate_imputed_zero_uses_daily_basic_gap_for_bj_post() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2021, 11, 15),
        symbol="bj920130",
        market_phase="bj_post_20211115",
        basic_row={},
        prev_state=v2_common.PrevState(),
        row_status="traded",
        volume=10000,
        ak_cache=_DummyAkCache(None),
        exceptions=exceptions,
        ts_code="920130.BJ",
    )

    assert value == 0.0
    assert source == "imputed_zero"
    assert confidence == 0
    assert exceptions[-1]["issue_type"] == "turnover_rate_imputed_zero"
    assert exceptions[-1]["cause_class"] == "bj_post_daily_basic_gap"
    assert "basic_turnover=None" in str(exceptions[-1]["issue_detail"])


def test_resolve_turnover_rate_uses_left_censored_gap_for_sh_sz_non_traded_rows() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_turnover_rate(
        trade_date=date(2012, 1, 4),
        symbol="sz000156",
        market_phase="sz",
        basic_row={},
        prev_state=v2_common.PrevState(),
        row_status="synthetic_gap_fill",
        pre_close_source="imputed_zero",
        volume=0,
        ak_cache=_DummyAkCache(None),
        exceptions=exceptions,
        ts_code="000156.SZ",
    )

    assert value == 0.0
    assert source == "imputed_zero"
    assert confidence == 0
    assert exceptions[-1]["issue_type"] == "turnover_rate_imputed_zero"
    assert exceptions[-1]["cause_class"] == v2_common.TURNOVER_LEFT_CENSORED_CAUSE


def test_resolve_anchor_price_marks_left_censored_gap_for_synthetic_gap_fill() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_anchor_price(
        prev_state=v2_common.PrevState(),
        basic_row={},
        daily_row={},
        row_status="synthetic_gap_fill",
        exceptions=exceptions,
        trade_date=date(2012, 1, 4),
        symbol="sz000156",
        ts_code="000156.SZ",
    )

    assert value == 0.0
    assert source == "imputed_zero"
    assert confidence == 0
    assert exceptions[-1]["issue_type"] == "pre_close_imputed_zero"
    assert exceptions[-1]["cause_class"] == v2_common.PRE_CLOSE_LEFT_CENSORED_CAUSE


def test_resolve_anchor_price_keeps_generic_cause_for_source_unresolved() -> None:
    exceptions: list[dict[str, object]] = []

    value, source, confidence = updater._resolve_anchor_price(
        prev_state=v2_common.PrevState(),
        basic_row={},
        daily_row={},
        row_status="source_unresolved",
        exceptions=exceptions,
        trade_date=date(2007, 1, 4),
        symbol="sh600286",
        ts_code="600286.SH",
    )

    assert value == 0.0
    assert source == "imputed_zero"
    assert confidence == 0
    assert exceptions[-1]["issue_type"] == "pre_close_imputed_zero"
    assert exceptions[-1]["cause_class"] == "source_present_low_confidence_fill"


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


def test_build_trade_date_rows_reclassifies_sh_side_evidence_gap_fill() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "600705.SH",
                "symbol": "sh600705",
                "exchange": "SH",
                "list_date": date(2000, 1, 1),
                "delist_date": None,
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"sh600705": v2_common.PrevState(close=10.0, adj_factor=1.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2026, 3, 16),
        eligible_frame=eligible,
        daily_frame=pd.DataFrame(columns=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "symbol"]),
        adj_frame=pd.DataFrame([{"ts_code": "600705.SH", "trade_date": date(2026, 3, 16), "adj_factor": 1.2, "symbol": "sh600705"}]),
        basic_frame=pd.DataFrame(columns=["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS, "symbol"]),
        suspend_frame=pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type", "symbol"]),
        limit_frame=pd.DataFrame([{"ts_code": "600705.SH", "trade_date": date(2026, 3, 16), "up_limit": 11.0, "down_limit": 9.0, "symbol": "sh600705"}]),
        st_periods={},
        prev_state=prev_state,
        ak_cache=_DummyAkCache(None),  # type: ignore[arg-type]
        bj_pre_evidence_dates={},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["row_status"] == "synthetic_gap_fill"
    assert bool(row["is_suspended"]) is False
    assert stats["eligible_no_source_rows"] == 0
    assert any(item["issue_type"] == "synthetic_gap_fill_side_evidence" for item in exceptions)
    assert not any(item["issue_type"] == "eligible_no_source" for item in exceptions)


def test_build_trade_date_rows_reclassifies_bj_post_side_evidence_gap_fill() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "920931.BJ",
                "symbol": "bj920931",
                "exchange": "BJ",
                "list_date": date(2021, 11, 15),
                "delist_date": None,
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"bj920931": v2_common.PrevState(close=10.0, adj_factor=1.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2026, 3, 16),
        eligible_frame=eligible,
        daily_frame=pd.DataFrame(columns=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "symbol"]),
        adj_frame=pd.DataFrame([{"ts_code": "920931.BJ", "trade_date": date(2026, 3, 16), "adj_factor": 1.2, "symbol": "bj920931"}]),
        basic_frame=pd.DataFrame(columns=["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS, "symbol"]),
        suspend_frame=pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type", "symbol"]),
        limit_frame=pd.DataFrame([{"ts_code": "920931.BJ", "trade_date": date(2026, 3, 16), "up_limit": 11.0, "down_limit": 9.0, "symbol": "bj920931"}]),
        st_periods={},
        prev_state=prev_state,
        ak_cache=_DummyAkCache(None),  # type: ignore[arg-type]
        bj_pre_evidence_dates={},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["market_phase"] == "bj_post_20211115"
    assert row["row_status"] == "synthetic_gap_fill"
    assert bool(row["is_suspended"]) is False
    assert stats["eligible_no_source_rows"] == 0
    assert any(item["issue_type"] == "synthetic_gap_fill_side_evidence" for item in exceptions)
    assert not any(item["issue_type"] == "eligible_no_source" for item in exceptions)


def test_build_trade_date_rows_does_not_reclassify_bj_pre_side_evidence() -> None:
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
    prev_state = {"bj920047": v2_common.PrevState(close=10.0, adj_factor=1.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2010, 4, 23),
        eligible_frame=eligible,
        daily_frame=pd.DataFrame(columns=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "symbol"]),
        adj_frame=pd.DataFrame([{"ts_code": "920047.BJ", "trade_date": date(2010, 4, 23), "adj_factor": 1.2, "symbol": "bj920047"}]),
        basic_frame=pd.DataFrame(columns=["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS, "symbol"]),
        suspend_frame=pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type", "symbol"]),
        limit_frame=pd.DataFrame([{"ts_code": "920047.BJ", "trade_date": date(2010, 4, 23), "up_limit": 11.0, "down_limit": 9.0, "symbol": "bj920047"}]),
        st_periods={},
        prev_state=prev_state,
        ak_cache=_DummyAkCache(None),  # type: ignore[arg-type]
        bj_pre_evidence_dates={"bj920047": {date(2010, 4, 23)}},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["market_phase"] == "bj_pre_20211115"
    assert row["row_status"] == "source_unresolved"
    assert stats["eligible_no_source_rows"] == 1
    assert any(item["issue_type"] == "eligible_no_source" for item in exceptions)
    assert not any(item["issue_type"] == "synthetic_gap_fill_side_evidence" for item in exceptions)


def test_build_trade_date_rows_reclassifies_delist_tail_confirmed() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "000043.SZ",
                "symbol": "sz000043",
                "exchange": "SZ",
                "list_date": date(1994, 9, 28),
                "delist_date": date(2019, 12, 16),
                "effective_end_date": date(2019, 12, 16),
                "effective_end_source": "pit_security_master",
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"sz000043": v2_common.PrevState(close=10.0, adj_factor=1.0, float_share=1000.0, free_share=900.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2019, 12, 16),
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
        last_source_trade_dates={"sz000043": date(2019, 12, 13)},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["row_status"] == "delist_tail_confirmed"
    assert bool(row["is_suspended"]) is False
    assert stats["eligible_no_source_rows"] == 0
    assert stats["delist_tail_confirmed_rows"] == 1
    assert any(item["issue_type"] == "delist_tail_confirmed" for item in exceptions)


def test_build_trade_date_rows_reclassifies_official_terminal_override_on_delist_day() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "600680.SH",
                "symbol": "sh600680",
                "exchange": "SH",
                "list_date": date(1993, 10, 18),
                "delist_date": date(2019, 5, 24),
                "effective_end_date": date(2019, 5, 24),
                "effective_end_source": "pit_security_master",
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"sh600680": v2_common.PrevState(close=8.0, adj_factor=1.0, float_share=1000.0, free_share=900.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2019, 5, 24),
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
        last_source_trade_dates={"sh600680": date(2025, 8, 14)},
        official_terminal_overrides={"sh600680": v2_common.OFFICIAL_TERMINAL_OVERRIDES["sh600680"]},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    assert frame.iloc[0]["row_status"] == "delist_tail_confirmed"
    assert stats["eligible_no_source_rows"] == 0
    assert stats["delist_tail_confirmed_rows"] == 1
    hit = next(item for item in exceptions if item["issue_type"] == "delist_tail_confirmed")
    assert hit["cause_class"] == "official_terminal_override"
    assert hit["source_table"] == "sse_c_20190517_4820838"


def test_build_trade_date_rows_reclassifies_official_terminal_override_for_suspension_window() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "601268.SH",
                "symbol": "sh601268",
                "exchange": "SH",
                "list_date": date(2010, 2, 2),
                "delist_date": date(2015, 5, 21),
                "effective_end_date": date(2015, 5, 21),
                "effective_end_source": "pit_security_master",
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"sh601268": v2_common.PrevState(close=5.0, adj_factor=1.0, float_share=1000.0, free_share=900.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2014, 5, 26),
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
        last_source_trade_dates={"sh601268": date(2018, 8, 27)},
        official_terminal_overrides={"sh601268": v2_common.OFFICIAL_TERMINAL_OVERRIDES["sh601268"]},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    assert frame.iloc[0]["row_status"] == "delist_tail_confirmed"
    assert stats["eligible_no_source_rows"] == 0
    assert stats["delist_tail_confirmed_rows"] == 1
    hit = next(item for item in exceptions if item["issue_type"] == "delist_tail_confirmed")
    assert hit["cause_class"] == "official_terminal_override"
    assert "override_start_date=2014-05-26" in str(hit["issue_detail"])


def test_build_trade_date_rows_reclassifies_pre_window_pause_override_tail() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "000699.SZ",
                "symbol": "sz000699",
                "exchange": "SZ",
                "list_date": date(1997, 3, 10),
                "delist_date": date(2007, 4, 4),
                "effective_end_date": date(2007, 4, 4),
                "effective_end_source": "pit_security_master",
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"sz000699": v2_common.PrevState()}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2007, 1, 4),
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
        last_source_trade_dates={},
        official_terminal_overrides={"sz000699": v2_common.OFFICIAL_TERMINAL_OVERRIDES["sz000699"]},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    assert frame.iloc[0]["row_status"] == "delist_tail_confirmed"
    assert stats["eligible_no_source_rows"] == 0
    assert stats["delist_tail_confirmed_rows"] == 1
    hit = next(item for item in exceptions if item["issue_type"] == "delist_tail_confirmed")
    assert hit["cause_class"] == "official_terminal_override"
    assert hit["source_table"] == "cninfo_15880923_pause_20050509_plus_stock_basic_delist_date"


def test_build_trade_date_rows_official_override_does_not_overwrite_synthetic_gap_fill() -> None:
    eligible = pd.DataFrame(
        [
            {
                "ts_code": "601268.SH",
                "symbol": "sh601268",
                "exchange": "SH",
                "list_date": date(2010, 2, 2),
                "delist_date": date(2015, 5, 21),
                "effective_end_date": date(2015, 5, 21),
                "effective_end_source": "pit_security_master",
                "market_type": "CN_A",
            }
        ]
    )
    prev_state = {"sh601268": v2_common.PrevState(close=5.0, adj_factor=1.0, float_share=1000.0, free_share=900.0)}

    frame, stats, exceptions = updater._build_trade_date_rows(
        trade_date=date(2014, 9, 2),
        eligible_frame=eligible,
        daily_frame=pd.DataFrame(columns=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "symbol"]),
        adj_frame=pd.DataFrame([{"ts_code": "601268.SH", "trade_date": date(2014, 9, 2), "adj_factor": 1.2, "symbol": "sh601268"}]),
        basic_frame=pd.DataFrame(columns=["ts_code", "trade_date", *v2_common.DAILY_BASIC_FIELDS, "symbol"]),
        suspend_frame=pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type", "symbol"]),
        limit_frame=pd.DataFrame([{"ts_code": "601268.SH", "trade_date": date(2014, 9, 2), "up_limit": 5.5, "down_limit": 4.5, "symbol": "sh601268"}]),
        st_periods={},
        prev_state=prev_state,
        ak_cache=_DummyAkCache(None),  # type: ignore[arg-type]
        bj_pre_evidence_dates={},
        last_source_trade_dates={"sh601268": date(2018, 8, 27)},
        official_terminal_overrides={"sh601268": v2_common.OFFICIAL_TERMINAL_OVERRIDES["sh601268"]},
        build_run_id="test_run",
    )

    assert len(frame) == 1
    assert frame.iloc[0]["row_status"] == "synthetic_gap_fill"
    assert stats["eligible_no_source_rows"] == 0
    assert not any(item["cause_class"] == "official_terminal_override" for item in exceptions)


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
