from __future__ import annotations

from dataclasses import dataclass


def calc_qty_fixed_value(order_value: float, price_ref: float, lot_size: int) -> int:
    if order_value <= 0 or price_ref <= 0 or lot_size <= 0:
        return 0
    raw_qty = int(order_value // price_ref)
    return (raw_qty // lot_size) * lot_size


def calc_effective_order_value(
    base_order_value: float,
    last_close: float,
    lot_size: int,
    lot_mode: str = "OFF",
) -> float:
    mode = str(lot_mode or "OFF").upper()
    base = float(base_order_value)
    if mode != "LOT100_MIN1LOT":
        return base
    if last_close <= 0 or lot_size <= 0:
        return base
    min_order_value_for_1_lot = float(last_close) * int(lot_size) * 1.05
    return max(base, min_order_value_for_1_lot)


@dataclass(slots=True)
class FixedValueSizer:
    order_value: float
    reserve_cash_ratio: float
    lot_size: int
    lot_mode: str = "OFF"

    def calc_buy_qty(self, account_cash: float, price_ref: float, last_close: float | None = None) -> tuple[int, str | None]:
        if price_ref <= 0:
            return 0, "SKIP_QTY_ZERO"
        mode = str(self.lot_mode or "OFF").upper()
        effective_lot_size = 1 if mode == "ODDLOT_1" else int(self.lot_size)
        reserve_cash = max(0.0, account_cash * float(self.reserve_cash_ratio))
        usable_cash = max(0.0, account_cash - reserve_cash)
        if usable_cash < (price_ref * max(1, effective_lot_size)):
            return 0, "SKIP_NO_CASH"
        effective_order_value = calc_effective_order_value(
            base_order_value=float(self.order_value),
            last_close=float(last_close if last_close is not None else price_ref),
            lot_size=max(1, int(self.lot_size)),
            lot_mode=mode,
        )
        capped_value = min(effective_order_value, usable_cash)
        qty = calc_qty_fixed_value(capped_value, price_ref, max(1, effective_lot_size))
        if qty <= 0:
            if usable_cash < (price_ref * max(1, effective_lot_size)):
                return 0, "SKIP_NO_CASH"
            return 0, "SKIP_QTY_ZERO"
        return qty, None
