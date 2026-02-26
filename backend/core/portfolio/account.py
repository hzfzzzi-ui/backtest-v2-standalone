from __future__ import annotations

from datetime import date

from backend.core.core.models import AccountState, Position


def unlock_day_state(account: AccountState, day: date) -> None:
    cash_release = account.locked_cash_by_date.pop(day, 0.0)
    if cash_release:
        account.cash_available += cash_release

    keys = [(sym, d) for (sym, d) in account.pending_sellable_by_date if d <= day]
    for key in keys:
        sym, _ = key
        qty = account.pending_sellable_by_date.pop(key)
        pos = account.positions.get(sym)
        if pos:
            pos.sellable_qty += qty


def get_or_create_position(account: AccountState, symbol: str) -> Position:
    if symbol not in account.positions:
        account.positions[symbol] = Position(symbol=symbol)
    return account.positions[symbol]


def apply_buy(account: AccountState, symbol: str, qty: int, price: float, unlock_date: date) -> None:
    pos = get_or_create_position(account, symbol)
    new_total = pos.total_qty + qty
    if new_total <= 0:
        return
    pos.avg_cost = ((pos.avg_cost * pos.total_qty) + (price * qty)) / new_total
    pos.total_qty = new_total
    account.pending_sellable_by_date[(symbol, unlock_date)] = account.pending_sellable_by_date.get((symbol, unlock_date), 0) + qty


def apply_sell(account: AccountState, symbol: str, qty: int) -> None:
    pos = get_or_create_position(account, symbol)
    pos.total_qty -= qty
    pos.sellable_qty -= qty
    if pos.total_qty <= 0:
        account.positions.pop(symbol, None)
