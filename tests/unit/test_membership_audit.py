from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.universe.membership_audit import audit_membership_history


def _membership_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "index_code": "000852.SH",
                "symbol": "000001.SZ",
                "start_date": "2015-07-31",
                "end_date": "2015-08-31",
                "source": "tushare_csi1000_calendar",
                "event_type": "scheduled",
                "rebalance_calendar_version": "official-v1",
                "rebalance_calendar_source": "official_calendar",
                "rebalance_calendar_generated_at": "2026-03-23T00:00:00+08:00",
            },
            {
                "index_code": "000852.SH",
                "symbol": "000001.SZ",
                "start_date": "2015-08-31",
                "end_date": None,
                "source": "tushare_csi1000_calendar",
                "event_type": "scheduled",
                "rebalance_calendar_version": "official-v1",
                "rebalance_calendar_source": "official_calendar",
                "rebalance_calendar_generated_at": "2026-03-23T00:00:00+08:00",
            },
        ]
    )


def _refresh_membership() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "index_code": "000852.SH",
                "refresh_date": "2015-07-31",
                "symbol": "000001.SZ",
                "constituent_start_date": "2015-07-31",
                "source": "tushare_csi1000_calendar",
                "event_type": "scheduled",
                "snapshot_trade_date": "2015-07-31",
            },
            {
                "index_code": "000852.SH",
                "refresh_date": "2015-08-31",
                "symbol": "000001.SZ",
                "constituent_start_date": "2015-08-31",
                "source": "tushare_csi1000_calendar",
                "event_type": "scheduled",
                "snapshot_trade_date": "2015-08-31",
            },
        ]
    )


def test_membership_audit_marks_pre_floor_window_as_approximate() -> None:
    audit = audit_membership_history(
        _membership_history(),
        refresh_membership=_refresh_membership(),
        required_start=date(2012, 1, 4),
        required_end=date(2016, 12, 31),
        require_calendar_metadata=True,
    )

    assert audit["provider_floor_date"] == "2015-07-31"
    assert audit["membership_data_quality"] == "approximate"
    assert "provider_floor_uncovered_start" in audit["audit_reason"]
    assert audit["refresh_event_count"] == 2
    assert audit["covered_refresh_event_count"] == 2


def test_membership_audit_keeps_covered_window_pit_verified_when_refresh_sidecar_present() -> None:
    audit = audit_membership_history(
        _membership_history(),
        refresh_membership=_refresh_membership(),
        required_start=date(2015, 7, 31),
        required_end=date(2016, 12, 31),
        require_calendar_metadata=True,
    )

    assert audit["membership_data_quality"] == "pit_verified"
    assert audit["audit_status"] == "ok"
    assert audit["covers_required_start"] is True
    assert audit["refresh_sidecar_present"] is True
    assert audit["zero_diff_refresh_event_count"] == 0
