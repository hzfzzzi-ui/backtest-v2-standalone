from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from backend.core.core.models import Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class SMACrossStrategy(Strategy):
    fast: int = 5
    slow: int = 20
    order_size: int = 1000
    ma_type: str = "SMA"
    # ATR 退出
    enable_atr_stop: bool = False
    atr_stop_k: float = 2.0
    enable_atr_trail: bool = False
    atr_trail_k: float = 3.0
    # 时间退出
    max_hold_days: int = 0
    # 持仓约束 / 再入场约束
    min_hold_days: int = 0
    cooldown_days: int = 0
    min_hold_exempt_reasons: list[str] = field(default_factory=lambda: ["ATR_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT", "TREND_BREAK_EXIT"])

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
            fast_ma = close.rolling(self.fast).mean().iloc[-1]
            slow_ma = close.rolling(self.slow).mean().iloc[-1]
            if pd.isna(fast_ma) or pd.isna(slow_ma):
                continue

            has_pos = symbol in positions and positions[symbol].total_qty > 0
            meta = {
                "signal_class": "TREND",
                "trend_signal_family": "MA_CROSS",
                "ma_type": "SMA",
                "fast_ma": round(float(fast_ma), 6),
                "slow_ma": round(float(slow_ma), 6),
            }
            if fast_ma > slow_ma and not has_pos:
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=self.order_size,
                        reason="SMA_CROSS_UP",
                        reason_code="SMA_CROSS_UP",
                        meta=meta,
                    )
                )
            elif fast_ma < slow_ma and has_pos:
                qty = int(positions[symbol].sellable_qty)
                if qty > 0:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol,
                            side=Side.SELL,
                            qty=qty,
                            reason="SMA_CROSS_DOWN",
                            reason_code="SMA_CROSS_DOWN",
                            meta=meta,
                        )
                    )
        return out
