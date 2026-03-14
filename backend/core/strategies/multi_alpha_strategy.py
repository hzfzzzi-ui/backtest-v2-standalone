from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from backend.core.core.models import Position, Signal
from .base import Strategy


@dataclass(slots=True)
class MultiAlphaStrategy(Strategy):
    """Provider-owned wrapper for multi-alpha composition runtime."""

    multi_alpha: dict[str, Any] = field(default_factory=dict)
    portfolio_mode: str = "hard_sleeve_budget"

    def __post_init__(self) -> None:
        Strategy.__init__(self)

    def generate_signals(
        self,
        day: date,
        history: pd.DataFrame,
        positions: dict[str, Position],
    ) -> list[Signal]:
        raise RuntimeError("MultiAlphaStrategy must run through MultiAlphaSignalProvider")
