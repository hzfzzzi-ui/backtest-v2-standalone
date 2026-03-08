from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping, Sequence

from backend.core.core.types import Side


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


def apply_open_fills(runtime: Any, day: date, fills_today: Sequence[Any]) -> None:
    for raw_order in list(fills_today or ()):
        order = normalize_order_payload(raw_order)
        symbol = str(order["symbol"]).lower()
        px = float(runtime.open_idx.get((day, symbol), 0.0) or 0.0)
        if px <= 0:
            continue
        if order["side"] == Side.SELL:
            held = int(runtime.positions.get(symbol, 0))
            qty = min(held, int(order["qty"]))
            if qty <= 0:
                continue
            fill_px = px * (1.0 - runtime._slip_bps)
            gross = qty * fill_px
            comm = max(runtime._comm_min, gross * runtime._comm_rate)
            stax = gross * runtime._stamp_rate
            net = gross - comm - stax
            runtime.cash += net
            runtime._traded_value_today += gross
            runtime.positions[symbol] = held - qty
            if runtime.positions[symbol] <= 0:
                runtime.positions.pop(symbol, None)
                runtime.position_avg_cost.pop(symbol, None)
                if getattr(runtime.provider, "last_sell_day", None) is not None:
                    runtime.provider.last_sell_day[symbol] = day
                for clear_dict in list(getattr(runtime.provider, "extra_clear_dicts", []) or []):
                    clear_dict.pop(symbol, None)
                getattr(runtime.provider, "entry_day", {}).pop(symbol, None)
            runtime.trade_rows.append(
                {
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
                    "triggered_rule": str((order["meta"] or {}).get("triggered_rule", "")),
                    "break_streak": int((order["meta"] or {}).get("break_streak", 0) or 0),
                    "meta_json": json.dumps(order["meta"] or {}, ensure_ascii=False),
                }
            )
            continue

        if runtime._min_trade_price > 0 and px < runtime._min_trade_price:
            continue
        qty = int(order["qty"])
        fill_px = px * (1.0 + runtime._slip_bps)
        gross = qty * fill_px
        comm = max(runtime._comm_min, gross * runtime._comm_rate)
        net = gross + comm
        if qty <= 0 or net > runtime.cash:
            continue
        runtime.cash -= net
        runtime._traded_value_today += gross
        prev_qty = int(runtime.positions.get(symbol, 0))
        prev_avg = float(runtime.position_avg_cost.get(symbol, 0.0))
        new_qty = prev_qty + qty
        new_avg = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
        runtime.positions[symbol] = new_qty
        runtime.position_avg_cost[symbol] = float(new_avg)
        if prev_qty == 0 or bool(getattr(runtime.provider, "entry_day_overwrite", False)):
            getattr(runtime.provider, "entry_day", {})[symbol] = day
        if getattr(runtime.provider, "peak_state_on_buy", None) is not None:
            raw_close = float(runtime.close_idx.get((day, symbol), px) or px)
            runtime.provider.peak_state_on_buy.setdefault(symbol, raw_close)
        runtime.trade_rows.append(
            {
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
                "triggered_rule": str((order["meta"] or {}).get("triggered_rule", "")),
                "break_streak": int((order["meta"] or {}).get("break_streak", 0) or 0),
                "meta_json": json.dumps(order["meta"] or {}, ensure_ascii=False),
            }
        )
