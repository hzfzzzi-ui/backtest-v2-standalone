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


def test_build_runtime_gate_tracks_exclusion_reasons() -> None:
    runtime_breakdown = pd.DataFrame(
        [
            {"market_phase": "sh", "exclusion_reason": "runtime_eligible", "rows": 10},
            {"market_phase": "sz", "exclusion_reason": "row_status_source_unresolved", "rows": 2},
            {"market_phase": "sz", "exclusion_reason": "low_adj_factor_confidence", "rows": 3},
        ]
    )

    gate = updater._build_runtime_gate(
        runtime_breakdown,
        row_status_totals={"source_unresolved": 2, "synthetic_gap_fill": 0, "traded": 10},
    )

    assert gate["runtime_eligible_rows"] == 10
    assert gate["unresolved_rows"] == 2
    assert gate["excluded_low_adj_factor_confidence_rows"] == 3
    assert gate["exclusion_breakdown"] == {
        "row_status_source_unresolved": 2,
        "low_adj_factor_confidence": 3,
    }
    assert gate["can_consume_v10_1"] is False
