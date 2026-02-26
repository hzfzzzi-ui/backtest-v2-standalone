"""
20日动量策略（Momentum ROC Strategy）

独立的信号发生器，基于20日动量（Rate of Change）产生买入信号。

条件：roc_20 > threshold（例如0%或2%）
作用：过滤假金叉/弱反弹
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class MomentumROCStrategy(Strategy):
    """
    20日动量策略（ROC - Rate of Change）

    买入条件：
    1. roc_20 = (close_today - close_20d_ago) / close_20d_ago > threshold
    2. 当前无持仓

    卖出条件：
    1. roc_20 转负（可选）
    2. 或由组合其他策略决定卖出时机

    参数：
        roc_period: ROC计算周期（默认20日）
        roc_threshold: ROC阈值（0.0表示0%，0.02表示2%）
        enable_roc_exit: 是否在ROC转负时卖出
        min_data_days: 最小历史数据天数
    """

    roc_period: int = 20
    roc_threshold: float = 0.0  # 0% 或 0.02 (2%)
    enable_roc_exit: bool = False
    min_data_days: int = 30

    def __post_init__(self) -> None:
        if self.roc_period < 1:
            raise ValueError("roc_period must be at least 1")

        Strategy.__init__(self)
        self.state.setdefault("entry_date", {})

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        """
        基于20日动量产生买入/卖出信号

        流程：
        1. 计算每只股票的roc_20
        2. 检查roc_20是否大于阈值
        3. 产生买入信号（如果无持仓）
        4. 检查持仓：roc_20转负 → 卖出（如果enable_roc_exit=True）
        5. 返回信号列表（按ROC值排序）
        """
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]

        if day_data.empty:
            return out

        # 排除基准数据
        non_bench = day_data[~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")]

        entry_date_state: dict[str, str] = self.state["entry_date"]

        # 候选列表：(roc_value, symbol)
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

            # 计算ROC
            if len(sym_df) < self.roc_period + 1:
                continue

            close_n_days_ago_df = sym_df.iloc[-(self.roc_period + 1)]
            close_n_days_ago = close_n_days_ago_df["close"]

            if pd.isna(close_n_days_ago) or close_n_days_ago <= 0:
                continue

            roc = (close_today - close_n_days_ago) / close_n_days_ago

            # 处理卖出信号（如果启用）
            if symbol_str in positions and positions[symbol_str].total_qty > 0:
                if self.enable_roc_exit and roc < 0:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol_str,
                            side=Side.SELL,
                            qty=positions[symbol_str].total_qty,
                            reason="ROC_NEGATIVE",
                            reason_code="MOMENTUM_EXIT",
                            meta={
                                "roc_value": round(roc * 100, 2),
                                "roc_period": self.roc_period,
                                "signal_type": "momentum_exit",
                            },
                        )
                    )
                    entry_date_state.pop(symbol_str, None)
                continue

            # 检查买入条件
            if roc >= self.roc_threshold:
                buy_candidates.append((roc, symbol_str))

        # 按ROC值排序（值越高优先级越高）
        buy_candidates.sort(key=lambda x: x[0], reverse=True)

        # 生成买入信号
        for roc, symbol in buy_candidates:
            out.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.BUY,
                    qty=0,  # 由上层portfolio决定
                    reason=f"ROC_{roc*100:.1f}%",
                    reason_code="MOMENTUM_BREAKOUT",
                    meta={
                        "roc_value": round(roc * 100, 2),
                        "roc_threshold": round(self.roc_threshold * 100, 2),
                        "roc_period": self.roc_period,
                        "signal_type": "momentum_roc",
                    },
                )
            )
            entry_date_state[symbol] = day.isoformat()

        return out
