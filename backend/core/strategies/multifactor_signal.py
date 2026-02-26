"""
多因子信号策略（独立信号发生器）

完全独立地基于多因子评分产生买入/卖出信号，不依赖其他策略。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy
from .factors import compute_multifactor_score
from .signal_fusion import SignalStrength, classify_signal_strength


@dataclass(slots=True)
class MultifactorSignalStrategy(Strategy):
    """
    多因子信号策略（独立信号发生器）

    完全基于多因子评分产生买入/卖出信号，不依赖SMA或其他指标。

    买入条件：
    1. 多因子评分 >= buy_threshold
    2. 当前无持仓

    卖出条件：
    1. 多因子评分 < sell_threshold（止损）
    2. 或持仓天数 >= max_hold_days（强制退出）

    参数：
        benchmark_symbol: 基准指数代码
        buy_threshold: 买入评分阈值（0-100）
        sell_threshold: 卖出评分阈值（0-100）
        max_hold_days: 最大持仓天数（0表示不限制）
        min_data_days: 最小历史数据天数
        rebalance_on_score_change: 是否在评分变化时重新排序
    """

    benchmark_symbol: str = "000300.SH"
    buy_threshold: float = 50.0  # 买入评分阈值
    sell_threshold: float = 30.0  # 卖出评分阈值（低于此分数卖出）
    max_hold_days: int = 0  # 最大持仓天数（0=不限制）
    min_data_days: int = 60  # 最小历史数据天数
    rebalance_on_score_change: bool = True  # 是否在评分变化时重新排序

    def __post_init__(self) -> None:
        if self.buy_threshold <= self.sell_threshold:
            raise ValueError("buy_threshold must be greater than sell_threshold")
        if self.buy_threshold > 100 or self.sell_threshold < 0:
            raise ValueError("thresholds must be in range [0, 100]")

        Strategy.__init__(self)
        self.state.setdefault("entry_date", {})  # 持仓进入日期
        self.state.setdefault("entry_score", {})  # 持仓进入时的评分
        self.state.setdefault("daily_scores", {})  # 每日评分记录

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        """
        基于多因子评分产生买入/卖出信号（完全独立）

        流程：
        1. 计算所有股票的多因子评分
        2. 检查持仓：评分低于sell_threshold → 卖出
        3. 检查持仓：超过max_hold_days → 卖出
        4. 检查候选：评分 >= buy_threshold → 买入
        5. 返回排序后的信号（高分优先）
        """
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]

        if day_data.empty:
            return out

        # 加载基准数据
        bench_code = f"BENCH:{self.benchmark_symbol}".lower()
        bench_df = day_data[day_data["symbol"].astype(str).str.lower() == bench_code].sort_values("date")

        entry_date_state: dict[str, str] = self.state["entry_date"]
        entry_score_state: dict[str, float] = self.state["entry_score"]

        # 第一遍：计算所有股票的多因子评分
        all_symbols_scores: dict[str, float] = {}
        all_symbols_details: dict[str, dict] = {}
        all_symbols_rs: dict[str, float] = {}

        non_bench = day_data[~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")]

        # 先计算RS排名
        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")
            if len(sym_df) < self.min_data_days:
                continue

            score, details = compute_multifactor_score(
                sym_df=sym_df,
                benchmark_df=bench_df if len(bench_df) > 0 else None,
                all_symbols_rs=None,
                symbol=str(symbol),
                config={},
            )

            all_symbols_scores[str(symbol)] = score
            all_symbols_details[str(symbol)] = details

            if "rs" in details and details["rs"].get("value") is not None:
                all_symbols_rs[str(symbol)] = details["rs"]["value"]

        # 第二遍：重新计算带RS排名的评分
        for symbol in list(all_symbols_scores.keys()):
            sym_df = non_bench[non_bench["symbol"] == symbol].sort_values("date")
            score, details = compute_multifactor_score(
                sym_df=sym_df,
                benchmark_df=bench_df if len(bench_df) > 0 else None,
                all_symbols_rs=all_symbols_rs,
                symbol=str(symbol),
                config={},
            )
            all_symbols_scores[symbol] = score
            all_symbols_details[symbol] = details

        # 存储今日评分
        self.state["daily_scores"][day.isoformat()] = all_symbols_scores

        # 处理卖出信号（检查持仓）
        for symbol, pos in positions.items():
            if pos.qty <= 0:
                continue

            score = all_symbols_scores.get(symbol, 0.0)
            strength = classify_signal_strength(score)
            entry_date_str = entry_date_state.get(symbol)
            entry_score = entry_score_state.get(symbol, 0.0)

            # 计算持仓天数
            hold_days = 0
            if entry_date_str:
                try:
                    entry_date_obj = date.fromisoformat(entry_date_str)
                    hold_days = (day - entry_date_obj).days
                except Exception:
                    pass

            # 卖出条件1: 评分低于阈值
            should_sell_score = score < self.sell_threshold

            # 卖出条件2: 超过最大持仓天数
            should_sell_days = self.max_hold_days > 0 and hold_days >= self.max_hold_days

            if should_sell_score or should_sell_days:
                reason = "MF_SCORE_LOW" if should_sell_score else "MF_MAX_HOLD_DAYS"
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.SELL,
                        qty=pos.qty,
                        reason=reason,
                        reason_code=reason,
                        meta={
                            "multifactor_score": round(score, 2),
                            "multifactor_strength": strength.value,
                            "entry_score": round(entry_score, 2),
                            "hold_days": hold_days,
                            "sell_reason": "score_low" if should_sell_score else "max_hold_days",
                        },
                    )
                )

                # 清理状态
                entry_date_state.pop(symbol, None)
                entry_score_state.pop(symbol, None)

        # 处理买入信号（评分 >= buy_threshold）
        buy_candidates: list[tuple[float, str, dict]] = []

        for symbol, score in all_symbols_scores.items():
            # 跳过已持仓的
            if symbol in positions and positions[symbol].total_qty > 0:
                continue

            # 检查买入阈值
            if score >= self.buy_threshold:
                details = all_symbols_details.get(symbol, {})
                strength = classify_signal_strength(score)
                buy_candidates.append((score, symbol, details))

        # 按评分排序（高分优先）
        buy_candidates.sort(key=lambda x: x[0], reverse=True)

        # 生成买入信号
        for score, symbol, details in buy_candidates:
            strength = classify_signal_strength(score)

            out.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.BUY,
                    qty=0,  # 由上层portfolio决定
                    reason=f"MF_{strength.value}",
                    reason_code=f"MULTIFACTOR_{strength.value}",
                    meta={
                        "multifactor_score": round(score, 2),
                        "multifactor_strength": strength.value,
                        "multifactor_details": details,
                        "signal_type": "pure_multifactor",
                    },
                )
            )

            # 记录进入状态（实际买入后会更新）
            entry_date_state[symbol] = day.isoformat()
            entry_score_state[symbol] = score

        return out


def create_balanced_multifactor_strategy(**kwargs) -> MultifactorSignalStrategy:
    """创建平衡模式的多因子策略"""
    return MultifactorSignalStrategy(
        buy_threshold=50.0,
        sell_threshold=30.0,
        max_hold_days=0,
        **kwargs,
    )


def create_aggressive_multifactor_strategy(**kwargs) -> MultifactorSignalStrategy:
    """创建激进模式的多因子策略"""
    return MultifactorSignalStrategy(
        buy_threshold=30.0,  # 更低的买入门槛
        sell_threshold=20.0,  # 更低的卖出门槛
        max_hold_days=0,
        **kwargs,
    )


def create_conservative_multifactor_strategy(**kwargs) -> MultifactorSignalStrategy:
    """创建保守模式的多因子策略"""
    return MultifactorSignalStrategy(
        buy_threshold=70.0,  # 更高的买入门槛
        sell_threshold=50.0,  # 更高的卖出门槛
        max_hold_days=60,  # 限制持仓天数
        **kwargs,
    )
