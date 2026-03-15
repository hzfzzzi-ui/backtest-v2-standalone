from __future__ import annotations

from math import floor


def calc_buy_slots(max_positions: int, positions_after_sell: int) -> int:
    max_pos = max(0, int(max_positions))
    pos_cnt = max(0, int(positions_after_sell))
    return max(0, max_pos - pos_cnt)


def calc_lot_qty(target_amount: float, open_price: float, lot_size: int) -> int:
    if target_amount <= 0 or open_price <= 0 or lot_size <= 0:
        return 0
    raw = floor(target_amount / open_price)
    return int(raw // lot_size * lot_size)
