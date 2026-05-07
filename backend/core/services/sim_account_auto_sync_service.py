from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Mapping

from backend.core.services.sim_account_reconcile_service import run_position_aware_reconcile
from backend.core.services import sim_account_domain_service as sim_account_domain
from backend.core.services.sim_account_service import (
    default_sim_account_id,
    load_latest_holdings_snapshot,
    normalize_holdings_snapshot,
    store_holdings_snapshot,
)

_STATUS_SCHEMA_VERSION = "sim_account_auto_sync_status@1"
_DEFAULT_SOURCE_TYPE = "auto_file_import"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}


def _now_ts(now_ts: int | None = None) -> int:
    return int(now_ts if now_ts is not None else time.time())


def _now_iso(now_ts: int | None = None) -> str:
    return datetime.fromtimestamp(_now_ts(now_ts), tz=UTC).replace(microsecond=0).isoformat()


def _normalize_account_id(value: str | None) -> str:
    text = str(value or "").strip().lower()
    return text or default_sim_account_id()


def _normalize_trade_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False, dir=str(path.parent)) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_path = Path(fh.name)
    os.replace(str(tmp_path), str(path))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _sim_account_root(results_root: Path, account_id: str) -> Path:
    root = results_root / "ops" / "sim_account" / _normalize_account_id(account_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _status_path(results_root: Path, account_id: str) -> Path:
    return _sim_account_root(results_root, account_id) / "auto_sync_status.json"


def _audit_log_path(results_root: Path, account_id: str) -> Path:
    return _sim_account_root(results_root, account_id) / "audit_log.jsonl"


def _configured_account_id() -> str:
    return _normalize_account_id(str(os.environ.get("SIM_ACCOUNT_AUTO_SYNC_ACCOUNT_ID") or "").strip())


def _source_path_text(source_path: str | None = None) -> str:
    return str(source_path or os.environ.get("SIM_ACCOUNT_AUTO_SYNC_SOURCE_PATH") or "").strip()


def _resolve_source_path(source_path: str | None = None) -> Path | None:
    raw = _source_path_text(source_path)
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def auto_sync_enabled(source_path: str | None = None) -> bool:
    path = _source_path_text(source_path)
    return _env_flag("SIM_ACCOUNT_AUTO_SYNC_ENABLED", default=False) and bool(path)


def _base_status(*, account_id: str, source_path: str) -> dict[str, Any]:
    return {
        "schema_version": _STATUS_SCHEMA_VERSION,
        "account_id": account_id,
        "source_path": source_path,
        "target_trade_date": "",
        "status": "idle",
        "snapshot_id": "",
        "trade_date": "",
        "reconcile_id": "",
        "synced_at": "",
        "updated_at": "",
        "message": "",
        "error": "",
    }


def _write_status(results_root: Path, account_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    base = _base_status(account_id=_normalize_account_id(account_id), source_path=str(payload.get("source_path") or ""))
    merged = {**base, **dict(payload or {})}
    merged["updated_at"] = str(merged.get("updated_at") or _now_iso())
    _atomic_write_json(_status_path(results_root, account_id), merged)
    sim_account_domain.write_sync_log_entry(
        results_root,
        account_id=_normalize_account_id(account_id),
        entry={
            "event_type": f"auto_sync_{str(merged.get('status') or 'unknown')}",
            "status": str(merged.get("status") or ""),
            "snapshot_id": str(merged.get("snapshot_id") or ""),
            "trade_date": str(merged.get("trade_date") or ""),
            "reconcile_id": str(merged.get("reconcile_id") or ""),
            "source_type": "auto_sync",
            "message": str(merged.get("message") or ""),
            "error": str(merged.get("error") or ""),
            "created_at": str(merged.get("updated_at") or _now_iso()),
        },
    )
    return merged


def get_auto_sync_status(results_root: Path, account_id: str | None = None) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(account_id or _configured_account_id())
    payload = _read_json(_status_path(results_root, normalized_account_id))
    return {**_base_status(account_id=normalized_account_id, source_path=str(payload.get("source_path") or "")), **payload}


def _status_event_payload(
    *,
    event_type: str,
    account_id: str,
    source_path: str,
    target_trade_date: str,
    status: str,
    snapshot_id: str = "",
    trade_date: str = "",
    reconcile_id: str = "",
    message: str = "",
    error: str = "",
    now_ts: int | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "account_id": account_id,
        "source_path": source_path,
        "target_trade_date": target_trade_date,
        "status": status,
        "snapshot_id": snapshot_id,
        "trade_date": trade_date,
        "reconcile_id": reconcile_id,
        "message": message,
        "error": error,
        "at": _now_iso(now_ts),
    }


def run_auto_sync(
    results_root: Path,
    *,
    target_trade_date: str | date | None,
    account_id: str | None = None,
    source_path: str | None = None,
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(account_id or _configured_account_id())
    resolved_source_path = _resolve_source_path(source_path)
    source_path_text = str(resolved_source_path) if resolved_source_path is not None else ""
    target_trade_day = _normalize_trade_date(target_trade_date)
    target_trade_date_text = target_trade_day.isoformat() if target_trade_day is not None else ""

    if not auto_sync_enabled(source_path):
        disabled_message = (
            "auto sync source path is not configured"
            if not source_path_text
            else "auto sync disabled by SIM_ACCOUNT_AUTO_SYNC_ENABLED"
        )
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "disabled",
                "message": disabled_message,
                "error": "",
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_disabled",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="disabled",
                message=str(status_payload.get("message") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    if resolved_source_path is None or not resolved_source_path.exists():
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "failed",
                "message": "auto sync source file is missing",
                "error": "source_file_missing",
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_failed",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="failed",
                message=str(status_payload.get("message") or ""),
                error=str(status_payload.get("error") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    try:
        raw_payload = json.loads(resolved_source_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "failed",
                "message": "auto sync source file is not valid json",
                "error": str(exc),
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_failed",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="failed",
                message=str(status_payload.get("message") or ""),
                error=str(status_payload.get("error") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    if not isinstance(raw_payload, Mapping):
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "failed",
                "message": "auto sync payload must be an object",
                "error": "payload_not_object",
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_failed",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="failed",
                message=str(status_payload.get("message") or ""),
                error=str(status_payload.get("error") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    candidate_payload = {
        **dict(raw_payload),
        "account_id": normalized_account_id,
        "source_type": str(raw_payload.get("source_type") or _DEFAULT_SOURCE_TYPE),
    }
    try:
        normalized_snapshot = normalize_holdings_snapshot(
            candidate_payload,
            default_account_id_value=normalized_account_id,
            now_ts=now_ts,
        )
    except ValueError as exc:
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "failed",
                "message": "auto sync payload failed validation",
                "error": str(exc),
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_failed",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="failed",
                message=str(status_payload.get("message") or ""),
                error=str(status_payload.get("error") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    snapshot_trade_day = _normalize_trade_date(normalized_snapshot.get("trade_date"))
    snapshot_trade_date_text = snapshot_trade_day.isoformat() if snapshot_trade_day is not None else ""
    if target_trade_day is not None and snapshot_trade_day is not None and snapshot_trade_day > target_trade_day:
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "failed",
                "trade_date": snapshot_trade_date_text,
                "message": "input trade date is later than market sync target date",
                "error": "future_input",
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_failed",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="failed",
                trade_date=snapshot_trade_date_text,
                message=str(status_payload.get("message") or ""),
                error=str(status_payload.get("error") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    previous_snapshot = load_latest_holdings_snapshot(results_root, normalized_account_id)
    try:
        stored_snapshot = store_holdings_snapshot(
            results_root,
            candidate_payload,
            default_account_id_value=normalized_account_id,
            now_ts=now_ts,
        )
    except ValueError as exc:
        fallback_snapshot_id = str((previous_snapshot or {}).get("snapshot_id") or "")
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "failed",
                "snapshot_id": fallback_snapshot_id,
                "message": "auto sync write failed",
                "error": str(exc),
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_failed",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="failed",
                snapshot_id=fallback_snapshot_id,
                message=str(status_payload.get("message") or ""),
                error=str(status_payload.get("error") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    stored_snapshot_id = str(stored_snapshot.get("snapshot_id") or "")
    previous_cash = float(previous_snapshot.get("cash") or 0.0) if isinstance(previous_snapshot, dict) else 0.0
    current_cash = float(stored_snapshot.get("cash") or 0.0)
    if current_cash != previous_cash:
        sim_account_domain.write_cash_ledger_entry(
            results_root,
            account_id=normalized_account_id,
            entry={
                "entry_type": "snapshot_cash_refresh",
                "amount": round(current_cash - previous_cash, 6),
                "balance_before": previous_cash,
                "balance_after": current_cash,
                "reference_id": stored_snapshot_id,
                "source_type": "auto_sync",
                "message": "auto sync refreshed cash balance",
                "created_at": str(stored_snapshot.get("synced_at") or _now_iso(now_ts)),
            },
            now_ts=now_ts,
        )
    if target_trade_day is not None and snapshot_trade_day is not None and snapshot_trade_day < target_trade_day:
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "stale_input",
                "snapshot_id": stored_snapshot_id,
                "trade_date": snapshot_trade_date_text,
                "synced_at": str(stored_snapshot.get("synced_at") or ""),
                "message": "snapshot was written but trade date lags market sync target date",
                "error": "",
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_stale_input",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="stale_input",
                snapshot_id=stored_snapshot_id,
                trade_date=snapshot_trade_date_text,
                message=str(status_payload.get("message") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    reconcile_as_of_date = target_trade_date_text or snapshot_trade_date_text
    try:
        reconcile_payload = run_position_aware_reconcile(
            results_root,
            normalized_account_id,
            strategy_as_of_date=reconcile_as_of_date or None,
            now_ts=now_ts,
        )
    except Exception as exc:
        status_payload = _write_status(
            results_root,
            normalized_account_id,
            {
                "source_path": source_path_text,
                "target_trade_date": target_trade_date_text,
                "status": "failed",
                "snapshot_id": stored_snapshot_id,
                "trade_date": snapshot_trade_date_text,
                "synced_at": str(stored_snapshot.get("synced_at") or ""),
                "message": "auto sync reconcile failed",
                "error": str(exc),
            },
        )
        _append_jsonl(
            _audit_log_path(results_root, normalized_account_id),
            _status_event_payload(
                event_type="auto_sync_failed",
                account_id=normalized_account_id,
                source_path=source_path_text,
                target_trade_date=target_trade_date_text,
                status="failed",
                snapshot_id=stored_snapshot_id,
                trade_date=snapshot_trade_date_text,
                message=str(status_payload.get("message") or ""),
                error=str(status_payload.get("error") or ""),
                now_ts=now_ts,
            ),
        )
        return status_payload

    status_payload = _write_status(
        results_root,
        normalized_account_id,
        {
            "source_path": source_path_text,
            "target_trade_date": target_trade_date_text,
            "status": "success",
            "snapshot_id": stored_snapshot_id,
            "trade_date": snapshot_trade_date_text,
            "reconcile_id": str(reconcile_payload.get("reconcile_id") or ""),
            "synced_at": str(stored_snapshot.get("synced_at") or ""),
            "message": "auto sync completed",
            "error": "",
        },
    )
    _append_jsonl(
        _audit_log_path(results_root, normalized_account_id),
        _status_event_payload(
            event_type="auto_sync_succeeded",
            account_id=normalized_account_id,
            source_path=source_path_text,
            target_trade_date=target_trade_date_text,
            status="success",
            snapshot_id=stored_snapshot_id,
            trade_date=snapshot_trade_date_text,
            reconcile_id=str(reconcile_payload.get("reconcile_id") or ""),
            message=str(status_payload.get("message") or ""),
            now_ts=now_ts,
        ),
    )
    return status_payload


__all__ = [
    "auto_sync_enabled",
    "get_auto_sync_status",
    "run_auto_sync",
]
