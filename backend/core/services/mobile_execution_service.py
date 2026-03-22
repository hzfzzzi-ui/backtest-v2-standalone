from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.core.services import mobile_ops_service as mobile_ops

_CLAIMABLE_STATUS = "approved_pending"
_ACTIVE_EXECUTION_STATUSES = {"claimed", "submitted", "partially_filled"}
_FINAL_EXECUTION_STATUSES = {"filled", "cancelled", "rejected", "expired"}
_ALLOWED_TRANSITIONS = {
    "approved_pending": {"claimed"},
    "claimed": {"submitted", "partially_filled", "filled", "cancelled", "rejected", "expired"},
    "submitted": {"partially_filled", "filled", "cancelled", "rejected", "expired"},
    "partially_filled": {"partially_filled", "filled", "cancelled", "rejected", "expired"},
}


def execution_active_ttl_seconds() -> int:
    return mobile_ops._env_int("MOBILE_EXECUTION_ACTIVE_TICKET_TTL_SECONDS", 21600, minimum=300)


def _execution_events_root(results_root: Path) -> Path:
    root = mobile_ops._mobile_ops_root(results_root) / "execution_events"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _execution_events_path(results_root: Path, ticket_id: str) -> Path:
    return _execution_events_root(results_root) / f"{ticket_id}.jsonl"


def _read_execution_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _ticket_path(results_root: Path, ticket_id: str) -> Path:
    return mobile_ops._approval_tickets_root(results_root) / f"{ticket_id}.json"


def _clean_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in ticket.items() if not str(key).startswith("_")}


def _ticket_target_qty(ticket: dict[str, Any]) -> int | None:
    approval = ticket.get("approval") if isinstance(ticket.get("approval"), dict) else {}
    final_values = approval.get("final_values") if isinstance(approval.get("final_values"), dict) else {}
    value = final_values.get("qty")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _execution_state(ticket: dict[str, Any]) -> dict[str, Any]:
    payload = ticket.get("execution") if isinstance(ticket.get("execution"), dict) else {}
    return dict(payload)


def _build_event_payload(
    *,
    ticket: dict[str, Any],
    status: str,
    executor_id: str,
    at: str,
    filled_qty: int | None = None,
    avg_fill_price: float | None = None,
    message: str = "",
    error_code: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = "|".join(
        [
            str(ticket.get("ticket_id") or ""),
            status,
            executor_id,
            at,
            str(filled_qty if filled_qty is not None else ""),
            str(avg_fill_price if avg_fill_price is not None else ""),
            error_code,
        ]
    )
    payload = {
        "event_id": f"ev_{hashlib.sha1(base.encode('utf-8')).hexdigest()[:16]}",
        "ticket_id": str(ticket.get("ticket_id") or ""),
        "suggestion_id": str(ticket.get("suggestion_id") or ""),
        "symbol": str(ticket.get("symbol") or ""),
        "action_type": str(ticket.get("action_type") or ""),
        "status": status,
        "event_type": status,
        "executor_id": executor_id,
        "filled_qty": filled_qty,
        "avg_fill_price": avg_fill_price,
        "error_code": error_code,
        "message": message,
        "at": at,
    }
    if metadata:
        payload["metadata"] = dict(metadata)
    return payload


def _append_execution_event_locked(results_root: Path, event_payload: dict[str, Any]) -> None:
    mobile_ops._append_jsonl(_execution_events_path(results_root, str(event_payload.get("ticket_id") or "")), event_payload)
    mobile_ops._append_jsonl(
        mobile_ops._audit_log_path(results_root),
        {
            "event_type": "execution_event",
            "ticket_id": event_payload.get("ticket_id"),
            "suggestion_id": event_payload.get("suggestion_id"),
            "status": event_payload.get("status"),
            "executor_id": event_payload.get("executor_id"),
            "filled_qty": event_payload.get("filled_qty"),
            "avg_fill_price": event_payload.get("avg_fill_price"),
            "error_code": event_payload.get("error_code"),
            "message": event_payload.get("message"),
            "at": event_payload.get("at"),
        },
    )


def _apply_status_transition_locked(
    results_root: Path,
    ticket: dict[str, Any],
    *,
    new_status: str,
    executor_id: str,
    now_ts: int | None = None,
    filled_qty: int | None = None,
    avg_fill_price: float | None = None,
    message: str = "",
    error_code: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_status = str(ticket.get("status") or "").strip().lower()
    normalized_status = str(new_status or "").strip().lower()
    if normalized_status not in _ACTIVE_EXECUTION_STATUSES | _FINAL_EXECUTION_STATUSES:
        raise ValueError("unsupported_execution_status")
    allowed = _ALLOWED_TRANSITIONS.get(current_status, set())
    if normalized_status not in allowed:
        raise ValueError("invalid_execution_transition")

    target_qty = _ticket_target_qty(ticket)
    normalized_filled_qty = filled_qty
    if normalized_status in {"partially_filled", "filled"}:
        if normalized_filled_qty is None:
            raise ValueError("filled_qty_required")
        normalized_filled_qty = int(normalized_filled_qty)
        if normalized_filled_qty < 0:
            raise ValueError("filled_qty_invalid")
        if target_qty is not None and normalized_filled_qty >= target_qty:
            normalized_status = "filled"
        elif normalized_status == "filled" and target_qty is not None and normalized_filled_qty < target_qty:
            raise ValueError("filled_qty_incomplete")
        elif normalized_status == "partially_filled" and normalized_filled_qty <= 0:
            raise ValueError("filled_qty_invalid")

    now_iso = mobile_ops._now_iso(now_ts)
    execution = _execution_state(ticket)
    previous_filled_qty = execution.get("filled_qty")
    if previous_filled_qty not in (None, ""):
        try:
            previous_filled_qty = int(previous_filled_qty)
        except Exception:
            previous_filled_qty = None
    if normalized_status == "partially_filled" and previous_filled_qty is not None and normalized_filled_qty is not None and normalized_filled_qty < previous_filled_qty:
        raise ValueError("filled_qty_regression")
    if normalized_status == "filled" and previous_filled_qty is not None and normalized_filled_qty is not None and normalized_filled_qty < previous_filled_qty:
        raise ValueError("filled_qty_regression")

    ticket_payload = _clean_ticket(ticket)
    execution = {
        **execution,
        "executor_id": executor_id or str(execution.get("executor_id") or ""),
        "last_event_at": now_iso,
        "last_event_status": normalized_status,
        "last_error_code": str(error_code or ""),
        "last_error_message": str(message or ""),
        "event_count": int(execution.get("event_count") or 0) + 1,
    }
    if normalized_status == "claimed":
        execution["claimed_at"] = execution.get("claimed_at") or now_iso
    if normalized_status == "submitted":
        execution["submitted_at"] = execution.get("submitted_at") or now_iso
    if normalized_status in {"partially_filled", "filled"}:
        execution["submitted_at"] = execution.get("submitted_at") or now_iso
        execution["filled_qty"] = normalized_filled_qty
        execution["avg_fill_price"] = avg_fill_price
        execution["remaining_qty"] = (target_qty - normalized_filled_qty) if (target_qty is not None and normalized_filled_qty is not None) else None
    if normalized_status in _FINAL_EXECUTION_STATUSES:
        execution["completed_at"] = now_iso
        if normalized_status in {"cancelled", "rejected", "expired"}:
            execution["remaining_qty"] = execution.get("remaining_qty") if execution.get("remaining_qty") is not None else target_qty
    if normalized_status == "filled" and execution.get("remaining_qty") not in (None, ""):
        execution["remaining_qty"] = 0

    ticket_payload["status"] = normalized_status
    ticket_payload["updated_at"] = now_iso
    ticket_payload["execution"] = execution
    mobile_ops._atomic_write_json(_ticket_path(results_root, str(ticket_payload.get("ticket_id") or "")), ticket_payload)

    event_payload = _build_event_payload(
        ticket=ticket_payload,
        status=normalized_status,
        executor_id=str(execution.get("executor_id") or executor_id or ""),
        at=now_iso,
        filled_qty=normalized_filled_qty if normalized_status in {"partially_filled", "filled"} else None,
        avg_fill_price=avg_fill_price if normalized_status in {"partially_filled", "filled"} else None,
        message=str(message or ""),
        error_code=str(error_code or ""),
        metadata=metadata,
    )
    _append_execution_event_locked(results_root, event_payload)
    return ticket_payload


def _maybe_timeout_execution_ticket_locked(results_root: Path, ticket: dict[str, Any], *, now_ts: int | None = None) -> dict[str, Any]:
    status = str(ticket.get("status") or "").strip().lower()
    if status not in _ACTIVE_EXECUTION_STATUSES:
        return ticket
    updated_ts = mobile_ops._parse_iso_ts(ticket.get("updated_at")) or mobile_ops._parse_iso_ts(ticket.get("created_at"))
    now_value = mobile_ops._now_ts(now_ts)
    if updated_ts is None or updated_ts + execution_active_ttl_seconds() > now_value:
        return ticket
    executor_id = str((_execution_state(ticket).get("executor_id")) or "")
    return _apply_status_transition_locked(
        results_root,
        ticket,
        new_status="expired",
        executor_id=executor_id,
        now_ts=now_value,
        message="execution timeout",
        error_code="execution_timeout",
    )


def _load_ticket_locked(results_root: Path, ticket_id: str, *, now_ts: int | None = None) -> dict[str, Any]:
    normalized = str(ticket_id or "").strip()
    if not normalized:
        raise ValueError("ticket_id is required")
    ticket = mobile_ops._read_json(_ticket_path(results_root, normalized))
    if not ticket:
        raise FileNotFoundError(normalized)
    ticket["_path"] = str(_ticket_path(results_root, normalized))
    ticket = mobile_ops._maybe_expire_ticket_locked(results_root, ticket, now_ts=now_ts)
    return _maybe_timeout_execution_ticket_locked(results_root, ticket, now_ts=now_ts)


def list_execution_events(results_root: Path, ticket_id: str) -> list[dict[str, Any]]:
    normalized = str(ticket_id or "").strip()
    if not normalized:
        return []
    return _read_execution_events(_execution_events_path(results_root, normalized))


def execution_ticket_summary(results_root: Path, ticket: dict[str, Any]) -> dict[str, Any]:
    summary = mobile_ops.ticket_summary(ticket)
    events = list_execution_events(results_root, str(summary.get("ticket_id") or ""))
    summary["recent_events"] = events[-5:]
    return summary


def list_executable_tickets(results_root: Path, *, limit: int = 20, now_ts: int | None = None) -> list[dict[str, Any]]:
    with mobile_ops._MOBILE_OPS_LOCK:
        tickets = [
            _maybe_timeout_execution_ticket_locked(results_root, item, now_ts=now_ts)
            for item in mobile_ops._load_all_tickets_locked(results_root, now_ts=now_ts)
            if str(item.get("status") or "").strip().lower() == _CLAIMABLE_STATUS
        ]
    return [execution_ticket_summary(results_root, item) for item in tickets[: max(1, int(limit))]]


def list_execution_tickets(results_root: Path, *, limit: int = 50, now_ts: int | None = None) -> list[dict[str, Any]]:
    with mobile_ops._MOBILE_OPS_LOCK:
        tickets = [
            _maybe_timeout_execution_ticket_locked(results_root, item, now_ts=now_ts)
            for item in mobile_ops._load_all_tickets_locked(results_root, now_ts=now_ts)
        ]
    summaries = [execution_ticket_summary(results_root, item) for item in tickets]
    summaries.sort(
        key=lambda item: (
            str(item.get("updated_at") or item.get("created_at") or ""),
            str(item.get("ticket_id") or ""),
        ),
        reverse=True,
    )
    return summaries[: max(1, int(limit))]


def claim_approval_ticket(
    results_root: Path,
    *,
    ticket_id: str,
    executor_id: str,
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized_executor = str(executor_id or "").strip()
    if not normalized_executor:
        raise ValueError("executor_id is required")
    with mobile_ops._MOBILE_OPS_LOCK:
        ticket = _load_ticket_locked(results_root, ticket_id, now_ts=now_ts)
        if str(ticket.get("status") or "").strip().lower() != _CLAIMABLE_STATUS:
            raise ValueError("ticket_not_claimable")
        ticket = _apply_status_transition_locked(
            results_root,
            ticket,
            new_status="claimed",
            executor_id=normalized_executor,
            now_ts=now_ts,
        )
    return execution_ticket_summary(results_root, ticket)


def record_execution_update(
    results_root: Path,
    *,
    ticket_id: str,
    status: str,
    executor_id: str,
    filled_qty: int | None = None,
    avg_fill_price: float | None = None,
    message: str = "",
    error_code: str = "",
    metadata: dict[str, Any] | None = None,
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized_executor = str(executor_id or "").strip()
    if not normalized_executor:
        raise ValueError("executor_id is required")
    with mobile_ops._MOBILE_OPS_LOCK:
        ticket = _load_ticket_locked(results_root, ticket_id, now_ts=now_ts)
        execution = _execution_state(ticket)
        claimed_by = str(execution.get("executor_id") or "")
        if claimed_by and claimed_by != normalized_executor:
            raise ValueError("executor_mismatch")
        if not claimed_by and str(ticket.get("status") or "").strip().lower() != "claimed":
            raise ValueError("ticket_not_claimed")
        ticket = _apply_status_transition_locked(
            results_root,
            ticket,
            new_status=status,
            executor_id=normalized_executor,
            now_ts=now_ts,
            filled_qty=filled_qty,
            avg_fill_price=avg_fill_price,
            message=message,
            error_code=error_code,
            metadata=metadata,
        )
    return execution_ticket_summary(results_root, ticket)
