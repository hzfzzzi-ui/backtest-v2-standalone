from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class MAAtrStopStrategy(Strategy):
    fast: int = 5
    slow: int = 20
    order_size: int = 1000
    atr_n: int = 14
    atr_k: float = 2.5

    def __post_init__(self) -> None:
        Strategy.__init__(self)

    def _atr(self, sym_df: pd.DataFrame) -> float | None:
        if len(sym_df) < self.atr_n + 1:
            return None
        h = sym_df["high"].astype(float)
        l = sym_df["low"].astype(float)
        c = sym_df["close"].astype(float)
        prev_c = c.shift(1)
        tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_n).mean().iloc[-1]
        if pd.isna(atr):
            return None
        return float(atr)

    def _state_row(self, symbol: str) -> dict[str, Any]:
        row = self.state.get(symbol)
        if isinstance(row, dict):
            return row
        row = {"entry_price": None, "peak": None, "stop": None, "in_position": False}
        self.state[symbol] = row
        return row

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        out: list[Signal] = []
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]
        if day_data.empty:
            return out

        for symbol, sym_df in day_data.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")
            if len(sym_df) < max(self.slow + 1, self.atr_n + 1):
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
            atr = self._atr(sym_df)
            if atr is None:
                continue

            has_pos = symbol in positions and positions[symbol].total_qty > 0
            st = self._state_row(symbol)
            st["in_position"] = bool(has_pos)

            if has_pos:
                peak = float(st["peak"]) if st.get("peak") is not None else close_last
                peak = max(peak, close_last)
                stop = peak - self.atr_k * float(atr)
                st["peak"] = peak
                st["stop"] = stop
                meta = {"atr": round(float(atr), 6), "peak": round(peak, 6), "stop": round(stop, 6), "close_last": round(close_last, 6)}

                sell_qty = int(positions[symbol].sellable_qty)
                if sell_qty > 0 and close_last < stop:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol,
                            side=Side.SELL,
                            qty=sell_qty,
                            reason="ATR_STOP",
                            reason_code="ATR_STOP",
                            meta=meta,
                        )
                    )
                    st["in_position"] = False
                    continue
                if sell_qty > 0 and cross_down:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol,
                            side=Side.SELL,
                            qty=sell_qty,
                            reason="SMA_CROSS_DOWN",
                            reason_code="SMA_CROSS_DOWN",
                            meta=meta,
                        )
                    )
                    st["in_position"] = False
                    continue

            if cross_up and not has_pos:
                st["entry_price"] = close_last
                st["peak"] = close_last
                st["stop"] = close_last - self.atr_k * float(atr)
                st["in_position"] = True
                out.append(
                    Signal(
                        signal_date=day,
                        symbol=symbol,
                        side=Side.BUY,
                        qty=self.order_size,
                        reason="SMA_CROSS_UP",
                        reason_code="SMA_CROSS_UP",
                        meta={
                            "atr": round(float(atr), 6),
                            "peak": round(close_last, 6),
                            "stop": round(float(st["stop"]), 6),
                            "close_last": round(close_last, 6),
                        },
                    )
                )
        return out
