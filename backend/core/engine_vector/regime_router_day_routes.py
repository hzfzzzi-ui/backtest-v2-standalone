"""Day-route helpers for the regime router provider."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from backend.core.core.models import Signal
from backend.core.core.types import Side


def run_regime_router_trend_route(
    provider: Any,
    i: int,
    day: date,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    exit_rule_syms: set[str],
    sell_sigs: list[Signal],
    buy_sigs: list[Signal],
) -> None:
    mx = provider._mx

    for sym in list(provider._mr_symbols):
        if sym in exit_rule_syms:
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)
            continue
        qty = int(positions.get(sym, 0))
        if qty <= 0:
            continue

        col = provider._sym_to_col.get(sym)
        adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
        entry_px = provider._mr_entry_price.get(sym, 0.0)
        sell_reason = ""

        if entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - provider._mr_stop_loss_pct):
            sell_reason = "MR_STOP_LOSS"
            provider.mr_stop_loss_count += 1
        elif provider._mr_max_hold_days > 0 and sym in provider._mr_entry_day:
            if (day - provider._mr_entry_day[sym]).days >= provider._mr_max_hold_days:
                sell_reason = "MR_TIME_EXIT"
                provider.mr_time_exit_count += 1

        if sell_reason:
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=sell_reason,
                    reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - provider._mr_entry_day.get(sym, day)).days,
                        "regime_on": True,
                        "signal_mode": "TREND",
                    },
                )
            )
            exit_rule_syms.add(sym)
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)

    for sym, qty_v in list(positions.items()):
        qty = int(qty_v)
        if qty <= 0 or sym in exit_rule_syms or sym in provider._mr_symbols:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        if bool(provider._sma_sell_ok[i, col]):
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=f"{provider._ma_type}_CROSS_DOWN",
                    reason_code=f"{provider._ma_type}_CROSS_DOWN",
                    meta={
                        "triggered_rule": f"{provider._ma_type}_CROSS_DOWN",
                        "regime_on": True,
                        "signal_mode": "TREND",
                    },
                )
            )

    for c in provider._sma_cand_idx[i]:
        sym = mx.symbols[int(c)]
        if sym in positions and int(positions[sym]) > 0:
            continue
        if sym in provider._mr_symbols:
            continue
        provider.total_buy_signals += 1
        buy_sigs.append(
            Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=provider._trend_order_size,
                reason=f"{provider._ma_type}_CROSS_UP",
                reason_code=f"{provider._ma_type}_CROSS_UP",
                meta={"regime_on": True, "signal_mode": "TREND"},
            )
        )


def run_regime_router_mr_route(
    provider: Any,
    i: int,
    day: date,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    exit_rule_syms: set[str],
    sell_sigs: list[Signal],
    buy_sigs: list[Signal],
) -> None:
    mx = provider._mx

    for sym in list(provider._mr_symbols):
        if sym in exit_rule_syms:
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)
            continue
        qty = int(positions.get(sym, 0))
        if qty <= 0:
            continue

        col = provider._sym_to_col.get(sym)
        adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
        entry_px = provider._mr_entry_price.get(sym, 0.0)
        sell_reason = ""

        if col is not None and bool(provider._rsi_overbought[i, col]):
            sell_reason = "MR_RSI_OVERBOUGHT_SELL"
            provider.mr_rsi_overbought_sell_count += 1
        elif entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - provider._mr_stop_loss_pct):
            sell_reason = "MR_STOP_LOSS"
            provider.mr_stop_loss_count += 1
        elif provider._mr_max_hold_days > 0 and sym in provider._mr_entry_day:
            if (day - provider._mr_entry_day[sym]).days >= provider._mr_max_hold_days:
                sell_reason = "MR_TIME_EXIT"
                provider.mr_time_exit_count += 1

        if sell_reason:
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=sell_reason,
                    reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - provider._mr_entry_day.get(sym, day)).days,
                        "regime_on": False,
                        "signal_mode": "MEAN_REVERT",
                    },
                )
            )
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)

    for c in provider._rsi_cand_idx[i]:
        sym = mx.symbols[int(c)]
        if sym in positions and int(positions[sym]) > 0:
            continue
        adj_close = float(mx.close[i, int(c)])
        if np.isnan(adj_close) or adj_close <= 0:
            continue

        provider.total_buy_signals += 1
        provider.mr_rsi_oversold_buy_count += 1
        provider._mr_symbols.add(sym)
        provider._mr_entry_day[sym] = day
        provider._mr_entry_price[sym] = adj_close

        rsi_val = (
            float(provider._feats.rsi[i, int(c)])
            if not np.isnan(provider._feats.rsi[i, int(c)])
            else None
        )
        buy_sigs.append(
            Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=provider._mr_order_size,
                reason="MR_RSI_OVERSOLD_BUY",
                reason_code="MR_RSI_OVERSOLD_BUY",
                meta={
                    "triggered_rule": "MR_RSI_OVERSOLD_BUY",
                    "regime_on": False,
                    "signal_mode": "MEAN_REVERT",
                    "rsi_value": rsi_val,
                    "close": round(adj_close, 6),
                },
            )
        )


def run_regime_router_light_route(
    provider: Any,
    i: int,
    day: date,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    exit_rule_syms: set[str],
    sell_sigs: list[Signal],
    buy_sigs: list[Signal],
) -> None:
    mx = provider._mx

    for sym in list(provider._mr_symbols):
        if sym in exit_rule_syms:
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)
            continue
        qty = int(positions.get(sym, 0))
        if qty <= 0:
            continue
        col = provider._sym_to_col.get(sym)
        adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
        entry_px = provider._mr_entry_price.get(sym, 0.0)
        sell_reason = ""
        if entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - provider._mr_stop_loss_pct):
            sell_reason = "MR_STOP_LOSS"
            provider.mr_stop_loss_count += 1
        elif provider._mr_max_hold_days > 0 and sym in provider._mr_entry_day:
            if (day - provider._mr_entry_day[sym]).days >= provider._mr_max_hold_days:
                sell_reason = "MR_TIME_EXIT"
                provider.mr_time_exit_count += 1
        if sell_reason:
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=sell_reason,
                    reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - provider._mr_entry_day.get(sym, day)).days,
                        "regime_on": True,
                        "signal_mode": "TREND_LIGHT",
                    },
                )
            )
            exit_rule_syms.add(sym)
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)

    for sym, qty_v in list(positions.items()):
        qty = int(qty_v)
        if qty <= 0 or sym in exit_rule_syms or sym in provider._mr_symbols:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        if bool(provider._ema_light_sell_ok[i, col]):
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason="EMA_LIGHT_CROSS_DOWN",
                    reason_code="EMA_LIGHT_CROSS_DOWN",
                    meta={
                        "triggered_rule": "EMA_LIGHT_CROSS_DOWN",
                        "regime_on": True,
                        "signal_mode": "TREND_LIGHT",
                    },
                )
            )

    for c in provider._ema_light_cand_idx[i]:
        sym = mx.symbols[int(c)]
        if sym in positions and int(positions[sym]) > 0:
            continue
        if sym in provider._mr_symbols:
            continue
        provider.total_buy_signals += 1
        buy_sigs.append(
            Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=provider._trend_order_size,
                reason="EMA_LIGHT_CROSS_UP",
                reason_code="EMA_LIGHT_CROSS_UP",
                meta={"regime_on": True, "signal_mode": "TREND_LIGHT"},
            )
        )


def run_regime_router_exits_only_route(
    provider: Any,
    i: int,
    day: date,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    exit_rule_syms: set[str],
    sell_sigs: list[Signal],
    buy_sigs: list[Signal],
) -> None:
    mx = provider._mx

    for sym in list(provider._mr_symbols):
        if sym in exit_rule_syms:
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)
            continue
        qty = int(positions.get(sym, 0))
        if qty <= 0:
            continue
        col = provider._sym_to_col.get(sym)
        adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
        entry_px = provider._mr_entry_price.get(sym, 0.0)
        sell_reason = ""
        if entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - provider._mr_stop_loss_pct):
            sell_reason = "MR_STOP_LOSS"
            provider.mr_stop_loss_count += 1
        elif provider._mr_max_hold_days > 0 and sym in provider._mr_entry_day:
            if (day - provider._mr_entry_day[sym]).days >= provider._mr_max_hold_days:
                sell_reason = "MR_TIME_EXIT"
                provider.mr_time_exit_count += 1
        if sell_reason:
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=sell_reason,
                    reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - provider._mr_entry_day.get(sym, day)).days,
                        "regime_on": False,
                        "signal_mode": "NO_TRADE",
                    },
                )
            )
            exit_rule_syms.add(sym)
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)

    for sym, qty_v in list(positions.items()):
        qty = int(qty_v)
        if qty <= 0 or sym in exit_rule_syms or sym in provider._mr_symbols:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        if bool(provider._sma_sell_ok[i, col]):
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=f"{provider._ma_type}_CROSS_DOWN",
                    reason_code=f"{provider._ma_type}_CROSS_DOWN",
                    meta={
                        "triggered_rule": f"{provider._ma_type}_CROSS_DOWN",
                        "signal_mode": "NO_TRADE",
                    },
                )
            )


def run_regime_router_perstock_route(
    provider: Any,
    i: int,
    day: date,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    exit_rule_syms: set[str],
    sell_sigs: list[Signal],
    buy_sigs: list[Signal],
) -> None:
    mx = provider._mx
    regime_row = provider._regime_on[i]

    for sym in list(provider._mr_symbols):
        if sym in exit_rule_syms:
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)
            continue
        qty = int(positions.get(sym, 0))
        if qty <= 0:
            continue

        col = provider._sym_to_col.get(sym)
        adj_close = float(mx.close[i, col]) if col is not None and not np.isnan(mx.close[i, col]) else 0.0
        entry_px = provider._mr_entry_price.get(sym, 0.0)
        sell_reason = ""

        if col is not None and bool(provider._rsi_overbought[i, col]):
            sell_reason = "MR_RSI_OVERBOUGHT_SELL"
            provider.mr_rsi_overbought_sell_count += 1
        elif entry_px > 0 and adj_close > 0 and adj_close <= entry_px * (1.0 - provider._mr_stop_loss_pct):
            sell_reason = "MR_STOP_LOSS"
            provider.mr_stop_loss_count += 1
        elif provider._mr_max_hold_days > 0 and sym in provider._mr_entry_day:
            if (day - provider._mr_entry_day[sym]).days >= provider._mr_max_hold_days:
                sell_reason = "MR_TIME_EXIT"
                provider.mr_time_exit_count += 1

        if sell_reason:
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=sell_reason,
                    reason_code=sell_reason,
                    meta={
                        "triggered_rule": sell_reason,
                        "entry_price": round(entry_px, 6),
                        "held_days": (day - provider._mr_entry_day.get(sym, day)).days,
                        "regime_on": False,
                        "signal_mode": "MEAN_REVERT",
                    },
                )
            )
            exit_rule_syms.add(sym)
            provider._mr_symbols.discard(sym)
            provider._mr_entry_day.pop(sym, None)
            provider._mr_entry_price.pop(sym, None)

    for sym, qty_v in list(positions.items()):
        qty = int(qty_v)
        if qty <= 0 or sym in exit_rule_syms or sym in provider._mr_symbols:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        if bool(provider._sma_sell_ok[i, col]):
            sell_sigs.append(
                Signal(
                    signal_date=day,
                    symbol=sym,
                    side=Side.SELL,
                    qty=qty,
                    reason=f"{provider._ma_type}_CROSS_DOWN",
                    reason_code=f"{provider._ma_type}_CROSS_DOWN",
                    meta={
                        "triggered_rule": f"{provider._ma_type}_CROSS_DOWN",
                        "signal_mode": "TREND",
                    },
                )
            )

    for c in provider._sma_cand_idx[i]:
        col = int(c)
        sym = mx.symbols[col]
        if sym in positions and int(positions[sym]) > 0:
            continue
        if sym in provider._mr_symbols:
            continue
        if not bool(regime_row[col]):
            continue
        provider.total_buy_signals += 1
        buy_sigs.append(
            Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=provider._trend_order_size,
                reason=f"{provider._ma_type}_CROSS_UP",
                reason_code=f"{provider._ma_type}_CROSS_UP",
                meta={"regime_on": True, "signal_mode": "TREND"},
            )
        )

    for c in provider._rsi_cand_idx[i]:
        col = int(c)
        sym = mx.symbols[col]
        if sym in positions and int(positions[sym]) > 0:
            continue
        if bool(regime_row[col]):
            continue
        adj_close = float(mx.close[i, col])
        if np.isnan(adj_close) or adj_close <= 0:
            continue

        provider.total_buy_signals += 1
        provider.mr_rsi_oversold_buy_count += 1
        provider._mr_symbols.add(sym)
        provider._mr_entry_day[sym] = day
        provider._mr_entry_price[sym] = adj_close

        rsi_val = float(provider._feats.rsi[i, col]) if not np.isnan(provider._feats.rsi[i, col]) else None
        buy_sigs.append(
            Signal(
                signal_date=day,
                symbol=sym,
                side=Side.BUY,
                qty=provider._mr_order_size,
                reason="MR_RSI_OVERSOLD_BUY",
                reason_code="MR_RSI_OVERSOLD_BUY",
                meta={
                    "triggered_rule": "MR_RSI_OVERSOLD_BUY",
                    "regime_on": False,
                    "signal_mode": "MEAN_REVERT",
                    "rsi_value": rsi_val,
                    "close": round(adj_close, 6),
                },
            )
        )
