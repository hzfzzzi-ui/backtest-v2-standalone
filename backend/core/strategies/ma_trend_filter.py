from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class MATrendFilterStrategy(Strategy):
    fast: int = 5
    slow: int = 20
    order_size: int = 1000
    trend_ma: int = 200
    use_benchmark_regime: bool = False

    def __post_init__(self) -> None:
        Strategy.__init__(self)

    def _trend_ok(self, sym_df: pd.DataFrame, close_last: float) -> bool:
        if len(sym_df) < self.trend_ma:
            return False
        trend = float(sym_df["close"].astype(float).rolling(self.trend_ma).mean().iloc[-1])
        if pd.isna(trend):
            return False
        return close_last > trend

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]
        if day_data.empty:
            return out

        for symbol, sym_df in day_data.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")
            if len(sym_df) < max(self.slow + 1, self.trend_ma):
                continue

            close = sym_df["close"].astype(float)
            fast_ma = close.rolling(self.fast).mean()
            slow_ma = close.rolling(self.slow).mean()
            i = len(sym_df) - 1
            fast_now = float(fast_ma.iloc[i])
            slow_now = float(slow_ma.iloc[i])
            fast_prev = float(fast_ma.iloc[i - 1])
            slow_prev = float(slow_ma.iloc[i - 1])
            if any(pd.isna(v) for v in (fast_now, slow_now, fast_prev, slow_prev)):
                continue

            cross_up = fast_now > slow_now and fast_prev <= slow_prev
            cross_down = fast_now < slow_now and fast_prev >= slow_prev
            close_last = float(close.iloc[-1])
            trend_ok = self._trend_ok(sym_df, close_last)
            has_pos = symbol in positions and positions[symbol].total_qty > 0

            meta = {
                "fast_ma": round(fast_now, 6),
                "slow_ma": round(slow_now, 6),
                "trend_ma": self.trend_ma,
                "trend_ok": bool(trend_ok),
                "use_benchmark_regime": bool(self.use_benchmark_regime),
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
                            reason="SMA_CROSS_DOWN",
                            reason_code="SMA_CROSS_DOWN",
                            meta=meta,
                        )
                    )
                continue

            if has_pos and not trend_ok:
                qty = int(positions[symbol].sellable_qty)
                if qty > 0:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol,
                            side=Side.SELL,
                            qty=qty,
                            reason="RISK_OFF_EXIT",
                            reason_code="RISK_OFF_EXIT",
                            meta=meta,
                        )
                    )
                continue

            if cross_up and not has_pos and trend_ok:
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=self.order_size,
                        reason="SMA_CROSS_UP_TREND_OK",
                        reason_code="SMA_CROSS_UP_TREND_OK",
                        meta=meta,
                    )
                )
        return out
