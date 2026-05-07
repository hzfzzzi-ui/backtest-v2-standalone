from __future__ import annotations

from datetime import date
from math import isnan
from typing import Any

from backend.core.core.types import Side
from backend.core.portfolio.order_sizing import (
    build_sizing_context,
    estimate_buy_fill_net_cost,
    resolve_affordable_buy_qty,
    resolve_order_sizing,
)
from backend.core.portfolio.sizing import calc_buy_slots
from backend.core.portfolio.types import PortfolioOrder


def _safe_float(value: Any, *, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(fallback)
    if isnan(out):
        return float(fallback)
    return float(out)


def _safe_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    out = _safe_float(value, fallback=float("nan"))
    if isnan(out):
        return None
    return float(out)


def _build_candidate_audit_row(
    *,
    decision_date_s: str,
    symbol: str,
    strength: float | None,
    strength_ma: int,
    selected: bool,
    selected_rank: int | None,
    reject_reason: str,
    meta: dict[str, Any] | None = None,
    mf_score: float | None = None,
    mf_rank: int | None = None,
    final_score_value: float | None = None,
    final_score_rank: int | None = None,
    overlay_score: float | None = None,
    overlay_gate_on: bool = False,
    overlay_mode: str = "off",
    overlay_observation_date: date | None = None,
    overlay_score_source: str = "",
    cash_available: float | None = None,
    estimated_qty: int | None = None,
    estimated_amount: float | None = None,
    estimated_price: float | None = None,
    cash_blocked_flag: bool = False,
    cash_blocked_reason: str = "",
    decision_layer: str = "execution_kernel",
) -> dict[str, Any]:
    payload = dict(meta or {})
    canonical_final_score_value = (
        final_score_value
        if final_score_value is not None
        else (
            mf_score
            if mf_score is not None
            else _safe_float_or_none(payload.get("final_score"))
        )
    )
    canonical_final_score_rank = final_score_rank if final_score_rank is not None else mf_rank
    return {
        "date": decision_date_s,
        "symbol": str(symbol).lower(),
        "is_candidate": True,
        "strength": None if strength is None else float(strength),
        "strength_ma": int(strength_ma),
        "selected": bool(selected),
        "selected_flag": bool(selected),
        "selected_rank": selected_rank,
        "reject_reason": str(reject_reason or ""),
        "owner_system": str(
            payload.get("owner_system")
            or payload.get("sleeve_id")
            or payload.get("alpha_id")
            or ""
        ),
        "decision_layer": str(decision_layer or "execution_kernel"),
        "alpha_source": str(payload.get("alpha_source", "") or ""),
        "final_score": _safe_float_or_none(payload.get("final_score")),
        "final_score_value": (
            None if canonical_final_score_value is None else float(canonical_final_score_value)
        ),
        "final_score_rank": (
            None if canonical_final_score_rank is None else int(canonical_final_score_rank)
        ),
        "mf_score": None if mf_score is None else float(mf_score),
        "mf_rank": None if mf_rank is None else int(mf_rank),
        "overlay_score": None if overlay_score is None else float(overlay_score),
        "overlay_gate_on": bool(overlay_gate_on),
        "overlay_mode": str(overlay_mode or "off"),
        "overlay_observation_date": (
            overlay_observation_date.isoformat()
            if isinstance(overlay_observation_date, date)
            else ""
        ),
        "overlay_score_source": str(overlay_score_source or ""),
        "cash_available": None if cash_available is None else float(cash_available),
        "estimated_qty": None if estimated_qty is None else int(estimated_qty),
        "estimated_amount": None if estimated_amount is None else float(estimated_amount),
        "estimated_price": None if estimated_price is None else float(estimated_price),
        "cash_blocked_flag": bool(cash_blocked_flag),
        "cash_blocked_reason": str(cash_blocked_reason or ""),
    }


def _resolve_owner_system(sig_meta: dict[str, Any] | None) -> str:
    meta = dict(sig_meta or {})
    return str(
        meta.get("owner_system")
        or meta.get("sleeve_id")
        or meta.get("alpha_id")
        or ""
    ).strip()


def _resolve_formal_reason_codes(
    *,
    sig_meta: dict[str, Any] | None,
    reason_code: str,
) -> list[str]:
    meta = dict(sig_meta or {})
    raw_codes = meta.get("formal_reason_codes")
    if isinstance(raw_codes, (list, tuple)):
        codes = [str(code).strip() for code in raw_codes if str(code).strip()]
        if codes:
            return codes
    code = str(reason_code or "").strip()
    return [code] if code else []


def _source_only_sell_allowed(
    *,
    signal_meta: dict[str, Any] | None,
    holding_source: dict[str, Any] | None,
) -> bool:
    meta = dict(signal_meta or {})
    source = dict(holding_source or {})
    if str(meta.get("exit_owner", "") or "").strip() == "global_risk_override":
        return True
    if not source:
        return True
    signal_owner_candidates = {
        str(meta.get("owner_system", "") or "").strip(),
        str(meta.get("sleeve_id", "") or "").strip(),
        str(meta.get("alpha_id", "") or "").strip(),
        str(meta.get("entry_sleeve_id", "") or "").strip(),
        str(meta.get("entry_alpha_id", "") or "").strip(),
    }
    holding_owner_candidates = {
        str(source.get("entry_sleeve_id", "") or "").strip(),
        str(source.get("entry_alpha_id", "") or "").strip(),
    }
    signal_owner_candidates.discard("")
    holding_owner_candidates.discard("")
    if not signal_owner_candidates or not holding_owner_candidates:
        return True
    return bool(signal_owner_candidates & holding_owner_candidates)


def build_execution_orders_from_candidate_plan(
    *,
    positions: dict[str, int],
    cash_available: float,
    nav_close: float,
    max_positions: int,
    lot_size: int,
    sell_signals: list[Any],
    planned_items: list[dict[str, Any]],
    next_open: dict[str, float],
    decision_date: date | None = None,
    candidate_audit: list[dict[str, Any]] | None = None,
    debug_plan: dict[str, Any] | None = None,
    strength_ma: int = 120,
    overlay_mode: str = "off",
    overlay_gate_on_today: bool = False,
    overlay_observation_date: date | None = None,
    overlay_score_source: str = "",
    slip_bps: float = 0.0,
    comm_rate: float = 0.0,
    comm_min: float = 0.0,
    base_order_value: float = 0.0,
    risk_amount: float = 0.0,
    atr_stop_k: float = 2.0,
    weight_mode: str = "equal",
    min_positions: int = 10,
    atr_close_map: dict[str, tuple[float, float]] | None = None,
    holding_sources: dict[str, Any] | None = None,
) -> list[PortfolioOrder]:
    orders: list[PortfolioOrder] = []
    future_positions = {str(k).lower(): int(v) for k, v in dict(positions or {}).items() if int(v) > 0}
    est_cash = float(cash_available)
    decision_date_s = decision_date.isoformat() if isinstance(decision_date, date) else ""
    reject_reason_counts: dict[str, int] = {}
    source_only_rejected_sells: list[dict[str, Any]] = []
    normalized_holding_sources = {
        str(symbol).lower(): dict(source or {})
        for symbol, source in dict(holding_sources or {}).items()
    }

    for raw_signal in list(sell_signals or ()):
        sym = str(getattr(raw_signal, "symbol", "") or "").lower()
        held = int(future_positions.get(sym, 0))
        if held <= 0:
            continue
        signal_meta = dict(getattr(raw_signal, "meta", {}) or {})
        holding_source = dict(normalized_holding_sources.get(sym) or {})
        if not _source_only_sell_allowed(signal_meta=signal_meta, holding_source=holding_source):
            reject_reason = "SOURCE_ONLY_OWNER_MISMATCH"
            reject_reason_counts[reject_reason] = int(reject_reason_counts.get(reject_reason, 0)) + 1
            source_only_rejected_sells.append(
                {
                    "owner_system": _resolve_owner_system(signal_meta),
                    "symbol": sym,
                    "holding_entry_alpha_id": str(holding_source.get("entry_alpha_id") or ""),
                    "holding_entry_sleeve_id": str(holding_source.get("entry_sleeve_id") or ""),
                }
            )
            if candidate_audit is not None:
                candidate_audit.append(
                    _build_candidate_audit_row(
                        decision_date_s=decision_date_s,
                        symbol=sym,
                        strength=None,
                        strength_ma=int(strength_ma),
                        selected=False,
                        selected_rank=None,
                        reject_reason=reject_reason,
                        meta=signal_meta,
                        decision_layer="execution_kernel",
                    )
                )
            continue
        sig_qty = int(getattr(raw_signal, "qty", 0) or 0)
        qty = held if sig_qty <= 0 else min(held, sig_qty)
        px = float(next_open.get(sym, 0.0) or 0.0)
        if qty <= 0 or px <= 0.0:
            continue
        orders.append(
            PortfolioOrder(
                side=Side.SELL,
                symbol=sym,
                qty=qty,
                reason_code=str(getattr(raw_signal, "reason_code", "") or getattr(raw_signal, "reason", "") or "SELL"),
                meta=(dict(getattr(raw_signal, "meta", {}) or {}) or None),
            )
        )
        remain = held - qty
        if remain > 0:
            future_positions[sym] = remain
        else:
            future_positions.pop(sym, None)
        est_cash += float(qty) * float(px)

    positions_after_sell = len([qty for qty in future_positions.values() if int(qty) > 0])
    slots = calc_buy_slots(int(max_positions), int(positions_after_sell))
    selected_n = 0
    slot_pass_symbols: list[str] = []
    cash_lot_pass_symbols: list[str] = []
    buy_exec_plan: list[dict[str, Any]] = []
    annotated_items: list[dict[str, Any]] = []
    sizing_context = build_sizing_context(
        items=planned_items,
        nav_close=float(nav_close),
        max_positions=int(max_positions),
        min_positions=int(min_positions),
        base_order_value=float(base_order_value),
        weight_mode=str(weight_mode),
        atr_close_map=atr_close_map,
    )

    for raw_item in list(planned_items or ()):
        item = dict(raw_item or {})
        sym = str(item.get("symbol", "") or "").lower()
        signal = item.get("signal")
        signal_meta = dict(getattr(signal, "meta", {}) or {})
        pre_reject_reason = str(item.get("pre_reject_reason", "") or "").strip()

        if pre_reject_reason:
            item["reject_reason"] = pre_reject_reason
            reject_reason_counts[pre_reject_reason] = int(reject_reason_counts.get(pre_reject_reason, 0)) + 1
            annotated_items.append(item)
            continue

        if selected_n >= int(slots):
            insufficient_history = bool(item.get("strength") is None) or (
                item.get("mf_rank") is not None and item.get("mf_score") is None
            )
            reject_reason = "INSUFFICIENT_HISTORY" if insufficient_history else "NOT_IN_TOPK"
            item["reject_reason"] = reject_reason
            reject_reason_counts[reject_reason] = int(reject_reason_counts.get(reject_reason, 0)) + 1
            annotated_items.append(item)
            continue

        slot_pass_symbols.append(sym)
        px = float(item.get("price", next_open.get(sym, 0.0)) or 0.0)
        order_value_scale = float(item.get("order_value_scale", 1.0) or 1.0)
        sizing = resolve_order_sizing(
            sig_meta=signal_meta,
            symbol=sym,
            price=float(px),
            nav_close=float(nav_close),
            order_value_scale=float(order_value_scale),
            risk_amount=float(risk_amount),
            atr_stop_k=float(atr_stop_k),
            sizing_context=sizing_context,
            lot_size=int(lot_size),
        )
        target_amount_scaled = float(sizing["target_amount_scaled"])
        qty = int(sizing["qty"])
        if qty < int(lot_size):
            item["reject_reason"] = "SKIP_QTY_ZERO"
            reject_reason_counts["SKIP_QTY_ZERO"] = int(reject_reason_counts.get("SKIP_QTY_ZERO", 0)) + 1
            annotated_items.append(item)
            continue

        cost = float(
            estimate_buy_fill_net_cost(
                price=float(px),
                qty=int(qty),
                slip_bps=float(slip_bps),
                comm_rate=float(comm_rate),
                comm_min=float(comm_min),
            )
        )
        if cost > float(est_cash):
            affordable_qty = int(
                resolve_affordable_buy_qty(
                    price=float(px),
                    requested_qty=int(qty),
                    lot_size=int(lot_size),
                    cash_available=float(est_cash),
                    slip_bps=float(slip_bps),
                    comm_rate=float(comm_rate),
                    comm_min=float(comm_min),
                )
            )
            if affordable_qty >= int(lot_size):
                qty = int(affordable_qty)
                target_amount_scaled = min(float(target_amount_scaled), float(qty) * float(px))
                cost = float(
                    estimate_buy_fill_net_cost(
                        price=float(px),
                        qty=int(qty),
                        slip_bps=float(slip_bps),
                        comm_rate=float(comm_rate),
                        comm_min=float(comm_min),
                    )
                )

        gross_order_value = float(qty) * float(px)
        item["estimated_qty"] = int(qty)
        item["estimated_amount"] = float(cost)
        item["estimated_price"] = float(px)
        if cost > float(est_cash):
            item["reject_reason"] = "SKIP_NO_CASH"
            item["cash_available"] = float(est_cash)
            item["cash_blocked_flag"] = True
            item["cash_blocked_reason"] = "SKIP_NO_CASH"
            reject_reason_counts["SKIP_NO_CASH"] = int(reject_reason_counts.get("SKIP_NO_CASH", 0)) + 1
            annotated_items.append(item)
            continue

        cash_lot_pass_symbols.append(sym)
        mf_score = item.get("mf_score")
        mf_rank = item.get("mf_rank")
        final_score_value = item.get("final_score_value", mf_score)
        final_score_rank = item.get("final_score_rank", mf_rank)
        effective_overlay_gate_on = bool(item.get("overlay_gate_on", overlay_gate_on_today))
        effective_overlay_mode = str(item.get("overlay_mode", overlay_mode) or "off")
        effective_overlay_observation_date = item.get("overlay_observation_date", overlay_observation_date)
        effective_overlay_score_source = str(item.get("overlay_score_source", overlay_score_source) or "")
        effective_overlay_score = _safe_float_or_none(item.get("overlay_score"))
        score_weight_score = item.get("score_weight_score")
        score_weight_raw_scale = float(item.get("score_weight_raw_scale", item.get("score_weight_scale", 1.0)) or 1.0)
        score_weight_scale = float(item.get("score_weight_scale", 1.0) or 1.0)
        rotation_pair = dict(item.get("rotation_pair") or {}) if isinstance(item.get("rotation_pair"), dict) else {}
        meta = {
            **signal_meta,
            "requested_target_weight": _safe_float_or_none(signal_meta.get("target_weight")),
            "final_score_value": None if final_score_value is None else float(final_score_value),
            "final_score_rank": None if final_score_rank is None else int(final_score_rank),
            "mf_score": None if mf_score is None else float(mf_score),
            "mf_rank": None if mf_rank is None else int(mf_rank),
            "mf_concentrated": bool(item.get("mf_concentrated", False)),
            "mf_rank_tilt_scale": float(item.get("mf_rank_tilt_scale", 1.0) or 1.0),
            "score_weight_score": None if score_weight_score is None else float(score_weight_score),
            "score_weight_raw_scale": float(score_weight_raw_scale),
            "score_weight_scale": float(score_weight_scale),
            "moneyflow_overlay_score": effective_overlay_score,
            "moneyflow_overlay_gate_on": bool(effective_overlay_gate_on),
            "moneyflow_overlay_mode": str(effective_overlay_mode),
            "moneyflow_overlay_observation_date": (
                effective_overlay_observation_date.isoformat()
                if isinstance(effective_overlay_observation_date, date)
                else str(effective_overlay_observation_date or "")
            ),
            "moneyflow_overlay_score_source": str(effective_overlay_score_source),
            "order_value_final": float(gross_order_value),
            "order_net_cost": float(cost),
            "target_weight": (
                float(gross_order_value) / float(nav_close)
                if float(nav_close) > 0.0
                else None
            ),
            "owner_system": _resolve_owner_system(signal_meta),
            "formal_reason_codes": _resolve_formal_reason_codes(
                sig_meta=signal_meta,
                reason_code=str(getattr(signal, "reason_code", "") or getattr(signal, "reason", "") or "BUY"),
            ),
            **rotation_pair,
        }
        orders.append(
            PortfolioOrder(
                side=Side.BUY,
                symbol=sym,
                qty=qty,
                reason_code=str(getattr(signal, "reason_code", "") or getattr(signal, "reason", "") or "BUY"),
                order_value_scale=float(order_value_scale),
                trend_tier=str(signal_meta.get("trend_tier", "")),
                strong_trend=bool(signal_meta.get("strong_trend", False)),
                meta=meta,
            )
        )
        est_cash -= float(cost)
        future_positions[sym] = int(future_positions.get(sym, 0)) + int(qty)
        selected_n += 1
        item["selected"] = True
        item["selected_rank"] = int(selected_n)
        buy_exec_plan.append(
            {
                "symbol": sym,
                "qty": int(qty),
                "price": float(px),
                "cost": float(cost),
                "gross_order_value": float(gross_order_value),
                "cash_after_each": float(est_cash),
                "order_value_scale": float(order_value_scale),
                "final_score_value": None if final_score_value is None else float(final_score_value),
                "final_score_rank": None if final_score_rank is None else int(final_score_rank),
                "mf_score": None if mf_score is None else float(mf_score),
                "mf_rank": None if mf_rank is None else int(mf_rank),
                "mf_concentrated": bool(item.get("mf_concentrated", False)),
                "mf_rank_tilt_scale": float(item.get("mf_rank_tilt_scale", 1.0) or 1.0),
                "score_weight_score": None if score_weight_score is None else float(score_weight_score),
                "score_weight_raw_scale": float(score_weight_raw_scale),
                "score_weight_scale": float(score_weight_scale),
            }
        )
        annotated_items.append(item)

    if candidate_audit is not None:
        for item in annotated_items:
            signal = item.get("signal")
            signal_meta = dict(getattr(signal, "meta", {}) or {})
            effective_overlay_gate_on = bool(item.get("overlay_gate_on", overlay_gate_on_today))
            effective_overlay_mode = str(item.get("overlay_mode", overlay_mode) or "off")
            effective_overlay_observation_date = item.get("overlay_observation_date", overlay_observation_date)
            effective_overlay_score_source = str(item.get("overlay_score_source", overlay_score_source) or "")
            candidate_audit.append(
                _build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=str(item.get("symbol", "")).lower(),
                    strength=(None if item.get("strength") is None else float(item.get("strength"))),
                    strength_ma=int(strength_ma),
                    selected=bool(item.get("selected", False)),
                    selected_rank=item.get("selected_rank"),
                    reject_reason=str(item.get("reject_reason", "") or ""),
                    meta=signal_meta,
                    final_score_value=_safe_float_or_none(item.get("final_score_value")),
                    final_score_rank=(int(item["final_score_rank"]) if item.get("final_score_rank") is not None else None),
                    mf_score=_safe_float_or_none(item.get("mf_score")),
                    mf_rank=(int(item["mf_rank"]) if item.get("mf_rank") is not None else None),
                    overlay_score=_safe_float_or_none(item.get("overlay_score")),
                    overlay_gate_on=bool(effective_overlay_gate_on),
                    overlay_mode=str(effective_overlay_mode),
                    overlay_observation_date=effective_overlay_observation_date,
                    overlay_score_source=effective_overlay_score_source,
                    cash_available=_safe_float_or_none(item.get("cash_available")),
                    estimated_qty=(int(item["estimated_qty"]) if item.get("estimated_qty") is not None else None),
                    estimated_amount=_safe_float_or_none(item.get("estimated_amount")),
                    estimated_price=_safe_float_or_none(item.get("estimated_price")),
                    cash_blocked_flag=bool(item.get("cash_blocked_flag", False)),
                    cash_blocked_reason=str(item.get("cash_blocked_reason", "") or ""),
                    decision_layer="execution_kernel",
                )
            )

    if debug_plan is not None:
        debug_plan.setdefault("buy_candidates_count", int(len(list(planned_items or ()))))
        debug_plan["buy_slots"] = int(slots)
        debug_plan["selected_symbols"] = [str(item.get("symbol", "")).lower() for item in annotated_items if bool(item.get("selected"))]
        debug_plan["selected_count"] = int(selected_n)
        debug_plan["after_slot_filter_count"] = int(len(slot_pass_symbols))
        debug_plan["after_cash_lot_count"] = int(len(cash_lot_pass_symbols))
        debug_plan["buys_executed"] = buy_exec_plan
        debug_plan["annotated_items"] = [dict(item) for item in annotated_items]
        debug_plan["source_only_rejected_sells"] = [dict(item) for item in source_only_rejected_sells]
        debug_plan["reject_reason_counts"] = dict(reject_reason_counts)
        debug_plan["execution_kernel_reject_reason_counts"] = dict(reject_reason_counts)
        debug_plan["selected_order_value_scales"] = [float(item.get("order_value_scale", 1.0) or 1.0) for item in buy_exec_plan]
        debug_plan["execution_kernel_reject_count"] = int(sum(int(v or 0) for v in reject_reason_counts.values()))
        debug_plan["execution_kernel_selected_symbols"] = [str(item.get("symbol", "")).lower() for item in annotated_items if bool(item.get("selected"))]

    return orders
