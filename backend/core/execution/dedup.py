from __future__ import annotations

from datetime import date

from backend.core.config.models import ExecutionConfig
from backend.core.core.types import Side


class OrderDeduper:
    def should_skip(
        self,
        day: date,
        symbol: str,
        side: Side,
        positions: dict[str, object],
        orders_today: set[tuple[str, str]],
        cfg_exec: ExecutionConfig,
    ) -> tuple[bool, str | None]:
        key = (symbol, side.value)
        if cfg_exec.dedup_same_day and key in orders_today:
            return True, "SKIP_DUPLICATE_ORDER_TODAY"

        if side == Side.BUY and cfg_exec.block_buy_if_holding and (not cfg_exec.allow_pyramiding):
            pos = positions.get(symbol)
            if pos is not None and int(getattr(pos, "total_qty", 0)) > 0:
                return True, "SKIP_ALREADY_HOLDING"

        return False, None
