"""
自适应市场状态策略（Adaptive Regime Strategy）

根据 benchmark 实时 regime 信号自动在趋势跟踪模式（SMA Cross）
和均值回归模式（RSI Reversal）之间切换。

- 趋势模式: benchmark > benchmark_MA(regime_ma) → SMA fast/slow 金叉/死叉
- 均值回归模式: benchmark ≤ benchmark_MA(regime_ma) → RSI 超卖买入/超买卖出
- 所有指标只使用当前 bar 及之前的数据（无未来函数）
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
class AdaptiveRegimeStrategy(Strategy):
    # 趋势模式参数
    fast: int = 5
    slow: int = 20
    order_size: int = 1000

    # Regime 检测参数
    regime_ma: int = 60
    benchmark_symbol: str = "000300.SH"

    # 均值回归模式参数
    rsi_period: int = 6
    rsi_buy_threshold: float = 20.0
    rsi_sell_threshold: float = 80.0
    mr_max_hold_days: int = 5
    mr_stop_loss_pct: float = 0.03

    def __post_init__(self) -> None:
        if self.rsi_buy_threshold >= self.rsi_sell_threshold:
            raise ValueError("rsi_buy_threshold must be less than rsi_sell_threshold")
        Strategy.__init__(self)
        # 均值回归模式入场记录: symbol → entry_date
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

        # --- Regime 检测 ---
        regime_on, bench_close_val, bench_ma_val = self._detect_regime(day_data, day_ts)

        # 基础 meta 信息
        base_meta = {
            "regime_on": bool(regime_on),
            "signal_mode": "TREND" if regime_on else "MEAN_REVERT",
            "benchmark_close": bench_close_val,
            "benchmark_ma": bench_ma_val,
            "regime_ma": self.regime_ma,
        }

        # 排除 benchmark 数据
        non_bench = day_data[
            ~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")
        ]

        # MR 持仓需要由 MR 退出规则管理（即使 regime 已切回 TREND）
        mr_entry_date: dict[str, date] = self.state["mr_entry_date"]
        mr_positions = {s for s in mr_entry_date if s in positions and positions[s].total_qty > 0}

        if regime_on:
            self._generate_trend_signals(day, non_bench, positions, base_meta, out, skip_symbols=mr_positions)
            # 对 MR 持仓继续应用 MR 退出规则
            if mr_positions:
                self._generate_mr_exit_only(day, non_bench, positions, base_meta, out, mr_positions)
        else:
            self._generate_mr_signals(day, non_bench, positions, base_meta, out)

        return out

    def _detect_regime(
        self, day_data: pd.DataFrame, day_ts: pd.Timestamp
    ) -> tuple[bool, float | None, float | None]:
        """检测市场状态：benchmark close vs benchmark MA(regime_ma)。"""
        # generic 路径用 "bench:composite"，vectorized 路径用 "bench:<symbol>"
        sym_lower = day_data["symbol"].astype(str).str.lower()
        bench_df = day_data[sym_lower.str.startswith("bench:")].sort_values("date")

        if len(bench_df) < self.regime_ma:
            return True, None, None  # 数据不足时默认为趋势模式

        bclose = bench_df["close"].astype(float)
        bench_close_val = float(bclose.iloc[-1])
        bench_ma_val = float(bclose.rolling(self.regime_ma).mean().iloc[-1])

        if pd.isna(bench_ma_val):
            return True, bench_close_val, None

        regime_on = bench_close_val > bench_ma_val
        return bool(regime_on), bench_close_val, bench_ma_val

    def _generate_trend_signals(
        self,
        day: date,
        non_bench: pd.DataFrame,
        positions: dict[str, Position],
        base_meta: dict,
        out: list[Signal],
        skip_symbols: set[str] | None = None,
    ) -> None:
        """趋势模式: SMA 金叉买入，死叉卖出。"""
        _skip = skip_symbols or set()
        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            if str(symbol) in _skip:
                continue
            sym_df = sym_df.sort_values("date")
            if len(sym_df) < self.slow + 1:
                continue

            close = sym_df["close"].astype(float)
            fast_ser = close.rolling(self.fast).mean()
            slow_ser = close.rolling(self.slow).mean()

            fast_now = float(fast_ser.iloc[-1])
            slow_now = float(slow_ser.iloc[-1])
            fast_prev = float(fast_ser.iloc[-2])
            slow_prev = float(slow_ser.iloc[-2])

            if any(pd.isna(v) for v in (fast_now, slow_now, fast_prev, slow_prev)):
                continue

            cross_up = fast_prev <= slow_prev and fast_now > slow_now
            cross_down = fast_prev >= slow_prev and fast_now < slow_now
            has_pos = symbol in positions and positions[symbol].total_qty > 0

            meta = {
                **base_meta,
                "fast_ma": round(fast_now, 6),
                "slow_ma": round(slow_now, 6),
                "cross_up": bool(cross_up),
                "cross_down": bool(cross_down),
                "close": round(float(close.iloc[-1]), 6),
            }

            if cross_down and has_pos:
                qty = int(positions[symbol].sellable_qty)
                if qty > 0:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol,
                            side=Side.SELL,
                            qty=qty,
                            reason="TREND_SMA_CROSS_DOWN",
                            reason_code="TREND_SMA_CROSS_DOWN",
                            meta={**meta, "triggered_rule": "TREND_SMA_CROSS_DOWN"},
                        )
                    )
                continue

            if cross_up and not has_pos:
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=self.order_size,
                        reason="TREND_SMA_CROSS_UP",
                        reason_code="TREND_SMA_CROSS_UP",
                        meta={**meta, "triggered_rule": "TREND_SMA_CROSS_UP"},
                    )
                )

    def _generate_mr_signals(
        self,
        day: date,
        non_bench: pd.DataFrame,
        positions: dict[str, Position],
        base_meta: dict,
        out: list[Signal],
    ) -> None:
        """均值回归模式: RSI 超卖买入，超买/超时/止损卖出。"""
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
                **base_meta,
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

                # RSI 超买卖出
                if rsi_cross_down:
                    sell_reason = "MR_RSI_OVERBOUGHT_SELL"
                # 止损卖出
                elif entry_px > 0 and close_today <= entry_px * (1.0 - self.mr_stop_loss_pct):
                    sell_reason = "MR_STOP_LOSS"
                # 超时卖出
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

    def _generate_mr_exit_only(
        self,
        day: date,
        non_bench: pd.DataFrame,
        positions: dict[str, Position],
        base_meta: dict,
        out: list[Signal],
        mr_symbols: set[str],
    ) -> None:
        """对 MR 持仓应用退出规则（不产生新买入），用于 regime 已切回 TREND 时。"""
        mr_entry_date: dict[str, date] = self.state["mr_entry_date"]
        mr_entry_price: dict[str, float] = self.state["mr_entry_price"]

        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            symbol_str = str(symbol)
            if symbol_str not in mr_symbols:
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

            # 止损
            if entry_px > 0 and close_today <= entry_px * (1.0 - self.mr_stop_loss_pct):
                sell_reason = "MR_STOP_LOSS"
            # 超时
            elif self.mr_max_hold_days > 0 and symbol_str in mr_entry_date:
                held_days = (day - mr_entry_date[symbol_str]).days
                if held_days >= self.mr_max_hold_days:
                    sell_reason = "MR_TIME_EXIT"

            if sell_reason:
                meta = {
                    **base_meta,
                    "close": round(close_today, 6),
                    "triggered_rule": sell_reason,
                    "entry_price": round(entry_px, 6),
                    "held_days": (day - mr_entry_date.get(symbol_str, day)).days,
                }
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol_str,
                        side=Side.SELL,
                        qty=qty,
                        reason=sell_reason,
                        reason_code=sell_reason,
                        meta=meta,
                    )
                )
                mr_entry_date.pop(symbol_str, None)
                mr_entry_price.pop(symbol_str, None)
