from __future__ import annotations

from typing import Any

CANONICAL_ORDER_STATUSES = {
    "FILLED",
    "PARTIAL_FILLED",
    "REJECTED",
    "CANCELLED",
    "SUBMITTED",
    "NEW",
}

ORDERS_CSV_COLUMNS = [
    "order_id",
    "signal_date",
    "submit_date",
    "symbol",
    "side",
    "qty",
    "status",
    "filled_qty",
    "fill_price",
    "reject_reason",
    "note",
    "reason_code",
    "meta",
    "meta_json",
    "limit_state",
    "slippage",
    "slippage_cost",
    "skip_reason",
    "reject_stage",
]

TRADES_CSV_COLUMNS = [
    "trade_id",
    "order_id",
    "trade_date",
    "symbol",
    "side",
    "qty",
    "price",
    "gross_amount",
    "commission",
    "stamp_tax",
    "slippage",
    "slippage_cost",
    "net_amount",
    "reject_reason",
    "skip_reason",
    "limit_state",
    "reason_code",
]

SIGNALS_CSV_COLUMNS = [
    "date",
    "symbol",
    "action",
    "side",
    "qty",
    "reason_code",
    "meta_json",
]


def normalize_order_status(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if s in {"FILLED", "EXECUTED"}:
        return "FILLED"
    if s in {"PARTIAL", "PARTIAL_FILLED", "PARTIALLY_FILLED"}:
        return "PARTIAL_FILLED"
    if s in {"REJECT", "REJECTED", "FAILED"}:
        return "REJECTED"
    if s in {"CANCEL", "CANCELED", "CANCELLED"}:
        return "CANCELLED"
    if s in {"SUBMITTED", "PENDING", "SENT"}:
        return "SUBMITTED"
    if s in {"NEW", ""}:
        return "NEW"
    return "NEW"
