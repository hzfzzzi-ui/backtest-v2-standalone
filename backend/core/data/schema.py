from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalColumns:
    date: str = "date"
    symbol: str = "symbol"
    open: str = "open"
    high: str = "high"
    low: str = "low"
    close: str = "close"
    volume: str = "volume"
    amount: str = "amount"


CANONICAL_COLUMNS = CanonicalColumns()
SOURCE_STOCKS = "stocks"
SOURCE_INDEX = "index"
