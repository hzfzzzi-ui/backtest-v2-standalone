from __future__ import annotations

from datetime import date

from backend.core.core.models import AccountState, DailySnapshot


def build_daily_snapshot(
    day: date,
    account: AccountState,
    close_map: dict[str, float],
    realized_pnl: float,
) -> DailySnapshot:
    market_value = 0.0
    unrealized = 0.0
    for sym, pos in account.positions.items():
        px = float(close_map.get(sym, 0.0))
        market_value += pos.total_qty * px
        unrealized += pos.total_qty * (px - pos.avg_cost)
    equity = account.cash_total + market_value
    return DailySnapshot(
        date=day,
        cash_total=account.cash_total,
        cash_available=account.cash_available,
        market_value=market_value,
        equity=equity,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized,
    )
