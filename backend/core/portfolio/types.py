from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.core.core.types import Side


@dataclass(slots=True)
class PortfolioOrder:
    side: Side
    symbol: str
    qty: int
    reason_code: str
    order_value_scale: float = 1.0
    trend_tier: str = ""
    strong_trend: bool = False
    meta: dict[str, Any] | None = None


@dataclass(slots=True)
class PortfolioBacktestResult:
    daily: pd.DataFrame
    trades: pd.DataFrame
    candidates: pd.DataFrame
    metrics: dict[str, Any]
    cash_events: pd.DataFrame | None = None
