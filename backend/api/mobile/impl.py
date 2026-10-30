from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.api.backtest_v2.routes.execution_preview import (
    BacktestV2ExecutionPreviewRequest,
    preview_backtest_v2_execution,
)
from backend.api.shared.mobile_access import (
    clear_mobile_session_cookie,
    create_mobile_session_token,
    get_mobile_session,
    mobile_auth_configured,
    require_mobile_auth_configured,
    require_mobile_session,
    set_mobile_session_cookie,
    verify_mobile_password,
)
from backend.api.shared.paths import results_root as _results_root
from backend.api.shared.json_utils import sanitize_json
from backend.core.services.mobile_dashboard_service import build_mobile_dashboard
from backend.core.services.mobile_ops_service import (
    create_ticket_from_confirmed_action,
    issue_confirm_token,
    list_approval_tickets,
    parse_confirm_token,
    revoke_ticket,
    ticket_summary,
)


class MobileLoginRequest(BaseModel):
    password: str


class MobileApprovalPrepareRequest(BaseModel):
    suggestion_id: str
    decision: str
    final_qty: int | None = None
    final_target_weight: float | None = None
    reject_reason: str | None = None


class MobileApprovalCommitRequest(BaseModel):
    confirm_token: str
    idempotency_key: str


class MobileApprovalRevokeRequest(BaseModel):
    reason: str | None = None




def _preview_execution(config_json: dict[str, Any], exp_id: str, as_of_date: str | None) -> dict[str, Any]:
    body = BacktestV2ExecutionPreviewRequest(
        config_json=config_json,
        exp_id=exp_id,
        as_of_date=as_of_date,
        top_n=10,
    )
    return preview_backtest_v2_execution(body)


def _current_mobile_dashboard() -> dict[str, Any]:
    return build_mobile_dashboard(_results_root(), preview_loader=_preview_execution)


def _find_approval_card(payload: dict[str, Any], suggestion_id: str) -> dict[str, Any] | None:
    cards = ((payload.get("guidance") or {}) if isinstance(payload, dict) else {}).get("approval_cards") or []
    for item in cards:
        if not isinstance(item, dict):
            continue
        if str(item.get("suggestion_id") or "") == str(suggestion_id or "").strip():
            return item
    return None


def _require_available_suggestion_source(payload: dict[str, Any]) -> None:
    reconcile = payload.get("reconcile") if isinstance(payload, dict) else None
    if isinstance(reconcile, dict) and reconcile.get("status") == "unavailable":
        raise HTTPException(
            status_code=503,
            detail="real holdings or reconciliation are unavailable; approval suggestions cannot be generated",
        )


def _mobile_operator(request: Request) -> str:
    host = str(request.headers.get("host") or "").strip()
    client_host = str(getattr(request.client, "host", "") or "").strip()
    parts = [part for part in [host, client_host] if part]
    return "mobile@" + "|".join(parts or ["private-host"])


def _prepare_preview(card: dict[str, Any], body: MobileApprovalPrepareRequest) -> dict[str, Any]:
    system_suggestion = card.get("system_suggestion") if isinstance(card.get("system_suggestion"), dict) else {}
    return {
        "suggestion_id": str(card.get("suggestion_id") or ""),
        "symbol": str(card.get("symbol") or ""),
        "name": str(card.get("name") or ""),
        "action_type": str(card.get("action_type") or ""),
        "source_mode": str(card.get("source_mode") or ""),
        "snapshot_id": str(card.get("snapshot_id") or ""),
        "reconcile_id": str(card.get("reconcile_id") or ""),
        "as_of_date": str(card.get("as_of_date") or card.get("signal_date") or ""),
        "decision": str(body.decision or "").strip().lower(),
        "original_qty": system_suggestion.get("suggested_qty"),
        "original_target_weight": system_suggestion.get("target_weight"),
        "current_qty": system_suggestion.get("current_qty"),
        "reference_price": system_suggestion.get("reference_price"),
        "reference_price_basis": system_suggestion.get("reference_price_basis"),
        "final_qty": body.final_qty,
        "final_target_weight": body.final_target_weight,
        "reject_reason": str(body.reject_reason or "").strip(),
        "manual_adjusted": (
            (body.final_qty is not None and body.final_qty != system_suggestion.get("suggested_qty"))
            or (
                body.final_target_weight is not None
                and body.final_target_weight != system_suggestion.get("target_weight")
            )
        ),
    }


def _validate_prepare_request(card: dict[str, Any], body: MobileApprovalPrepareRequest) -> JSONResponse | None:
    decision = str(body.decision or "").strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="decision must be approve or reject")
    if str(card.get("source_mode") or "").strip().lower() == "experiment_fallback":
        return JSONResponse({"ok": False, "detail": "experiment fallback cards are read-only"}, status_code=409)
    if str(card.get("action_type") or "") not in {"buy", "sell"}:
        return JSONResponse({"ok": False, "detail": "hold suggestion is not actionable"}, status_code=409)
    if body.final_qty is not None and int(body.final_qty) <= 0:
        raise HTTPException(status_code=422, detail="final_qty must be > 0")
    if body.final_target_weight is not None and (float(body.final_target_weight) < 0 or float(body.final_target_weight) > 1):
        raise HTTPException(status_code=422, detail="final_target_weight must be between 0 and 1")
    if decision == "reject" and not str(body.reject_reason or "").strip():
        raise HTTPException(status_code=422, detail="reject_reason is required")
    if decision == "reject" and str(((card.get("user_decision") or {}) if isinstance(card.get("user_decision"), dict) else {}).get("status") or "") == "approved_pending":
        return JSONResponse({"ok": False, "detail": "approved ticket must be revoked instead"}, status_code=409)
    if decision == "approve":
        blockers = list(card.get("blockers") or [])
        if blockers:
            return JSONResponse(
                {"ok": False, "detail": "mobile approval is blocked", "blockers": blockers},
                status_code=409,
            )
    return None


def _validate_card_version(card: dict[str, Any], token_payload: dict[str, Any]) -> None:
    checks = [
        ("source_mode", "dashboard source mode changed"),
        ("exp_id", "suggestion snapshot changed"),
        ("signal_date", "signal date changed"),
        ("snapshot_id", "holding snapshot changed"),
        ("reconcile_id", "reconcile surface changed"),
        ("as_of_date", "as_of_date changed"),
    ]
    for field_name, detail in checks:
        token_value = str(token_payload.get(field_name) or "").strip()
        card_value = str(card.get(field_name) or "").strip()
        if token_value != card_value:
            raise HTTPException(status_code=409, detail=detail)


def get_mobile_session_status(request: Request):
    session = get_mobile_session(request)
    return sanitize_json(
        {
            "authenticated": session is not None,
            "configured": mobile_auth_configured(),
            "expires_at": session.expires_at if session is not None else None,
        }
    )


def login_mobile(request: MobileLoginRequest):
    require_mobile_auth_configured()
    if not verify_mobile_password(request.password):
        return JSONResponse({"ok": False, "detail": "mobile password is invalid"}, status_code=401)

    token, session = create_mobile_session_token()
    response = JSONResponse(
        sanitize_json(
            {
                "ok": True,
                "authenticated": True,
                "expires_at": session.expires_at,
            }
        )
    )
    set_mobile_session_cookie(response, token)
    return response


def logout_mobile():
    response = JSONResponse({"ok": True, "authenticated": False})
    clear_mobile_session_cookie(response)
    return response


def get_mobile_dashboard(request: Request):
    require_mobile_session(request)
    payload = _current_mobile_dashboard()
    return sanitize_json(payload)


def prepare_mobile_approval(body: MobileApprovalPrepareRequest, request: Request):
    require_mobile_session(request)
    payload = _current_mobile_dashboard()
    card = _find_approval_card(payload, body.suggestion_id)
    if card is None:
        _require_available_suggestion_source(payload)
        raise HTTPException(status_code=404, detail="suggestion not found")
    blocked_response = _validate_prepare_request(card, body)
    if blocked_response is not None:
        return blocked_response
    preview = _prepare_preview(card, body)
    confirm_token = issue_confirm_token(
        {
            "suggestion_id": str(card.get("suggestion_id") or ""),
            "source_mode": str(card.get("source_mode") or ""),
            "exp_id": str(card.get("exp_id") or ""),
            "signal_date": str(card.get("signal_date") or ""),
            "snapshot_id": str(card.get("snapshot_id") or ""),
            "reconcile_id": str(card.get("reconcile_id") or ""),
            "as_of_date": str(card.get("as_of_date") or card.get("signal_date") or ""),
            "symbol": str(card.get("symbol") or ""),
            "action_type": str(card.get("action_type") or ""),
            "decision": preview["decision"],
            "final_qty": preview["final_qty"],
            "final_target_weight": preview["final_target_weight"],
            "reject_reason": preview["reject_reason"],
        }
    )
    return sanitize_json(
        {
            "ok": True,
            "requires_second_confirmation": True,
            "confirm_token": confirm_token,
            "preview": preview,
        }
    )


def commit_mobile_approval(body: MobileApprovalCommitRequest, request: Request):
    require_mobile_session(request)
    token_payload = parse_confirm_token(body.confirm_token)
    if token_payload is None:
        raise HTTPException(status_code=400, detail="confirm_token is invalid or expired")

    payload = _current_mobile_dashboard()
    card = _find_approval_card(payload, str(token_payload.get("suggestion_id") or ""))
    if card is None:
        _require_available_suggestion_source(payload)
        raise HTTPException(status_code=409, detail="suggestion snapshot changed")
    _validate_card_version(card, token_payload)
    if str(token_payload.get("decision") or "").strip().lower() == "approve":
        blockers = [item for item in list(card.get("blockers") or []) if str(item.get("code") or "") != "duplicate_submission"]
        if blockers:
            return JSONResponse(
                {"ok": False, "detail": "mobile approval is blocked", "blockers": blockers},
                status_code=409,
            )

    try:
        ticket, created = create_ticket_from_confirmed_action(
            _results_root(),
            card=card,
            decision=str(token_payload.get("decision") or ""),
            operator=_mobile_operator(request),
            idempotency_key=body.idempotency_key,
            confirm_payload=dict(token_payload),
        )
    except ValueError as exc:
        if str(exc) == "duplicate_submission":
            return JSONResponse({"ok": False, "detail": "duplicate_submission"}, status_code=409)
        raise HTTPException(status_code=422, detail=str(exc))

    return sanitize_json({"ok": True, "created": created, "ticket": ticket_summary(ticket)})


def get_mobile_approval_tickets(request: Request, status: str = Query("approved_pending")):
    require_mobile_session(request)
    items = list_approval_tickets(_results_root(), status=status)
    return sanitize_json({"items": items, "count": len(items), "status": status})


def revoke_mobile_approval_ticket(ticket_id: str, body: MobileApprovalRevokeRequest, request: Request):
    require_mobile_session(request)
    try:
        ticket = revoke_ticket(
            _results_root(),
            ticket_id=ticket_id,
            operator=_mobile_operator(request),
            reason=str(body.reason or "").strip(),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="ticket not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return sanitize_json({"ok": True, "ticket": ticket_summary(ticket)})
