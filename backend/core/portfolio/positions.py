from __future__ import annotations

from backend.core.core.models import AccountState


def total_position_qty(account: AccountState, symbol: str) -> int:
    pos = account.positions.get(symbol)
    return 0 if pos is None else pos.total_qty
