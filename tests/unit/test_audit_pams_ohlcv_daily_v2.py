from __future__ import annotations

from datetime import date

import pandas as pd

from backend.cli.managed import audit_pams_ohlcv_daily_v2 as updater


def test_build_trade_date_audit_counts_missing_and_hard_null_rows() -> None:
    main_frame = pd.DataFrame(
        [
            {
                "symbol": "sh600000",
                "ts_code": "600000.SH",
                "trade_date": date(2026, 3, 16),
                "market": "CN_A",
                "market_phase": "sh",
                "row_status": "traded",
                "is_suspended": False,
                "pre_close": 10.0,
                "pre_close_source": "daily_pre_close",
                "pre_close_confidence": 3,
                "open": 10.0,
                "high": 10.2,
                "low": 9.9,
                "close": 10.1,
                "volume": 100000,
                "turnover": 1000000.0,
                "adj_factor": 1.0,
                "adj_factor_source": "tushare_adj_factor",
                "adj_factor_confidence": 3,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "turnover_rate": 1.0,
                "turnover_rate_source": "formula_from_float_share",
                "turnover_rate_confidence": 1,
                "source_daily_present": True,
                "source_daily_basic_present": False,
                "source_suspend_present": False,
                "turnover_rate_f": None,
                "volume_ratio": None,
                "float_share": None,
                "free_share": None,
                "circ_mv": None,
            },
            {
                "symbol": "sz000001",
                "ts_code": "000001.SZ",
                "trade_date": date(2026, 3, 16),
                "market": "CN_A",
                "market_phase": "sz",
                "row_status": "source_unresolved",
                "is_suspended": False,
                "pre_close": 8.0,
                "pre_close_source": "prev_close_carry",
                "pre_close_confidence": 2,
                "open": 8.0,
                "high": 8.0,
                "low": 8.0,
                "close": 8.0,
                "volume": 0,
                "turnover": 0.0,
                "adj_factor": 1.0,
                "adj_factor_source": "default_1",
                "adj_factor_confidence": 0,
                "limit_up": 8.8,
                "limit_down": 7.2,
                "turnover_rate": 0.0,
                "turnover_rate_source": "imputed_zero",
                "turnover_rate_confidence": 0,
                "source_daily_present": False,
                "source_daily_basic_present": True,
                "source_suspend_present": False,
                "turnover_rate_f": 0.0,
                "volume_ratio": None,
                "float_share": 1000.0,
                "free_share": None,
                "circ_mv": 8000.0,
            },
        ]
    )
    side_frame = pd.DataFrame(
        [
            {
                "symbol": "sh600000",
                "trade_date": date(2026, 3, 16),
                "source_moneyflow_present": True,
                "net_fields_present": True,
            }
        ]
    )

    row, exceptions = updater._build_trade_date_audit(
        trade_date=date(2026, 3, 16),
        eligible_count=2,
        raw_daily_count=1,
        main_frame=main_frame,
        side_frame=side_frame,
        v1_count=1,
    )

    assert row["eligible_symbol_count"] == 2
    assert row["v2_count"] == 2
    assert row["moneyflow_join_count"] == 1
    assert row["moneyflow_missing_count"] == 0
    assert row["daily_basic_missing_count"] == 1
    assert row["eligible_missing_daily_count"] == 1
    assert row["hard_field_null_count"] == 0
    assert row["v2_minus_v1"] == 1
    assert row["market_phase_counts"] == {"sh": 1, "sz": 1}
    assert row["row_status_counts"] == {"source_unresolved": 1, "traded": 1}
    issue_types = {item[3] for item in exceptions}
    assert "daily_basic_missing" in issue_types
    assert "eligible_no_source" in issue_types


def test_build_update_args_accepts_symbol_filter() -> None:
    args = updater.build_update_args(
        start="2026-03-16",
        end="2026-03-16",
        symbols_csv="sh600000,sz000001",
        apply=False,
    )

    assert args.start == "2026-03-16"
    assert args.end == "2026-03-16"
    assert args.symbols_csv == "sh600000,sz000001"
    assert args.apply is False


def test_build_canonical_gate_requires_full_window_and_zero_critical_exceptions() -> None:
    per_trade_date = [
        {
            "eligible_missing_daily_count": 0,
            "v2_minus_v1": 0,
            "hard_field_null_count": 0,
            "market_phase_counts": {"sh": 1, "sz": 1},
            "row_status_counts": {"traded": 2},
        }
    ]

    full_gate = updater._build_canonical_gate(
        per_trade_date=per_trade_date,
        critical_exception_rows_raw=0,
        known_source_gap_rows=0,
        critical_exception_rows=0,
        start=updater.v2_common.DEFAULT_BACKFILL_START,
        end=updater.v2_common.OFFICIAL_END_DATE,
    )

    assert full_gate["official_window"] == {
        "start": updater.v2_common.DEFAULT_BACKFILL_START.isoformat(),
        "end": updater.v2_common.OFFICIAL_END_DATE.isoformat(),
    }
    assert full_gate["critical_exception_rows_raw"] == 0
    assert full_gate["known_source_gap_rows"] == 0
    assert full_gate["has_full_window"] is True
    assert full_gate["can_promote_shadow"] is True

    partial_gate = updater._build_canonical_gate(
        per_trade_date=per_trade_date,
        critical_exception_rows_raw=0,
        known_source_gap_rows=0,
        critical_exception_rows=0,
        start=date(2007, 1, 5),
        end=updater.v2_common.OFFICIAL_END_DATE,
    )
    assert partial_gate["has_full_window"] is False
    assert partial_gate["can_promote_shadow"] is False

    critical_gate = updater._build_canonical_gate(
        per_trade_date=per_trade_date,
        critical_exception_rows_raw=5,
        known_source_gap_rows=4,
        critical_exception_rows=1,
        start=updater.v2_common.DEFAULT_BACKFILL_START,
        end=updater.v2_common.OFFICIAL_END_DATE,
    )
    assert critical_gate["critical_exception_rows_raw"] == 5
    assert critical_gate["known_source_gap_rows"] == 4
    assert critical_gate["has_full_window"] is True
    assert critical_gate["can_promote_shadow"] is False


def test_build_runtime_gate_tracks_exclusion_reasons() -> None:
    runtime_breakdown = pd.DataFrame(
        [
            {"market_phase": "sh", "exclusion_reason": "runtime_eligible", "rows": 10},
            {"market_phase": "sh", "exclusion_reason": "row_status_delist_tail_confirmed", "rows": 4},
            {"market_phase": "sz", "exclusion_reason": "row_status_source_unresolved", "rows": 2},
            {
                "market_phase": "bj_pre_20211115",
                "exclusion_reason": updater.v2_common.KNOWN_SOURCE_GAP_LOW_TURNOVER_REASON,
                "rows": 5,
            },
            {"market_phase": "sz", "exclusion_reason": "low_adj_factor_confidence", "rows": 3},
        ]
    )

    gate = updater._build_runtime_gate(
        runtime_breakdown,
        row_status_totals={"source_unresolved": 2, "delist_tail_confirmed": 4, "synthetic_gap_fill": 0, "traded": 10},
    )

    assert gate["runtime_eligible_rows"] == 10
    assert gate["unresolved_rows"] == 2
    assert gate["delist_tail_confirmed_rows"] == 4
    assert gate["excluded_delist_tail_confirmed_rows"] == 4
    assert gate["excluded_low_adj_factor_confidence_rows"] == 3
    assert gate["excluded_known_source_gap_low_turnover_rows"] == 5
    assert gate["exclusion_breakdown"] == {
        "row_status_delist_tail_confirmed": 4,
        "row_status_source_unresolved": 2,
        updater.v2_common.KNOWN_SOURCE_GAP_LOW_TURNOVER_REASON: 5,
        "low_adj_factor_confidence": 3,
    }
    assert gate["can_consume_v10_1"] is False


def test_load_runtime_exclusion_breakdown_marks_bj_post_known_source_gap(monkeypatch) -> None:
    captured_query: dict[str, str] = {}

    def fake_df_from_query(conn, query, params):
        captured_query["sql"] = query
        _ = (conn, params)
        return pd.DataFrame(
            [
                {
                    "market_phase": "bj_post_20211115",
                    "exclusion_reason": updater.v2_common.KNOWN_SOURCE_GAP_LOW_TURNOVER_REASON,
                    "rows": 4932,
                }
            ]
        )

    monkeypatch.setattr(updater.v2_common, "df_from_query", fake_df_from_query)

    frame = updater._load_runtime_exclusion_breakdown(
        None,
        start=date(2021, 11, 15),
        end=date(2026, 3, 20),
        symbol_filter=set(),
    )

    assert frame.iloc[0]["exclusion_reason"] == updater.v2_common.KNOWN_SOURCE_GAP_LOW_TURNOVER_REASON
    assert "market_phase = 'bj_post_20211115'" in captured_query["sql"]
    assert "source_daily_basic_present = FALSE" in captured_query["sql"]


def test_count_exception_gate_rows_separates_known_source_gap(monkeypatch) -> None:
    captured_query: dict[str, str] = {}

    def fake_df_from_query(conn, query, params):
        captured_query["sql"] = query
        return pd.DataFrame(
            [
                {
                    "raw_rows": 27876,
                    "known_source_gap_rows": 26364,
                    "effective_rows": 1512,
                }
            ]
        )

    monkeypatch.setattr(updater.v2_common, "df_from_query", fake_df_from_query)

    rows = updater._count_exception_gate_rows(
        None,
        start=date(2012, 1, 4),
        end=date(2017, 12, 29),
        issue_types=updater.v2_common.CRITICAL_BUILD_ISSUE_TYPES,
        symbol_filter=set(),
    )

    assert rows == {
        "critical_exception_rows_raw": 27876,
        "known_source_gap_rows": 26364,
        "critical_exception_rows": 1512,
    }
    assert "v2.build_run_id = e.build_run_id" in captured_query["sql"]
    assert "left_censored_turnover_gap" in captured_query["sql"]


def test_load_key_exception_drilldown_filters_stale_exceptions(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_df_from_query(conn, query, params):
        _ = (conn, params)
        captured[str(len(captured))] = query
        return pd.DataFrame(columns=["year", "issue_type", "rows"])

    monkeypatch.setattr(updater.v2_common, "df_from_query", fake_df_from_query)

    updater._load_key_exception_drilldown(
        None,
        start=date(2016, 3, 1),
        end=date(2026, 3, 20),
        symbol_filter=set(),
    )

    assert captured
    for query in captured.values():
        assert "v2.build_run_id = e.build_run_id" in query


def test_build_trade_date_audit_excludes_synthetic_gap_fill_from_eligible_no_source() -> None:
    main_frame = pd.DataFrame(
        [
            {
                "symbol": "sh600705",
                "ts_code": "600705.SH",
                "trade_date": date(2026, 3, 16),
                "market": "CN_A",
                "market_phase": "sh",
                "row_status": "synthetic_gap_fill",
                "is_suspended": False,
                "pre_close": 10.0,
                "pre_close_source": "prev_close_carry",
                "pre_close_confidence": 2,
                "open": 10.0,
                "high": 10.0,
                "low": 10.0,
                "close": 10.0,
                "volume": 0,
                "turnover": 0.0,
                "adj_factor": 1.0,
                "adj_factor_source": "tushare_adj_factor",
                "adj_factor_confidence": 3,
                "limit_up": 11.0,
                "limit_down": 9.0,
                "turnover_rate": 0.0,
                "turnover_rate_source": "imputed_zero",
                "turnover_rate_confidence": 0,
                "source_daily_present": False,
                "source_daily_basic_present": False,
                "source_suspend_present": False,
                "turnover_rate_f": None,
                "volume_ratio": None,
                "float_share": None,
                "free_share": None,
                "circ_mv": None,
            }
        ]
    )
    side_frame = pd.DataFrame(columns=["symbol", "trade_date", "source_moneyflow_present", "net_fields_present"])

    row, exceptions = updater._build_trade_date_audit(
        trade_date=date(2026, 3, 16),
        eligible_count=1,
        raw_daily_count=0,
        main_frame=main_frame,
        side_frame=side_frame,
        v1_count=0,
    )

    assert row["eligible_missing_daily_count"] == 0
    assert row["row_status_counts"] == {"synthetic_gap_fill": 1}
    issue_types = {item[3] for item in exceptions}
    assert "eligible_no_source" not in issue_types
    assert "synthetic_gap_fill_side_evidence" in issue_types


def test_build_trade_date_audit_tracks_delist_tail_confirmed_separately() -> None:
    main_frame = pd.DataFrame(
        [
            {
                "symbol": "sz000043",
                "ts_code": "000043.SZ",
                "trade_date": date(2019, 12, 16),
                "market": "CN_A",
                "market_phase": "sz",
                "row_status": "delist_tail_confirmed",
                "is_suspended": False,
                "pre_close": 8.0,
                "pre_close_source": "prev_close_carry",
                "pre_close_confidence": 2,
                "open": 8.0,
                "high": 8.0,
                "low": 8.0,
                "close": 8.0,
                "volume": 0,
                "turnover": 0.0,
                "adj_factor": 1.0,
                "adj_factor_source": "prev_adj_factor_carry",
                "adj_factor_confidence": 2,
                "limit_up": 8.8,
                "limit_down": 7.2,
                "turnover_rate": 0.0,
                "turnover_rate_source": "formula_from_prev_float_share",
                "turnover_rate_confidence": 1,
                "source_daily_present": False,
                "source_daily_basic_present": False,
                "source_suspend_present": False,
                "turnover_rate_f": None,
                "volume_ratio": None,
                "float_share": 1000.0,
                "free_share": 900.0,
                "circ_mv": 8000.0,
            }
        ]
    )
    side_frame = pd.DataFrame(columns=["symbol", "trade_date", "source_moneyflow_present", "net_fields_present"])

    row, exceptions = updater._build_trade_date_audit(
        trade_date=date(2019, 12, 16),
        eligible_count=1,
        raw_daily_count=0,
        main_frame=main_frame,
        side_frame=side_frame,
        v1_count=0,
    )

    assert row["eligible_missing_daily_count"] == 0
    assert row["row_status_counts"] == {"delist_tail_confirmed": 1}
    issue_types = {item[3] for item in exceptions}
    assert "eligible_no_source" not in issue_types
    assert "delist_tail_confirmed" in issue_types
