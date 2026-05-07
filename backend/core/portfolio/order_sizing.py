from __future__ import annotations

from math import isnan
from typing import Any, Iterable

from backend.core.portfolio.sizing import calc_lot_qty


def safe_float(value: Any, *, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(fallback)
    if isnan(out):
        return float(fallback)
    return float(out)


def resolve_direct_target_amount(*, sig_meta: dict[str, Any] | None, nav_close: float) -> float | None:
    meta = dict(sig_meta or {})
    raw_target_weight = meta.get("target_weight")
    if raw_target_weight is None:
        return None
    try:
        target_weight = float(raw_target_weight)
    except Exception:
        return None
    if target_weight != target_weight:
        return None
    if target_weight <= 0.0:
        return 0.0
    if target_weight > 1.0 + 1e-12:
        raise ValueError(f"target_weight must be <= 1.0, got {target_weight}")
    return float(nav_close) * float(target_weight)


def build_sizing_context(
    *,
    items: Iterable[dict[str, Any]],
    nav_close: float,
    max_positions: int,
    min_positions: int,
    base_order_value: float,
    weight_mode: str,
    atr_close_map: dict[str, tuple[float, float]] | None,
) -> dict[str, Any]:
    min_pos = max(1, int(min_positions))
    sizing_denom = max(min_pos, int(max_positions)) if int(max_positions) > 0 else min_pos
    base_target_amount = (
        float(base_order_value)
        if float(base_order_value) > 0.0
        else (float(nav_close) / float(sizing_denom) if sizing_denom > 0 else 0.0)
    )

    inv_vol_weights: dict[str, float] = {}
    atr_close = dict(atr_close_map or {})
    if str(weight_mode).lower() == "inverse_vol" and atr_close:
        inv_sigmas: dict[str, float] = {}
        for item in list(items):
            sym = str((item or {}).get("symbol", "") or "").lower()
            pair = atr_close.get(sym)
            if pair is None:
                continue
            atr_val, close_val = float(pair[0]), float(pair[1])
            if close_val > 1e-8 and atr_val > 1e-8:
                sigma = atr_val / close_val
                inv_sigmas[sym] = 1.0 / sigma
        total_inv = float(sum(inv_sigmas.values()) or 0.0)
        if total_inv > 1e-12:
            for sym, inv_sigma in inv_sigmas.items():
                inv_vol_weights[sym] = float(inv_sigma) / float(total_inv)

    return {
        "sizing_denom": int(sizing_denom),
        "base_target_amount": float(base_target_amount),
        "inverse_vol_weights": inv_vol_weights,
    }


def resolve_target_amount_scaled(
    *,
    sig_meta: dict[str, Any] | None,
    symbol: str,
    price: float,
    nav_close: float,
    order_value_scale: float,
    risk_amount: float,
    atr_stop_k: float,
    sizing_context: dict[str, Any],
) -> float:
    direct_target_amount = resolve_direct_target_amount(sig_meta=sig_meta, nav_close=float(nav_close))
    if direct_target_amount is not None:
        return float(direct_target_amount)

    sizing_denom = int((sizing_context or {}).get("sizing_denom", 0) or 0)
    base_target_amount = float((sizing_context or {}).get("base_target_amount", 0.0) or 0.0)
    inverse_vol_weights = dict((sizing_context or {}).get("inverse_vol_weights", {}) or {})
    sym = str(symbol or "").lower()

    if float(risk_amount) > 0.0:
        atr_value = dict(sig_meta or {}).get("atr_last")
        if atr_value is not None and float(atr_value) > 0.0 and float(price) > 0.0:
            stop_dist = float(atr_stop_k) * float(atr_value)
            shares_raw = float(risk_amount) / float(stop_dist)
            target_amount_scaled = float(shares_raw) * float(price)
            cap_value = float(nav_close) * 0.2
            return float(min(target_amount_scaled, cap_value))
        return float(nav_close) / float(sizing_denom) if sizing_denom > 0 else 0.0

    if sym in inverse_vol_weights:
        return float(nav_close) * float(inverse_vol_weights[sym]) * float(order_value_scale)

    return float(base_target_amount) * float(order_value_scale)


def resolve_order_sizing(
    *,
    sig_meta: dict[str, Any] | None,
    symbol: str,
    price: float,
    nav_close: float,
    order_value_scale: float,
    risk_amount: float,
    atr_stop_k: float,
    sizing_context: dict[str, Any],
    lot_size: int,
) -> dict[str, Any]:
    target_amount_scaled = resolve_target_amount_scaled(
        sig_meta=sig_meta,
        symbol=symbol,
        price=float(price),
        nav_close=float(nav_close),
        order_value_scale=float(order_value_scale),
        risk_amount=float(risk_amount),
        atr_stop_k=float(atr_stop_k),
        sizing_context=sizing_context,
    )
    qty = calc_lot_qty(float(target_amount_scaled), float(price), int(lot_size))
    cost = float(qty) * float(price)
    return {
        "target_amount_scaled": float(target_amount_scaled),
        "qty": int(qty),
        "cost": float(cost),
    }


def estimate_buy_fill_net_cost(
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
    commission = max(float(comm_min), float(gross) * float(comm_rate))
    return float(gross) + float(commission)


def resolve_affordable_buy_qty(
    *,
    price: float,
    requested_qty: int,
    lot_size: int,
    cash_available: float,
    slip_bps: float,
    comm_rate: float,
    comm_min: float,
) -> int:
    px = max(float(price), 0.0)
    lot = max(int(lot_size), 1)
    qty_cap = max(int(requested_qty), 0)
    cash = max(float(cash_available), 0.0)
    if px <= 0.0 or qty_cap < lot or cash <= 0.0:
        return 0

    fill_px = float(px) * (1.0 + float(slip_bps))
    if fill_px <= 0.0:
        return 0

    qty_by_rate = int(cash / (float(fill_px) * (1.0 + max(float(comm_rate), 0.0))))
    qty_by_min = 0
    if cash > float(comm_min):
        qty_by_min = int((cash - float(comm_min)) / float(fill_px))
    candidate_qty = min(qty_cap, max(qty_by_rate, qty_by_min))
    candidate_qty = (int(candidate_qty) // lot) * lot

    while candidate_qty >= lot:
        net_cost = estimate_buy_fill_net_cost(
            price=float(px),
            qty=int(candidate_qty),
            slip_bps=float(slip_bps),
            comm_rate=float(comm_rate),
            comm_min=float(comm_min),
        )
        if float(net_cost) <= float(cash) + 1e-9:
            return int(candidate_qty)
        candidate_qty -= lot
    return 0
