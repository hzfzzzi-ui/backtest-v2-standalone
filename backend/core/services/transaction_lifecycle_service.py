from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from backend.core.services import ops_domain_pg

_PENDING_STATUS = "approved_pending"
_FINAL_STATUSES = {"rejected", "revoked", "expired", "filled", "cancelled"}
_ACTIVE_STATUSES = {"approved_pending", "claimed", "submitted", "partially_filled"}
_LIFECYCLE_STATUSES = _ACTIVE_STATUSES | _FINAL_STATUSES


def _execution_root(results_root: Path) -> Path:
    root = results_root / "execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _transaction_root(results_root: Path) -> Path:
    root = _execution_root(results_root) / "transactions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _record_path(results_root: Path, transaction_id: str) -> Path:
    return _transaction_root(results_root) / f"{str(transaction_id or '').strip()}.json"


def _compat_approval_tickets_root(results_root: Path) -> Path:
    return results_root / "mobile_ops" / "approval_tickets"


def _compat_execution_events_path(results_root: Path, transaction_id: str) -> Path:
    return results_root / "mobile_ops" / "execution_events" / f"{str(transaction_id or '').strip()}.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False, dir=str(path.parent)) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_path = Path(fh.name)
    os.replace(str(tmp_path), str(path))


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_reason_codes(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [value]
    out: list[str] = []
    for item in items:
        text = _normalize_text(item)
        if text and text not in out:
            out.append(text)
    return out


def _normalize_source_intent_id(ticket: dict[str, Any]) -> str:
    approval = ticket.get("approval") if isinstance(ticket.get("approval"), dict) else {}
    signal_snapshot = ticket.get("signal_snapshot") if isinstance(ticket.get("signal_snapshot"), dict) else {}
    for value in [
        ticket.get("source_intent_id"),
        approval.get("source_intent_id"),
        ticket.get("suggestion_id"),
        signal_snapshot.get("suggestion_id"),
    ]:
        text = _normalize_text(value)
        if text:
            return text
    return ""


def _normalize_approval_source(ticket: dict[str, Any]) -> str:
    approval = ticket.get("approval") if isinstance(ticket.get("approval"), dict) else {}
    for value in [
        ticket.get("approval_source"),
        approval.get("operator"),
        approval.get("approval_source"),
    ]:
        text = _normalize_text(value)
        if text:
            return text
    return ""


def _normalize_failure_reason_codes(ticket: dict[str, Any]) -> list[str]:
    approval = ticket.get("approval") if isinstance(ticket.get("approval"), dict) else {}
    execution = ticket.get("execution") if isinstance(ticket.get("execution"), dict) else {}
    out: list[str] = []
    for value in [
        ticket.get("failure_reason_codes"),
        approval.get("failure_reason_codes"),
        approval.get("reject_reason"),
        approval.get("revoke_reason"),
        execution.get("last_error_code"),
        execution.get("last_error_message"),
    ]:
        for text in _normalize_reason_codes(value):
            if text not in out:
                out.append(text)
    return out


def _normalize_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in ticket.items() if not str(k).startswith("_")}
    approval = cleaned.get("approval") if isinstance(cleaned.get("approval"), dict) else {}
    execution = cleaned.get("execution") if isinstance(cleaned.get("execution"), dict) else {}
    status = _normalize_text(cleaned.get("status"))
    lifecycle_status = status if status in _LIFECYCLE_STATUSES else _PENDING_STATUS
    return {
        **cleaned,
        "status": lifecycle_status,
        "lifecycle_status": lifecycle_status,
        "source_intent_id": _normalize_source_intent_id(cleaned),
        "approval_source": _normalize_approval_source(cleaned),
        "failure_reason_codes": _normalize_failure_reason_codes(cleaned),
        "approval_status": _normalize_text(approval.get("decision")),
        "execution_status": _normalize_text(execution.get("last_event_status") or lifecycle_status),
    }


def _collect_status_history(ticket: dict[str, Any], events: list[dict[str, Any]] | None = None) -> list[str]:
    history: list[str] = []
    for value in [
        ticket.get("status"),
        ticket.get("lifecycle_status"),
        ticket.get("execution_status"),
    ]:
        text = _normalize_text(value)
        if text and text not in history:
            history.append(text)
    for event in events or []:
        if not isinstance(event, dict):
            continue
        for value in [event.get("status"), event.get("event_type")]:
            text = _normalize_text(value)
            if text and text not in history:
                history.append(text)
    return history


def ticket_summary_from_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_ticket(ticket)
    approval = normalized.get("approval") if isinstance(normalized.get("approval"), dict) else {}
    final_values = approval.get("final_values") if isinstance(approval.get("final_values"), dict) else {}
    original_values = approval.get("original_values") if isinstance(approval.get("original_values"), dict) else {}
    signal_snapshot = normalized.get("signal_snapshot") if isinstance(normalized.get("signal_snapshot"), dict) else {}
    execution = normalized.get("execution") if isinstance(normalized.get("execution"), dict) else {}
    return {
        "ticket_id": _normalize_text(normalized.get("ticket_id")),
        "transaction_id": _normalize_text(normalized.get("ticket_id")),
        "suggestion_id": _normalize_text(normalized.get("suggestion_id") or signal_snapshot.get("suggestion_id")),
        "source_intent_id": _normalize_text(normalized.get("source_intent_id")),
        "status": _normalize_text(normalized.get("status")),
        "lifecycle_status": _normalize_text(normalized.get("lifecycle_status")),
        "status_group": "active" if _normalize_text(normalized.get("status")) in _ACTIVE_STATUSES else "final" if _normalize_text(normalized.get("status")) in _FINAL_STATUSES else "unknown",
        "updated_at": _normalize_text(normalized.get("updated_at") or normalized.get("created_at")),
        "created_at": _normalize_text(normalized.get("created_at")),
        "expires_at": _normalize_text(normalized.get("expires_at")),
        "symbol": _normalize_text(normalized.get("symbol") or signal_snapshot.get("symbol")).lower(),
        "name": _normalize_text(normalized.get("name") or signal_snapshot.get("name")),
        "action_type": _normalize_text(normalized.get("action_type") or signal_snapshot.get("action_type")),
        "side": _normalize_text(normalized.get("action_type") or signal_snapshot.get("action_type")).upper(),
        "decision": _normalize_text(approval.get("decision")),
        "approval_status": _normalize_text(normalized.get("approval_status")),
        "manual_adjusted": bool(approval.get("manual_adjusted")),
        "final_qty": final_values.get("qty"),
        "final_target_weight": final_values.get("target_weight"),
        "original_qty": original_values.get("qty"),
        "original_target_weight": original_values.get("target_weight"),
        "reject_reason": _normalize_text(approval.get("reject_reason")),
        "revoke_reason": _normalize_text(approval.get("revoke_reason")),
        "operator": _normalize_text(approval.get("operator")),
        "approval_source": _normalize_text(normalized.get("approval_source")),
        "account_id": _normalize_text(normalized.get("account_id") or signal_snapshot.get("account_id")),
        "exp_id": _normalize_text(signal_snapshot.get("exp_id")),
        "signal_date": _normalize_text(signal_snapshot.get("signal_date")),
        "source_mode": _normalize_text(signal_snapshot.get("source_mode")),
        "snapshot_id": _normalize_text(signal_snapshot.get("snapshot_id")),
        "reconcile_id": _normalize_text(signal_snapshot.get("reconcile_id")),
        "as_of_date": _normalize_text(signal_snapshot.get("as_of_date") or signal_snapshot.get("signal_date")),
        "executor_id": _normalize_text(execution.get("executor_id")),
        "claimed_at": _normalize_text(execution.get("claimed_at")),
        "submitted_at": _normalize_text(execution.get("submitted_at")),
        "completed_at": _normalize_text(execution.get("completed_at")),
        "last_event_at": _normalize_text(execution.get("last_event_at")),
        "last_event_status": _normalize_text(execution.get("last_event_status")),
        "execution_status": _normalize_text(normalized.get("execution_status")),
        "filled_qty": execution.get("filled_qty"),
        "requested_qty": final_values.get("qty"),
        "remaining_qty": execution.get("remaining_qty"),
        "avg_fill_price": execution.get("avg_fill_price"),
        "event_count": int(execution.get("event_count") or 0),
        "last_error_code": _normalize_text(execution.get("last_error_code")),
        "last_error_message": _normalize_text(execution.get("last_error_message")),
        "failure_reason_codes": list(normalized.get("failure_reason_codes") or []),
        "status_history": _collect_status_history(normalized, normalized.get("events") if isinstance(normalized.get("events"), list) else []),
    }


def _record_from_ticket(ticket: dict[str, Any], *, events: list[dict[str, Any]] | None = None, compat_source: str = "mobile_ops_file") -> dict[str, Any]:
    cleaned = _normalize_ticket(ticket)
    summary = ticket_summary_from_ticket(cleaned)
    summary["status_history"] = _collect_status_history(cleaned, events)
    return {
        "schema_version": "transaction_lifecycle_v1",
        "transaction_id": summary["transaction_id"],
        "account_id": summary["account_id"],
        "symbol": summary["symbol"],
        "side": summary["side"],
        "lifecycle_status": summary["lifecycle_status"],
        "status_group": summary["status_group"],
        "approval_status": summary["approval_status"],
        "execution_status": summary["execution_status"],
        "source_intent_id": summary["source_intent_id"],
        "approval_source": summary["approval_source"],
        "failure_reason_codes": summary["failure_reason_codes"],
        "status_history": summary["status_history"],
        "compat_source": compat_source,
        "ticket": cleaned,
        "summary": summary,
        "events": list(events or []),
    }


def preflight_transaction_schema() -> None:
    """Fail before caller-side file writes when the lifecycle table is absent."""
    try:
        with ops_domain_pg.connect() as conn:
            ops_domain_pg.ensure_tables(conn)
    except ops_domain_pg.OpsDomainDbUnavailable:
        # Preserve the existing file-backed compatibility mode for connection failures.
        return


def sync_ticket(results_root: Path, ticket: dict[str, Any], *, compat_source: str = "mobile_ops_file") -> dict[str, Any]:
    transaction_id = str(ticket.get("ticket_id") or "").strip()
    if not transaction_id:
        raise ValueError("ticket_id is required")
    existing = get_record(results_root, transaction_id) or {}
    existing_events = existing.get("events") if isinstance(existing.get("events"), list) else []
    payload = _record_from_ticket(ticket, events=[item for item in existing_events if isinstance(item, dict)], compat_source=compat_source)
    try:
        ops_domain_pg.upsert_transaction_record(results_root, payload)
    except ops_domain_pg.OpsDomainDbUnavailable:
        pass
    _atomic_write_json(_record_path(results_root, transaction_id), payload)
    return payload


def append_event(results_root: Path, ticket: dict[str, Any], event_payload: dict[str, Any], *, compat_source: str = "mobile_ops_file") -> dict[str, Any]:
    transaction_id = str(ticket.get("ticket_id") or "").strip()
    if not transaction_id:
        raise ValueError("ticket_id is required")
    record = get_record(results_root, transaction_id) or {}
    events = [item for item in (record.get("events") if isinstance(record.get("events"), list) else []) if isinstance(item, dict)]
    events.append(dict(event_payload))
    payload = _record_from_ticket(ticket, events=events, compat_source=compat_source)
    try:
        ops_domain_pg.upsert_transaction_record(results_root, payload)
    except ops_domain_pg.OpsDomainDbUnavailable:
        pass
    _atomic_write_json(_record_path(results_root, transaction_id), payload)
    return payload


def _record_from_compat(results_root: Path, transaction_id: str) -> dict[str, Any] | None:
    ticket = _read_json(_compat_approval_tickets_root(results_root) / f"{transaction_id}.json")
    if not ticket:
        return None
    events = _read_jsonl(_compat_execution_events_path(results_root, transaction_id))
    return _record_from_ticket(ticket, events=events)


def transaction_main_table_root(results_root: Path) -> Path:
    return _transaction_root(results_root)


def get_record(results_root: Path, transaction_id: str) -> dict[str, Any] | None:
    normalized = str(transaction_id or "").strip()
    if not normalized:
        return None
    try:
        record = ops_domain_pg.get_transaction_record(results_root, normalized)
    except ops_domain_pg.OpsDomainDbUnavailable:
        record = None
    if record:
        _atomic_write_json(_record_path(results_root, normalized), record)
        return record
    record = _read_json(_record_path(results_root, normalized))
    if record:
        try:
            ops_domain_pg.upsert_transaction_record(results_root, record)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
        return record
    compat_record = _record_from_compat(results_root, normalized)
    if compat_record:
        try:
            ops_domain_pg.upsert_transaction_record(results_root, compat_record)
        except ops_domain_pg.OpsDomainDbUnavailable:
            pass
        _atomic_write_json(_record_path(results_root, normalized), compat_record)
    return compat_record


def get_main_table_record(results_root: Path, transaction_id: str) -> dict[str, Any] | None:
    return get_record(results_root, transaction_id)


def list_records(results_root: Path) -> list[dict[str, Any]]:
    try:
        records = ops_domain_pg.list_transaction_records(results_root)
    except ops_domain_pg.OpsDomainDbUnavailable:
        records = []
    if records:
        return records
    root = _transaction_root(results_root)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(root.glob("*.json")):
        record = _read_json(path)
        transaction_id = str(record.get("transaction_id") or path.stem).strip()
        if not record or not transaction_id:
            continue
        seen.add(transaction_id)
        records.append(record)
    compat_root = _compat_approval_tickets_root(results_root)
    if compat_root.exists():
        for path in sorted(compat_root.glob("*.json")):
            transaction_id = path.stem.strip()
            if not transaction_id or transaction_id in seen:
                continue
            compat_record = _record_from_compat(results_root, transaction_id)
            if compat_record:
                records.append(compat_record)
    records.sort(
        key=lambda item: (
            str(((item.get("summary") or {}) if isinstance(item.get("summary"), dict) else {}).get("updated_at") or ""),
            str(item.get("transaction_id") or ""),
        ),
        reverse=True,
    )
    return records


def list_main_table_records(results_root: Path) -> list[dict[str, Any]]:
    return list_records(results_root)


def get_summary(results_root: Path, transaction_id: str) -> dict[str, Any] | None:
    record = get_record(results_root, transaction_id)
    if not record:
        return None
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    if not summary and isinstance(record.get("ticket"), dict):
        summary = ticket_summary_from_ticket(record["ticket"])
    return dict(summary)


def get_main_table_summary(results_root: Path, transaction_id: str) -> dict[str, Any] | None:
    return get_summary(results_root, transaction_id)


def list_summaries(results_root: Path, *, status: str | None = None) -> list[dict[str, Any]]:
    wanted = str(status or "").strip().lower()
    out: list[dict[str, Any]] = []
    for record in list_records(results_root):
        summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
        if not summary:
            ticket = record.get("ticket") if isinstance(record.get("ticket"), dict) else {}
            summary = ticket_summary_from_ticket(ticket)
        normalized = str(summary.get("status") or "").strip().lower()
        if wanted and normalized != wanted:
            continue
        out.append(dict(summary))
    out.sort(
        key=lambda item: (
            str(item.get("updated_at") or item.get("last_event_at") or item.get("created_at") or ""),
            str(item.get("ticket_id") or ""),
        ),
        reverse=True,
    )
    return out


def list_main_table_summaries(results_root: Path, *, status: str | None = None) -> list[dict[str, Any]]:
    return list_summaries(results_root, status=status)


def list_events(results_root: Path, transaction_id: str) -> list[dict[str, Any]]:
    record = get_record(results_root, transaction_id)
    if not record:
        return []
    return [dict(item) for item in (record.get("events") if isinstance(record.get("events"), list) else []) if isinstance(item, dict)]


def is_final_status(status: str) -> bool:
    return str(status or "").strip().lower() in _FINAL_STATUSES
