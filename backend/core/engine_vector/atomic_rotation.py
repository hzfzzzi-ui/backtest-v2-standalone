from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from backend.core.core.types import Side


def _side_is(value: Any, expected: Side) -> bool:
    if value == expected:
        return True
    raw = str(value or "").strip().upper()
    expected_text = str(getattr(expected, "value", expected)).strip().upper()
    return raw == expected_text or raw.endswith(f".{expected_text}")


def _meta(order: Mapping[str, Any]) -> dict[str, Any]:
    return dict(order.get("meta") or {})


def _is_rotation_sell(order: Mapping[str, Any]) -> bool:
    meta = _meta(order)
    reason_code = str(order.get("reason_code", "") or "").strip().upper()
    return bool(_side_is(order.get("side"), Side.SELL) and (reason_code == "ROTATION_REPLACE" or meta.get("rotation_replace")))


def _is_rotation_buy(order: Mapping[str, Any]) -> bool:
    meta = _meta(order)
    return bool(_side_is(order.get("side"), Side.BUY) and meta.get("rotation_replace"))


def _sell_net(
    *,
    price: float,
    qty: int,
    slip_bps: float,
    comm_rate: float,
    comm_min: float,
    stamp_rate: float,
) -> float:
    shares = max(int(qty), 0)
    px = max(float(price), 0.0)
    if shares <= 0 or px <= 0.0:
        return 0.0
    fill_px = float(px) * (1.0 - float(slip_bps))
    gross = float(shares) * float(fill_px)
    comm = max(float(comm_min), gross * float(comm_rate))
    stax = gross * float(stamp_rate)
    return float(gross - comm - stax)


def _buy_net(
    *,
    price: float,
    qty: int,
    slip_bps: float,
    comm_rate: float,
    comm_min: float,
) -> float:
    shares = max(int(qty), 0)
    px = max(float(price), 0.0)
    if shares <= 0 or px <= 0.0:
        return 0.0
    fill_px = float(px) * (1.0 + float(slip_bps))
    gross = float(shares) * float(fill_px)
    comm = max(float(comm_min), gross * float(comm_rate))
    return float(gross + comm)


def _order_open(open_idx: Mapping[tuple[Any, str], float], day: date, symbol: str) -> float:
    return float(open_idx.get((day, str(symbol).lower()), 0.0) or 0.0)


def filter_atomic_rotation_pending_orders(
    *,
    orders: list[dict[str, Any]],
    day: date,
    cash: float,
    positions: Mapping[str, int],
    open_idx: Mapping[tuple[Any, str], float],
    slip_bps: float,
    comm_rate: float,
    comm_min: float,
    stamp_rate: float,
    min_trade_price: float = 0.0,
    position_cap: int | None = None,
    buy_blocked_symbols: set[str] | None = None,
    sell_blocked_symbols: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not orders:
        return []

    temp_cash = float(cash)
    temp_positions = {str(k).lower(): int(v) for k, v in dict(positions or {}).items() if int(v) > 0}
    consumed: set[int] = set()
    filtered: list[dict[str, Any]] = []
    blocked_buys = {str(symbol).lower() for symbol in set(buy_blocked_symbols or set())}
    blocked_sells = {str(symbol).lower() for symbol in set(sell_blocked_symbols or set())}

    def find_pair_buy(start_idx: int, sell_order: Mapping[str, Any]) -> int | None:
        sell_meta = _meta(sell_order)
        held_symbol = str(sell_order.get("symbol", "") or "").lower()
        candidate_symbol = str(sell_meta.get("rotation_candidate_symbol", "") or "").lower()
        if not candidate_symbol or not held_symbol:
            return None
        for j, candidate in enumerate(orders):
            if j == start_idx or j in consumed or not _is_rotation_buy(candidate):
                continue
            candidate_meta = _meta(candidate)
            if str(candidate.get("symbol", "") or "").lower() != candidate_symbol:
                continue
            if str(candidate_meta.get("rotation_held_symbol", "") or "").lower() != held_symbol:
                continue
            return int(j)
        return None

    for idx, order in enumerate(orders):
        if idx in consumed:
            continue
        normalized = dict(order)
        symbol = str(normalized.get("symbol", "") or "").lower()
        side = normalized.get("side")

        if _is_rotation_buy(normalized):
            consumed.add(idx)
            continue

        if _is_rotation_sell(normalized):
            pair_idx = find_pair_buy(idx, normalized)
            if pair_idx is None:
                consumed.add(idx)
                continue
            buy_order = dict(orders[pair_idx])
            held = int(temp_positions.get(symbol, 0))
            sell_qty = min(held, int(normalized.get("qty", 0) or 0))
            sell_px = _order_open(open_idx, day, symbol)
            buy_symbol = str(buy_order.get("symbol", "") or "").lower()
            buy_qty = int(buy_order.get("qty", 0) or 0)
            buy_px = _order_open(open_idx, day, buy_symbol)
            sell_net = _sell_net(
                price=float(sell_px),
                qty=int(sell_qty),
                slip_bps=float(slip_bps),
                comm_rate=float(comm_rate),
                comm_min=float(comm_min),
                stamp_rate=float(stamp_rate),
            )
            buy_net = _buy_net(
                price=float(buy_px),
                qty=int(buy_qty),
                slip_bps=float(slip_bps),
                comm_rate=float(comm_rate),
                comm_min=float(comm_min),
            )
            buy_allowed = not (float(min_trade_price) > 0 and float(buy_px) < float(min_trade_price))
            buy_allowed = bool(buy_allowed) and buy_symbol not in blocked_buys
            sell_allowed = symbol not in blocked_sells
            temp_positions_after_sell = dict(temp_positions)
            remain_after_sell = held - sell_qty
            if remain_after_sell > 0:
                temp_positions_after_sell[symbol] = int(remain_after_sell)
            else:
                temp_positions_after_sell.pop(symbol, None)
            buy_already_held = int(temp_positions_after_sell.get(buy_symbol, 0) or 0) > 0
            active_after_sell = int(sum(1 for qty in temp_positions_after_sell.values() if int(qty or 0) > 0))
            cap_allows_buy = (
                position_cap is None
                or bool(buy_already_held)
                or active_after_sell < int(position_cap)
            )
            if (
                sell_qty > 0
                and sell_px > 0.0
                and buy_qty > 0
                and buy_px > 0.0
                and buy_allowed
                and sell_allowed
                and cap_allows_buy
                and buy_net <= temp_cash + sell_net
            ):
                normalized = dict(normalized)
                normalized_meta = _meta(normalized)
                normalized_meta["rotation_atomic_fill_approved"] = True
                normalized["meta"] = normalized_meta
                buy_order = dict(buy_order)
                buy_meta = _meta(buy_order)
                buy_meta["rotation_atomic_fill_approved"] = True
                buy_order["meta"] = buy_meta
                filtered.append(normalized)
                filtered.append(buy_order)
                temp_positions = temp_positions_after_sell
                temp_cash += float(sell_net)
                temp_cash -= float(buy_net)
                temp_positions[buy_symbol] = int(temp_positions.get(buy_symbol, 0)) + int(buy_qty)
            consumed.add(idx)
            consumed.add(pair_idx)
            continue

        filtered.append(normalized)
        px = _order_open(open_idx, day, symbol)
        if _side_is(side, Side.SELL):
            held = int(temp_positions.get(symbol, 0))
            qty = min(held, int(normalized.get("qty", 0) or 0))
            if qty > 0 and px > 0.0 and symbol not in blocked_sells:
                temp_cash += _sell_net(
                    price=float(px),
                    qty=int(qty),
                    slip_bps=float(slip_bps),
                    comm_rate=float(comm_rate),
                    comm_min=float(comm_min),
                    stamp_rate=float(stamp_rate),
                )
                remain = held - qty
                if remain > 0:
                    temp_positions[symbol] = int(remain)
                else:
                    temp_positions.pop(symbol, None)
            continue
        if _side_is(side, Side.BUY):
            qty = int(normalized.get("qty", 0) or 0)
            if float(min_trade_price) > 0 and px < float(min_trade_price):
                continue
            if symbol in blocked_buys:
                continue
            held_before_buy = int(temp_positions.get(symbol, 0) or 0)
            active_positions = int(sum(1 for pos_qty in temp_positions.values() if int(pos_qty or 0) > 0))
            if (
                held_before_buy <= 0
                and position_cap is not None
                and active_positions >= int(position_cap)
            ):
                continue
            net = _buy_net(
                price=float(px),
                qty=int(qty),
                slip_bps=float(slip_bps),
                comm_rate=float(comm_rate),
                comm_min=float(comm_min),
            )
            if qty > 0 and px > 0.0 and net <= temp_cash:
                temp_cash -= float(net)
                temp_positions[symbol] = int(temp_positions.get(symbol, 0)) + int(qty)

    return filtered
