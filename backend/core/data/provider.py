from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataProvider(ABC):
    @abstractmethod
    def load_ohlcv_daily(self, symbols: list[str], start: date, end: date, source: str) -> pd.DataFrame:
        """Return canonical OHLCV columns plus optional extras on the same date/symbol row."""

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

    def load_st_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        """Return ST history: columns ts_code, start_date, end_date, st_type.

        Default implementation returns empty DataFrame (no ST data available).
        """
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"])

    def load_sector_indices(self, start: date, end: date) -> pd.DataFrame:
        """加载申万 L1 行业指数日线 (801xxx.SI)。

        返回 columns: index_code, trade_date, open, high, low, close。
        默认返回空 DataFrame。
        """
        return pd.DataFrame(columns=["index_code", "trade_date", "open", "high", "low", "close"])

    def load_industry_mapping(self, symbols: list[str]) -> dict[str, str]:
        """加载股票→行业 L1 映射（最新有效记录）。

        返回 {symbol: industry_l1} 字典。默认返回空 dict。
        """
        return {}

    def load_industry_history(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        """加载股票→行业历史映射（PIT-safe 区间记录）。

        返回至少包含 ts_code/start_date/end_date/industry_l1 的 DataFrame，
        如可用应同时返回 standard / industry_l2。
        默认返回空 DataFrame。
        """
        return pd.DataFrame(columns=["ts_code", "start_date", "end_date", "standard", "industry_l1", "industry_l2"])

    def load_security_master(self, symbols: list[str]) -> pd.DataFrame:
        """Return security master rows with at least symbol/list_date/delist_date.

        Default implementation returns empty DataFrame when source is unavailable.
        """
        return pd.DataFrame(columns=["symbol", "list_date", "delist_date"])

    def load_index_constituent_history(
        self,
        index_code: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """Load PIT constituent ranges for an index.

        Returns columns: index_code, symbol, start_date, end_date and optional
        source/event_type/rebalance_calendar_* lineage metadata.
        Default implementation returns an empty DataFrame.
        """
        return pd.DataFrame(columns=["index_code", "symbol", "start_date", "end_date"])

    @property
    @abstractmethod
    def query_audit(self) -> list[dict]:
        """Executed query metadata for snapshot/report."""
