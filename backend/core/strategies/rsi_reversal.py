"""
RSI 均值回归策略（RSI Reversal Strategy）

RSI 超卖上穿买入，超买下穿/超时/止损卖出。
从 AdaptiveRegimeStrategy 的 MR 模式提取为独立策略。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class RSIReversalStrategy(Strategy):
    rsi_period: int = 6
    rsi_buy_threshold: float = 20.0
    rsi_sell_threshold: float = 80.0
    mr_max_hold_days: int = 5
    mr_stop_loss_pct: float = 0.03
    order_size: int = 1000

    def __post_init__(self) -> None:
        if self.rsi_buy_threshold >= self.rsi_sell_threshold:
            raise ValueError("rsi_buy_threshold must be less than rsi_sell_threshold")
        Strategy.__init__(self)
        self.state.setdefault("mr_entry_date", {})
        self.state.setdefault("mr_entry_price", {})

    def generate_signals(
        self, day: date, history: pd.DataFrame, positions: dict[str, Position]
    ) -> list[Signal]:
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]
        if day_data.empty:
            return out

        # 排除 benchmark 数据
        non_bench = day_data[
            ~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")
        ]

        mr_entry_date: dict[str, date] = self.state["mr_entry_date"]
        mr_entry_price: dict[str, float] = self.state["mr_entry_price"]

        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")
            symbol_str = str(symbol)
            min_rows = self.rsi_period + 2
            if len(sym_df) < min_rows:
                continue

            close = sym_df["close"].astype(float)
            close_today = float(close.iloc[-1])
            if pd.isna(close_today) or close_today <= 0:
                continue

            # 计算 RSI (Wilder's smoothed)
            delta = close.diff()
            gain = delta.clip(lower=0.0)
            loss = (-delta).clip(lower=0.0)
            avg_gain = gain.ewm(alpha=1.0 / self.rsi_period, min_periods=self.rsi_period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1.0 / self.rsi_period, min_periods=self.rsi_period, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0.0, np.nan)
            rsi = 100.0 - 100.0 / (1.0 + rs)

            rsi_now = float(rsi.iloc[-1])
            rsi_prev = float(rsi.iloc[-2])
            if pd.isna(rsi_now) or pd.isna(rsi_prev):
                continue

            rsi_cross_up = rsi_prev <= self.rsi_buy_threshold and rsi_now > self.rsi_buy_threshold
            rsi_cross_down = rsi_prev >= self.rsi_sell_threshold and rsi_now < self.rsi_sell_threshold

            has_pos = symbol_str in positions and positions[symbol_str].total_qty > 0

            meta = {
                "rsi_value": round(rsi_now, 2),
                "rsi_prev": round(rsi_prev, 2),
                "rsi_cross_up": bool(rsi_cross_up),
                "rsi_cross_down": bool(rsi_cross_down),
                "close": round(close_today, 6),
            }

            # --- 卖出逻辑 ---
            if has_pos:
                qty = int(positions[symbol_str].sellable_qty)
                if qty <= 0:
                    continue

                sell_reason = ""
                entry_px = mr_entry_price.get(symbol_str, 0.0)

                if rsi_cross_down:
                    sell_reason = "MR_RSI_OVERBOUGHT_SELL"
                elif entry_px > 0 and close_today <= entry_px * (1.0 - self.mr_stop_loss_pct):
                    sell_reason = "MR_STOP_LOSS"
                elif self.mr_max_hold_days > 0 and symbol_str in mr_entry_date:
                    held_days = (day - mr_entry_date[symbol_str]).days
                    if held_days >= self.mr_max_hold_days:
                        sell_reason = "MR_TIME_EXIT"

                if sell_reason:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol_str,
                            side=Side.SELL,
                            qty=qty,
                            reason=sell_reason,
                            reason_code=sell_reason,
                            meta={
                                **meta,
                                "triggered_rule": sell_reason,
                                "entry_price": round(entry_px, 6),
                                "held_days": (day - mr_entry_date.get(symbol_str, day)).days,
                            },
                        )
                    )
                    mr_entry_date.pop(symbol_str, None)
                    mr_entry_price.pop(symbol_str, None)
                continue

            # --- 买入逻辑 ---
            if rsi_cross_up and not has_pos:
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol_str,
                        side=Side.BUY,
                        qty=self.order_size,
                        reason="MR_RSI_OVERSOLD_BUY",
                        reason_code="MR_RSI_OVERSOLD_BUY",
                        meta={**meta, "triggered_rule": "MR_RSI_OVERSOLD_BUY"},
                    )
                )
                mr_entry_date[symbol_str] = day
                mr_entry_price[symbol_str] = close_today

        return out

    def generate_exit_only_signals(
        self,
        day: date,
        history: pd.DataFrame,
        positions: dict[str, Position],
        symbols: set[str],
    ) -> list[Signal]:
        """仅对指定 symbols 应用退出规则（不产生新买入）。"""
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]
        if day_data.empty:
            return out

        non_bench = day_data[
            ~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")
        ]

        mr_entry_date: dict[str, date] = self.state["mr_entry_date"]
        mr_entry_price: dict[str, float] = self.state["mr_entry_price"]

        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            symbol_str = str(symbol)
            if symbol_str not in symbols:
                continue

            sym_df = sym_df.sort_values("date")
            if len(sym_df) < self.rsi_period + 2:
                continue

            close = sym_df["close"].astype(float)
            close_today = float(close.iloc[-1])
            if pd.isna(close_today) or close_today <= 0:
                continue

            qty = int(positions[symbol_str].sellable_qty)
            if qty <= 0:
                continue

            sell_reason = ""
            entry_px = mr_entry_price.get(symbol_str, 0.0)

            if entry_px > 0 and close_today <= entry_px * (1.0 - self.mr_stop_loss_pct):
                sell_reason = "MR_STOP_LOSS"
            elif self.mr_max_hold_days > 0 and symbol_str in mr_entry_date:
                held_days = (day - mr_entry_date[symbol_str]).days
                if held_days >= self.mr_max_hold_days:
                    sell_reason = "MR_TIME_EXIT"

            if sell_reason:
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol_str,
                        side=Side.SELL,
                        qty=qty,
                        reason=sell_reason,
                        reason_code=sell_reason,
                        meta={
                            "close": round(close_today, 6),
                            "triggered_rule": sell_reason,
                            "entry_price": round(entry_px, 6),
                            "held_days": (day - mr_entry_date.get(symbol_str, day)).days,
                        },
                    )
                )
                mr_entry_date.pop(symbol_str, None)
                mr_entry_price.pop(symbol_str, None)

        return out
