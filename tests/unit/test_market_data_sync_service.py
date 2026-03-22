from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import threading

import pandas as pd
import pytest

from backend.core.services import market_data_sync_service as mod


class _DummyConn:
    def cursor(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchone(self):
        return (date(2026, 3, 14),)

    def close(self):
        return None

    def commit(self):
        return None


def test_resolve_target_trade_date_uses_today_after_schedule(monkeypatch) -> None:
    monkeypatch.setenv("CN_DAILY_SYNC_TIME", "18:30")
    monkeypatch.setenv("TUSHARE_TOKEN", "dummy-token")

    class _DummyPro:
        def __init__(self):
            self.calls = []

        def trade_cal(self, **kwargs):
            self.calls.append(kwargs)
            return pd.DataFrame(
                [
                    {"exchange": "SSE", "cal_date": "20260313", "is_open": 1},
                    {"exchange": "SSE", "cal_date": "20260314", "is_open": 0},
                    {"exchange": "SSE", "cal_date": "20260315", "is_open": 0},
                    {"exchange": "SSE", "cal_date": "20260316", "is_open": 1},
                ]
            )

    pro = _DummyPro()
    monkeypatch.setattr(mod.daily_updater, "_load_tushare_client", lambda token: pro)

    target = mod.resolve_target_trade_date(datetime(2026, 3, 16, 20, 0))

    assert target == date(2026, 3, 16)
    assert pro.calls
    assert pro.calls[0]["exchange"] == "SSE"


def test_schedule_window_open_respects_configured_time(monkeypatch) -> None:
    monkeypatch.setenv("CN_DAILY_SYNC_TIME", "18:30")

    assert mod._schedule_window_open(datetime(2026, 3, 16, 18, 30)) is True
    assert mod._schedule_window_open(datetime(2026, 3, 16, 17, 59)) is False


def test_build_market_data_sync_status_returns_fresh(monkeypatch) -> None:
    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 14))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 14))
    monkeypatch.setattr(
        mod,
        "_load_latest_records",
        lambda conn=None: (
            mod.SyncRunRecord(
                id=2,
                sync_key=mod.SYNC_KEY,
                asset_scope=mod.ASSET_SCOPE,
                target_trade_date=date(2026, 3, 14),
                status="success",
                started_at=datetime(2026, 3, 14, 18, 30, tzinfo=UTC),
                finished_at=datetime(2026, 3, 14, 18, 32, tzinfo=UTC),
                latest_trade_date_before=date(2026, 3, 13),
                latest_trade_date_after=date(2026, 3, 14),
                rows_upserted=128,
                summary_json={},
                error_text=None,
            ),
            mod.SyncRunRecord(
                id=2,
                sync_key=mod.SYNC_KEY,
                asset_scope=mod.ASSET_SCOPE,
                target_trade_date=date(2026, 3, 14),
                status="success",
                started_at=datetime(2026, 3, 14, 18, 30, tzinfo=UTC),
                finished_at=datetime(2026, 3, 14, 18, 32, tzinfo=UTC),
                latest_trade_date_before=date(2026, 3, 13),
                latest_trade_date_after=date(2026, 3, 14),
                rows_upserted=128,
                summary_json={},
                error_text=None,
            ),
        ),
    )

    payload = mod.build_market_data_sync_status()

    assert payload["status"] == "fresh"
    assert payload["latest_success_trade_date"] == "2026-03-14"
    assert payload["latest_display_trade_date"] == "2026-03-14"
    assert payload["lag_days"] == 0


def test_build_market_data_sync_status_returns_never_synced_with_db_fallback(monkeypatch) -> None:
    monkeypatch.delenv("CN_DAILY_SYNC_ENABLED", raising=False)
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 14))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 13))
    monkeypatch.setattr(mod, "_load_latest_records", lambda conn=None: (None, None))

    payload = mod.build_market_data_sync_status()

    assert payload["status"] == "disabled"
    assert payload["latest_success_trade_date"] is None
    assert payload["latest_available_trade_date"] == "2026-03-13"
    assert payload["latest_display_trade_date"] == "2026-03-13"
    assert payload["date_source"] == "db_max_date"


def test_build_market_data_sync_status_returns_failed_when_db_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")

    def _boom():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(mod, "ensure_sync_runs_table", _boom)

    payload = mod.build_market_data_sync_status()

    assert payload["status"] == "failed"
    assert payload["scheduler_enabled"] is True
    assert payload["latest_display_trade_date"] is None
    assert "db unavailable" in payload["message"]


def test_build_market_data_sync_status_uses_live_target_date_even_when_db_latest_is_older(monkeypatch) -> None:
    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 13))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 10))
    monkeypatch.setattr(mod, "_load_latest_records", lambda conn=None: (None, None))

    payload = mod.build_market_data_sync_status()

    assert payload["status"] == "never_synced"
    assert payload["target_trade_date"] == "2026-03-13"
    assert payload["latest_available_trade_date"] == "2026-03-10"
    assert payload["lag_days"] == 3


def test_build_market_data_sync_status_ignores_outdated_failed_run_for_current_target(monkeypatch) -> None:
    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 13))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 12))
    monkeypatch.setattr(
        mod,
        "_load_latest_records",
        lambda conn=None: (
            mod.SyncRunRecord(
                id=7,
                sync_key=mod.SYNC_KEY,
                asset_scope=mod.ASSET_SCOPE,
                target_trade_date=date(2026, 2, 13),
                status="failed",
                started_at=datetime(2026, 3, 16, 9, 4, tzinfo=UTC),
                finished_at=datetime(2026, 3, 16, 9, 4, tzinfo=UTC),
                latest_trade_date_before=date(2026, 3, 12),
                latest_trade_date_after=date(2026, 3, 12),
                rows_upserted=0,
                summary_json={},
                error_text="old failure",
            ),
            mod.SyncRunRecord(
                id=6,
                sync_key=mod.SYNC_KEY,
                asset_scope=mod.ASSET_SCOPE,
                target_trade_date=date(2026, 3, 12),
                status="success",
                started_at=datetime(2026, 3, 16, 9, 3, tzinfo=UTC),
                finished_at=datetime(2026, 3, 16, 9, 3, tzinfo=UTC),
                latest_trade_date_before=date(2026, 3, 10),
                latest_trade_date_after=date(2026, 3, 12),
                rows_upserted=10980,
                summary_json={},
                error_text=None,
            ),
        ),
    )

    payload = mod.build_market_data_sync_status()

    assert payload["status"] == "stale"
    assert payload["target_trade_date"] == "2026-03-13"
    assert payload["latest_success_trade_date"] == "2026-03-12"
    assert payload["message"] == "当前落后 1 个交易日"


def test_run_cn_daily_sync_once_can_sync_when_live_target_exceeds_db_max(monkeypatch) -> None:
    updates = []
    pit_index_calls = []
    pit_calls = []
    auto_sync_calls = []

    def _record_insert(**kwargs):
        return 1

    def _record_update(**kwargs):
        updates.append(kwargs)

    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 12))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_advisory_lock", lambda conn, sync_key: True)
    monkeypatch.setattr(mod, "_advisory_unlock", lambda conn, sync_key: None)
    monkeypatch.setattr(mod, "_load_latest_records", lambda conn=None: (None, None))
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 10))
    monkeypatch.setattr(mod, "_insert_run_record", _record_insert)
    monkeypatch.setattr(mod, "_update_run_record", _record_update)
    monkeypatch.setattr(
        mod.daily_updater,
        "run_update_to_target",
        lambda **kwargs: {
            "latest_cn_a_before": "2026-03-10",
            "latest_cn_a_after": "2026-03-12",
            "upserted_rows": 128,
        },
    )
    monkeypatch.setattr(
        mod.pit_index_updater,
        "run_update_to_target",
        lambda **kwargs: pit_index_calls.append(kwargs) or {"status": "ok", "after_max": {"000001.SH": "2026-03-12"}},
    )
    monkeypatch.setattr(
        mod.csi800_pit_refresher,
        "run_refresh",
        lambda **kwargs: pit_calls.append(kwargs) or {"status": "ok", "outputs": {"changes_csv": "csi800.csv"}},
    )
    monkeypatch.setattr(
        mod.sim_account_auto_sync_service,
        "run_auto_sync",
        lambda *args, **kwargs: auto_sync_calls.append((args, kwargs)) or {"status": "disabled", "message": "not configured"},
    )

    payload = mod.run_cn_daily_sync_once(force=True)

    assert payload["status"] == "success"
    assert payload["target_trade_date"] == "2026-03-12"
    assert pit_index_calls
    assert payload["pit_index_daily_refresh"]["status"] == "ok"
    assert pit_calls
    assert payload["csi800_pit_refresh"]["status"] == "ok"
    assert auto_sync_calls
    assert payload["sim_account_auto_sync"]["status"] == "disabled"
    assert updates
    assert updates[0]["status"] == "success"
    assert updates[0]["latest_trade_date_after"] == date(2026, 3, 12)


def test_run_cn_daily_sync_once_fails_when_pit_index_refresh_raises(monkeypatch) -> None:
    updates = []

    def _record_insert(**kwargs):
        return 1

    def _record_update(**kwargs):
        updates.append(kwargs)

    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 12))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_advisory_lock", lambda conn, sync_key: True)
    monkeypatch.setattr(mod, "_advisory_unlock", lambda conn, sync_key: None)
    monkeypatch.setattr(mod, "_load_latest_records", lambda conn=None: (None, None))
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 10))
    monkeypatch.setattr(mod, "_insert_run_record", _record_insert)
    monkeypatch.setattr(mod, "_update_run_record", _record_update)
    monkeypatch.setattr(
        mod.daily_updater,
        "run_update_to_target",
        lambda **kwargs: {
            "latest_cn_a_before": "2026-03-10",
            "latest_cn_a_after": "2026-03-12",
            "upserted_rows": 128,
        },
    )
    monkeypatch.setattr(
        mod.pit_index_updater,
        "run_update_to_target",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("pit index sync failed")),
    )

    with pytest.raises(RuntimeError, match="pit index sync failed"):
        mod.run_cn_daily_sync_once(force=True)

    assert updates
    assert updates[0]["status"] == "failed"
    assert updates[0]["error_text"] == "pit index sync failed"


def test_run_cn_daily_sync_once_keeps_success_when_auto_sync_raises(monkeypatch) -> None:
    updates = []

    def _record_insert(**kwargs):
        return 1

    def _record_update(**kwargs):
        updates.append(kwargs)

    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 12))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_advisory_lock", lambda conn, sync_key: True)
    monkeypatch.setattr(mod, "_advisory_unlock", lambda conn, sync_key: None)
    monkeypatch.setattr(mod, "_load_latest_records", lambda conn=None: (None, None))
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 10))
    monkeypatch.setattr(mod, "_insert_run_record", _record_insert)
    monkeypatch.setattr(mod, "_update_run_record", _record_update)
    monkeypatch.setattr(
        mod.daily_updater,
        "run_update_to_target",
        lambda **kwargs: {
            "latest_cn_a_before": "2026-03-10",
            "latest_cn_a_after": "2026-03-12",
            "upserted_rows": 128,
        },
    )
    monkeypatch.setattr(
        mod.pit_index_updater,
        "run_update_to_target",
        lambda **kwargs: {"status": "ok", "after_max": {"000001.SH": "2026-03-12"}},
    )
    monkeypatch.setattr(
        mod.csi800_pit_refresher,
        "run_refresh",
        lambda **kwargs: {"status": "ok", "outputs": {"changes_csv": "csi800.csv"}},
    )
    monkeypatch.setattr(
        mod.sim_account_auto_sync_service,
        "run_auto_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("auto sync crashed")),
    )

    payload = mod.run_cn_daily_sync_once(force=True)

    assert payload["status"] == "success"
    assert payload["sim_account_auto_sync"]["status"] == "failed"
    assert payload["sim_account_auto_sync"]["error"] == "auto sync crashed"
    assert updates
    assert updates[0]["status"] == "success"


def test_run_cn_daily_sync_once_treats_noop_daily_refresh_as_success_when_already_fresh(monkeypatch) -> None:
    updates = []

    def _record_insert(**kwargs):
        return 1

    def _record_update(**kwargs):
        updates.append(kwargs)

    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 16))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_advisory_lock", lambda conn, sync_key: True)
    monkeypatch.setattr(mod, "_advisory_unlock", lambda conn, sync_key: None)
    monkeypatch.setattr(mod, "_load_latest_records", lambda conn=None: (None, None))
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 16))
    monkeypatch.setattr(mod, "_insert_run_record", _record_insert)
    monkeypatch.setattr(mod, "_update_run_record", _record_update)
    monkeypatch.setattr(
        mod.daily_updater,
        "run_update_to_target",
        lambda **kwargs: {
            "status": "noop",
            "latest_cn_a_before": "2026-03-16",
            "upserted_rows": 0,
        },
    )
    monkeypatch.setattr(
        mod.pit_index_updater,
        "run_update_to_target",
        lambda **kwargs: {"status": "noop", "after_max": {"000001.SH": "2026-03-16"}},
    )
    monkeypatch.setattr(
        mod.csi800_pit_refresher,
        "run_refresh",
        lambda **kwargs: {"status": "ok", "outputs": {"changes_csv": "csi800.csv"}},
    )
    monkeypatch.setattr(
        mod.sim_account_auto_sync_service,
        "run_auto_sync",
        lambda *args, **kwargs: {"status": "disabled", "message": "not configured"},
    )

    payload = mod.run_cn_daily_sync_once(force=True)

    assert payload["status"] == "success"
    assert updates
    assert updates[0]["status"] == "success"
    assert updates[0]["latest_trade_date_after"] == date(2026, 3, 16)


def test_run_cn_daily_sync_once_fails_when_adj_factor_integrity_check_fails(monkeypatch) -> None:
    updates = []
    pit_index_calls = []
    pit_calls = []
    auto_sync_calls = []

    def _record_insert(**kwargs):
        return 1

    def _record_update(**kwargs):
        updates.append(kwargs)

    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: None)
    monkeypatch.setattr(mod, "resolve_target_trade_date", lambda now=None: date(2026, 3, 12))
    monkeypatch.setattr(mod, "_connect", lambda: _DummyConn())
    monkeypatch.setattr(mod, "_advisory_lock", lambda conn, sync_key: True)
    monkeypatch.setattr(mod, "_advisory_unlock", lambda conn, sync_key: None)
    monkeypatch.setattr(mod, "_load_latest_records", lambda conn=None: (None, None))
    monkeypatch.setattr(mod, "_latest_cn_a_trade_date", lambda conn=None: date(2026, 3, 10))
    monkeypatch.setattr(mod, "_insert_run_record", _record_insert)
    monkeypatch.setattr(mod, "_update_run_record", _record_update)
    monkeypatch.setattr(
        mod.daily_updater,
        "run_update_to_target",
        lambda **kwargs: {
            "latest_cn_a_before": "2026-03-10",
            "latest_cn_a_after": "2026-03-12",
            "upserted_rows": 128,
            "adj_factor_integrity": {
                "before_dates": ["2026-03-12"],
                "after_dates": ["2026-03-12"],
                "before_rows": 1,
                "remaining_rows": 1,
                "ok": False,
            },
        },
    )
    monkeypatch.setattr(
        mod.pit_index_updater,
        "run_update_to_target",
        lambda **kwargs: pit_index_calls.append(kwargs) or {"status": "ok", "after_max": {"000001.SH": "2026-03-12"}},
    )
    monkeypatch.setattr(
        mod.csi800_pit_refresher,
        "run_refresh",
        lambda **kwargs: pit_calls.append(kwargs) or {"status": "ok", "outputs": {"changes_csv": "csi800.csv"}},
    )
    monkeypatch.setattr(
        mod.sim_account_auto_sync_service,
        "run_auto_sync",
        lambda *args, **kwargs: auto_sync_calls.append((args, kwargs)) or {"status": "disabled", "message": "not configured"},
    )

    payload = mod.run_cn_daily_sync_once(force=True)

    assert payload["status"] == "failed"
    assert pit_index_calls
    assert pit_calls
    assert auto_sync_calls
    assert updates
    assert updates[0]["status"] == "failed"
    assert updates[0]["latest_trade_date_after"] == date(2026, 3, 12)
    assert "adj_factor integrity failed after sync" in str(updates[0]["error_text"])


def test_start_market_data_sync_scheduler_does_not_raise_when_init_fails(monkeypatch) -> None:
    class _DummyThread:
        def __init__(self, *args, **kwargs):
            self.started = False

        def start(self):
            self.started = True

        def is_alive(self):
            return self.started

        def join(self, timeout=None):
            self.started = False

    monkeypatch.setenv("CN_DAILY_SYNC_ENABLED", "true")
    monkeypatch.setattr(mod, "ensure_sync_runs_table", lambda: (_ for _ in ()).throw(RuntimeError("init failed")))
    monkeypatch.setattr(mod.threading, "Thread", _DummyThread)

    old_thread = mod._SCHEDULER_THREAD
    old_stop = mod._SCHEDULER_STOP
    mod._SCHEDULER_THREAD = None
    mod._SCHEDULER_STOP = threading.Event()
    try:
        mod.start_market_data_sync_scheduler()
        assert mod._SCHEDULER_THREAD is not None
        assert mod._SCHEDULER_THREAD.is_alive() is True
    finally:
        mod.stop_market_data_sync_scheduler()
        mod._SCHEDULER_THREAD = old_thread
        mod._SCHEDULER_STOP = old_stop
