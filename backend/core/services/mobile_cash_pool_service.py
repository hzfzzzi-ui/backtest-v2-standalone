from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.services.sim_account_reconcile_service import (
    load_latest_reconcile_run,
    run_position_aware_reconcile,
)
from backend.core.services import sim_account_domain_service as sim_account_domain
from backend.core.services.sim_account_service import (
    default_sim_account_id,
    load_latest_holdings_snapshot,
    store_holdings_snapshot,
)

_REFRESH_LOCK = threading.Lock()
_REFRESH_WORKERS: dict[str, dict[str, Any]] = {}


def _now_ts(now_ts: int | None = None) -> int:
    return int(now_ts if now_ts is not None else time.time())


def _now_iso(now_ts: int | None = None) -> str:
    return datetime.fromtimestamp(_now_ts(now_ts), tz=UTC).replace(microsecond=0).isoformat()


def _normalize_account_id(value: str) -> str:
    text = str(value or "").strip().lower()
    return text or default_sim_account_id()


def _sim_account_root(results_root: Path, account_id: str) -> Path:
    root = results_root / "ops" / "sim_account" / _normalize_account_id(account_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _reconcile_root(results_root: Path, account_id: str) -> Path:
    root = _sim_account_root(results_root, account_id) / "reconcile"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _latest_reconcile_path(results_root: Path, account_id: str) -> Path:
    return _reconcile_root(results_root, account_id) / "latest.json"


def _reconcile_history_path(results_root: Path, account_id: str, reconcile_id: str) -> Path:
    history_root = _reconcile_root(results_root, account_id) / "history"
    history_root.mkdir(parents=True, exist_ok=True)
    return history_root / f"{reconcile_id}.json"


def _refresh_status_path(results_root: Path, account_id: str) -> Path:
    return _reconcile_root(results_root, account_id) / "refresh_status.json"


def _audit_log_path(results_root: Path, account_id: str) -> Path:
    return _sim_account_root(results_root, account_id) / "audit_log.jsonl"


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


def _patch_reconcile_surface_snapshot(
    results_root: Path,
    *,
    account_id: str,
    previous_reconcile: dict[str, Any],
    snapshot: dict[str, Any],
    amount: float,
    now_ts: int | None = None,
) -> dict[str, Any]:
    payload = dict(previous_reconcile)
    payload["snapshot_id"] = str(snapshot.get("snapshot_id") or "")
    payload["snapshot_trade_date"] = str(snapshot.get("trade_date") or "")
    payload["snapshot_synced_at"] = str(snapshot.get("synced_at") or "")
    reconcile_id = str(payload.get("reconcile_id") or "").strip()
    if reconcile_id:
        _atomic_write_json(_reconcile_history_path(results_root, account_id, reconcile_id), payload)
    _atomic_write_json(_latest_reconcile_path(results_root, account_id), payload)
    _append_jsonl(
        _audit_log_path(results_root, account_id),
        {
            "event_type": "cash_pool_deposit_reconcile_patched",
            "account_id": account_id,
            "snapshot_id": str(snapshot.get("snapshot_id") or ""),
            "reconcile_id": reconcile_id,
            "amount": round(float(amount), 6),
            "at": _now_iso(now_ts),
        },
    )
    sim_account_domain.write_reconcile_summary(results_root, payload)
    return payload


def _base_refresh_status(*, account_id: str) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "status": "idle",
        "requested_snapshot_id": "",
        "running_snapshot_id": "",
        "strategy_as_of_date": "",
        "reconcile_id": "",
        "requested_at": "",
        "started_at": "",
        "finished_at": "",
        "message": "",
        "error": "",
    }


def _resolve_strategy_as_of_date(previous_reconcile: dict[str, Any] | None, snapshot: dict[str, Any] | None) -> str:
    payload = previous_reconcile if isinstance(previous_reconcile, dict) else {}
    action_sheet = list(payload.get("action_sheet") or [])
    action_dates = sorted(
        {
            str(item.get("as_of_date") or item.get("signal_date") or "").strip()
            for item in action_sheet
            if isinstance(item, dict) and str(item.get("as_of_date") or item.get("signal_date") or "").strip()
        },
        reverse=True,
    )
    return (
        str(payload.get("as_of_date") or "").strip()
        or (action_dates[0] if action_dates else "")
        or str((snapshot or {}).get("trade_date") or "").strip()
    )


def _write_refresh_status(results_root: Path, account_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(account_id)
    status_payload = {**_base_refresh_status(account_id=normalized_account_id), **dict(payload or {})}
    _atomic_write_json(_refresh_status_path(results_root, normalized_account_id), status_payload)
    return status_payload


def get_reconcile_refresh_status(results_root: Path, account_id: str | None = None) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    payload = _read_json(_refresh_status_path(results_root, normalized_account_id))
    return {**_base_refresh_status(account_id=normalized_account_id), **payload}


def _run_refresh_worker(results_root: Path, account_id: str) -> None:
    normalized_account_id = _normalize_account_id(account_id)
    while True:
        with _REFRESH_LOCK:
            worker = _REFRESH_WORKERS.get(normalized_account_id) or {}
            requested_snapshot_id = str(worker.get("requested_snapshot_id") or "").strip()
            strategy_as_of_date = str(worker.get("strategy_as_of_date") or "").strip()
            if not requested_snapshot_id:
                _REFRESH_WORKERS.pop(normalized_account_id, None)
                return
            worker["requested_snapshot_id"] = ""
            _REFRESH_WORKERS[normalized_account_id] = worker

        running_state = _write_refresh_status(
            results_root,
            normalized_account_id,
                {
                    "status": "running",
                    "running_snapshot_id": requested_snapshot_id,
                    "requested_snapshot_id": requested_snapshot_id,
                    "strategy_as_of_date": strategy_as_of_date,
                    "started_at": _now_iso(),
                    "finished_at": "",
                    "message": "reconcile rerun is in progress",
                    "error": "",
                },
            )
        try:
            reconcile_payload = run_position_aware_reconcile(
                results_root,
                normalized_account_id,
                strategy_as_of_date=strategy_as_of_date or None,
            )
        except Exception as exc:
            _write_refresh_status(
                results_root,
                normalized_account_id,
                {
                    **running_state,
                    "status": "failed",
                    "finished_at": _now_iso(),
                    "message": "reconcile rerun failed",
                    "error": str(exc),
                },
            )
            _append_jsonl(
                _audit_log_path(results_root, normalized_account_id),
                {
                    "event_type": "cash_pool_reconcile_failed",
                    "account_id": normalized_account_id,
                    "snapshot_id": requested_snapshot_id,
                    "error": str(exc),
                    "at": _now_iso(),
                },
            )
        else:
            _write_refresh_status(
                results_root,
                normalized_account_id,
                {
                    **running_state,
                    "status": "succeeded",
                    "running_snapshot_id": str(reconcile_payload.get("snapshot_id") or requested_snapshot_id),
                    "reconcile_id": str(reconcile_payload.get("reconcile_id") or ""),
                    "finished_at": _now_iso(),
                    "message": "reconcile rerun completed",
                    "error": "",
                },
            )
            _append_jsonl(
                _audit_log_path(results_root, normalized_account_id),
                {
                    "event_type": "cash_pool_reconcile_completed",
                    "account_id": normalized_account_id,
                    "snapshot_id": str(reconcile_payload.get("snapshot_id") or requested_snapshot_id),
                    "reconcile_id": str(reconcile_payload.get("reconcile_id") or ""),
                    "at": _now_iso(),
                },
            )


def request_reconcile_refresh(
    results_root: Path,
    *,
    account_id: str | None = None,
    snapshot_id: str | None = None,
    strategy_as_of_date: str | None = None,
) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    target_snapshot_id = str(snapshot_id or "").strip()
    target_as_of_date = str(strategy_as_of_date or "").strip()
    if not target_snapshot_id:
        snapshot = load_latest_holdings_snapshot(results_root, normalized_account_id)
        target_snapshot_id = str((snapshot or {}).get("snapshot_id") or "").strip()
    if not target_snapshot_id:
        raise FileNotFoundError(f"latest holdings snapshot is missing: {normalized_account_id}")

    with _REFRESH_LOCK:
        worker = _REFRESH_WORKERS.get(normalized_account_id)
        if worker is None:
            worker = {
                "requested_snapshot_id": target_snapshot_id,
                "strategy_as_of_date": target_as_of_date,
                "thread": None,
            }
            _REFRESH_WORKERS[normalized_account_id] = worker
        else:
            worker["requested_snapshot_id"] = target_snapshot_id
            worker["strategy_as_of_date"] = target_as_of_date
        is_running = bool(worker.get("thread")) and bool(worker["thread"].is_alive())
        status = "running" if is_running else "queued"
        status_payload = _write_refresh_status(
            results_root,
            normalized_account_id,
            {
                "status": status,
                "requested_snapshot_id": target_snapshot_id,
                "strategy_as_of_date": target_as_of_date,
                "running_snapshot_id": str(get_reconcile_refresh_status(results_root, normalized_account_id).get("running_snapshot_id") or ""),
                "requested_at": _now_iso(),
                "message": "reconcile rerun requested",
                "error": "",
            },
        )
        if not is_running:
            thread = threading.Thread(
                target=_run_refresh_worker,
                args=(results_root, normalized_account_id),
                daemon=True,
                name=f"cash-pool-refresh-{normalized_account_id}",
            )
            worker["thread"] = thread
            thread.start()
    return status_payload


def deposit_cash_into_pool(
    results_root: Path,
    *,
    amount: float,
    account_id: str | None = None,
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized_account_id = _normalize_account_id(str(account_id or default_sim_account_id()))
    deposit_amount = float(amount)
    if deposit_amount <= 0:
        raise ValueError("amount must be > 0")

    previous_snapshot = load_latest_holdings_snapshot(results_root, normalized_account_id)
    if not isinstance(previous_snapshot, dict) or not previous_snapshot:
        raise FileNotFoundError(f"latest holdings snapshot is missing: {normalized_account_id}")

    previous_reconcile = load_latest_reconcile_run(results_root, normalized_account_id)
    cash_before = float(previous_snapshot.get("cash") or 0.0)
    updated_snapshot = store_holdings_snapshot(
        results_root,
        {
            "account_id": normalized_account_id,
            "trade_date": str(previous_snapshot.get("trade_date") or ""),
            "cash": round(cash_before + deposit_amount, 6),
            "positions": list(previous_snapshot.get("positions") or []),
            "source_type": "mobile_cash_deposit",
        },
        now_ts=now_ts,
    )
    sim_account_domain.write_cash_ledger_entry(
        results_root,
        account_id=normalized_account_id,
        entry={
            "entry_type": "cash_deposit",
            "amount": deposit_amount,
            "balance_before": cash_before,
            "balance_after": float(updated_snapshot.get("cash") or 0.0),
            "reference_id": str(updated_snapshot.get("snapshot_id") or ""),
            "source_type": "mobile_cash_pool",
            "message": "cash pool deposit recorded",
            "created_at": _now_iso(now_ts),
        },
        now_ts=now_ts,
    )

    mode = "snapshot_only"
    reconcile_payload: dict[str, Any] | None = None
    warning = ""
    strategy_as_of_date = _resolve_strategy_as_of_date(previous_reconcile, previous_snapshot)
    if isinstance(previous_reconcile, dict) and previous_reconcile:
        reconcile_payload = _patch_reconcile_surface_snapshot(
            results_root,
            account_id=normalized_account_id,
            previous_reconcile=previous_reconcile,
            snapshot=updated_snapshot,
            amount=deposit_amount,
            now_ts=now_ts,
        )
        mode = "patched"
        warning = "cash pool updated, reconcile rerun requested"

    refresh_status = request_reconcile_refresh(
        results_root,
        account_id=normalized_account_id,
        snapshot_id=str(updated_snapshot.get("snapshot_id") or ""),
        strategy_as_of_date=strategy_as_of_date,
    )

    _append_jsonl(
        _audit_log_path(results_root, normalized_account_id),
        {
            "event_type": "cash_pool_deposit",
            "account_id": normalized_account_id,
            "amount": round(deposit_amount, 6),
            "cash_before": round(cash_before, 6),
            "cash_after": round(float(updated_snapshot.get("cash") or 0.0), 6),
            "snapshot_id": str(updated_snapshot.get("snapshot_id") or ""),
            "reconcile_id": str((reconcile_payload or {}).get("reconcile_id") or ""),
            "mode": mode,
            "at": _now_iso(now_ts),
        },
    )

    return {
        "account_id": normalized_account_id,
        "amount": round(deposit_amount, 6),
        "cash_before": round(cash_before, 6),
        "cash_after": round(float(updated_snapshot.get("cash") or 0.0), 6),
        "snapshot_id": str(updated_snapshot.get("snapshot_id") or ""),
        "reconcile_id": str((reconcile_payload or {}).get("reconcile_id") or ""),
        "trade_date": str(updated_snapshot.get("trade_date") or ""),
        "strategy_as_of_date": strategy_as_of_date,
        "mode": mode,
        "warning": warning,
        "refresh_status": refresh_status,
    }


__all__ = [
    "deposit_cash_into_pool",
    "get_reconcile_refresh_status",
    "request_reconcile_refresh",
]
