from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.core.config.models import ExecutionConfig
from backend.core.core.models import AccountState
from backend.core.core.types import RejectReason, Side
from .price_limit import floor_lot, infer_limit_pct, limit_prices


@dataclass(slots=True)
class ConstraintResult:
    ok: bool
    qty: int
    reason: RejectReason | None = None
    note: str = ""
    limit_source: str = "none"
    limit_epsilon: float = 0.0
    limit_fallback_reason: str | None = None


def apply_cn_constraints(
    side: Side,
    desired_qty: int,
    bar: pd.Series,
    prev_close: float | None,
    account: AccountState,
    rules_row: pd.Series,
    cfg: ExecutionConfig,
) -> ConstraintResult:
    price = float(bar.get("open", 0.0) or 0.0)
    if price <= 0:
        return ConstraintResult(False, 0, RejectReason.PRICE_INVALID)

    suspended_flag = bar.get("is_suspended", bar.get("suspended_flag", None))
    volume = bar.get("volume", None)
    is_suspended = bool(suspended_flag) if suspended_flag is not None and not pd.isna(suspended_flag) else (pd.isna(volume) or float(volume) <= 0)
    if is_suspended:
        return ConstraintResult(False, 0, RejectReason.SUSPENDED)

    lot_size = int(rules_row.get("lot_size", cfg.lot_size) or cfg.lot_size)
    qty = floor_lot(desired_qty, lot_size)
    if qty <= 0:
        return ConstraintResult(False, 0, RejectReason.LOT_SIZE)

    tick_size = float(rules_row.get("tick_size", cfg.tick_size) or cfg.tick_size)
    epsilon = tick_size if cfg.limit_price_epsilon_mode == "tick_or_default" and tick_size > 0 else float(cfg.limit_price_epsilon_default)

    limit_source = "none"
    limit_up: float | None = None
    limit_down: float | None = None

    bar_limit_up = bar.get("limit_up", None)
    bar_limit_down = bar.get("limit_down", None)
    if bar_limit_up is not None and bar_limit_down is not None and not pd.isna(bar_limit_up) and not pd.isna(bar_limit_down):
        lu = float(bar_limit_up)
        ld = float(bar_limit_down)
        if lu > 0 and ld > 0 and lu > ld:
            limit_up = lu
            limit_down = ld
            limit_source = "db"

    fallback_reason: str | None = None
    if limit_source == "none" and prev_close is not None:
        limit_pct = float(rules_row.get("limit_pct", 0.0) or 0.0)
        if limit_pct <= 0:
            limit_pct = infer_limit_pct(
                str(bar.get("symbol", "")),
                str(rules_row.get("board", "MAIN")),
                cfg.limit_pct_default,
                cfg.limit_pct_star,
                cfg.limit_pct_kcb_gem,
            )
        limit_up, limit_down = limit_prices(
            float(prev_close),
            limit_pct,
            tick_size,
        )
        limit_source = "fallback_calc"
        fallback_reason = "MISSING_LIMIT_FIELDS"

    if limit_source != "none" and limit_up is not None and limit_down is not None:
        if side == Side.BUY and price >= (limit_up - epsilon):
            return ConstraintResult(
                False,
                0,
                RejectReason.LIMIT_UP,
                limit_source=limit_source,
                limit_epsilon=epsilon,
                limit_fallback_reason=fallback_reason,
            )
        if side == Side.SELL and price <= (limit_down + epsilon):
            return ConstraintResult(
                False,
                0,
                RejectReason.LIMIT_DOWN,
                limit_source=limit_source,
                limit_epsilon=epsilon,
                limit_fallback_reason=fallback_reason,
            )

    if side == Side.SELL:
        pos = account.positions.get(str(bar["symbol"]))
        if pos is None or pos.total_qty <= 0:
            return ConstraintResult(False, 0, RejectReason.NO_POSITION)
        if pos.sellable_qty <= 0:
            return ConstraintResult(False, 0, RejectReason.NO_SELLABLE)
        qty = min(qty, pos.sellable_qty)
        qty = floor_lot(qty, lot_size)
        if qty <= 0:
            return ConstraintResult(False, 0, RejectReason.NO_SELLABLE)

    # Liquidity cap
    if pd.isna(volume) or volume is None:
        if cfg.allow_liquidity_without_volume:
            max_fill = qty
        else:
            amount = bar.get("amount", None)
            close = bar.get("close", None)
            if amount is not None and close is not None and not pd.isna(amount) and not pd.isna(close) and float(close) > 0:
                max_fill = int((float(amount) / float(close)) * cfg.liquidity_cap_pct)
            else:
                return ConstraintResult(False, 0, RejectReason.LIQUIDITY, "volume missing")
    else:
        max_fill = int(float(volume) * cfg.liquidity_cap_pct)

    max_fill = floor_lot(max_fill, lot_size)
    if max_fill <= 0:
        return ConstraintResult(False, 0, RejectReason.LIQUIDITY)

    if qty > max_fill:
        return ConstraintResult(
            True,
            max_fill,
            None,
            "PARTIAL_BY_LIQUIDITY",
            limit_source=limit_source,
            limit_epsilon=epsilon,
            limit_fallback_reason=fallback_reason,
        )

    return ConstraintResult(
        True,
        qty,
        None,
        "",
        limit_source=limit_source,
        limit_epsilon=epsilon,
        limit_fallback_reason=fallback_reason,
    )
