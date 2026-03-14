from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_MOBILE_OPS_LOCK = threading.RLock()
_PENDING_STATUS = "approved_pending"
_FINAL_STATUSES = {"rejected", "revoked", "expired"}


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = str(os.getenv(name) or "").strip()
    try:
        return max(minimum, int(raw))
    except Exception:
        return int(default)


def approval_ticket_ttl_seconds() -> int:
    return _env_int("MOBILE_APPROVAL_TICKET_TTL_SECONDS", 21600, minimum=300)


def confirm_token_ttl_seconds() -> int:
    return _env_int("MOBILE_CONFIRM_TOKEN_TTL_SECONDS", 300, minimum=30)


def signal_staleness_threshold_days() -> int:
    return _env_int("MOBILE_SIGNAL_STALENESS_DAYS", 1, minimum=0)


def _now_ts(now_ts: int | None = None) -> int:
    return int(now_ts if now_ts is not None else time.time())


def _now_iso(now_ts: int | None = None) -> str:
    return datetime.fromtimestamp(_now_ts(now_ts), tz=UTC).replace(microsecond=0).isoformat()


def _mobile_secret() -> str:
    return str(os.getenv("MOBILE_AUTH_SECRET") or "").strip()


def _urlsafe_b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _urlsafe_b64decode(payload: str) -> bytes:
    padded = payload + "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_iso_ts(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
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


def _mobile_ops_root(results_root: Path) -> Path:
    root = results_root / "mobile_ops"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _approval_tickets_root(results_root: Path) -> Path:
    root = _mobile_ops_root(results_root) / "approval_tickets"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _idempotency_root(results_root: Path) -> Path:
    root = _mobile_ops_root(results_root) / "idempotency"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _audit_log_path(results_root: Path) -> Path:
    return _mobile_ops_root(results_root) / "audit_log.jsonl"


def _risk_lock_path(results_root: Path) -> Path:
    return _mobile_ops_root(results_root) / "risk_lock.json"


def _executor_status_path(results_root: Path) -> Path:
    return _mobile_ops_root(results_root) / "executor_status.json"


def build_suggestion_id(*, exp_id: str, signal_date: str, symbol: str, action_type: str) -> str:
    normalized = "|".join(
        [
            str(exp_id or "").strip(),
            str(signal_date or "").strip(),
            str(symbol or "").strip().lower(),
            str(action_type or "").strip().lower(),
        ]
    )
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"sg_{digest}"


def issue_confirm_token(payload: dict[str, Any], *, now_ts: int | None = None) -> str:
    secret = _mobile_secret()
    if not secret:
        raise ValueError("mobile auth secret is not configured")
    issued_ts = _now_ts(now_ts)
    body = {
        **payload,
        "iat": issued_ts,
        "exp": issued_ts + confirm_token_ttl_seconds(),
        "nonce": secrets.token_hex(8),
    }
    payload_b64 = _urlsafe_b64encode(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def parse_confirm_token(token: str | None, *, now_ts: int | None = None) -> dict[str, Any] | None:
    secret = _mobile_secret()
    raw = str(token or "").strip()
    if not secret or not raw or "." not in raw:
        return None
    payload_b64, signature = raw.split(".", 1)
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    issued_ts = int(payload.get("iat") or 0)
    exp_ts = int(payload.get("exp") or 0)
    now_value = _now_ts(now_ts)
    if issued_ts <= 0 or exp_ts <= issued_ts or exp_ts <= now_value:
        return None
    return payload


def ticket_summary(ticket: dict[str, Any]) -> dict[str, Any]:
    approval = ticket.get("approval") if isinstance(ticket.get("approval"), dict) else {}
    final_values = approval.get("final_values") if isinstance(approval.get("final_values"), dict) else {}
    original_values = approval.get("original_values") if isinstance(approval.get("original_values"), dict) else {}
    signal_snapshot = ticket.get("signal_snapshot") if isinstance(ticket.get("signal_snapshot"), dict) else {}
    return {
        "ticket_id": str(ticket.get("ticket_id") or ""),
        "suggestion_id": str(ticket.get("suggestion_id") or signal_snapshot.get("suggestion_id") or ""),
        "status": str(ticket.get("status") or ""),
        "updated_at": str(ticket.get("updated_at") or ticket.get("created_at") or ""),
        "created_at": str(ticket.get("created_at") or ""),
        "expires_at": str(ticket.get("expires_at") or ""),
        "symbol": str(ticket.get("symbol") or signal_snapshot.get("symbol") or "").lower(),
        "name": str(ticket.get("name") or signal_snapshot.get("name") or ""),
        "action_type": str(ticket.get("action_type") or signal_snapshot.get("action_type") or ""),
        "decision": str(approval.get("decision") or ""),
        "manual_adjusted": bool(approval.get("manual_adjusted")),
        "final_qty": final_values.get("qty"),
        "final_target_weight": final_values.get("target_weight"),
        "original_qty": original_values.get("qty"),
        "original_target_weight": original_values.get("target_weight"),
        "reject_reason": str(approval.get("reject_reason") or ""),
        "revoke_reason": str(approval.get("revoke_reason") or ""),
        "operator": str(approval.get("operator") or ""),
        "signal_date": str(signal_snapshot.get("signal_date") or ""),
    }


def _load_all_tickets_locked(results_root: Path, *, now_ts: int | None = None) -> list[dict[str, Any]]:
    ticket_root = _approval_tickets_root(results_root)
    tickets: list[dict[str, Any]] = []
    for path in sorted(ticket_root.glob("*.json")):
        ticket = _read_json(path)
        if not ticket:
            continue
        ticket["_path"] = str(path)
        tickets.append(_maybe_expire_ticket_locked(results_root, ticket, now_ts=now_ts))
    tickets.sort(key=lambda item: (str(item.get("updated_at") or item.get("created_at") or ""), str(item.get("ticket_id") or "")), reverse=True)
    return tickets


def _maybe_expire_ticket_locked(results_root: Path, ticket: dict[str, Any], *, now_ts: int | None = None) -> dict[str, Any]:
    if str(ticket.get("status") or "") != _PENDING_STATUS:
        return ticket
    exp_ts = _parse_iso_ts(ticket.get("expires_at"))
    now_value = _now_ts(now_ts)
    if exp_ts is None or exp_ts > now_value:
        return ticket
    ticket = dict(ticket)
    ticket["status"] = "expired"
    ticket["updated_at"] = _now_iso(now_value)
    _atomic_write_json(Path(str(ticket.get("_path") or _approval_tickets_root(results_root) / f"{ticket.get('ticket_id')}.json")), {k: v for k, v in ticket.items() if not str(k).startswith("_")})
    _append_jsonl(
        _audit_log_path(results_root),
        {
            "event_type": "ticket_expired",
            "ticket_id": ticket.get("ticket_id"),
            "suggestion_id": ticket.get("suggestion_id"),
            "status": "expired",
            "at": ticket["updated_at"],
        },
    )
    return ticket


def load_mobile_control_state(results_root: Path, *, now_ts: int | None = None) -> dict[str, Any]:
    with _MOBILE_OPS_LOCK:
        tickets = _load_all_tickets_locked(results_root, now_ts=now_ts)
        latest_by_suggestion: dict[str, dict[str, Any]] = {}
        active_pending_by_suggestion: dict[str, dict[str, Any]] = {}
        pending_tickets: list[dict[str, Any]] = []
        for ticket in tickets:
            summary = ticket_summary(ticket)
            suggestion_id = str(summary.get("suggestion_id") or "")
            if suggestion_id and suggestion_id not in latest_by_suggestion:
                latest_by_suggestion[suggestion_id] = summary
            if str(summary.get("status") or "") == _PENDING_STATUS and suggestion_id:
                active_pending_by_suggestion[suggestion_id] = summary
                pending_tickets.append(summary)

        risk_payload = _read_json(_risk_lock_path(results_root))
        executor_payload = _read_json(_executor_status_path(results_root))

    risk_locked = bool(
        risk_payload and (
            bool(risk_payload.get("locked"))
            or str(risk_payload.get("status") or "").strip().lower() == "locked"
        )
    )
    risk_reason = str(risk_payload.get("reason") or risk_payload.get("message") or "") if risk_payload else ""

    executor_declared = bool(executor_payload)
    executor_available = True
    executor_reason = ""
    if executor_payload:
        executor_available = bool(
            executor_payload.get("available", executor_payload.get("healthy", executor_payload.get("online", True)))
        )
        executor_reason = str(executor_payload.get("reason") or executor_payload.get("message") or "")

    return {
        "latest_by_suggestion": latest_by_suggestion,
        "active_pending_by_suggestion": active_pending_by_suggestion,
        "pending_tickets": pending_tickets,
        "risk_lock": {
            "locked": risk_locked,
            "reason": risk_reason,
        },
        "executor": {
            "declared": executor_declared,
            "available": executor_available,
            "reason": executor_reason,
        },
    }


def list_approval_tickets(results_root: Path, *, status: str | None = None, now_ts: int | None = None) -> list[dict[str, Any]]:
    wanted = str(status or "").strip().lower()
    snapshot = load_mobile_control_state(results_root, now_ts=now_ts)
    if not wanted:
        tickets = list(snapshot["pending_tickets"])
    else:
        with _MOBILE_OPS_LOCK:
            tickets = [ticket_summary(item) for item in _load_all_tickets_locked(results_root, now_ts=now_ts) if str(item.get("status") or "").lower() == wanted]
    tickets.sort(key=lambda item: (str(item.get("updated_at") or item.get("created_at") or ""), str(item.get("ticket_id") or "")), reverse=True)
    return tickets


def get_ticket_by_id(results_root: Path, ticket_id: str, *, now_ts: int | None = None) -> dict[str, Any] | None:
    normalized = str(ticket_id or "").strip()
    if not normalized:
        return None
    with _MOBILE_OPS_LOCK:
        ticket = _read_json(_approval_tickets_root(results_root) / f"{normalized}.json")
        if not ticket:
            return None
        ticket["_path"] = str(_approval_tickets_root(results_root) / f"{normalized}.json")
        return _maybe_expire_ticket_locked(results_root, ticket, now_ts=now_ts)


def create_ticket_from_confirmed_action(
    results_root: Path,
    *,
    card: dict[str, Any],
    decision: str,
    operator: str,
    idempotency_key: str,
    confirm_payload: dict[str, Any],
    now_ts: int | None = None,
) -> tuple[dict[str, Any], bool]:
    now_value = _now_ts(now_ts)
    now_iso = _now_iso(now_value)
    normalized_decision = str(decision or "").strip().lower()
    normalized_key = str(idempotency_key or "").strip()
    suggestion_id = str(card.get("suggestion_id") or "").strip()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("unsupported decision")
    if not normalized_key:
        raise ValueError("idempotency_key is required")
    if not suggestion_id:
        raise ValueError("suggestion_id is required")

    digest = hashlib.sha1(normalized_key.encode("utf-8")).hexdigest()
    mapping_path = _idempotency_root(results_root) / f"{digest}.json"

    with _MOBILE_OPS_LOCK:
        existing_mapping = _read_json(mapping_path)
        existing_ticket_id = str(existing_mapping.get("ticket_id") or "").strip()
        if existing_ticket_id:
            existing = get_ticket_by_id(results_root, existing_ticket_id, now_ts=now_value)
            if existing:
                return existing, False

        tickets = _load_all_tickets_locked(results_root, now_ts=now_value)
        if normalized_decision == "approve":
            for item in tickets:
                if str(item.get("suggestion_id") or "") != suggestion_id:
                    continue
                if str(item.get("status") or "") == _PENDING_STATUS:
                    raise ValueError("duplicate_submission")

        original = card.get("system_suggestion") if isinstance(card.get("system_suggestion"), dict) else {}
        final_qty = confirm_payload.get("final_qty")
        final_target_weight = confirm_payload.get("final_target_weight")
        original_qty = original.get("suggested_qty")
        original_target_weight = original.get("target_weight")
        manual_adjusted = False
        if final_qty is not None and final_qty != original_qty:
            manual_adjusted = True
        if final_target_weight is not None and final_target_weight != original_target_weight:
            manual_adjusted = True

        if normalized_decision == "approve":
            if final_qty is None:
                final_qty = original_qty
            if final_target_weight is None:
                final_target_weight = original_target_weight
            status = _PENDING_STATUS
            expires_at = _now_iso(now_value + approval_ticket_ttl_seconds())
        else:
            status = "rejected"
            expires_at = None

        ticket_payload = {
            "ticket_id": f"mt_{hashlib.sha1(f'{suggestion_id}|{normalized_key}|{normalized_decision}'.encode('utf-8')).hexdigest()[:16]}",
            "suggestion_id": suggestion_id,
            "status": status,
            "created_at": now_iso,
            "updated_at": now_iso,
            "expires_at": expires_at,
            "symbol": str(card.get("symbol") or "").lower(),
            "name": str(card.get("name") or ""),
            "action_type": str(card.get("action_type") or ""),
            "bucket": str(card.get("bucket") or ""),
            "signal_snapshot": {
                "suggestion_id": suggestion_id,
                "exp_id": str(card.get("exp_id") or ""),
                "signal_date": str(card.get("signal_date") or ""),
                "symbol": str(card.get("symbol") or "").lower(),
                "name": str(card.get("name") or ""),
                "action_type": str(card.get("action_type") or ""),
                "system_suggestion": original,
                "reason_tags": list(card.get("reason_tags") or []),
                "exit_tags": list(card.get("exit_tags") or []),
                "freshness": dict(card.get("freshness") or {}),
            },
            "approval": {
                "decision": normalized_decision,
                "operator": operator,
                "confirmed_at": now_iso,
                "second_confirmed": True,
                "manual_adjusted": manual_adjusted,
                "idempotency_key": normalized_key,
                "confirm_nonce": str(confirm_payload.get("nonce") or ""),
                "original_values": {
                    "qty": original_qty,
                    "target_weight": original_target_weight,
                },
                "final_values": {
                    "qty": final_qty,
                    "target_weight": final_target_weight,
                },
                "reject_reason": str(confirm_payload.get("reject_reason") or ""),
            },
            "blockers_at_submit": list(card.get("blockers") or []),
        }
        ticket_path = _approval_tickets_root(results_root) / f"{ticket_payload['ticket_id']}.json"
        _atomic_write_json(ticket_path, ticket_payload)
        _atomic_write_json(mapping_path, {"ticket_id": ticket_payload["ticket_id"]})
        _append_jsonl(
            _audit_log_path(results_root),
            {
                "event_type": "ticket_created",
                "ticket_id": ticket_payload["ticket_id"],
                "suggestion_id": suggestion_id,
                "decision": normalized_decision,
                "status": status,
                "operator": operator,
                "manual_adjusted": manual_adjusted,
                "at": now_iso,
            },
        )
        return ticket_payload, True


def revoke_ticket(
    results_root: Path,
    *,
    ticket_id: str,
    operator: str,
    reason: str,
    now_ts: int | None = None,
) -> dict[str, Any]:
    normalized = str(ticket_id or "").strip()
    if not normalized:
        raise ValueError("ticket_id is required")
    now_value = _now_ts(now_ts)
    now_iso = _now_iso(now_value)
    with _MOBILE_OPS_LOCK:
        ticket_path = _approval_tickets_root(results_root) / f"{normalized}.json"
        ticket = _read_json(ticket_path)
        if not ticket:
            raise FileNotFoundError(normalized)
        ticket["_path"] = str(ticket_path)
        ticket = _maybe_expire_ticket_locked(results_root, ticket, now_ts=now_value)
        if str(ticket.get("status") or "") != _PENDING_STATUS:
            raise ValueError("ticket_not_revocable")
        approval = ticket.get("approval") if isinstance(ticket.get("approval"), dict) else {}
        approval = dict(approval)
        approval["revoke_reason"] = str(reason or "").strip()
        approval["revoked_at"] = now_iso
        approval["revoked_by"] = operator
        ticket = {k: v for k, v in ticket.items() if not str(k).startswith("_")}
        ticket["status"] = "revoked"
        ticket["updated_at"] = now_iso
        ticket["approval"] = approval
        _atomic_write_json(ticket_path, ticket)
        _append_jsonl(
            _audit_log_path(results_root),
            {
                "event_type": "ticket_revoked",
                "ticket_id": normalized,
                "suggestion_id": ticket.get("suggestion_id"),
                "status": "revoked",
                "operator": operator,
                "reason": str(reason or "").strip(),
                "at": now_iso,
            },
        )
        return ticket
