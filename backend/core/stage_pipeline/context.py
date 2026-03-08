from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import pandas as pd

from backend.core.tools.data_bundle_builder import DataBundle


def _freeze_mapping(raw: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return MappingProxyType(dict(raw or {}))


def _freeze_orders(raw: Mapping[date, Sequence[Mapping[str, Any] | Any]] | None = None) -> Mapping[date, tuple[Any, ...]]:
    cooked: dict[date, tuple[Any, ...]] = {}
    for key, value in dict(raw or {}).items():
        items: list[Any] = []
        for item in list(value or ()):
            if isinstance(item, Mapping):
                items.append(dict(item))
            else:
                items.append(item)
        cooked[key] = tuple(items)
    return MappingProxyType(cooked)


def _detect_date_column(frame: pd.DataFrame, columns: Sequence[str]) -> str | None:
    for column in columns:
        if column in frame.columns:
            return column
    return None


@dataclass(frozen=True, slots=True)
class DayContext:
    day_index: int
    trading_day: date
    previous_trading_day: date | None
    next_trading_day: date | None
    is_first_day: bool
    is_last_day: bool
    signal_clock: str = "POST_CLOSE"
    execution_clock: str = "NEXT_OPEN"

    @classmethod
    def from_trading_days(cls, trading_days: Sequence[date], day_index: int) -> "DayContext":
        if day_index < 0 or day_index >= len(trading_days):
            raise IndexError(f"day_index out of range: {day_index}")
        previous_day = trading_days[day_index - 1] if day_index > 0 else None
        next_day = trading_days[day_index + 1] if day_index + 1 < len(trading_days) else None
        return cls(
            day_index=day_index,
            trading_day=trading_days[day_index],
            previous_trading_day=previous_day,
            next_trading_day=next_day,
            is_first_day=day_index == 0,
            is_last_day=day_index == len(trading_days) - 1,
        )


@dataclass(frozen=True, slots=True)
class PortfolioState:
    cash: float
    positions: Mapping[str, Any] = field(default_factory=dict)
    pending_orders: Mapping[date, tuple[Any, ...]] = field(default_factory=dict)
    nav: float | None = None
    market_value: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cash", float(self.cash))
        object.__setattr__(self, "positions", _freeze_mapping(self.positions))
        object.__setattr__(self, "pending_orders", _freeze_orders(self.pending_orders))
        object.__setattr__(self, "nav", None if self.nav is None else float(self.nav))
        object.__setattr__(self, "market_value", None if self.market_value is None else float(self.market_value))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @classmethod
    def empty(cls, *, cash: float = 0.0) -> "PortfolioState":
        return cls(cash=float(cash))


@dataclass(frozen=True, slots=True)
class DataBundleView:
    _bundle: DataBundle
    day_context: DayContext

    @classmethod
    def at(cls, bundle: DataBundle, day_index: int) -> "DataBundleView":
        return cls(_bundle=bundle, day_context=DayContext.from_trading_days(bundle.trading_days, day_index))

    @property
    def trading_day(self) -> date:
        return self.day_context.trading_day

    @property
    def previous_trading_day(self) -> date | None:
        return self.day_context.previous_trading_day

    @property
    def next_trading_day(self) -> date | None:
        return self.day_context.next_trading_day

    @property
    def visible_trading_days(self) -> tuple[date, ...]:
        return tuple(self._bundle.trading_days[: self.day_context.day_index + 1])

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(self._bundle.symbols)

    @property
    def universe_meta(self) -> Mapping[str, Any]:
        return _freeze_mapping(self._bundle.universe_meta)

    @property
    def industry_map(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self._bundle.industry_map))

    @property
    def sector_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._bundle.sector_data.keys()))

    def raw_history_view(self) -> pd.DataFrame:
        return self._slice_until_day(self._bundle.raw_history)

    def signal_history_view(self) -> pd.DataFrame:
        return self._slice_until_day(self._bundle.signal_history)

    def benchmark_view(self) -> pd.DataFrame:
        return self._slice_until_day(self._bundle.benchmark)

    def sector_data_view(self) -> dict[str, pd.DataFrame]:
        return {
            key: self._slice_until_day(value, date_columns=("trade_date", "date"))
            for key, value in self._bundle.sector_data.items()
        }

    def st_history_view(self) -> pd.DataFrame:
        return self._slice_until_day(self._bundle.st_history, date_columns=("start_date", "date", "trade_date"))

    def current_signal_frame(self) -> pd.DataFrame:
        return self._slice_for_day(self._bundle.signal_history)

    def current_raw_frame(self) -> pd.DataFrame:
        return self._slice_for_day(self._bundle.raw_history)

    def current_benchmark_frame(self) -> pd.DataFrame:
        return self._slice_for_day(self._bundle.benchmark)

    def _slice_until_day(self, frame: pd.DataFrame, date_columns: Sequence[str] = ("date", "trade_date")) -> pd.DataFrame:
        return self._slice(frame, mode="until", date_columns=date_columns)

    def _slice_for_day(self, frame: pd.DataFrame, date_columns: Sequence[str] = ("date", "trade_date")) -> pd.DataFrame:
        return self._slice(frame, mode="exact", date_columns=date_columns)

    def _slice(self, frame: pd.DataFrame, *, mode: str, date_columns: Sequence[str]) -> pd.DataFrame:
        if frame.empty:
            return frame.copy(deep=True)
        date_column = _detect_date_column(frame, date_columns)
        if not date_column:
            return frame.copy(deep=True)
        ts = pd.to_datetime(frame[date_column], errors="coerce").dt.normalize()
        trading_day = pd.Timestamp(self.trading_day).normalize()
        if mode == "exact":
            mask = ts == trading_day
        else:
            mask = ts <= trading_day
        return frame.loc[mask].copy(deep=True).reset_index(drop=True)
