from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.cli.managed import update_pams_ohlcv_daily as daily_updater


LOGGER = logging.getLogger(__name__)

SYNC_KEY = "cn_a_ohlcv_daily"
ASSET_SCOPE = "cn_a_equity"
DEFAULT_STATUS_TABLE = "pams_data_sync_runs"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_SCHEDULE_TIME = "18:30"
DEFAULT_POLL_SECONDS = 300
DEFAULT_RETRY_SECONDS = 3600
DEFAULT_LIVE_CALENDAR_LOOKBACK_DAYS = 60

_SCHEDULER_LOCK = threading.Lock()
_SCHEDULER_STOP = threading.Event()
_SCHEDULER_THREAD: threading.Thread | None = None
_RUN_LOCK = threading.Lock()


@dataclass(slots=True)
class SyncRunRecord:
    id: int | None
    sync_key: str
    asset_scope: str
    target_trade_date: date | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    latest_trade_date_before: date | None
    latest_trade_date_after: date | None
    rows_upserted: int | None
    summary_json: dict[str, Any]
    error_text: str | None


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}


def sync_scheduler_enabled() -> bool:
    return _env_flag("CN_DAILY_SYNC_ENABLED", default=False)


def _poll_seconds() -> int:
    raw = str(os.environ.get("CN_DAILY_SYNC_POLL_SECONDS") or "").strip()
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_POLL_SECONDS
    return max(30, value)


def _retry_seconds() -> int:
    raw = str(os.environ.get("CN_DAILY_SYNC_RETRY_SECONDS") or "").strip()
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_RETRY_SECONDS
    return max(300, value)


def _status_table() -> str:
    return str(os.environ.get("CN_DAILY_SYNC_STATUS_TABLE") or DEFAULT_STATUS_TABLE).strip() or DEFAULT_STATUS_TABLE


def _sync_timezone() -> ZoneInfo:
    raw = str(os.environ.get("CN_DAILY_SYNC_TIMEZONE") or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(raw)
    except Exception:
        LOGGER.warning("invalid CN_DAILY_SYNC_TIMEZONE=%s, fallback to %s", raw, DEFAULT_TIMEZONE)
        return ZoneInfo(DEFAULT_TIMEZONE)


def _scheduled_local_time() -> dt_time:
    raw = str(os.environ.get("CN_DAILY_SYNC_TIME") or DEFAULT_SCHEDULE_TIME).strip() or DEFAULT_SCHEDULE_TIME
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(raw)
        return dt_time(hour=hour, minute=minute)
    except Exception:
        LOGGER.warning("invalid CN_DAILY_SYNC_TIME=%s, fallback to %s", raw, DEFAULT_SCHEDULE_TIME)
        return dt_time(hour=18, minute=30)


def _schedule_window_open(now: datetime | None = None) -> bool:
    return _now_local(now).time() >= _scheduled_local_time()


def _now_local(now: datetime | None = None) -> datetime:
    tz = _sync_timezone()
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def _normalize_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _normalize_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value))
    except Exception:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _connect():
    return daily_updater._connect()


def ensure_sync_runs_table() -> None:
    table = daily_updater._safe_ident(_status_table())
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS public.{table} (
                    id BIGSERIAL PRIMARY KEY,
                    sync_key TEXT NOT NULL,
                    asset_scope TEXT NOT NULL,
                    target_trade_date DATE NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMPTZ NULL,
                    latest_trade_date_before DATE NULL,
                    latest_trade_date_after DATE NULL,
                    rows_upserted INTEGER NULL,
                    summary_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    error_text TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_sync_key_started_at ON public.{table} (sync_key, started_at DESC)"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_target_trade_date ON public.{table} (target_trade_date DESC)"
            )
        conn.commit()


def _latest_cn_a_trade_date(*, conn: Any | None = None) -> date | None:
    owns_conn = conn is None
    conn = conn or _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT MAX(trade_date)
                FROM public.{daily_updater._safe_ident(daily_updater.DEFAULT_TABLE)}
                WHERE market = 'CN_A'
                """
            )
            row = cur.fetchone()
        return _normalize_date(row[0] if row else None)
    finally:
        if owns_conn:
            conn.close()


def _advisory_lock(conn: Any, sync_key: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (sync_key,))
        row = cur.fetchone()
    return bool(row[0]) if row else False


def _advisory_unlock(conn: Any, sync_key: str) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (sync_key,))
    except Exception:
        LOGGER.exception("failed to release advisory lock for %s", sync_key)


def _is_open_flag(value: Any) -> bool:
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y"}


def _resolve_target_trade_date_from_live_calendar(cutoff_date: date) -> date | None:
    token = str(os.environ.get("TUSHARE_TOKEN") or "").strip()
    pro = daily_updater._load_tushare_client(token)
    window_start = cutoff_date - timedelta(days=DEFAULT_LIVE_CALENDAR_LOOKBACK_DAYS)
    raw = pro.trade_cal(
        exchange="SSE",
        start_date=window_start.strftime("%Y%m%d"),
        end_date=cutoff_date.strftime("%Y%m%d"),
        fields="exchange,cal_date,is_open",
    )
    if raw is None or raw.empty:
        return None
    open_days: list[date] = []
    for row in raw.itertuples(index=False):
        cal_date = _normalize_date(getattr(row, "cal_date", None))
        if cal_date is None or cal_date > cutoff_date:
            continue
        if _is_open_flag(getattr(row, "is_open", None)):
            open_days.append(cal_date)
    if not open_days:
        return None
    return max(open_days)


def resolve_target_trade_date(now: datetime | None = None) -> date | None:
    local_now = _now_local(now)
    cutoff_date = local_now.date()
    if local_now.time() < _scheduled_local_time():
        cutoff_date = cutoff_date - timedelta(days=1)
    if cutoff_date is None:
        return None
    return _resolve_target_trade_date_from_live_calendar(cutoff_date)


def _row_to_record(row: Any) -> SyncRunRecord | None:
    if row is None:
        return None
    summary_json = row.get("summary_json") if isinstance(row, dict) else None
    if isinstance(summary_json, str):
        try:
            summary_json = json.loads(summary_json)
        except Exception:
            summary_json = {}
    if not isinstance(summary_json, dict):
        summary_json = {}
    return SyncRunRecord(
        id=int(row.get("id")) if row.get("id") is not None else None,
        sync_key=str(row.get("sync_key") or SYNC_KEY),
        asset_scope=str(row.get("asset_scope") or ASSET_SCOPE),
        target_trade_date=_normalize_date(row.get("target_trade_date")),
        status=str(row.get("status") or "").strip().lower() or "unknown",
        started_at=_normalize_datetime(row.get("started_at")),
        finished_at=_normalize_datetime(row.get("finished_at")),
        latest_trade_date_before=_normalize_date(row.get("latest_trade_date_before")),
        latest_trade_date_after=_normalize_date(row.get("latest_trade_date_after")),
        rows_upserted=int(row.get("rows_upserted")) if row.get("rows_upserted") is not None else None,
        summary_json=summary_json,
        error_text=str(row.get("error_text") or "").strip() or None,
    )


def _load_latest_records(*, conn: Any | None = None) -> tuple[SyncRunRecord | None, SyncRunRecord | None]:
    table = daily_updater._safe_ident(_status_table())
    owns_conn = conn is None
    conn = conn or _connect()
    try:
        with conn.cursor(row_factory=None) as cur:
            cur.execute(
                f"""
                SELECT id, sync_key, asset_scope, target_trade_date, status, started_at, finished_at,
                       latest_trade_date_before, latest_trade_date_after, rows_upserted, summary_json, error_text
                FROM public.{table}
                WHERE sync_key = %s
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (SYNC_KEY,),
            )
            latest_cols = [desc.name for desc in cur.description] if cur.description else []
            latest_row_raw = cur.fetchone()
            latest_row = dict(zip(latest_cols, latest_row_raw)) if latest_row_raw else None

            cur.execute(
                f"""
                SELECT id, sync_key, asset_scope, target_trade_date, status, started_at, finished_at,
                       latest_trade_date_before, latest_trade_date_after, rows_upserted, summary_json, error_text
                FROM public.{table}
                WHERE sync_key = %s AND status = 'success'
                ORDER BY finished_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (SYNC_KEY,),
            )
            success_cols = [desc.name for desc in cur.description] if cur.description else []
            success_row_raw = cur.fetchone()
            success_row = dict(zip(success_cols, success_row_raw)) if success_row_raw else None
        return _row_to_record(latest_row), _row_to_record(success_row)
    finally:
        if owns_conn:
            conn.close()


def _insert_run_record(
    *,
    conn: Any,
    target_trade_date: date | None,
    status: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    latest_trade_date_before: date | None = None,
    latest_trade_date_after: date | None = None,
    rows_upserted: int | None = None,
    summary_json: dict[str, Any] | None = None,
    error_text: str | None = None,
) -> int:
    table = daily_updater._safe_ident(_status_table())
    payload = json.dumps(summary_json or {}, ensure_ascii=False)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO public.{table} (
                sync_key,
                asset_scope,
                target_trade_date,
                status,
                started_at,
                finished_at,
                latest_trade_date_before,
                latest_trade_date_after,
                rows_upserted,
                summary_json,
                error_text
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id
            """,
            (
                SYNC_KEY,
                ASSET_SCOPE,
                target_trade_date,
                str(status or "").strip().lower() or "unknown",
                started_at or datetime.now(UTC),
                finished_at,
                latest_trade_date_before,
                latest_trade_date_after,
                rows_upserted,
                payload,
                error_text,
            ),
        )
        row = cur.fetchone()
    return int(row[0]) if row else 0


def _update_run_record(
    *,
    conn: Any,
    run_id: int,
    status: str,
    finished_at: datetime | None = None,
    latest_trade_date_before: date | None = None,
    latest_trade_date_after: date | None = None,
    rows_upserted: int | None = None,
    summary_json: dict[str, Any] | None = None,
    error_text: str | None = None,
) -> None:
    table = daily_updater._safe_ident(_status_table())
    payload = json.dumps(summary_json or {}, ensure_ascii=False)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE public.{table}
            SET status = %s,
                finished_at = %s,
                latest_trade_date_before = %s,
                latest_trade_date_after = %s,
                rows_upserted = %s,
                summary_json = %s::jsonb,
                error_text = %s
            WHERE id = %s
            """,
            (
                str(status or "").strip().lower() or "unknown",
                finished_at or datetime.now(UTC),
                latest_trade_date_before,
                latest_trade_date_after,
                rows_upserted,
                payload,
                error_text,
                int(run_id),
            ),
        )


def _should_retry_failed_run(latest_run: SyncRunRecord | None, target_trade_date: date | None, now: datetime) -> bool:
    if latest_run is None or latest_run.target_trade_date != target_trade_date:
        return True
    if latest_run.status not in {"failed", "running"}:
        return True
    started_at = latest_run.started_at or latest_run.finished_at
    if started_at is None:
        return True
    return (now.astimezone(UTC) - started_at.astimezone(UTC)).total_seconds() >= _retry_seconds()


def run_cn_daily_sync_once(now: datetime | None = None, *, force: bool = False) -> dict[str, Any]:
    ensure_sync_runs_table()
    local_now = _now_local(now)
    started_at_utc = datetime.now(UTC)
    target_trade_date = resolve_target_trade_date(local_now)
    if target_trade_date is None:
        with _connect() as conn:
            _insert_run_record(
                conn=conn,
                target_trade_date=None,
                status="failed",
                started_at=started_at_utc,
                finished_at=started_at_utc,
                summary_json={},
                error_text="target_trade_date unavailable from pit_trade_cal",
            )
            conn.commit()
        return {"status": "failed", "target_trade_date": None, "message": "target_trade_date unavailable from pit_trade_cal"}

    if not _RUN_LOCK.acquire(blocking=False):
        return {"status": "running", "target_trade_date": target_trade_date.isoformat(), "message": "sync already running in process"}

    lock_conn = None
    try:
        lock_conn = _connect()
        if not _advisory_lock(lock_conn, SYNC_KEY):
            return {"status": "running", "target_trade_date": target_trade_date.isoformat(), "message": "sync already locked by another process"}

        latest_run, latest_success = _load_latest_records(conn=lock_conn)
        latest_success_date = latest_success.latest_trade_date_after if latest_success else None
        latest_available_before = _latest_cn_a_trade_date(conn=lock_conn)
        if not force and latest_success_date is not None and latest_success_date >= target_trade_date:
            if latest_run is None or latest_run.target_trade_date != target_trade_date or latest_run.status not in {"success", "skipped"}:
                _insert_run_record(
                    conn=lock_conn,
                    target_trade_date=target_trade_date,
                    status="skipped",
                    started_at=started_at_utc,
                    finished_at=started_at_utc,
                    latest_trade_date_before=latest_available_before,
                    latest_trade_date_after=latest_available_before,
                    rows_upserted=0,
                    summary_json={"reason": "already_fresh", "latest_trade_date_after": latest_success_date.isoformat()},
                )
                lock_conn.commit()
            return {
                "status": "skipped",
                "target_trade_date": target_trade_date.isoformat(),
                "latest_trade_date_after": latest_success_date.isoformat(),
                "message": "already synced to target trade date",
            }

        if not force and not _should_retry_failed_run(latest_run, target_trade_date, local_now):
            return {
                "status": latest_run.status if latest_run else "running",
                "target_trade_date": target_trade_date.isoformat(),
                "message": "recent run already attempted for current target trade date",
            }

        started_at = datetime.now(UTC)
        run_id = _insert_run_record(
            conn=lock_conn,
            target_trade_date=target_trade_date,
            status="running",
            started_at=started_at,
            latest_trade_date_before=latest_available_before,
            summary_json={"target_trade_date": target_trade_date.isoformat()},
        )
        lock_conn.commit()

        output_dir = daily_updater.DEFAULT_OUTPUT_ROOT / "cn_daily_sync" / local_now.strftime("%Y%m%dT%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            summary = daily_updater.run_update_to_target(
                end=target_trade_date.isoformat(),
                output_dir=str(output_dir),
                apply=True,
            )
        except Exception as exc:
            with _connect() as record_conn:
                _update_run_record(
                    conn=record_conn,
                    run_id=run_id,
                    status="failed",
                    finished_at=datetime.now(UTC),
                    latest_trade_date_before=latest_available_before,
                    latest_trade_date_after=_latest_cn_a_trade_date(conn=record_conn),
                    rows_upserted=0,
                    summary_json={"output_dir": str(output_dir)},
                    error_text=str(exc),
                )
                record_conn.commit()
            raise

        latest_after = _normalize_date(summary.get("latest_cn_a_after"))
        success = latest_after is not None and latest_after >= target_trade_date
        final_status = "success" if success else "failed"
        error_text = None if success else f"sync finished without reaching target trade date {target_trade_date.isoformat()}"
        with _connect() as record_conn:
            _update_run_record(
                conn=record_conn,
                run_id=run_id,
                status=final_status,
                finished_at=datetime.now(UTC),
                latest_trade_date_before=_normalize_date(summary.get("latest_cn_a_before")) or latest_available_before,
                latest_trade_date_after=latest_after,
                rows_upserted=int(summary.get("upserted_rows") or 0),
                summary_json={**summary, "output_dir": str(output_dir)},
                error_text=error_text,
            )
            record_conn.commit()
        summary["status"] = final_status
        summary["target_trade_date"] = target_trade_date.isoformat()
        return summary
    finally:
        if lock_conn is not None:
            _advisory_unlock(lock_conn, SYNC_KEY)
            lock_conn.close()
        _RUN_LOCK.release()


def _format_status_message(
    *,
    status: str,
    latest_success_trade_date: date | None,
    latest_available_trade_date: date | None,
    target_trade_date: date | None,
    lag_days: int | None,
    latest_run: SyncRunRecord | None,
) -> str:
    if status == "fresh" and latest_success_trade_date is not None:
        return f"已同步至 {latest_success_trade_date.isoformat()}"
    if status == "running":
        if target_trade_date is not None:
            return f"正在同步至 {target_trade_date.isoformat()}"
        return "正在同步市场数据"
    if status == "failed":
        if latest_run and latest_run.error_text:
            return latest_run.error_text
        return "最近一次同步失败"
    if status == "stale":
        if lag_days is not None:
            return f"当前落后 {lag_days} 个交易日"
        return "市场数据落后于目标交易日"
    if status == "disabled":
        return "定时同步未启用"
    if status == "never_synced":
        if latest_available_trade_date is not None:
            return f"尚无正式同步记录，库内最新为 {latest_available_trade_date.isoformat()}"
        return "尚无同步记录"
    return "同步状态未知"


def _serialize_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _build_status_payload(
    *,
    status: str,
    scheduler_enabled: bool,
    target_trade_date: date | None,
    latest_success_trade_date: date | None,
    latest_available_trade_date: date | None,
    lag_days: int | None,
    latest_run: SyncRunRecord | None,
    message: str,
) -> dict[str, Any]:
    latest_display_trade_date = latest_success_trade_date or latest_available_trade_date
    return {
        "sync_key": SYNC_KEY,
        "asset_scope": ASSET_SCOPE,
        "scheduler_enabled": scheduler_enabled,
        "status": status,
        "scheduled_time": _scheduled_local_time().strftime("%H:%M"),
        "timezone": str(_sync_timezone()),
        "target_trade_date": _serialize_date(target_trade_date),
        "latest_success_trade_date": _serialize_date(latest_success_trade_date),
        "latest_available_trade_date": _serialize_date(latest_available_trade_date),
        "latest_display_trade_date": _serialize_date(latest_display_trade_date),
        "date_source": "sync_runs" if latest_success_trade_date else ("db_max_date" if latest_available_trade_date else "none"),
        "lag_days": lag_days,
        "last_run_status": latest_run.status if latest_run else None,
        "last_run_started_at": _serialize_datetime(latest_run.started_at if latest_run else None),
        "last_run_finished_at": _serialize_datetime(latest_run.finished_at if latest_run else None),
        "message": message,
    }


def build_market_data_sync_status(now: datetime | None = None) -> dict[str, Any]:
    scheduler_enabled = sync_scheduler_enabled()
    try:
        ensure_sync_runs_table()
        local_now = _now_local(now)
        target_trade_date = resolve_target_trade_date(local_now)
        with _connect() as conn:
            latest_available_trade_date = _latest_cn_a_trade_date(conn=conn)
            latest_run, latest_success = _load_latest_records(conn=conn)

        latest_success_trade_date = latest_success.latest_trade_date_after if latest_success else None
        lag_anchor = latest_success_trade_date or latest_available_trade_date
        lag_days = None
        if target_trade_date is not None and lag_anchor is not None:
            lag_days = max((target_trade_date - lag_anchor).days, 0)

        latest_run_status = latest_run.status if latest_run else None
        latest_run_matches_target = (
            latest_run is not None
            and latest_run.target_trade_date is not None
            and latest_run.target_trade_date == target_trade_date
        )
        latest_run_for_message = latest_run if latest_run_matches_target else None
        if latest_run_status == "running" and latest_run and latest_run.finished_at is None and latest_run_matches_target:
            status = "running"
        elif not scheduler_enabled:
            status = "disabled"
        elif latest_success_trade_date is None:
            status = "never_synced"
        elif target_trade_date is not None and latest_success_trade_date >= target_trade_date:
            status = "fresh"
        elif latest_run_status == "failed" and latest_run_matches_target:
            status = "failed"
        else:
            status = "stale"

        return _build_status_payload(
            status=status,
            scheduler_enabled=scheduler_enabled,
            target_trade_date=target_trade_date,
            latest_success_trade_date=latest_success_trade_date,
            latest_available_trade_date=latest_available_trade_date,
            lag_days=lag_days,
            latest_run=latest_run,
            message=_format_status_message(
                status=status,
                latest_success_trade_date=latest_success_trade_date,
                latest_available_trade_date=latest_available_trade_date,
                target_trade_date=target_trade_date,
                lag_days=lag_days,
                latest_run=latest_run_for_message,
            ),
        )
    except Exception as exc:
        LOGGER.exception("failed to build market data sync status")
        return _build_status_payload(
            status="failed",
            scheduler_enabled=scheduler_enabled,
            target_trade_date=None,
            latest_success_trade_date=None,
            latest_available_trade_date=None,
            lag_days=None,
            latest_run=None,
            message=str(exc) or "market data sync status unavailable",
        )


def _scheduler_loop() -> None:
    LOGGER.info("CN daily sync scheduler started")
    while not _SCHEDULER_STOP.wait(_poll_seconds()):
        if not _schedule_window_open():
            continue
        try:
            run_cn_daily_sync_once()
        except Exception:
            LOGGER.exception("CN daily sync run failed")


def start_market_data_sync_scheduler() -> None:
    global _SCHEDULER_THREAD
    if not sync_scheduler_enabled():
        LOGGER.info("CN daily sync scheduler disabled")
        return
    with _SCHEDULER_LOCK:
        if _SCHEDULER_THREAD is not None and _SCHEDULER_THREAD.is_alive():
            return
        _SCHEDULER_STOP.clear()
        _SCHEDULER_THREAD = threading.Thread(
            target=_scheduler_loop,
            name="cn-daily-sync-scheduler",
            daemon=True,
        )
        try:
            ensure_sync_runs_table()
        except Exception:
            LOGGER.exception("failed to initialize CN daily sync status table during startup; scheduler will retry")
        _SCHEDULER_THREAD.start()


def stop_market_data_sync_scheduler() -> None:
    global _SCHEDULER_THREAD
    with _SCHEDULER_LOCK:
        if _SCHEDULER_THREAD is None:
            return
        _SCHEDULER_STOP.set()
        _SCHEDULER_THREAD.join(timeout=3.0)
        _SCHEDULER_THREAD = None


__all__ = [
    "ASSET_SCOPE",
    "DEFAULT_STATUS_TABLE",
    "SYNC_KEY",
    "build_market_data_sync_status",
    "ensure_sync_runs_table",
    "resolve_target_trade_date",
    "run_cn_daily_sync_once",
    "_schedule_window_open",
    "start_market_data_sync_scheduler",
    "stop_market_data_sync_scheduler",
    "sync_scheduler_enabled",
]
