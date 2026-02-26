from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CompositeStrategy(Strategy):
    """Combine multiple child strategies with AND/OR/VOTE modes."""

    strategies: list[Strategy] = field(default_factory=list)
    combine_mode: str = "AND"
    vote_threshold: float = 0.5
    debug: bool = False
    log_interval_days: int = 0

    def __post_init__(self) -> None:
        if not self.strategies:
            raise ValueError("strategies list cannot be empty")
        if self.combine_mode not in ("AND", "OR", "VOTE"):
            raise ValueError(f"Invalid combine_mode: {self.combine_mode}")
        if not 0 < self.vote_threshold <= 1:
            raise ValueError("vote_threshold must be between 0 and 1")
        Strategy.__init__(self)

        if self.debug:
            print(f"\n{'=' * 80}", flush=True)
            print("=== CompositeStrategy init ===", flush=True)
            print(f"  combine_mode: {self.combine_mode}", flush=True)
            print(f"  sub_strategies: {len(self.strategies)}", flush=True)
            for i, s in enumerate(self.strategies):
                print(f"  [{i}] {type(s).__name__}", flush=True)
            print(f"{'=' * 80}\n", flush=True)

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        all_signals: list[list[Signal]] = []
        signal_stats: list[dict[str, int | str]] = []
        collect_stats = bool(self.debug)

        for strategy in self.strategies:
            signals = strategy.generate_signals(day, history, positions)
            all_signals.append(signals)

            if collect_stats:
                buy_count = sum(1 for s in signals if s.side == Side.BUY and s.action != "BLOCKED")
                blocked_count = sum(1 for s in signals if s.side == Side.BUY and s.action == "BLOCKED")
                sell_count = sum(1 for s in signals if s.side == Side.SELL)
                signal_stats.append(
                    {
                        "strategy": type(strategy).__name__,
                        "buy_signals": buy_count,
                        "blocked_signals": blocked_count,
                        "sell_signals": sell_count,
                    }
                )

        if self.combine_mode == "AND":
            result = self._combine_and(all_signals, day)
        elif self.combine_mode == "OR":
            result = self._combine_or(all_signals, day)
        else:
            result = self._combine_vote(all_signals, day)

        if self.debug and (signal_stats or result):
            emit = True
            if int(self.log_interval_days or 0) > 0:
                emit = (day.day % int(self.log_interval_days) == 0)
            if emit:
                combined_buy = sum(1 for s in result if s.side == Side.BUY)
                combined_sell = sum(1 for s in result if s.side == Side.SELL)
                logger.info(
                    "[%s] Composite[%s] sub=%d stats=%s -> BUY=%d SELL=%d",
                    day,
                    self.combine_mode,
                    len(self.strategies),
                    signal_stats,
                    combined_buy,
                    combined_sell,
                )

        return result

    def _combine_and(self, all_signals: list[list[Signal]], day: date) -> list[Signal]:
        out: list[Signal] = []
        buy_signals_by_symbol: dict[str, list[Signal]] = defaultdict(list)
        sell_signals_by_symbol: dict[str, list[Signal]] = defaultdict(list)

        for signals in all_signals:
            for sig in signals:
                if sig.side == Side.BUY and sig.action != "BLOCKED":
                    buy_signals_by_symbol[sig.symbol].append(sig)
                elif sig.side == Side.SELL:
                    sell_signals_by_symbol[sig.symbol].append(sig)

        if self.debug and buy_signals_by_symbol and day.day == 15:
            signal_count_dist: dict[int, int] = defaultdict(int)
            for _, sigs in buy_signals_by_symbol.items():
                signal_count_dist[len(sigs)] += 1
            dist_str = ", ".join(f"{n}={count}" for n, count in sorted(signal_count_dist.items()))
            print(
                f"\n[{day}] AND distribution: symbols={len(buy_signals_by_symbol)}, {dist_str}, need={len(self.strategies)}\n",
                flush=True,
            )

        for symbol, sigs in buy_signals_by_symbol.items():
            if len(sigs) == len(self.strategies):
                combined_meta = self._merge_signal_meta(sigs)
                qty = max(sig.qty for sig in sigs) if sigs else 0
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=qty,
                        reason=f"COMPOSITE_AND_{len(sigs)}",
                        reason_code="COMPOSITE_AND_BUY",
                        meta=combined_meta,
                    )
                )

        for symbol, sigs in sell_signals_by_symbol.items():
            if len(sigs) > 0:
                combined_meta = self._merge_signal_meta(sigs)
                qty = sigs[0].qty
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.SELL,
                        qty=qty,
                        reason=f"COMPOSITE_AND_SELL_{len(sigs)}",
                        reason_code="COMPOSITE_AND_SELL",
                        meta=combined_meta,
                    )
                )

        return out

    def _combine_or(self, all_signals: list[list[Signal]], day: date) -> list[Signal]:
        out: list[Signal] = []
        buy_signals_by_symbol: dict[str, list[Signal]] = defaultdict(list)
        sell_signals_by_symbol: dict[str, list[Signal]] = defaultdict(list)

        for signals in all_signals:
            for sig in signals:
                if sig.side == Side.BUY and sig.action != "BLOCKED":
                    buy_signals_by_symbol[sig.symbol].append(sig)
                elif sig.side == Side.SELL:
                    sell_signals_by_symbol[sig.symbol].append(sig)

        for symbol, sigs in buy_signals_by_symbol.items():
            if len(sigs) > 0:
                combined_meta = self._merge_signal_meta(sigs)
                qty = max(sig.qty for sig in sigs) if sigs else 0
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=qty,
                        reason=f"COMPOSITE_OR_{len(sigs)}",
                        reason_code="COMPOSITE_OR_BUY",
                        meta=combined_meta,
                    )
                )

        for symbol, sigs in sell_signals_by_symbol.items():
            if len(sigs) == len(self.strategies):
                combined_meta = self._merge_signal_meta(sigs)
                qty = sigs[0].qty
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.SELL,
                        qty=qty,
                        reason=f"COMPOSITE_OR_SELL_{len(sigs)}",
                        reason_code="COMPOSITE_OR_SELL",
                        meta=combined_meta,
                    )
                )

        return out

    def _combine_vote(self, all_signals: list[list[Signal]], day: date) -> list[Signal]:
        out: list[Signal] = []
        buy_signals_by_symbol: dict[str, list[Signal]] = defaultdict(list)
        sell_signals_by_symbol: dict[str, list[Signal]] = defaultdict(list)

        for signals in all_signals:
            for sig in signals:
                if sig.side == Side.BUY and sig.action != "BLOCKED":
                    buy_signals_by_symbol[sig.symbol].append(sig)
                elif sig.side == Side.SELL:
                    sell_signals_by_symbol[sig.symbol].append(sig)

        min_votes = int(len(self.strategies) * self.vote_threshold)
        if min_votes < 1:
            min_votes = 1

        for symbol, sigs in buy_signals_by_symbol.items():
            if len(sigs) >= min_votes:
                combined_meta = self._merge_signal_meta(sigs)
                combined_meta["vote_count"] = len(sigs)
                combined_meta["total_strategies"] = len(self.strategies)
                combined_meta["vote_ratio"] = round(len(sigs) / len(self.strategies), 2)
                qty = max(sig.qty for sig in sigs) if sigs else 0
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=qty,
                        reason=f"COMPOSITE_VOTE_{len(sigs)}/{len(self.strategies)}",
                        reason_code="COMPOSITE_VOTE_BUY",
                        meta=combined_meta,
                    )
                )

        for symbol, sigs in sell_signals_by_symbol.items():
            if len(sigs) >= min_votes:
                combined_meta = self._merge_signal_meta(sigs)
                combined_meta["vote_count"] = len(sigs)
                combined_meta["total_strategies"] = len(self.strategies)
                combined_meta["vote_ratio"] = round(len(sigs) / len(self.strategies), 2)
                qty = sigs[0].qty
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.SELL,
                        qty=qty,
                        reason=f"COMPOSITE_VOTE_SELL_{len(sigs)}/{len(self.strategies)}",
                        reason_code="COMPOSITE_VOTE_SELL",
                        meta=combined_meta,
                    )
                )

        return out

    def _merge_signal_meta(self, signals: list[Signal]) -> dict:
        merged: dict[str, object] = {"sub_signals": [], "strategy_count": len(signals)}
        sub_signals: list[dict[str, object]] = []
        for sig in signals:
            sub_meta: dict[str, object] = {
                "reason": sig.reason,
                "reason_code": sig.reason_code,
            }
            if sig.meta:
                sub_meta.update(sig.meta)
            sub_signals.append(sub_meta)
        merged["sub_signals"] = sub_signals
        return merged
