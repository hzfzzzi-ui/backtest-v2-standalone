"""
相对强度策略（Relative Strength Strategy）

独立的信号发生器，基于相对强度排名产生买入信号。

定义：过去60日（或120日）收益率在当日股票池里的分位数
条件：rs_pct >= 0.7（Top 30%）
作用：把交易集中到"更像赢家"的子集
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import numpy as np

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class RelativeStrengthStrategy(Strategy):
    """
    相对强度策略（RS Rank）

    买入条件：
    1. 计算每只股票过去rs_period日的收益率
    2. 对所有股票的收益率排序，计算分位数
    3. rs_pct >= rs_threshold（例如0.7表示Top 30%）
    4. 当前无持仓

    卖出条件：
    1. 无主动卖出条件（这是一个排序/过滤器）
    2. 可通过组合其他策略来决定卖出时机

    参数：
        rs_period: RS计算周期（60或120日）
        rs_threshold: RS分位数阈值（0.7 = Top 30%）
        min_data_days: 最小历史数据天数
    """

    rs_period: int = 60
    rs_threshold: float = 0.7  # Top 30%
    min_data_days: int = 70

    def __post_init__(self) -> None:
        if self.rs_period < 1:
            raise ValueError("rs_period must be at least 1")
        if not 0 <= self.rs_threshold <= 1:
            raise ValueError("rs_threshold must be between 0 and 1")

        Strategy.__init__(self)

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        """
        基于相对强度排名产生买入信号

        流程：
        1. 计算所有股票的rs_period日收益率
        2. 对收益率进行排序，计算每只股票的分位数
        3. 筛选rs_pct >= rs_threshold的股票
        4. 产生买入信号（如果无持仓）
        5. 返回信号列表（按RS排名排序，高分优先）
        """
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]

        if day_data.empty:
            return out

        # 排除基准数据
        non_bench = day_data[~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")]

        # 第一遍：计算所有股票的收益率
        returns_dict: dict[str, float] = {}

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

            # 计算rs_period日前的收盘价
            if len(sym_df) < self.rs_period + 1:
                continue

            close_n_days_ago_df = sym_df.iloc[-(self.rs_period + 1)]
            close_n_days_ago = close_n_days_ago_df["close"]

            if pd.isna(close_n_days_ago) or close_n_days_ago <= 0:
                continue

            # 计算收益率
            ret = (close_today - close_n_days_ago) / close_n_days_ago
            returns_dict[symbol_str] = ret

        # 如果没有足够的股票，返回空信号
        if len(returns_dict) < 2:
            return out

        # 第二遍：计算分位数排名
        returns_array = np.array(list(returns_dict.values()))
        rs_percentiles: dict[str, float] = {}

        for symbol_str, ret in returns_dict.items():
            # 计算分位数：比该股票收益率低的股票占比
            percentile = (returns_array < ret).sum() / len(returns_array)
            rs_percentiles[symbol_str] = percentile

        # 第三遍：筛选并生成信号
        buy_candidates: list[tuple[float, str, float]] = []  # (percentile, symbol, return)

        for symbol_str, percentile in rs_percentiles.items():
            # 检查是否已持仓
            if symbol_str in positions and positions[symbol_str].total_qty > 0:
                continue

            # 检查是否满足RS阈值
            if percentile >= self.rs_threshold:
                ret = returns_dict[symbol_str]
                buy_candidates.append((percentile, symbol_str, ret))

        # 按分位数排序（分位数越高优先级越高）
        buy_candidates.sort(key=lambda x: x[0], reverse=True)

        # 生成买入信号
        for percentile, symbol, ret in buy_candidates:
            rank_pct = percentile * 100
            out.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.BUY,
                    qty=0,  # 由上层portfolio决定
                    reason=f"RS_TOP{100-rank_pct:.0f}%",
                    reason_code="RELATIVE_STRENGTH",
                    meta={
                        "rs_percentile": round(percentile, 3),
                        "rs_rank_pct": round(rank_pct, 1),
                        "rs_return": round(ret * 100, 2),
                        "rs_period": self.rs_period,
                        "rs_threshold": self.rs_threshold,
                        "signal_type": "relative_strength",
                    },
                )
            )

        return out
