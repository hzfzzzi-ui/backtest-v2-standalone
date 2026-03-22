from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.services import mobile_ops_service as mobile_ops

_UNFINISHED_TICKET_STATUSES = {"approved_pending", "claimed", "submitted", "partially_filled"}
_EXECUTION_STARTED_STATUSES = {"claimed", "submitted", "partially_filled", "filled", "cancelled", "rejected", "expired"}


def _briefing_root(results_root: Path) -> Path:
    root = mobile_ops._mobile_ops_root(results_root) / "daily_briefings"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC).date().isoformat()
    except Exception:
        return ""


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


def _unique_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _dedupe_tickets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_ticket: dict[str, dict[str, Any]] = {}
    for item in list(items or []):
        if not isinstance(item, dict):
            continue
        ticket_id = str(item.get("ticket_id") or "").strip()
        if not ticket_id:
            continue
        previous = latest_by_ticket.get(ticket_id)
        previous_updated = str((previous or {}).get("updated_at") or (previous or {}).get("last_event_at") or "")
        current_updated = str(item.get("updated_at") or item.get("last_event_at") or "")
        if previous is None or current_updated >= previous_updated:
            latest_by_ticket[ticket_id] = dict(item)
    out = list(latest_by_ticket.values())
    out.sort(
        key=lambda item: (
            str(item.get("updated_at") or item.get("last_event_at") or item.get("created_at") or ""),
            str(item.get("ticket_id") or ""),
        ),
        reverse=True,
    )
    return out


def _ticket_status(ticket: dict[str, Any]) -> str:
    return str(ticket.get("status") or "").strip().lower()


def _ticket_date(ticket: dict[str, Any]) -> str:
    return (
        _normalize_date(ticket.get("as_of_date"))
        or _normalize_date(ticket.get("signal_date"))
        or _normalize_date(ticket.get("last_event_at"))
        or _normalize_date(ticket.get("created_at"))
    )


def _anchor_trade_date(
    *,
    experiment_summary: dict[str, Any],
    holding_sync: dict[str, Any],
    reconcile_surface: dict[str, Any],
    market_summary: dict[str, Any],
    tickets: list[dict[str, Any]],
) -> str:
    candidates = [
        reconcile_surface.get("as_of_date"),
        holding_sync.get("trade_date"),
        ((market_summary.get("summary") or {}) if isinstance(market_summary.get("summary"), dict) else {}).get("trade_date"),
        experiment_summary.get("latest_trade_date"),
    ]
    for value in candidates:
        normalized = _normalize_date(value)
        if normalized:
            return normalized
    ticket_dates = [value for value in (_ticket_date(ticket) for ticket in tickets) if value]
    return sorted(ticket_dates, reverse=True)[0] if ticket_dates else ""


def _filter_trade_day_tickets(tickets: list[dict[str, Any]], trade_date: str) -> list[dict[str, Any]]:
    if not trade_date:
        return list(tickets)
    filtered = [ticket for ticket in tickets if _ticket_date(ticket) == trade_date]
    return filtered or list(tickets)


def _suggested_action_for_status(status: str, *, error_code: str = "") -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "partially_filled":
        return "检查剩余数量是否继续执行或手动改单"
    if normalized == "expired":
        return "检查桌面执行器是否在线，并确认是否需要重新提交"
    if normalized == "rejected":
        return "检查拒单或风控原因，必要时重新确认"
    if normalized == "risk_locked":
        return "先解除风险锁，再重新评估候选动作"
    if normalized == "executor_unavailable":
        return "先恢复桌面执行器，再推进待执行单"
    if "writeback" in str(error_code or "").strip().lower():
        return "检查执行回写日志，确认事件是否落盘"
    return "请人工核查当前执行状态"


def _build_pre_open_summary(
    *,
    trade_date: str,
    guidance: dict[str, Any],
    holding_sync: dict[str, Any],
    reconcile_surface: dict[str, Any],
    market_summary: dict[str, Any],
    tickets: list[dict[str, Any]],
) -> dict[str, Any]:
    approval_cards = [item for item in list(guidance.get("approval_cards") or []) if isinstance(item, dict)]
    pending_confirmation_cards = [
        item
        for item in approval_cards
        if bool(item.get("can_confirm")) and str(item.get("action_type") or "").strip().lower() in {"buy", "sell"}
    ]
    unfinished_tickets = [ticket for ticket in tickets if _ticket_status(ticket) in _UNFINISHED_TICKET_STATUSES]
    carry_over_tickets = [
        ticket
        for ticket in unfinished_tickets
        if trade_date and _ticket_date(ticket) and _ticket_date(ticket) < trade_date
    ]

    risk_flags = reconcile_surface.get("risk_flags") if isinstance(reconcile_surface.get("risk_flags"), dict) else {}
    risks = _unique_strings(
        list(guidance.get("warnings") or [])
        + list(holding_sync.get("warnings") or [])
        + list(reconcile_surface.get("warnings") or [])
        + list(market_summary.get("warnings") or [])
        + ([str(risk_flags.get("risk_lock_reason") or "")] if risk_flags.get("risk_locked") else [])
        + ([str(risk_flags.get("executor_reason") or "")] if risk_flags.get("executor_declared") and not risk_flags.get("executor_available", True) else [])
    )

    items: list[dict[str, Any]] = []
    if pending_confirmation_cards:
        items.append(
            {
                "kind": "pending_confirmation",
                "label": "待确认动作",
                "count": len(pending_confirmation_cards),
                "symbols": [str(item.get("symbol") or "").lower() for item in pending_confirmation_cards[:5]],
            }
        )
    if unfinished_tickets:
        items.append(
            {
                "kind": "unfinished_ticket",
                "label": "未完成 ticket",
                "count": len(unfinished_tickets),
                "ticket_ids": [str(item.get("ticket_id") or "") for item in unfinished_tickets[:5]],
            }
        )
    if carry_over_tickets:
        items.append(
            {
                "kind": "carry_over_ticket",
                "label": "跨日未完成",
                "count": len(carry_over_tickets),
                "ticket_ids": [str(item.get("ticket_id") or "") for item in carry_over_tickets[:5]],
            }
        )
    if risks:
        items.append(
            {
                "kind": "risk_notice",
                "label": "主要风险提示",
                "count": len(risks[:5]),
                "messages": risks[:5],
            }
        )

    if pending_confirmation_cards or unfinished_tickets:
        message = f"待确认 {len(pending_confirmation_cards)} 笔，未完成 {len(unfinished_tickets)} 笔"
        status = "action_required"
    elif risks:
        message = "当前无新增待确认动作，但存在风险提示"
        status = "watch"
    else:
        message = "无新增待确认动作"
        status = "clear"

    return {
        "status": status,
        "trade_date": trade_date,
        "pending_confirmation_count": len(pending_confirmation_cards),
        "unfinished_ticket_count": len(unfinished_tickets),
        "carry_over_ticket_count": len(carry_over_tickets),
        "freshness_status": str((guidance.get("freshness") or {}).get("status") or ""),
        "primary_risks": risks[:5],
        "items": items,
        "message": message,
    }


def _build_execution_anomaly_summary(
    *,
    tickets: list[dict[str, Any]],
    reconcile_surface: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for ticket in tickets:
        status = _ticket_status(ticket)
        error_code = str(ticket.get("last_error_code") or "").strip()
        error_message = str(ticket.get("last_error_message") or "").strip()
        anomaly_type = ""
        if status in {"rejected", "expired", "partially_filled"}:
            anomaly_type = status
        elif error_code or error_message:
            anomaly_type = "writeback_failure" if "writeback" in error_code.lower() else "execution_error"
        if not anomaly_type:
            continue
        key = (str(ticket.get("ticket_id") or ""), anomaly_type)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "ticket_id": str(ticket.get("ticket_id") or ""),
                "symbol": str(ticket.get("symbol") or "").lower(),
                "status": status,
                "anomaly_type": anomaly_type,
                "message": error_message or error_code or status,
                "suggested_action": _suggested_action_for_status(status, error_code=error_code),
            }
        )

    risk_flags = reconcile_surface.get("risk_flags") if isinstance(reconcile_surface.get("risk_flags"), dict) else {}
    if bool(risk_flags.get("risk_locked")):
        items.append(
            {
                "ticket_id": "",
                "symbol": "",
                "status": "risk_locked",
                "anomaly_type": "risk_locked",
                "message": str(risk_flags.get("risk_lock_reason") or "当前风控已锁定交易"),
                "suggested_action": _suggested_action_for_status("risk_locked"),
            }
        )
    if bool(risk_flags.get("executor_declared")) and not bool(risk_flags.get("executor_available", True)):
        items.append(
            {
                "ticket_id": "",
                "symbol": "",
                "status": "executor_unavailable",
                "anomaly_type": "executor_unavailable",
                "message": str(risk_flags.get("executor_reason") or "桌面执行器不可用"),
                "suggested_action": _suggested_action_for_status("executor_unavailable"),
            }
        )

    return {
        "status": "attention" if items else "clear",
        "count": len(items),
        "items": items[:10],
    }


def _build_post_close_summary(
    *,
    trade_date: str,
    tickets: list[dict[str, Any]],
) -> dict[str, Any]:
    activity_tickets = _filter_trade_day_tickets(tickets, trade_date)
    if not activity_tickets:
        return {
            "status": "empty",
            "trade_date": trade_date,
            "confirmed_count": 0,
            "executed_count": 0,
            "unfinished_count": 0,
            "holding_change_count": 0,
            "source_exp_ids": [],
            "major_slippages": [],
            "holding_changes": [],
            "message": "当日无移动端交易操作",
        }

    executed_tickets = [ticket for ticket in activity_tickets if _ticket_status(ticket) in _EXECUTION_STARTED_STATUSES or int(ticket.get("event_count") or 0) > 0]
    unfinished_tickets = [ticket for ticket in activity_tickets if _ticket_status(ticket) in _UNFINISHED_TICKET_STATUSES]

    slippages: list[dict[str, Any]] = []
    holding_changes: list[dict[str, Any]] = []
    for ticket in activity_tickets:
        final_qty = _safe_int(ticket.get("final_qty"))
        filled_qty = _safe_int(ticket.get("filled_qty")) or 0
        variance_qty = None
        if final_qty is not None:
            variance_qty = final_qty - filled_qty
            if variance_qty != 0 or _ticket_status(ticket) in {"rejected", "expired", "cancelled"}:
                slippages.append(
                    {
                        "ticket_id": str(ticket.get("ticket_id") or ""),
                        "symbol": str(ticket.get("symbol") or "").lower(),
                        "action_type": str(ticket.get("action_type") or ""),
                        "status": _ticket_status(ticket),
                        "requested_qty": final_qty,
                        "filled_qty": filled_qty,
                        "variance_qty": variance_qty,
                        "avg_fill_price": ticket.get("avg_fill_price"),
                        "message": str(ticket.get("last_error_message") or ticket.get("last_error_code") or ""),
                    }
                )
        if filled_qty > 0 and str(ticket.get("action_type") or "").strip().lower() in {"buy", "sell"}:
            holding_changes.append(
                {
                    "ticket_id": str(ticket.get("ticket_id") or ""),
                    "symbol": str(ticket.get("symbol") or "").lower(),
                    "action_type": str(ticket.get("action_type") or ""),
                    "filled_qty": filled_qty,
                    "status": _ticket_status(ticket),
                }
            )

    slippages.sort(key=lambda item: abs(int(item.get("variance_qty") or 0)), reverse=True)
    source_exp_ids = _unique_strings([ticket.get("exp_id") for ticket in activity_tickets])

    return {
        "status": "has_activity",
        "trade_date": trade_date,
        "confirmed_count": len(activity_tickets),
        "executed_count": len(executed_tickets),
        "unfinished_count": len(unfinished_tickets),
        "holding_change_count": len(holding_changes),
        "source_exp_ids": source_exp_ids,
        "major_slippages": slippages[:5],
        "holding_changes": holding_changes[:5],
        "message": f"已确认 {len(activity_tickets)} 笔，已进入执行 {len(executed_tickets)} 笔，未完成 {len(unfinished_tickets)} 笔",
    }


def build_mobile_daily_briefing(
    results_root: Path,
    *,
    experiment_summary: dict[str, Any] | None,
    guidance: dict[str, Any] | None,
    holding_sync: dict[str, Any] | None,
    reconcile_surface: dict[str, Any] | None,
    market_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    experiment = dict(experiment_summary or {})
    guidance_payload = dict(guidance or {})
    holding = dict(holding_sync or {})
    reconcile = dict(reconcile_surface or {})
    market = dict(market_summary or {})

    tickets = _dedupe_tickets(
        list(guidance_payload.get("pending_tickets") or []) + list(guidance_payload.get("execution_tickets") or [])
    )
    trade_date = _anchor_trade_date(
        experiment_summary=experiment,
        holding_sync=holding,
        reconcile_surface=reconcile,
        market_summary=market,
        tickets=tickets,
    )
    payload = {
        "schema_version": "mobile_daily_briefing@1",
        "generated_at": mobile_ops._now_iso(),
        "trade_date": trade_date,
        "pre_open": _build_pre_open_summary(
            trade_date=trade_date,
            guidance=guidance_payload,
            holding_sync=holding,
            reconcile_surface=reconcile,
            market_summary=market,
            tickets=tickets,
        ),
        "execution_anomalies": _build_execution_anomaly_summary(
            tickets=tickets,
            reconcile_surface=reconcile,
        ),
        "post_close": _build_post_close_summary(
            trade_date=trade_date,
            tickets=tickets,
        ),
    }

    root = _briefing_root(results_root)
    mobile_ops._atomic_write_json(root / "latest.json", payload)
    history_name = trade_date or _normalize_date(payload.get("generated_at")) or "latest"
    mobile_ops._atomic_write_json(root / "history" / f"{history_name}.json", payload)
    return payload
