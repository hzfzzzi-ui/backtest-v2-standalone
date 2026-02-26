from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.config.models import CostConfig, ExecutionConfig
from backend.core.core.models import AccountState, Order, Trade
from backend.core.core.types import OrderStatus, RejectReason, Side
from backend.core.execution.constraints_cn import apply_cn_constraints
from backend.core.execution.costs import compute_costs
from backend.core.portfolio.account import apply_buy, apply_sell


def execute_order_l1(
    order: Order,
    bar: pd.Series | None,
    prev_close: float | None,
    account: AccountState,
    rules_row: pd.Series,
    exec_cfg: ExecutionConfig,
    cost_cfg: CostConfig,
    trade_id: int,
    next_unlock_date: date,
    prev_close_missing_policy: str = "disable_limit_check",
    exec_audit: dict[str, object] | None = None,
) -> tuple[Order, Trade | None, float]:
    """Execute order at next-day open under CN constraints.

    Returns (mutated order, optional trade, realized_pnl_delta).
    """
    realized = 0.0
    if bar is None:
        order.status = OrderStatus.REJECTED
        order.reject_reason = RejectReason.NO_DATA
        return order, None, realized

    if prev_close is None and prev_close_missing_policy == "reject_all_trades_on_missing_prev_close":
        order.status = OrderStatus.REJECTED
        order.reject_reason = RejectReason.MISSING_PREV_CLOSE
        order.note = "MISSING_PREV_CLOSE"
        return order, None, realized

    c = apply_cn_constraints(order.side, order.qty, bar, prev_close, account, rules_row, exec_cfg)
    if exec_audit is not None and c.limit_source != "none":
        sources = exec_audit.setdefault("limit_sources", set())
        if isinstance(sources, set):
            sources.add(c.limit_source)
        eps_values = exec_audit.setdefault("limit_epsilons", [])
        if isinstance(eps_values, list):
            eps_values.append(float(c.limit_epsilon))
        if c.limit_source == "fallback_calc":
            fb = exec_audit.setdefault("fallback_count", 0)
            if isinstance(fb, int):
                exec_audit["fallback_count"] = fb + 1
            reasons = exec_audit.setdefault("fallback_reasons", set())
            if isinstance(reasons, set):
                reasons.add(c.limit_fallback_reason or "OTHER")
    if not c.ok:
        order.status = OrderStatus.REJECTED
        order.reject_reason = c.reason
        order.note = c.note
        return order, None, realized

    fill_qty = int(c.qty)
    px_open = float(bar["open"])
    slippage_sign = 1.0 if order.side == Side.BUY else -1.0
    fill_price = px_open * (1.0 + slippage_sign * cost_cfg.slippage_bps / 10000.0)

    stamp_tax_sell = bool(rules_row.get("stamp_tax_sell", True))
    cb = compute_costs(
        order.side,
        fill_qty,
        fill_price,
        cost_cfg,
        stamp_tax_sell=stamp_tax_sell,
        reference_price=px_open,
        fill_price=fill_price,
    )
    gross = fill_qty * fill_price
    # Slippage is already applied in fill_price; do not deduct it again from cash.
    net = gross + cb.commission + cb.stamp_tax if order.side == Side.BUY else gross - cb.commission - cb.stamp_tax

    if order.side == Side.BUY:
        if account.cash_available < net:
            order.status = OrderStatus.REJECTED
            order.reject_reason = RejectReason.NO_CASH
            return order, None, realized
        account.cash_total -= net
        account.cash_available -= net
        apply_buy(account, str(bar["symbol"]), fill_qty, fill_price, next_unlock_date)
    else:
        # realized pnl from avg cost
        avg_cost = account.positions[str(bar["symbol"])].avg_cost
        # Realized PnL uses slipped execution price; fees are commission + stamp tax only.
        realized = (fill_price - avg_cost) * fill_qty - (cb.commission + cb.stamp_tax)
        account.cash_total += net
        if exec_cfg.t_plus_one_cash:
            account.locked_cash_by_date[next_unlock_date] = account.locked_cash_by_date.get(next_unlock_date, 0.0) + net
        else:
            account.cash_available += net
        apply_sell(account, str(bar["symbol"]), fill_qty)

    order.status = OrderStatus.FILLED if fill_qty == order.qty else OrderStatus.PARTIAL
    order.filled_qty = fill_qty
    order.fill_price = fill_price
    order.note = c.note

    trade = Trade(
        trade_id=trade_id,
        order_id=order.order_id,
        trade_date=order.submit_date,
        symbol=str(bar["symbol"]),
        side=order.side,
        qty=fill_qty,
        price=fill_price,
        gross_amount=gross,
        commission=cb.commission,
        stamp_tax=cb.stamp_tax,
        slippage=cb.slippage,
        net_amount=net,
    )
    return order, trade, realized
