from __future__ import annotations

from dataclasses import dataclass

from backend.core.config.models import BacktestConfig
from backend.core.data.provider import DataProvider


@dataclass(slots=True)
class BacktestContext:
    config: BacktestConfig
    provider: DataProvider
