from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from backend.core.core.models import Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class EMACrossStrategy(Strategy):
    fast: int = 5
    slow: int = 20
    order_size: int = 1000
    ma_type: str = "EMA"
    # Universe 过滤
    min_price: float = 0.0
    # 市场环境
    regime_ma: int = 60
    # V2 个股趋势过滤
    enable_v2_trend_filter: bool = False
    v2_trend_short_ma: int = 20
    v2_trend_long_ma: int = 60
    enable_trend_accel: bool = False
    enable_atr_stop: bool = False
    atr_stop_k: float = 2.0
    enable_atr_trail: bool = False
    atr_trail_k: float = 3.0
    # 止盈 / 固定止损
    enable_take_profit: bool = False
    take_profit_mode: str = "pct"
    take_profit_pct: float = 0.10
    take_profit_atr_k: float = 3.0
    enable_fixed_stop_loss: bool = False
    fixed_stop_loss_pct: float = 0.05
    # 入场趋势过滤（基于信号 slow_ma）
    enable_entry_above_slow_ma: bool = False
    enable_entry_slow_ma_slope: bool = False
    entry_slope_lookback: int = 5
    # 时间退出
    max_hold_days: int = 0
    # 持仓约束 / 再入场约束
    min_hold_days: int = 0
    cooldown_days: int = 0
    min_hold_exempt_reasons: list[str] = field(default_factory=lambda: ["ATR_STOP_LOSS", "FIXED_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT", "TREND_BREAK_EXIT"])
    # 趋势退出
    enable_ma20_exit: bool = False
    enable_low10_exit: bool = False
    # 动量排名选股
    momentum_top_pct: float = 0.0
    # 行业趋势门控
    enable_sector_gate: bool = False
    sector_rank_window: int = 60
    sector_top_pct: float = 0.30

    def __post_init__(self) -> None:
        Strategy.__init__(self)

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, object]) -> list[Signal]:
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]
        if day_data.empty:
            return out

        for symbol, sym_df in day_data.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")
            if len(sym_df) < self.slow:
                continue
            close = sym_df["close"].astype(float)
            fast_ema = close.ewm(span=self.fast, adjust=False).mean().iloc[-1]
            slow_ema = close.ewm(span=self.slow, adjust=False).mean().iloc[-1]
            if pd.isna(fast_ema) or pd.isna(slow_ema):
                continue

            has_pos = symbol in positions and positions[symbol].total_qty > 0
            meta = {
                "signal_class": "TREND",
                "trend_signal_family": "MA_CROSS",
                "ma_type": "EMA",
                "fast_ema": round(float(fast_ema), 6),
                "slow_ema": round(float(slow_ema), 6),
            }
            if fast_ema > slow_ema and not has_pos:
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=self.order_size,
                        reason="EMA_CROSS_UP",
                        reason_code="EMA_CROSS_UP",
                        meta=meta,
                    )
                )
            elif fast_ema < slow_ema and has_pos:
                qty = int(positions[symbol].sellable_qty)
                if qty > 0:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol,
                            side=Side.SELL,
                            qty=qty,
                            reason="EMA_CROSS_DOWN",
                            reason_code="EMA_CROSS_DOWN",
                            meta=meta,
                        )
                    )
        return out
