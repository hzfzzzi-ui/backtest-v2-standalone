"""
量能突破策略（Volume Breakout Strategy）

独立的信号发生器，基于成交量突破产生买入信号。

条件：vol_today > ma20_vol * vol_mult
作用：捕捉趋势启动/加速段
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class VolumeBreakoutStrategy(Strategy):
    """
    量能突破策略

    买入条件：
    1. 当日成交量 > 20日均量 * vol_mult
    2. 当前无持仓

    卖出条件：
    1. 无主动卖出条件（这是一个买入过滤器）
    2. 可通过组合其他策略来决定卖出时机

    参数：
        vol_ma_period: 成交量均线周期（默认20日）
        vol_mult: 突破倍数（建议1.3-1.6，默认1.5）
        min_data_days: 最小历史数据天数
    """

    vol_ma_period: int = 20
    vol_mult: float = 1.5
    min_data_days: int = 30

    def __post_init__(self) -> None:
        if self.vol_mult <= 0:
            raise ValueError("vol_mult must be positive")
        if self.vol_ma_period < 1:
            raise ValueError("vol_ma_period must be at least 1")

        Strategy.__init__(self)

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        """
        基于量能突破产生买入信号

        流程：
        1. 计算每只股票的20日均量
        2. 检查当日成交量是否突破阈值
        3. 产生买入信号（如果无持仓）
        4. 返回信号列表（按成交量突破幅度排序）
        """
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]

        if day_data.empty:
            return out

        # 排除基准数据
        non_bench = day_data[~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")]

        # 候选列表：(突破倍数, symbol)
        buy_candidates: list[tuple[float, str]] = []

        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")

            # 检查数据充足性
            if len(sym_df) < self.min_data_days:
                continue

            # 获取当日数据
            today_row = sym_df[sym_df["date"] == day_ts]
            if today_row.empty:
                continue

            vol_today = today_row.iloc[-1]["volume"]
            if pd.isna(vol_today) or vol_today <= 0:
                continue

            # 计算均量
            recent_vols = sym_df.tail(self.vol_ma_period)["volume"]
            vol_ma = recent_vols.mean()

            if pd.isna(vol_ma) or vol_ma <= 0:
                continue

            # 检查量能突破
            vol_ratio = vol_today / vol_ma
            if vol_ratio >= self.vol_mult:
                # 检查是否已持仓
                symbol_str = str(symbol)
                if symbol_str in positions and positions[symbol_str].total_qty > 0:
                    continue

                buy_candidates.append((vol_ratio, symbol_str))

        # 按突破倍数排序（倍数越高优先级越高）
        buy_candidates.sort(key=lambda x: x[0], reverse=True)

        # 生成买入信号
        for vol_ratio, symbol in buy_candidates:
            out.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.BUY,
                    qty=0,  # 由上层portfolio决定
                    reason=f"VOL_BREAKOUT_{vol_ratio:.2f}X",
                    reason_code="VOLUME_BREAKOUT",
                    meta={
                        "volume_ratio": round(vol_ratio, 2),
                        "vol_mult_threshold": self.vol_mult,
                        "signal_type": "volume_breakout",
                    },
                )
            )

        return out
