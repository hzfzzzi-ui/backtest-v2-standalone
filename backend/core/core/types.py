from __future__ import annotations

from enum import StrEnum


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class RejectReason(StrEnum):
    NO_DATA = "NO_DATA"
    SUSPENDED = "SUSPENDED"
    LIMIT_UP = "LIMIT_UP"
    LIMIT_DOWN = "LIMIT_DOWN"
    LOT_SIZE = "LOT_SIZE"
    NO_POSITION = "NO_POSITION"
    NO_SELLABLE = "NO_SELLABLE"
    NO_CASH = "NO_CASH"
    LIQUIDITY = "LIQUIDITY"
    PRICE_INVALID = "PRICE_INVALID"
    MISSING_PREV_CLOSE = "MISSING_PREV_CLOSE"
