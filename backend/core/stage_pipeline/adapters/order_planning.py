from __future__ import annotations

from typing import Any

import numpy as np

from backend.core.core.types import Side
from backend.core.portfolio.portfolio_builder import build_rebalance_orders, resolve_mf_gate_on_today
from backend.core.stage_pipeline.contracts import StageOutputs


def build_s7_order_stage_output(runtime: Any) -> StageOutputs:
    if runtime._current_day is None:
        raise RuntimeError("current day is not prepared")

    day = runtime._current_day["day"]
    controls = runtime._current_day["controls"]
    day_signals = runtime._current_day["day_signals"]
    next_open = dict(runtime._current_day["next_open"])
    nav = float(runtime._current_day["nav"])
    debug_plan: dict[str, Any] = {}
    day_candidate_rows: list[dict[str, Any]] = []
    mf_gate_on_today = resolve_mf_gate_on_today(
        enable_multifactor_rank=bool(runtime.request.enable_multifactor_rank),
        mf_rank_gate_mode=str(runtime.request.mf_rank_gate_mode or "ALWAYS_ON"),
        risk_on_today=bool(controls["risk_on_today"]),
        strong_risk_on_today=bool(day_signals.strong_risk_on),
    )
    atr_close_map: dict[str, tuple[float, float]] = {}
    provider_feats = getattr(runtime.provider, "_feats", None)
    provider_mx = getattr(runtime.provider, "_mx", None)
    provider_sym_to_col = getattr(runtime.provider, "_sym_to_col", {})
    if runtime._weight_mode == "inverse_vol" and provider_feats is not None and provider_mx is not None:
        row_idx = int(runtime._prepared_day_index or 0)
        for symbol, col_idx in dict(provider_sym_to_col or {}).items():
            atr_v = float(provider_feats.atr14[row_idx, col_idx])
            close_v = float(provider_mx.close[row_idx, col_idx])
            if not (np.isnan(atr_v) or np.isnan(close_v)):
                atr_close_map[str(symbol).lower()] = (atr_v, close_v)

    orders = build_rebalance_orders(
        positions=runtime.positions,
        cash_available=runtime.cash,
        nav_close=nav,
        max_positions=int(controls["effective_max_positions"]),
        lot_size=runtime.request.lot_size,
        sell_signals=list(day_signals.sell_signals),
        buy_signals=list(day_signals.buy_signals),
        next_open=next_open,
        enable_strength_rank=bool(runtime.request.enable_strength_rank),
        strength_ma=int(runtime.request.strength_ma),
        strength_top_k_mode=str(runtime.request.strength_top_k_mode),
        strength_map=dict(day_signals.strength_map),
        enable_multifactor_rank=bool(runtime.request.enable_multifactor_rank),
        mf_topk=int(runtime.request.mf_topk),
        mf_concentrate_topn=int(runtime.request.mf_concentrate_topn),
        mf_concentrate_scale=float(runtime.request.mf_concentrate_scale),
        mf_gate_on_today=bool(mf_gate_on_today),
        mf_score_map=dict(day_signals.mf_score_map),
        momentum_top_pct=float(runtime.request.momentum_top_pct),
        decision_date=day,
        candidate_audit=(None if bool(runtime.request.fast_mode) else day_candidate_rows),
        debug_plan=debug_plan,
        weight_mode=runtime._weight_mode,
        min_positions=runtime._min_positions_cfg,
        atr_close_map=atr_close_map,
        min_trade_price=runtime._min_trade_price,
    )
    if not bool(runtime.request.fast_mode):
        runtime.candidate_rows.extend(day_candidate_rows)

    runtime._apply_daily_decision_diagnostics(
        day_signals=day_signals,
        debug_plan=debug_plan,
    )
    next_day_orders = [
        {
            "side": order.side,
            "symbol": str(order.symbol).lower(),
            "qty": int(order.qty),
            "reason_code": str(order.reason_code),
            "meta": dict(order.meta or {}),
        }
        for order in orders
    ]
    return StageOutputs(
        stage_key="S7",
        holding_symbols=runtime._current_day["holding_symbols"],
        buy_symbols=tuple(od["symbol"] for od in next_day_orders if od["side"] == Side.BUY),
        sell_symbols=tuple(od["symbol"] for od in next_day_orders if od["side"] == Side.SELL),
        payload={"next_day_orders": tuple(next_day_orders)},
        reason_counts=dict((debug_plan or {}).get("reject_reason_counts", {}) or {}),
        summary_fragment={
            "mode": "legacy_order_planner",
            "buy_orders_count": sum(1 for od in next_day_orders if od["side"] == Side.BUY),
            "sell_orders_count": sum(1 for od in next_day_orders if od["side"] == Side.SELL),
        },
    )
