from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal


class Strategy(ABC):
    def __init__(self) -> None:
        self.state: dict = {}
        self.context: dict = {}

    def set_context(self, context: dict) -> None:
        self.context = dict(context or {})

    @abstractmethod
    def generate_signals(
        self,
        day: date,
        history: pd.DataFrame,
        positions: dict[str, Position],
    ) -> list[Signal]:
        ...
