from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .types import OrderStatus, RejectReason, Side


@dataclass(slots=True)
class Signal:
    signal_date: date
    symbol: str
    side: Side
    qty: int
    action: str = ""
    reason: str = ""
    reason_code: str = ""
    meta: dict[str, Any] | None = None


@dataclass(slots=True)
class Order:
    order_id: int
    signal_date: date
    submit_date: date
    symbol: str
    side: Side
    qty: int
    status: OrderStatus = OrderStatus.NEW
    filled_qty: int = 0
    fill_price: float | None = None
    reject_reason: RejectReason | None = None
    skip_reason: str = ""
    reject_stage: str = ""
    note: str = ""
    reason_code: str = ""
    meta: dict[str, Any] | None = None


@dataclass(slots=True)
class Trade:
    trade_id: int
    order_id: int
    trade_date: date
    symbol: str
    side: Side
    qty: int
    price: float
    gross_amount: float
    commission: float
    stamp_tax: float
    slippage: float
    net_amount: float


@dataclass(slots=True)
class Position:
    symbol: str
    total_qty: int = 0
    sellable_qty: int = 0
    avg_cost: float = 0.0


@dataclass(slots=True)
class AccountState:
    cash_total: float
    cash_available: float
    positions: dict[str, Position] = field(default_factory=dict)
    locked_cash_by_date: dict[date, float] = field(default_factory=dict)
    pending_sellable_by_date: dict[tuple[str, date], int] = field(default_factory=dict)


@dataclass(slots=True)
class DailySnapshot:
    date: date
    cash_total: float
    cash_available: float
    market_value: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
