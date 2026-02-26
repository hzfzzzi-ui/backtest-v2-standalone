from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataProvider(ABC):
    @abstractmethod
    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        """Return canonical columns: date,symbol,open,high,low,close,volume,amount."""

    @abstractmethod
    def load_trading_calendar_cn(self, start: date, end: date) -> pd.DatetimeIndex:
        """Return trading calendar index in ascending order."""

    @abstractmethod
    def get_previous_trading_day_cn(self, start: date) -> date | None:
        """Return latest trading day strictly before start, or None if not found."""

    @abstractmethod
    def load_instrument_rules(self, symbols: list[str]) -> pd.DataFrame:
        """Return rules by symbol."""

    @abstractmethod
    def load_benchmark_daily(self, benchmark_symbol: str, start: date, end: date) -> pd.DataFrame:
        """Return canonical benchmark daily bars."""

    @property
    @abstractmethod
    def query_audit(self) -> list[dict]:
        """Executed query metadata for snapshot/report."""
