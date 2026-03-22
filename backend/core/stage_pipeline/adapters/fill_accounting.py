from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping, Sequence

from backend.core.core.types import Side
from backend.core.data.price_limits import round_price_to_tick
from backend.core.stage_pipeline.adapters.lineage import record_fill_outcome
from backend.core.stage_pipeline.contracts import AccountingSnapshot


def normalize_order_payload(raw_order: Any) -> dict[str, Any]:
    if isinstance(raw_order, Mapping):
        payload = dict(raw_order)
    else:
        payload = {
            "side": getattr(raw_order, "side"),
            "symbol": getattr(raw_order, "symbol"),
            "qty": getattr(raw_order, "qty"),
            "reason_code": getattr(raw_order, "reason_code", ""),
            "meta": getattr(raw_order, "meta", None),
        }
    return {
        "side": payload.get("side"),
        "symbol": str(payload.get("symbol", "")).lower(),
        "qty": int(payload.get("qty", 0) or 0),
        "reason_code": str(payload.get("reason_code", "") or ""),
        "meta": dict(payload.get("meta") or {}),
    }


def _bar_is_untradable(runtime: Any, day: date, symbol: str, side: Any, px: float) -> bool:
    key = (day, str(symbol).lower())
    suspended = bool(getattr(runtime, "suspended_idx", {}).get(key, False))
    if suspended:
        return True
    volume = getattr(runtime, "volume_idx", {}).get(key)
    if volume is not None and float(volume) <= 0:
        return True
    amount = getattr(runtime, "amount_idx", {}).get(key)
    if amount is not None and float(amount) <= 0:
        return True
    limit_up = round_price_to_tick(getattr(runtime, "limit_up_idx", {}).get(key), symbol)
    if limit_up is not None and str(side).upper() == str(Side.BUY):
        tol_up = abs(float(limit_up)) * 1e-4 + 1e-6
        if float(px) >= float(limit_up) - tol_up:
            return True
    limit_down = round_price_to_tick(getattr(runtime, "limit_down_idx", {}).get(key), symbol)
    if limit_down is not None and str(side).upper() == str(Side.SELL):
        tol_down = abs(float(limit_down)) * 1e-4 + 1e-6
        if float(px) <= float(limit_down) + tol_down:
            return True
    return False


def _defer_sell_order(runtime: Any, day: date, order: dict[str, Any], qty: int) -> None:
    meta = dict(order.get("meta") or {})
    meta["deferred_execution"] = True
    meta.setdefault("deferred_from_date", day.isoformat())
    meta["last_deferred_date"] = day.isoformat()
    getattr(runtime, "deferred_sell_orders", []).append(
        {
            "side": order["side"],
            "symbol": str(order["symbol"]).lower(),
            "qty": int(qty),
            "reason_code": str(order["reason_code"]),
            "meta": meta,
        }
    )


def capture_accounting_snapshot(
    runtime: Any,
    *,
    filled_orders: Sequence[Mapping[str, Any]] | None = None,
    trade_rows: Sequence[Mapping[str, Any]] | None = None,
    daily_marks: Mapping[str, Any] | None = None,
) -> AccountingSnapshot:
    return AccountingSnapshot(
        cash=float(getattr(runtime, "cash", 0.0) or 0.0),
        positions={str(symbol).lower(): int(qty or 0) for symbol, qty in dict(getattr(runtime, "positions", {}) or {}).items()},
        filled_orders=tuple(dict(item) for item in list(filled_orders or ())),
        trade_rows=tuple(dict(item) for item in list(trade_rows if trade_rows is not None else (getattr(runtime, "trade_rows", []) or ()))),
        daily_marks=dict(daily_marks or {}),
        counters=dict(getattr(runtime, "order_reject_reason_counts", {}) or {}),
    )


def _resolve_effective_entry_adj(
    *,
    prev_qty: int,
    prev_entry_adj: float | None,
    buy_qty: int,
    buy_entry_adj: float | None,
) -> float:
    prev_adj = float(prev_entry_adj or 1.0)
    buy_adj = float(buy_entry_adj or 1.0)
    if prev_adj <= 1e-8:
        prev_adj = 1.0
    if buy_adj <= 1e-8:
        buy_adj = 1.0
    denom = (float(prev_qty) / prev_adj) + (float(buy_qty) / buy_adj)
    total_qty = int(prev_qty) + int(buy_qty)
    if total_qty <= 0 or denom <= 1e-8:
        return 1.0
    return float(total_qty) / float(denom)


def apply_open_fills(runtime: Any, day: date, fills_today: Sequence[Any]) -> None:
    filled_orders_payload: list[dict[str, Any]] = []
    trade_rows_today: list[dict[str, Any]] = []
    for raw_order in list(fills_today or ()):
        order = normalize_order_payload(raw_order)
        symbol = str(order["symbol"]).lower()
        px = float(runtime.open_idx.get((day, symbol), 0.0) or 0.0)
        if px <= 0:
            if order["side"] == Side.SELL:
                held = int(runtime.positions.get(symbol, 0))
                qty = min(held, int(order["qty"]))
                if qty > 0:
                    record_fill_outcome(runtime, day=day, order=order, status="deferred", reason="OPEN_PRICE_UNAVAILABLE")
                    _defer_sell_order(runtime, day, order, qty)
                else:
                    record_fill_outcome(runtime, day=day, order=order, status="canceled", reason="NO_POSITION")
            else:
                record_fill_outcome(runtime, day=day, order=order, status="expired", reason="OPEN_PRICE_UNAVAILABLE")
            continue
        # Do not fabricate fills on suspended or zero-liquidity bars.
        if _bar_is_untradable(runtime, day, symbol, order["side"], px):
            if order["side"] == Side.SELL:
                holding_source = dict(getattr(runtime, "holding_sources", {}).get(symbol) or {})
                held = int(runtime.positions.get(symbol, 0))
                qty = min(held, int(order["qty"]))
                if qty > 0:
                    if holding_source.get("entry_reason_code"):
                        order["meta"].setdefault("entry_reason_code", str(holding_source.get("entry_reason_code") or ""))
                    record_fill_outcome(runtime, day=day, order=order, status="deferred", reason="UNTRADABLE_BAR")
                    _defer_sell_order(runtime, day, order, qty)
                else:
                    record_fill_outcome(runtime, day=day, order=order, status="canceled", reason="NO_POSITION")
            else:
                record_fill_outcome(runtime, day=day, order=order, status="expired", reason="UNTRADABLE_BAR")
            continue
        if order["side"] == Side.SELL:
            holding_source = dict(getattr(runtime, "holding_sources", {}).get(symbol) or {})
            held = int(runtime.positions.get(symbol, 0))
            qty = min(held, int(order["qty"]))
            if qty <= 0:
                record_fill_outcome(runtime, day=day, order=order, status="canceled", reason="NO_POSITION")
                continue
            risk_off_partial_state = getattr(runtime.provider, "_risk_off_partial_state", None)
            fill_px = px * (1.0 - runtime._slip_bps)
            gross = qty * fill_px
            comm = max(runtime._comm_min, gross * runtime._comm_rate)
            stax = gross * runtime._stamp_rate
            net = gross - comm - stax
            runtime.cash += net
            runtime._traded_value_today += gross
            fill_id = record_fill_outcome(runtime, day=day, order=order, status="filled")
            runtime.positions[symbol] = held - qty
            if runtime.positions[symbol] <= 0:
                runtime.positions.pop(symbol, None)
                runtime.position_avg_cost.pop(symbol, None)
                getattr(runtime, "position_entry_adj", {}).pop(symbol, None)
                getattr(runtime, "holding_sources", {}).pop(symbol, None)
                if getattr(runtime.provider, "last_sell_day", None) is not None:
                    runtime.provider.last_sell_day[symbol] = day
                for clear_dict in list(getattr(runtime.provider, "extra_clear_dicts", []) or []):
                    clear_dict.pop(symbol, None)
                getattr(runtime.provider, "entry_day", {}).pop(symbol, None)
            elif bool((order["meta"] or {}).get("risk_off_partial_mark_on_fill", False)) and isinstance(risk_off_partial_state, dict):
                risk_off_partial_state[symbol] = True
            trade_row = {
                "date": day.isoformat(),
                "symbol": symbol,
                "side": "SELL",
                "price": px,
                "fill_price": round(fill_px, 4),
                "qty": qty,
                "value": round(gross, 2),
                "commission": round(comm, 2),
                "stamp_tax": round(stax, 2),
                "slippage": round(abs(fill_px - px) * qty, 2),
                "net_amount": round(net, 2),
                "reason_code": str(order["reason_code"]),
                "signal_id": str((order["meta"] or {}).get("signal_id", "") or ""),
                "order_id": str((order["meta"] or {}).get("order_id", "") or ""),
                "fill_id": str(fill_id or ""),
                "triggered_rule": str((order["meta"] or {}).get("triggered_rule", "")),
                "break_streak": int((order["meta"] or {}).get("break_streak", 0) or 0),
                "exit_owner": str((order["meta"] or {}).get("exit_owner", "") or ""),
                "entry_alpha_id": str(holding_source.get("entry_alpha_id", "") or ""),
                "entry_sleeve_id": str(holding_source.get("entry_sleeve_id", "") or ""),
                "entry_reason_code": str(holding_source.get("entry_reason_code", "") or ""),
                "entry_date": holding_source.get("entry_date"),
                "meta_json": json.dumps(order["meta"] or {}, ensure_ascii=False),
            }
            runtime.trade_rows.append(trade_row)
            trade_rows_today.append(dict(trade_row))
            filled_orders_payload.append(
                {
                    "side": "SELL",
                    "symbol": symbol,
                    "qty": int(qty),
                    "reason_code": str(order["reason_code"]),
                }
            )
            continue

        if runtime._min_trade_price > 0 and px < runtime._min_trade_price:
            record_fill_outcome(runtime, day=day, order=order, status="expired", reason="MIN_TRADE_PRICE")
            continue
        qty = int(order["qty"])
        fill_px = px * (1.0 + runtime._slip_bps)
        gross = qty * fill_px
        comm = max(runtime._comm_min, gross * runtime._comm_rate)
        net = gross + comm
        if qty <= 0 or net > runtime.cash:
            record_fill_outcome(runtime, day=day, order=order, status="rejected", reason="INSUFFICIENT_CASH")
            continue
        runtime.cash -= net
        runtime._traded_value_today += gross
        fill_id = record_fill_outcome(runtime, day=day, order=order, status="filled")
        prev_qty = int(runtime.positions.get(symbol, 0))
        prev_avg = float(runtime.position_avg_cost.get(symbol, 0.0))
        prev_entry_adj = float(getattr(runtime, "position_entry_adj", {}).get(symbol, 1.0) or 1.0)
        meta = dict(order["meta"] or {})
        new_qty = prev_qty + qty
        new_avg = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
        runtime.positions[symbol] = new_qty
        runtime.position_avg_cost[symbol] = float(new_avg)
        buy_entry_adj = float(getattr(runtime, "adj_factor_idx", {}).get((day, symbol), 1.0) or 1.0)
        getattr(runtime, "position_entry_adj", {})[symbol] = _resolve_effective_entry_adj(
            prev_qty=prev_qty,
            prev_entry_adj=prev_entry_adj,
            buy_qty=qty,
            buy_entry_adj=buy_entry_adj,
        )
        risk_off_partial_state = getattr(runtime.provider, "_risk_off_partial_state", None)
        if prev_qty <= 0 and isinstance(risk_off_partial_state, dict):
            risk_off_partial_state.pop(symbol, None)
        if prev_qty == 0 or bool(getattr(runtime.provider, "entry_day_overwrite", False)):
            getattr(runtime.provider, "entry_day", {})[symbol] = day
            data_bundle = getattr(getattr(runtime, "request", None), "data_bundle", None)
            trading_days = list(getattr(data_bundle, "trading_days", []) or [])
            try:
                entry_day_index = int(trading_days.index(day))
            except Exception:
                entry_day_index = -1
            if entry_day_index >= 0 and isinstance(getattr(runtime.provider, "entry_bar_index", None), dict):
                runtime.provider.entry_bar_index[symbol] = entry_day_index
            if isinstance(getattr(runtime.provider, "entry_breakout_floor_raw", None), dict):
                try:
                    breakout_floor_raw = float(meta.get("entry_breakout_floor_raw", 0.0) or 0.0)
                except Exception:
                    breakout_floor_raw = 0.0
                if breakout_floor_raw > 0.0:
                    runtime.provider.entry_breakout_floor_raw[symbol] = float(breakout_floor_raw)
        if getattr(runtime.provider, "peak_state_on_buy", None) is not None:
            raw_close = float(runtime.close_idx.get((day, symbol), px) or px)
            runtime.provider.peak_state_on_buy.setdefault(symbol, raw_close)
        holding_source = {
            "entry_alpha_id": str(meta.get("entry_alpha_id", meta.get("alpha_id", "")) or ""),
            "entry_sleeve_id": str(meta.get("entry_sleeve_id", meta.get("sleeve_id", "")) or ""),
            "entry_reason_code": str(meta.get("entry_reason_code", order["reason_code"]) or ""),
            "entry_date": day,
        }
        if prev_qty <= 0 or bool(getattr(runtime.provider, "entry_day_overwrite", False)):
            getattr(runtime, "holding_sources", {})[symbol] = holding_source
        trade_row = {
            "date": day.isoformat(),
            "symbol": symbol,
            "side": "BUY",
            "price": px,
            "fill_price": round(fill_px, 4),
            "qty": qty,
            "value": round(gross, 2),
            "commission": round(comm, 2),
            "stamp_tax": 0.0,
            "slippage": round(abs(fill_px - px) * qty, 2),
            "net_amount": round(net, 2),
            "reason_code": str(order["reason_code"]),
            "signal_id": str((order["meta"] or {}).get("signal_id", "") or ""),
            "order_id": str((order["meta"] or {}).get("order_id", "") or ""),
            "fill_id": str(fill_id or ""),
            "triggered_rule": str((order["meta"] or {}).get("triggered_rule", "")),
            "break_streak": int((order["meta"] or {}).get("break_streak", 0) or 0),
            "exit_owner": "",
            "entry_alpha_id": str(holding_source.get("entry_alpha_id", "") or ""),
            "entry_sleeve_id": str(holding_source.get("entry_sleeve_id", "") or ""),
            "entry_reason_code": str(holding_source.get("entry_reason_code", "") or ""),
            "entry_date": holding_source.get("entry_date"),
            "meta_json": json.dumps(order["meta"] or {}, ensure_ascii=False),
        }
        runtime.trade_rows.append(trade_row)
        trade_rows_today.append(dict(trade_row))
        filled_orders_payload.append(
            {
                "side": "BUY",
                "symbol": symbol,
                "qty": int(qty),
                "reason_code": str(order["reason_code"]),
            }
        )
    runtime._last_trade_rows_today = tuple(trade_rows_today)
    runtime._last_accounting_snapshot = capture_accounting_snapshot(
        runtime,
        filled_orders=filled_orders_payload,
        trade_rows=trade_rows_today,
        daily_marks={"day": day.isoformat()},
    )
