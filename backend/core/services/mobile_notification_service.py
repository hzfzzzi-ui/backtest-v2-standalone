from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.core.services import mobile_ops_service as mobile_ops


def _notification_root(results_root: Path) -> Path:
    root = mobile_ops._mobile_ops_root(results_root) / "notifications"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _preferred_channel() -> str:
    return str(os.getenv("MOBILE_PRIVATE_NOTIFICATION_CHANNEL") or "in_app_feed").strip().lower() or "in_app_feed"


def _normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        out.append(item)
    return out


def build_mobile_notification_feed(
    results_root: Path,
    *,
    briefing: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(briefing or {})
    pre_open = payload.get("pre_open") if isinstance(payload.get("pre_open"), dict) else {}
    anomalies = payload.get("execution_anomalies") if isinstance(payload.get("execution_anomalies"), dict) else {}
    post_close = payload.get("post_close") if isinstance(payload.get("post_close"), dict) else {}

    preferred_channel = _preferred_channel()
    active_channel = "in_app_feed"
    downgraded = preferred_channel != active_channel
    downgrade_reason = "channel_not_available" if downgraded else ""

    items: list[dict[str, Any]] = []
    if int(pre_open.get("pending_confirmation_count") or 0) > 0 or int(pre_open.get("unfinished_ticket_count") or 0) > 0:
        items.append(
            {
                "id": f"pre_open:{pre_open.get('trade_date') or ''}",
                "type": "pre_open_todo",
                "severity": "info" if int(pre_open.get("unfinished_ticket_count") or 0) == 0 else "warning",
                "title": "开盘前待办",
                "message": str(pre_open.get("message") or ""),
                "action": "打开首页查看待办摘要",
            }
        )
    for item in list(anomalies.get("items") or [])[:5]:
        items.append(
            {
                "id": f"anomaly:{item.get('ticket_id') or item.get('status') or item.get('symbol') or ''}",
                "type": "execution_anomaly",
                "severity": "warning",
                "title": f"执行异常 · {str(item.get('symbol') or item.get('status') or '--')}",
                "message": str(item.get("message") or item.get("suggested_action") or ""),
                "action": str(item.get("suggested_action") or "打开交易页查看异常"),
            }
        )
    if str(post_close.get("status") or "") == "has_activity":
        items.append(
            {
                "id": f"post_close:{post_close.get('trade_date') or ''}",
                "type": "post_close_recap",
                "severity": "info",
                "title": "收盘后复盘",
                "message": str(post_close.get("message") or ""),
                "action": "打开首页查看复盘摘要",
            }
        )

    feed = {
        "schema_version": "mobile_notification_feed@1",
        "generated_at": mobile_ops._now_iso(),
        "preferred_channel": preferred_channel,
        "active_channel": active_channel,
        "downgraded": downgraded,
        "downgrade_reason": downgrade_reason,
        "items": _normalize_items(items),
        "count": len(_normalize_items(items)),
    }
    root = _notification_root(results_root)
    mobile_ops._atomic_write_json(root / "latest.json", feed)
    return feed
