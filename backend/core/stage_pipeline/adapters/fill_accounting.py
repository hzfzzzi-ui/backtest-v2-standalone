from __future__ import annotations

import json
import math
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


def _resolve_slippage_mode(runtime: Any) -> str:
    raw = str(
        getattr(runtime, "_slippage_mode", "")
        or getattr(getattr(runtime, "_cc", None), "slippage_mode", "")
        or "price_adjustment_only"
    ).strip().lower()
    if raw in {"price_adjustment_only", "cost_only"}:
        return raw
    return "price_adjustment_only"


def _resolve_fill_terms(
    *,
    px: float,
    qty: int,
    slip_bps: float,
    comm_rate: float,
    comm_min: float,
    stamp_rate: float,
    side: Any,
    slippage_mode: str,
) -> tuple[float, float, float, float, float, float]:
    if slippage_mode == "cost_only":
        fill_px = float(px)
        gross = float(qty) * fill_px
        slippage_cash = float(qty) * float(px) * float(slip_bps)
    elif side == Side.SELL:
        fill_px = float(px) * (1.0 - float(slip_bps))
        gross = float(qty) * fill_px
        slippage_cash = abs(fill_px - float(px)) * float(qty)
    else:
        fill_px = float(px) * (1.0 + float(slip_bps))
        gross = float(qty) * fill_px
        slippage_cash = abs(fill_px - float(px)) * float(qty)
    comm = max(float(comm_min), gross * float(comm_rate))
    stax = gross * float(stamp_rate) if side == Side.SELL else 0.0
    if side == Side.SELL:
        net = gross - comm - stax - (slippage_cash if slippage_mode == "cost_only" else 0.0)
    else:
        net = gross + comm + (slippage_cash if slippage_mode == "cost_only" else 0.0)
    return fill_px, gross, comm, stax, slippage_cash, net


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


def _resolve_pending_buy_position_cap(runtime: Any) -> int | None:
    current_day = getattr(runtime, "_current_day", None)
    controls = dict(current_day.get("controls") or {}) if isinstance(current_day, Mapping) else {}
    raw_cap = controls.get("effective_max_positions")
    if raw_cap in (None, ""):
        raw_cap = getattr(getattr(runtime, "request", None), "max_positions", None)
    if raw_cap in (None, ""):
        return None
    try:
        cap = int(raw_cap)
    except Exception:
        try:
            cap = int(float(raw_cap))
        except Exception:
            return None
    return max(int(cap), 0)


def capture_accounting_snapshot(
    runtime: Any,
    *,
    filled_orders: Sequence[Mapping[str, Any]] | None = None,
    trade_rows: Sequence[Mapping[str, Any]] | None = None,
    daily_marks: Mapping[str, Any] | None = None,
) -> AccountingSnapshot:
    planning_counters = dict(getattr(runtime, "order_reject_reason_counts", {}) or {})
    fill_counters = dict(getattr(runtime, "fill_reject_reason_counts", {}) or {})
    counters = dict(planning_counters)
    for reason, count in fill_counters.items():
        counters[f"FILL::{str(reason)}"] = int(count or 0)
    return AccountingSnapshot(
        cash=float(getattr(runtime, "cash", 0.0) or 0.0),
        dividend_receivable=float(getattr(runtime, "dividend_receivable", 0.0) or 0.0),
        positions={str(symbol).lower(): int(qty or 0) for symbol, qty in dict(getattr(runtime, "positions", {}) or {}).items()},
        filled_orders=tuple(dict(item) for item in list(filled_orders or ())),
        trade_rows=tuple(dict(item) for item in list(trade_rows if trade_rows is not None else (getattr(runtime, "trade_rows", []) or ()))),
        daily_marks=dict(daily_marks or {}),
        counters=counters,
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


def _previous_trading_day(runtime: Any, day: date) -> date | None:
    data_bundle = getattr(getattr(runtime, "request", None), "data_bundle", None)
    trading_days = list(getattr(data_bundle, "trading_days", []) or [])
    if not trading_days:
        return None
    try:
        day_index = int(trading_days.index(day))
    except Exception:
        return None
    if day_index <= 0:
        return None
    return trading_days[day_index - 1]


def _looks_like_share_transform(runtime: Any, day: date, symbol: str, prev_adj: float, current_adj: float) -> bool:
    adj_ratio = max(float(prev_adj) / float(current_adj), float(current_adj) / float(prev_adj))
    if not math.isfinite(adj_ratio) or adj_ratio < 1.1:
        return False
    previous_day = _previous_trading_day(runtime, day)
    if previous_day is None:
        return adj_ratio >= 2.0
    previous_close = float(getattr(runtime, "close_idx", {}).get((previous_day, symbol), 0.0) or 0.0)
    current_open = float(getattr(runtime, "open_idx", {}).get((day, symbol), 0.0) or 0.0)
    if previous_close <= 1e-8 or current_open <= 1e-8:
        return adj_ratio >= 2.0
    expected_open_ratio = float(prev_adj) / float(current_adj)
    observed_open_ratio = float(current_open) / float(previous_close)
    if not math.isfinite(expected_open_ratio) or not math.isfinite(observed_open_ratio):
        return False
    if expected_open_ratio <= 1e-8 or observed_open_ratio <= 1e-8:
        return False
    ratio_match = float(observed_open_ratio) / float(expected_open_ratio)
    return abs(math.log(ratio_match)) <= math.log(1.2)


def _apply_position_corporate_actions(runtime: Any, day: date) -> list[dict[str, Any]]:
    adjustments: list[dict[str, Any]] = []
    positions = dict(getattr(runtime, "positions", {}) or {})
    if not positions:
        return adjustments
    adj_factor_idx = getattr(runtime, "adj_factor_idx", {}) or {}
    position_entry_adj = getattr(runtime, "position_entry_adj", {}) or {}
    position_avg_cost = getattr(runtime, "position_avg_cost", {}) or {}
    for symbol, held_qty in positions.items():
        held = int(held_qty or 0)
        if held <= 0:
            continue
        current_adj = float(adj_factor_idx.get((day, symbol), 0.0) or 0.0)
        entry_adj = float(position_entry_adj.get(symbol, 1.0) or 1.0)
        if current_adj <= 1e-8 or entry_adj <= 1e-8:
            continue
        if math.isclose(current_adj, entry_adj, rel_tol=1e-9, abs_tol=1e-12):
            continue
        if not _looks_like_share_transform(runtime, day, symbol, entry_adj, current_adj):
            continue
        scaled_qty = float(held) * float(current_adj) / float(entry_adj)
        if not math.isfinite(scaled_qty) or scaled_qty <= 0.0:
            continue
        adjusted_qty = max(1, int(round(scaled_qty)))
        avg_cost = float(position_avg_cost.get(symbol, 0.0) or 0.0)
        adjusted_avg_cost = avg_cost
        if avg_cost > 0.0:
            adjusted_avg_cost = float(avg_cost) * float(entry_adj) / float(current_adj)
        runtime.positions[symbol] = adjusted_qty
        runtime.position_avg_cost[symbol] = float(adjusted_avg_cost)
        position_entry_adj[symbol] = float(current_adj)
        adjustments.append(
            {
                "symbol": symbol,
                "date": day.isoformat(),
                "prev_qty": held,
                "adjusted_qty": adjusted_qty,
                "prev_entry_adj": float(entry_adj),
                "current_adj": float(current_adj),
                "prev_avg_cost": float(avg_cost),
                "adjusted_avg_cost": float(adjusted_avg_cost),
            }
        )
    return adjustments


def _resolve_dividend_cash_timing_mode(runtime: Any) -> str:
    raw = str(getattr(runtime, "_dividend_cash_timing_mode", "") or "pay_date").strip().lower()
    if raw in {"ex_date", "pay_date"}:
        return raw
    return "pay_date"


def _record_dividend_cash_credit(
    runtime: Any,
    *,
    day: date,
    event: Mapping[str, Any],
    amount: float,
    reason_code: str,
) -> dict[str, Any]:
    row = {
        "date": day.isoformat(),
        "symbol": str(event.get("symbol") or "").lower(),
        "event_id": str(event.get("event_id") or ""),
        "cash_event_type": "DIVIDEND_CASH",
        "timing_mode": _resolve_dividend_cash_timing_mode(runtime),
        "reason_code": reason_code,
        "amount": round(float(amount), 2),
        "div_cash_per_share": round(float(event.get("div_cash") or 0.0), 8),
        "ex_date": str(event.get("ex_date") or ""),
        "pay_date": str(event.get("cash_pay_date") or ""),
    }
    getattr(runtime, "dividend_event_rows", []).append(dict(row))
    return row


def _record_dividend_receivable_event(
    runtime: Any,
    *,
    day: date,
    event: Mapping[str, Any],
    amount: float,
    action: str,
) -> dict[str, Any]:
    row = {
        "date": day.isoformat(),
        "symbol": str(event.get("symbol") or "").lower(),
        "event_id": str(event.get("event_id") or ""),
        "cash_event_type": "DIVIDEND_RECEIVABLE",
        "action": action,
        "timing_mode": _resolve_dividend_cash_timing_mode(runtime),
        "amount": round(float(amount), 2),
        "div_cash_per_share": round(float(event.get("div_cash") or 0.0), 8),
        "ex_date": str(event.get("ex_date") or ""),
        "pay_date": str(event.get("cash_pay_date") or ""),
    }
    getattr(runtime, "dividend_event_rows", []).append(dict(row))
    return row


def _apply_explicit_dividend_events(runtime: Any, day: date) -> dict[str, Any]:
    timing_mode = _resolve_dividend_cash_timing_mode(runtime)
    runtime._dividend_cash_credit_today = 0.0
    runtime._dividend_receivable_create_today = 0.0
    runtime._dividend_receivable_settle_today = 0.0
    ex_marks: list[dict[str, Any]] = []
    pay_marks: list[dict[str, Any]] = []

    positions = dict(getattr(runtime, "positions", {}) or {})
    processed_ex = getattr(runtime, "processed_dividend_ex_event_ids", None)
    if not isinstance(processed_ex, set):
        processed_ex = set()
        setattr(runtime, "processed_dividend_ex_event_ids", processed_ex)
    processed_cash = getattr(runtime, "processed_dividend_cash_event_ids", None)
    if not isinstance(processed_cash, set):
        processed_cash = set()
        setattr(runtime, "processed_dividend_cash_event_ids", processed_cash)
    pending_receivables = getattr(runtime, "pending_dividend_receivables", None)
    if not isinstance(pending_receivables, dict):
        pending_receivables = {}
        setattr(runtime, "pending_dividend_receivables", pending_receivables)

    previous_day = _previous_trading_day(runtime, day)
    position_entry_adj = getattr(runtime, "position_entry_adj", {}) or {}
    adj_factor_idx = getattr(runtime, "adj_factor_idx", {}) or {}

    for event in list((getattr(runtime, "dividend_events_ex_idx", {}) or {}).get(day, ())):
        event_id = str(event.get("event_id") or "").strip()
        if not event_id or event_id in processed_ex:
            continue
        processed_ex.add(event_id)
        symbol = str(event.get("symbol") or "").lower()
        held_qty = int(positions.get(symbol, 0) or 0)
        if held_qty <= 0:
            ex_marks.append({"event_id": event_id, "symbol": symbol, "action": "ignored_no_position", "amount": 0.0})
            continue
        div_cash_per_share = float(event.get("div_cash") or 0.0)
        gross_amount = float(held_qty) * float(div_cash_per_share)
        if not math.isfinite(gross_amount) or gross_amount <= 0.0:
            continue
        prev_adj = float(adj_factor_idx.get((previous_day, symbol), 0.0) or 0.0) if previous_day is not None else 0.0
        current_adj = float(adj_factor_idx.get((day, symbol), 0.0) or 0.0)
        prev_entry_adj = float(position_entry_adj.get(symbol, 1.0) or 1.0)
        rebased_entry_adj = prev_entry_adj
        if prev_adj > 1e-8 and current_adj > 1e-8:
            rebased_entry_adj = float(prev_entry_adj) * float(current_adj) / float(prev_adj)
            position_entry_adj[symbol] = float(rebased_entry_adj)

        mark = {
            "event_id": event_id,
            "symbol": symbol,
            "held_qty": int(held_qty),
            "div_cash_per_share": float(div_cash_per_share),
            "gross_amount": round(float(gross_amount), 2),
            "prev_entry_adj": float(prev_entry_adj),
            "rebased_entry_adj": float(rebased_entry_adj),
            "prev_adj": float(prev_adj) if prev_adj > 0 else None,
            "current_adj": float(current_adj) if current_adj > 0 else None,
            "timing_mode": timing_mode,
        }
        cash_pay_date = event.get("cash_pay_date") or day
        if timing_mode == "ex_date" or cash_pay_date == day:
            runtime.cash += float(gross_amount)
            runtime._dividend_cash_credit_today = float(runtime._dividend_cash_credit_today) + float(gross_amount)
            if cash_pay_date == day:
                processed_cash.add(event_id)
            mark["action"] = "cash_credit"
            mark["cash_credit_row"] = _record_dividend_cash_credit(
                runtime,
                day=day,
                event=event,
                amount=float(gross_amount),
                reason_code="DIVIDEND_EX_DATE_CREDIT",
            )
        else:
            pending_receivables[event_id] = {
                "event_id": event_id,
                "symbol": symbol,
                "amount": float(gross_amount),
                "ex_date": event.get("ex_date"),
                "cash_pay_date": cash_pay_date,
            }
            runtime.dividend_receivable = float(getattr(runtime, "dividend_receivable", 0.0) or 0.0) + float(gross_amount)
            runtime._dividend_receivable_create_today = float(runtime._dividend_receivable_create_today) + float(gross_amount)
            mark["action"] = "receivable_create"
            mark["receivable_row"] = _record_dividend_receivable_event(
                runtime,
                day=day,
                event=event,
                amount=float(gross_amount),
                action="create",
            )
        ex_marks.append(mark)

    if timing_mode == "pay_date":
        for event in list((getattr(runtime, "dividend_events_pay_idx", {}) or {}).get(day, ())):
            event_id = str(event.get("event_id") or "").strip()
            if not event_id or event_id in processed_cash:
                continue
            processed_cash.add(event_id)
            pending = dict(pending_receivables.pop(event_id, {}) or {})
            if not pending:
                pay_marks.append(
                    {"event_id": event_id, "symbol": str(event.get("symbol") or "").lower(), "action": "ignored_no_receivable", "amount": 0.0}
                )
                continue
            amount = float(pending.get("amount") or 0.0)
            if not math.isfinite(amount) or amount <= 0.0:
                continue
            runtime.dividend_receivable = float(getattr(runtime, "dividend_receivable", 0.0) or 0.0) - float(amount)
            runtime.cash += float(amount)
            runtime._dividend_cash_credit_today = float(runtime._dividend_cash_credit_today) + float(amount)
            runtime._dividend_receivable_settle_today = float(runtime._dividend_receivable_settle_today) + float(amount)
            pay_marks.append(
                {
                    "event_id": event_id,
                    "symbol": str(event.get("symbol") or "").lower(),
                    "action": "cash_settlement",
                    "amount": round(float(amount), 2),
                    "cash_credit_row": _record_dividend_cash_credit(
                        runtime,
                        day=day,
                        event=event,
                        amount=float(amount),
                        reason_code="DIVIDEND_PAY_DATE_CREDIT",
                    ),
                    "receivable_row": _record_dividend_receivable_event(
                        runtime,
                        day=day,
                        event=event,
                        amount=float(amount),
                        action="settle",
                    ),
                }
            )

    runtime.dividend_receivable = max(float(getattr(runtime, "dividend_receivable", 0.0) or 0.0), 0.0)
    return {
        "timing_mode": timing_mode,
        "ex_dividend_events": ex_marks,
        "pay_dividend_events": pay_marks,
        "dividend_cash_credit_today": round(float(getattr(runtime, "_dividend_cash_credit_today", 0.0) or 0.0), 2),
        "dividend_receivable_create_today": round(float(getattr(runtime, "_dividend_receivable_create_today", 0.0) or 0.0), 2),
        "dividend_receivable_settle_today": round(float(getattr(runtime, "_dividend_receivable_settle_today", 0.0) or 0.0), 2),
        "dividend_receivable_after": round(float(getattr(runtime, "dividend_receivable", 0.0) or 0.0), 2),
    }


def apply_open_fills(runtime: Any, day: date, fills_today: Sequence[Any]) -> None:
    filled_orders_payload: list[dict[str, Any]] = []
    trade_rows_today: list[dict[str, Any]] = []
    fill_reject_reason_counts_today: dict[str, int] = {}
    corporate_action_adjustments = _apply_position_corporate_actions(runtime, day)
    dividend_event_marks = _apply_explicit_dividend_events(runtime, day)
    cumulative_fill_reject_reason_counts = getattr(runtime, "fill_reject_reason_counts", None)
    if not isinstance(cumulative_fill_reject_reason_counts, dict):
        cumulative_fill_reject_reason_counts = {}
        setattr(runtime, "fill_reject_reason_counts", cumulative_fill_reject_reason_counts)
    slippage_mode = _resolve_slippage_mode(runtime)
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
            fill_px, gross, comm, stax, slippage_cash, net = _resolve_fill_terms(
                px=px,
                qty=qty,
                slip_bps=runtime._slip_bps,
                comm_rate=runtime._comm_rate,
                comm_min=runtime._comm_min,
                stamp_rate=runtime._stamp_rate,
                side=Side.SELL,
                slippage_mode=slippage_mode,
            )
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
                "slippage": round(slippage_cash, 2),
                "slippage_mode": slippage_mode,
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
        pending_position_cap = _resolve_pending_buy_position_cap(runtime)
        held_before_buy = int(runtime.positions.get(symbol, 0) or 0)
        active_positions = int(
            sum(1 for qty in dict(getattr(runtime, "positions", {}) or {}).values() if int(qty or 0) > 0)
        )
        if (
            held_before_buy <= 0
            and pending_position_cap is not None
            and active_positions >= int(pending_position_cap)
        ):
            reject_reason = "POSITION_CAP_REACHED"
            record_fill_outcome(runtime, day=day, order=order, status="rejected", reason=reject_reason)
            fill_reject_reason_counts_today[reject_reason] = int(fill_reject_reason_counts_today.get(reject_reason, 0)) + 1
            cumulative_fill_reject_reason_counts[reject_reason] = int(cumulative_fill_reject_reason_counts.get(reject_reason, 0)) + 1
            continue
        qty = int(order["qty"])
        fill_px, gross, comm, _stax_unused, slippage_cash, net = _resolve_fill_terms(
            px=px,
            qty=qty,
            slip_bps=runtime._slip_bps,
            comm_rate=runtime._comm_rate,
            comm_min=runtime._comm_min,
            stamp_rate=runtime._stamp_rate,
            side=Side.BUY,
            slippage_mode=slippage_mode,
        )
        if qty <= 0 or net > runtime.cash:
            reject_reason = "INSUFFICIENT_CASH"
            record_fill_outcome(runtime, day=day, order=order, status="rejected", reason=reject_reason)
            fill_reject_reason_counts_today[reject_reason] = int(fill_reject_reason_counts_today.get(reject_reason, 0)) + 1
            cumulative_fill_reject_reason_counts[reject_reason] = int(cumulative_fill_reject_reason_counts.get(reject_reason, 0)) + 1
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
            "slippage": round(slippage_cash, 2),
            "slippage_mode": slippage_mode,
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
    runtime._last_fill_reject_reason_counts_today = dict(fill_reject_reason_counts_today)
    runtime._last_accounting_snapshot = capture_accounting_snapshot(
        runtime,
        filled_orders=filled_orders_payload,
        trade_rows=trade_rows_today,
        daily_marks={
            "day": day.isoformat(),
            "corporate_action_adjustments": list(corporate_action_adjustments),
            "dividend_event_marks": dict(dividend_event_marks),
            "dividend_cash_credit_today": float(getattr(runtime, "_dividend_cash_credit_today", 0.0) or 0.0),
            "dividend_receivable_create_today": float(getattr(runtime, "_dividend_receivable_create_today", 0.0) or 0.0),
            "dividend_receivable_settle_today": float(getattr(runtime, "_dividend_receivable_settle_today", 0.0) or 0.0),
            "dividend_receivable_after": float(getattr(runtime, "dividend_receivable", 0.0) or 0.0),
        },
    )
