"""
Regime Router — 市况路由器

根据 benchmark 实时 regime 状态，将信号生成委托给不同子策略:
- TREND 模式 → trend_strategy（如 SMA、EMA）
- MEAN_REVERT 模式 → mr_strategy（如 RSI Reversal）

RegimeDetector 独立负责市况检测，RegimeRouter 负责路由和 MR 遗留持仓管理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class RegimeDetector:
    """独立的市况检测器: benchmark close vs MA(regime_ma)。"""
    regime_ma: int = 60

    def detect(
        self, day_data: pd.DataFrame, day_ts: pd.Timestamp
    ) -> tuple[bool, float | None, float | None]:
        """返回 (regime_on, bench_close, bench_ma)。"""
        sym_lower = day_data["symbol"].astype(str).str.lower()
        bench_df = day_data[sym_lower.str.startswith("bench:")].sort_values("date")

        if len(bench_df) < self.regime_ma:
            return True, None, None

        bclose = bench_df["close"].astype(float)
        bench_close_val = float(bclose.iloc[-1])
        bench_ma_val = float(bclose.rolling(self.regime_ma).mean().iloc[-1])

        if pd.isna(bench_ma_val):
            return True, bench_close_val, None

        regime_on = bench_close_val > bench_ma_val
        return bool(regime_on), bench_close_val, bench_ma_val


@dataclass(slots=True)
class RegimeRouter(Strategy):
    """路由壳: 根据 regime 状态委托给 trend/mr 子策略。"""
    detector: RegimeDetector = field(default_factory=RegimeDetector)
    trend_strategy: Strategy = field(default=None)  # type: ignore[assignment]
    mr_strategy: Strategy = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        Strategy.__init__(self)
        # 跟踪哪些 symbol 是 MR 模式产生的持仓
        self.state.setdefault("mr_symbols", set())

    def generate_signals(
        self, day: date, history: pd.DataFrame, positions: dict[str, Position]
    ) -> list[Signal]:
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]
        if day_data.empty:
            return out

        # --- Regime 检测 ---
        regime_on, bench_close_val, bench_ma_val = self.detector.detect(day_data, day_ts)

        base_meta = {
            "regime_on": bool(regime_on),
            "signal_mode": "TREND" if regime_on else "MEAN_REVERT",
            "benchmark_close": bench_close_val,
            "benchmark_ma": bench_ma_val,
            "regime_ma": self.detector.regime_ma,
        }

        # MR 遗留持仓: 在 mr_symbols 中且仍有持仓
        mr_symbols: set[str] = self.state["mr_symbols"]
        active_mr = {s for s in mr_symbols if s in positions and positions[s].total_qty > 0}

        if regime_on:
            # 趋势模式: 对非 MR 持仓委托 trend_strategy
            trend_signals = self._delegate_trend(day, history, positions, skip_symbols=active_mr)
            for sig in trend_signals:
                sig.meta = {**base_meta, **sig.meta}
            out.extend(trend_signals)

            # MR 遗留持仓: 仅应用退出规则
            if active_mr and self.mr_strategy is not None:
                mr_exit_signals = self._delegate_mr_exit_only(day, history, positions, active_mr)
                for sig in mr_exit_signals:
                    sig.meta = {**base_meta, **sig.meta}
                    # 卖出后从 mr_symbols 移除
                    if sig.side == Side.SELL:
                        mr_symbols.discard(sig.symbol)
                out.extend(mr_exit_signals)
        else:
            # MR 模式: 委托 mr_strategy
            if self.mr_strategy is not None:
                mr_signals = self.mr_strategy.generate_signals(day, history, positions)
                for sig in mr_signals:
                    sig.meta = {**base_meta, **sig.meta}
                    # 买入时记录到 mr_symbols
                    if sig.side == Side.BUY:
                        mr_symbols.add(sig.symbol)
                    elif sig.side == Side.SELL:
                        mr_symbols.discard(sig.symbol)
                out.extend(mr_signals)

        # 清理已无持仓的 mr_symbols
        mr_symbols.difference_update(
            {s for s in mr_symbols if s not in positions or positions[s].total_qty <= 0}
        )

        return out

    def _delegate_trend(
        self,
        day: date,
        history: pd.DataFrame,
        positions: dict[str, Position],
        skip_symbols: set[str],
    ) -> list[Signal]:
        """委托 trend_strategy，过滤掉 MR 遗留持仓的 symbol。"""
        if self.trend_strategy is None:
            return []

        all_signals = self.trend_strategy.generate_signals(day, history, positions)
        if not skip_symbols:
            return all_signals

        # 过滤: 不对 MR 遗留持仓产生趋势信号
        return [s for s in all_signals if s.symbol not in skip_symbols]

    def _delegate_mr_exit_only(
        self,
        day: date,
        history: pd.DataFrame,
        positions: dict[str, Position],
        mr_symbols: set[str],
    ) -> list[Signal]:
        """对 MR 遗留持仓仅应用退出规则。"""
        # 如果 mr_strategy 有 generate_exit_only_signals 方法则使用
        if hasattr(self.mr_strategy, "generate_exit_only_signals"):
            return self.mr_strategy.generate_exit_only_signals(
                day, history, positions, mr_symbols
            )

        # 否则调用完整 generate_signals 并只保留 SELL 信号
        all_signals = self.mr_strategy.generate_signals(day, history, positions)
        return [
            s for s in all_signals
            if s.symbol in mr_symbols and s.side == Side.SELL
        ]
