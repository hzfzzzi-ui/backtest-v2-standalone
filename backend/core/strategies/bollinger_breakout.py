"""
布林带突破策略（Bollinger Breakout Strategy）

独立的信号发生器，基于布林带上轨突破产生买入信号。

条件：close > bb_upper(20, 2)
定义：bb_upper = ma20 + 2 * std20
作用：捕捉趋势突破段；与量能突破天然互补
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class BollingerBreakoutStrategy(Strategy):
    """
    布林带突破策略

    买入条件：
    1. close > bb_upper
    2. bb_upper = bb_mid + bb_std_mult * bb_std
    3. bb_mid = ma(close, bb_period)
    4. bb_std = std(close, bb_period)
    5. 当前无持仓

    卖出条件：
    1. close < bb_mid（跌破中轨，可选）
    2. 或由组合其他策略决定卖出时机

    参数：
        bb_period: 布林带周期（默认20日）
        bb_std_mult: 标准差倍数（默认2.0）
        enable_bb_mid_exit: 是否在跌破中轨时卖出
        min_data_days: 最小历史数据天数
    """

    bb_period: int = 20
    bb_std_mult: float = 2.0
    enable_bb_mid_exit: bool = False
    min_data_days: int = 30

    def __post_init__(self) -> None:
        if self.bb_period < 2:
            raise ValueError("bb_period must be at least 2")
        if self.bb_std_mult <= 0:
            raise ValueError("bb_std_mult must be positive")

        Strategy.__init__(self)
        self.state.setdefault("entry_date", {})

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        """
        基于布林带突破产生买入/卖出信号

        流程：
        1. 计算每只股票的布林带上轨和中轨
        2. 检查收盘价是否突破上轨
        3. 产生买入信号（如果无持仓）
        4. 检查持仓：收盘价跌破中轨 → 卖出（如果enable_bb_mid_exit=True）
        5. 返回信号列表（按突破幅度排序）
        """
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]

        if day_data.empty:
            return out

        # 排除基准数据
        non_bench = day_data[~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")]

        entry_date_state: dict[str, str] = self.state["entry_date"]

        # 候选列表：(breakout_pct, symbol)
        buy_candidates: list[tuple[float, str]] = []

        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")
            symbol_str = str(symbol)

            # 检查数据充足性
            if len(sym_df) < self.min_data_days:
                continue

            # 获取当日数据
            today_row = sym_df[sym_df["date"] == day_ts]
            if today_row.empty:
                continue

            close_today = today_row.iloc[-1]["close"]
            if pd.isna(close_today) or close_today <= 0:
                continue

            # 计算布林带
            recent_closes = sym_df.tail(self.bb_period)["close"]
            if len(recent_closes) < self.bb_period:
                continue

            bb_mid = recent_closes.mean()
            bb_std = recent_closes.std()

            if pd.isna(bb_mid) or pd.isna(bb_std) or bb_mid <= 0:
                continue

            bb_upper = bb_mid + self.bb_std_mult * bb_std
            bb_lower = bb_mid - self.bb_std_mult * bb_std

            # 处理卖出信号（如果启用）
            if symbol_str in positions and positions[symbol_str].total_qty > 0:
                if self.enable_bb_mid_exit and close_today < bb_mid:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol_str,
                            side=Side.SELL,
                            qty=positions[symbol_str].total_qty,
                            reason="BB_MID_BREAK",
                            reason_code="BOLLINGER_EXIT",
                            meta={
                                "close": round(close_today, 2),
                                "bb_mid": round(bb_mid, 2),
                                "bb_upper": round(bb_upper, 2),
                                "signal_type": "bollinger_exit",
                            },
                        )
                    )
                    entry_date_state.pop(symbol_str, None)
                continue

            # 检查买入条件：突破上轨
            if close_today > bb_upper:
                # 计算突破幅度
                breakout_pct = (close_today - bb_upper) / bb_upper
                buy_candidates.append((breakout_pct, symbol_str))

        # 按突破幅度排序（幅度越大优先级越高）
        buy_candidates.sort(key=lambda x: x[0], reverse=True)

        # 生成买入信号
        for breakout_pct, symbol in buy_candidates:
            # 重新获取布林带数据用于meta
            sym_df = non_bench[non_bench["symbol"] == symbol].sort_values("date")
            today_row = sym_df[sym_df["date"] == day_ts]
            close_today = today_row.iloc[-1]["close"]

            recent_closes = sym_df.tail(self.bb_period)["close"]
            bb_mid = recent_closes.mean()
            bb_std = recent_closes.std()
            bb_upper = bb_mid + self.bb_std_mult * bb_std

            out.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.BUY,
                    qty=0,  # 由上层portfolio决定
                    reason=f"BB_BREAKOUT_{breakout_pct*100:.1f}%",
                    reason_code="BOLLINGER_BREAKOUT",
                    meta={
                        "close": round(close_today, 2),
                        "bb_upper": round(bb_upper, 2),
                        "bb_mid": round(bb_mid, 2),
                        "bb_std": round(bb_std, 2),
                        "breakout_pct": round(breakout_pct * 100, 2),
                        "bb_period": self.bb_period,
                        "bb_std_mult": self.bb_std_mult,
                        "signal_type": "bollinger_breakout",
                    },
                )
            )
            entry_date_state[symbol] = day.isoformat()

        return out
