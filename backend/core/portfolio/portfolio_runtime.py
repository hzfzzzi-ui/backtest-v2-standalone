"""Portfolio runtime helpers and public loop entrypoint.

Pure helpers should continue to live in dedicated portfolio modules, while
routing and execution changes land in `foundation_shell.py` and
`stage_pipeline/*`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from backend.core.config.models import SizingConfig
from backend.core.core.models import Signal
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today as _resolve_mf_gate_on_today
from backend.core.portfolio.candidate_plan import build_candidate_plan
from backend.core.portfolio.execution_orders import build_execution_orders_from_candidate_plan
from backend.core.portfolio.nav_snapshot import compute_nav_snapshot as _compute_nav_snapshot
from backend.core.portfolio.price_index import build_backtest_price_indices as _build_backtest_price_indices
from backend.core.portfolio.sizing import calc_buy_slots as _calc_buy_slots, calc_lot_qty as _calc_lot_qty
from backend.core.portfolio.types import PortfolioOrder


def build_backtest_price_indices(
    *,
    history: pd.DataFrame,
    trading_days: list[date],
) -> tuple[dict[tuple[date, str], float], dict[tuple[date, str], float]]:
    return _build_backtest_price_indices(history=history, trading_days=trading_days)


def compute_nav_snapshot(
    *,
    cash: float,
    positions: dict[str, int],
    close_idx: dict[tuple[date, str], float],
    day: date,
    hfq_close_idx: dict[tuple[date, str], float] | None = None,
    position_entry_adj: dict[str, float] | None = None,
) -> tuple[float, float, list[tuple[str, float]]]:
    """计算 NAV 快照。

    当同时提供 hfq_close_idx 和 position_entry_adj 时，使用归一化公式：
        market_value = qty × hfq_close / entry_adj_factor
    这样持仓估值与 raw 价格空间一致，同时消除除权除息的虚假跳变。
    当只提供 close_idx 时，向后兼容使用 raw close。
    """
    return _compute_nav_snapshot(
        cash=cash,
        positions=positions,
        close_idx=close_idx,
        day=day,
        hfq_close_idx=hfq_close_idx,
        position_entry_adj=position_entry_adj,
    )


def calc_buy_slots(max_positions: int, positions_after_sell: int) -> int:
    return _calc_buy_slots(max_positions=max_positions, positions_after_sell=positions_after_sell)


def calc_lot_qty(target_amount: float, open_price: float, lot_size: int) -> int:
    return _calc_lot_qty(target_amount=target_amount, open_price=open_price, lot_size=lot_size)


def resolve_mf_gate_on_today(
    *,
    enable_multifactor_rank: bool,
    mf_rank_gate_mode: str,
    risk_on_today: bool,
    strong_risk_on_today: bool,
    market_state_today: str = "",
) -> bool:
    return _resolve_mf_gate_on_today(
        enable_multifactor_rank=enable_multifactor_rank,
        mf_rank_gate_mode=mf_rank_gate_mode,
        risk_on_today=risk_on_today,
        strong_risk_on_today=strong_risk_on_today,
        market_state_today=market_state_today,
    )


def build_rebalance_orders(
    *,
    positions: dict[str, int],
    cash_available: float,
    nav_close: float,
    max_positions: int,
    lot_size: int,
    sell_signals: list[Signal],
    buy_signals: list[Signal],
    next_open: dict[str, float],
    enable_strength_rank: bool = False,
    strength_ma: int = 120,
    strength_top_k_mode: str = "FILL_TO_MAX",
    strength_map: dict[str, float | None] | None = None,
    enable_multifactor_rank: bool = False,
    mf_topk: int = 10,
    mf_concentrate_topn: int = 3,
    mf_concentrate_scale: float = 1.5,
    mf_gate_on_today: bool = True,
    mf_score_map: dict[str, float | None] | None = None,
    overlay_mode: str = "off",
    overlay_gate_on_today: bool = False,
    overlay_score_map: dict[str, float | None] | None = None,
    overlay_band_limit: int = 0,
    overlay_observation_date: date | None = None,
    overlay_score_source: str = "",
    momentum_top_pct: float = 0.0,
    decision_date: date | None = None,
    candidate_audit: list[dict[str, Any]] | None = None,
    debug_plan: dict[str, Any] | None = None,
    base_order_value: float = 0.0,
    sizing_cfg: SizingConfig | None = None,
    risk_amount: float = 0.0,
    atr_stop_k: float = 2.0,
    weight_mode: str = "equal",
    min_positions: int = 10,
    tilt_strength: float = 0.0,
    tilt_top_n: int = 3,
    tilt_bottom_n: int = 2,
    atr_close_map: dict[str, tuple[float, float]] | None = None,
    min_trade_price: float = 0.0,
    decision_close_map: dict[str, float] | None = None,
    enable_entry_gap_guard: bool = False,
    entry_gap_guard_pct: float = 0.0,
    score_weight_min_scale: float = 0.75,
    score_weight_max_scale: float = 1.25,
    candidate_plan_mode: str = "ranked",
    cash_aware_search_top_n: int = 12,
    holding_entry_dates: dict[str, date | None] | None = None,
    market_state_today: str = "",
    strong_risk_on_today: bool = False,
    rotation_replace_enabled: bool = False,
    rotation_replace_only_strong_risk_on: bool = True,
    rotation_replace_max_swaps_per_day: int = 1,
    rotation_replace_candidate_top_n: int = 3,
    rotation_replace_min_score_gap: float = 0.15,
    rotation_min_hold_days: int = 0,
) -> list[PortfolioOrder]:
    _ = strength_top_k_mode, sizing_cfg

    candidate_plan_payload = build_candidate_plan(
        positions=positions,
        cash_available=float(cash_available),
        nav_close=float(nav_close),
        max_positions=int(max_positions),
        lot_size=int(lot_size),
        sell_signals=list(sell_signals or ()),
        buy_signals=list(buy_signals or ()),
        next_open=next_open,
        enable_strength_rank=bool(enable_strength_rank),
        strength_ma=int(strength_ma),
        strength_map=strength_map,
        enable_multifactor_rank=bool(enable_multifactor_rank),
        mf_topk=int(mf_topk),
        mf_concentrate_topn=int(mf_concentrate_topn),
        mf_concentrate_scale=float(mf_concentrate_scale),
        mf_gate_on_today=bool(mf_gate_on_today),
        mf_score_map=mf_score_map,
        overlay_mode=str(overlay_mode),
        overlay_gate_on_today=bool(overlay_gate_on_today),
        overlay_score_map=overlay_score_map,
        overlay_band_limit=int(overlay_band_limit),
        overlay_observation_date=overlay_observation_date,
        overlay_score_source=str(overlay_score_source or ''),
        momentum_top_pct=float(momentum_top_pct),
        decision_date=decision_date,
        base_order_value=float(base_order_value),
        risk_amount=float(risk_amount),
        atr_stop_k=float(atr_stop_k),
        weight_mode=str(weight_mode),
        min_positions=int(min_positions),
        tilt_strength=float(tilt_strength),
        tilt_top_n=int(tilt_top_n),
        tilt_bottom_n=int(tilt_bottom_n),
        atr_close_map=atr_close_map,
        min_trade_price=float(min_trade_price),
        decision_close_map=decision_close_map,
        enable_entry_gap_guard=bool(enable_entry_gap_guard),
        entry_gap_guard_pct=float(entry_gap_guard_pct),
        score_weight_min_scale=float(score_weight_min_scale),
        score_weight_max_scale=float(score_weight_max_scale),
        candidate_plan_mode=str(candidate_plan_mode),
        cash_aware_search_top_n=int(cash_aware_search_top_n),
        holding_entry_dates=holding_entry_dates,
        market_state_today=str(market_state_today or ""),
        strong_risk_on_today=bool(strong_risk_on_today),
        rotation_replace_enabled=bool(rotation_replace_enabled),
        rotation_replace_only_strong_risk_on=bool(rotation_replace_only_strong_risk_on),
        rotation_replace_max_swaps_per_day=int(rotation_replace_max_swaps_per_day),
        rotation_replace_candidate_top_n=int(rotation_replace_candidate_top_n),
        rotation_replace_min_score_gap=float(rotation_replace_min_score_gap),
        rotation_min_hold_days=int(rotation_min_hold_days),
    )

    if candidate_audit is not None:
        candidate_audit.extend(list(candidate_plan_payload.get('candidate_rows', []) or []))

    if debug_plan is not None:
        debug_plan.update(dict(candidate_plan_payload.get('debug_plan', {}) or {}))

    orders = build_execution_orders_from_candidate_plan(
        positions=positions,
        cash_available=float(cash_available),
        nav_close=float(nav_close),
        max_positions=int(max_positions),
        lot_size=int(lot_size),
        sell_signals=[
            *list(sell_signals or ()),
            *list(candidate_plan_payload.get('planned_rotation_sell_signals', []) or []),
        ],
        planned_items=list(candidate_plan_payload.get('planned_items', []) or []),
        next_open=next_open,
        decision_date=decision_date,
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        strength_ma=int(strength_ma),
        overlay_mode=str(overlay_mode),
        overlay_gate_on_today=bool(overlay_gate_on_today),
        overlay_observation_date=overlay_observation_date,
        overlay_score_source=str(overlay_score_source or ''),
        base_order_value=float(base_order_value),
        risk_amount=float(risk_amount),
        atr_stop_k=float(atr_stop_k),
        weight_mode=str(weight_mode),
        min_positions=int(min_positions),
        atr_close_map=atr_close_map,
    )

    if debug_plan is not None:
        aggregated_rejects = {
            str(k): int(v or 0)
            for k, v in dict(candidate_plan_payload.get('reject_reason_counts', {}) or {}).items()
            if str(k).strip()
        }
        for reason, count in dict(debug_plan.get('execution_kernel_reject_reason_counts', {}) or {}).items():
            key = str(reason).strip()
            if not key:
                continue
            aggregated_rejects[key] = int(aggregated_rejects.get(key, 0)) + int(count or 0)
        debug_plan['reject_reason_counts'] = aggregated_rejects

    return orders
from backend.core.portfolio.portfolio_loop import run_portfolio_backtest
