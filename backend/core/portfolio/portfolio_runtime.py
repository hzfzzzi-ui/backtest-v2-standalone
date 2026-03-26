"""Portfolio runtime helpers and public loop entrypoint.

Pure helpers should continue to live in dedicated portfolio modules, while
routing and execution changes land in `foundation_shell.py` and
`stage_pipeline/*`.
"""

from __future__ import annotations

import json
from datetime import date
from math import sqrt
from typing import Any

import pandas as pd

from backend.core.config.models import BenchmarkRegimeConfig, BreadthConfig, CostConfig, ExitConfig, MarketFilterConfig, RiskBudgetConfig, RiskConfig, SizingConfig
from backend.core.core.models import Position, Side, Signal
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today as _resolve_mf_gate_on_today
from backend.core.portfolio.metrics import compute_backtest_metrics
from backend.core.portfolio.nav_snapshot import compute_nav_snapshot as _compute_nav_snapshot
from backend.core.portfolio.price_index import build_backtest_price_indices as _build_backtest_price_indices
from backend.core.portfolio.selection_scoring import (
    build_score_weight_scale_maps as _build_score_weight_scale_maps,
    resolve_mf_rank_tilt_scale as _resolve_mf_rank_tilt_scale,
    resolve_rotation_score as _resolve_rotation_score,
    resolve_score_weight_scale as _resolve_score_weight_scale,
    resolve_score_weight_score as _resolve_score_weight_score,
    safe_date_or_none as _safe_date_or_none,
    safe_float_or_none as _safe_float_or_none,
    select_rotation_pairs as _select_rotation_pairs,
)
from backend.core.portfolio.selection_order import normalize_candidate_order, sort_by_strength_with_tiebreak
from backend.core.portfolio.sizing import calc_buy_slots as _calc_buy_slots, calc_lot_qty as _calc_lot_qty
from backend.core.portfolio.types import PortfolioBacktestResult, PortfolioOrder
from backend.core.strategies.base import Strategy


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


def _estimate_buy_slots_after_sell(
    *,
    positions: dict[str, int],
    sell_signals: list[Signal],
    max_positions: int,
) -> int:
    after = {str(k): int(v) for k, v in positions.items() if int(v) > 0}
    for sig in sell_signals:
        sym = str(sig.symbol).lower()
        held = int(after.get(sym, 0))
        if held <= 0:
            continue
        qty = held if int(sig.qty) <= 0 else min(held, int(sig.qty))
        remain = held - qty
        if remain > 0:
            after[sym] = remain
        else:
            after.pop(sym, None)
    return max(0, int(max_positions) - len(after))


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


def _entry_gap_guard_hit(
    *,
    enable_entry_gap_guard: bool,
    entry_gap_guard_pct: float,
    next_open_price: float,
    decision_close_price: float | None,
) -> bool:
    if not bool(enable_entry_gap_guard):
        return False
    if float(entry_gap_guard_pct) <= 0.0:
        return False
    if float(next_open_price) <= 0.0:
        return False
    if decision_close_price is None or float(decision_close_price) <= 0.0:
        return False
    gap_pct = float(next_open_price) / float(decision_close_price) - 1.0
    return gap_pct > float(entry_gap_guard_pct)


def _resolve_cash_aware_subset(
    *,
    planner_candidates: list[dict[str, Any]],
    slots: int,
    cash_available: float,
) -> list[str]:
    pool = list(planner_candidates)
    if not pool:
        return []
    slot_limit = max(0, int(slots))
    budget_cents = max(0, int(round(float(cash_available) * 100.0)))
    if slot_limit <= 0 or budget_cents <= 0:
        return []

    n = len(pool)
    costs = [max(0, int(round(float(item.get("candidate_cost", 0.0) or 0.0) * 100.0))) for item in pool]
    priorities = [n - idx for idx in range(n)]
    best_mask = 0
    best_tuple = (0, 0, 0)

    for mask in range(1, 1 << n):
        count = int(mask.bit_count())
        if count > slot_limit:
            continue
        cost_cents = 0
        priority_sum = 0
        feasible = True
        for idx in range(n):
            if (mask >> idx) & 1:
                cost_cents += int(costs[idx])
                if cost_cents > budget_cents:
                    feasible = False
                    break
                priority_sum += int(priorities[idx])
        if not feasible:
            continue
        candidate_tuple = (count, priority_sum, cost_cents)
        if candidate_tuple > best_tuple:
            best_tuple = candidate_tuple
            best_mask = mask

    return [
        str(pool[idx].get("symbol", "")).lower()
        for idx in range(n)
        if (best_mask >> idx) & 1
    ]


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
    is_candidate: bool = True,
    mf_score: float | None = None,
    mf_rank: int | None = None,
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
) -> dict[str, Any]:
    _meta = dict(meta or {})
    return {
        "date": decision_date_s,
        "symbol": str(symbol).lower(),
        "is_candidate": bool(is_candidate),
        "strength": None if strength is None else float(strength),
        "strength_ma": int(strength_ma),
        "selected": bool(selected),
        "selected_flag": bool(selected),
        "selected_rank": selected_rank,
        "reject_reason": str(reject_reason),
        "alpha_source": str(_meta.get("alpha_source", "") or ""),
        "overlap_flag": bool(_meta.get("overlap_flag", False)),
        "pullback_variant": str(_meta.get("pullback_variant", "") or ""),
        "breakout_margin_raw": _safe_float_or_none(_meta.get("breakout_margin_raw")),
        "breakout_margin_score": _safe_float_or_none(_meta.get("breakout_margin_score")),
        "breakout_fade_raw": _safe_float_or_none(_meta.get("breakout_fade_raw")),
        "breakout_open_gap_raw": _safe_float_or_none(_meta.get("breakout_open_gap_raw")),
        "breakout_quality_score": _safe_float_or_none(_meta.get("breakout_quality_score")),
        "breakout_quality_pass": bool(_meta.get("breakout_quality_pass", False)),
        "residual_strength_raw": _safe_float_or_none(_meta.get("residual_strength_raw")),
        "residual_strength_score": _safe_float_or_none(_meta.get("residual_strength_score")),
        "sector_strength_score": _safe_float_or_none(_meta.get("sector_strength_score")),
        "volume_price_quality_score": _safe_float_or_none(_meta.get("volume_price_quality_score")),
        "final_score": _safe_float_or_none(_meta.get("final_score")),
        "baseline_score": _safe_float_or_none(_meta.get("final_score")),
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


def _resolve_direct_target_amount(
    *,
    sig_meta: dict[str, Any] | None,
    nav_close: float,
) -> float | None:
    meta = dict(sig_meta or {})
    target_exposure_per_symbol = meta.get("target_exposure_per_symbol")
    if target_exposure_per_symbol is None:
        return None
    try:
        exposure = float(target_exposure_per_symbol)
    except Exception:
        return None
    if not pd.notna(exposure) or exposure <= 0.0:
        return None
    return float(nav_close) * float(exposure)


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
    strong_risk_on_today: bool = False,
    rotation_replace_enabled: bool = False,
    rotation_replace_only_strong_risk_on: bool = True,
    rotation_replace_max_swaps_per_day: int = 1,
    rotation_replace_candidate_top_n: int = 3,
    rotation_replace_min_score_gap: float = 0.15,
    rotation_min_hold_days: int = 0,
) -> list[PortfolioOrder]:
    orders: list[PortfolioOrder] = []
    future_positions = dict(positions)
    est_cash = float(cash_available)

    # 1) Sell first.
    for sig in sell_signals:
        sym = str(sig.symbol).lower()
        held = int(future_positions.get(sym, 0))
        if held <= 0:
            continue
        qty = held if int(sig.qty) <= 0 else min(held, int(sig.qty))
        px = float(next_open.get(sym, 0.0) or 0.0)
        if qty <= 0 or px <= 0:
            continue
        orders.append(
            PortfolioOrder(
                side=Side.SELL,
                symbol=sym,
                qty=qty,
                reason_code=str(sig.reason_code or sig.reason or "SELL"),
                meta=(dict(sig.meta) if isinstance(sig.meta, dict) else None),
            )
        )
        future_positions[sym] = held - qty
        if future_positions[sym] <= 0:
            future_positions.pop(sym, None)
        est_cash += qty * px

    positions_after_sell = len([q for q in future_positions.values() if q > 0])
    slots = calc_buy_slots(int(max_positions), int(positions_after_sell))
    candidate_plan_mode_norm = str(candidate_plan_mode or "ranked").strip().lower()
    rotation_enabled_today = bool(rotation_replace_enabled) and candidate_plan_mode_norm == "ranked"
    if bool(rotation_replace_only_strong_risk_on):
        rotation_enabled_today = bool(rotation_enabled_today) and bool(strong_risk_on_today)
    if slots <= 0 and not bool(rotation_enabled_today):
        if debug_plan is not None:
            debug_plan["rotation_replace_enabled"] = bool(rotation_replace_enabled)
            debug_plan["rotation_replace_active"] = bool(rotation_enabled_today)
            debug_plan["rotation_replace_only_strong_risk_on"] = bool(rotation_replace_only_strong_risk_on)
            debug_plan["rotation_replace_count"] = 0
            debug_plan["rotation_replace_pairs"] = []
            debug_plan["rotation_candidate_pool_count"] = 0
            debug_plan["rotation_eligible_held_count"] = 0
        return orders

    # 2) Buy candidates ranked by signal strength.
    ranked: list[dict[str, Any]] = []
    strength_map = dict(strength_map or {})
    decision_close_map = {str(k).lower(): float(v) for k, v in dict(decision_close_map or {}).items()}
    overlay_score_map = dict(overlay_score_map or {})
    overlay_mode_norm = str(overlay_mode or "off").strip().lower() or "off"
    overlay_active_today = bool(overlay_gate_on_today) and overlay_mode_norm in {"shadow", "tiebreak", "soft_weight"}
    decision_date_s = decision_date.isoformat() if isinstance(decision_date, date) else ""
    reject_reason_counts: dict[str, int] = {}
    for sig in buy_signals:
        sym = str(sig.symbol).lower()
        if sym in future_positions and int(future_positions.get(sym, 0)) > 0:
            if candidate_audit is not None:
                candidate_audit.append(_build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="ALREADY_HELD",
                    meta=(sig.meta if isinstance(sig.meta, dict) else None),
                    is_candidate=False,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                ))
            continue
        px = float(next_open.get(sym, 0.0) or 0.0)
        if px <= 0:
            if candidate_audit is not None:
                candidate_audit.append(_build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="NOT_TRADABLE",
                    meta=(sig.meta if isinstance(sig.meta, dict) else None),
                    is_candidate=False,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                ))
            continue
        if float(min_trade_price) > 0 and px < float(min_trade_price):
            if candidate_audit is not None:
                candidate_audit.append(_build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="SKIP_MIN_PRICE_AT_ORDER",
                    meta=(sig.meta if isinstance(sig.meta, dict) else None),
                    is_candidate=False,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                ))
            continue
        meta = sig.meta if isinstance(sig.meta, dict) else {}
        decision_close = _safe_float_or_none(decision_close_map.get(sym))
        if _entry_gap_guard_hit(
            enable_entry_gap_guard=bool(enable_entry_gap_guard),
            entry_gap_guard_pct=float(entry_gap_guard_pct),
            next_open_price=float(px),
            decision_close_price=decision_close,
        ):
            reject_reason_counts["SKIP_ENTRY_GAP_GUARD"] = int(reject_reason_counts.get("SKIP_ENTRY_GAP_GUARD", 0)) + 1
            if candidate_audit is not None:
                candidate_audit.append(_build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="SKIP_ENTRY_GAP_GUARD",
                    meta=meta,
                    is_candidate=False,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                ))
            continue
        close_v = float(meta.get("close", 0.0) or 0.0)
        slow_v = float(meta.get("slow_ma", 0.0) or 0.0)
        baseline_strength = (close_v / slow_v - 1.0) if slow_v > 0 else -1e9
        strength = strength_map.get(sym) if enable_strength_rank else baseline_strength
        ranked.append(
            {
                "signal": sig,
                "symbol": sym,
                "price": px,
                "strength": strength,
                "tiebreak_strength": (
                    _safe_float_or_none(meta.get("industry_second_stage_score"))
                    if str(meta.get("residual_refine_mode", "")).strip().lower() == "industry_second_stage_tiebreak"
                    and bool(meta.get("industry_second_stage_active"))
                    else None
                ),
                "baseline_strength": baseline_strength,
                "overlay_score": _safe_float_or_none(overlay_score_map.get(sym)),
                "order_value_scale": float(meta.get("order_value_scale", 1.0) or 1.0),
                "selected": False,
                "selected_rank": None,
                "reject_reason": "",
            }
        )
    mf_score_map = dict(mf_score_map or {})
    mf_rank_triggered = False
    mf_rank_applied = False
    mf_topk_reject_count = 0
    mf_concentrated_selected_count = 0
    forced_not_in_topk_symbols: set[str] = set()

    mf_enabled_today = bool(enable_multifactor_rank) and bool(mf_gate_on_today)
    if mf_enabled_today:
        for item in ranked:
            sym = str(item.get("symbol", "")).lower()
            score_raw = mf_score_map.get(sym, None)
            try:
                score_val = float(score_raw) if score_raw is not None else 0.5
            except Exception:
                score_val = 0.5
            item["mf_score"] = score_val
        if len(ranked) < 5:
            for item in ranked:
                item["mf_score"] = 0.5
        rank_sorted = sorted(
            ranked,
            key=lambda x: (
                -float(x.get("mf_score", 0.5)),
                -float(x.get("overlay_score", 0.5))
                if bool(overlay_active_today) and overlay_mode_norm == "tiebreak" and x.get("overlay_score") is not None
                else 0.0,
                str(x.get("symbol", "")).lower(),
            ),
        )
        for idx, item in enumerate(rank_sorted, start=1):
            item["mf_rank"] = int(idx)
        if len(ranked) > int(slots):
            mf_rank_triggered = True
            ranked.sort(
                key=lambda x: (
                    -float(x.get("mf_score", 0.5)),
                    -float(x.get("overlay_score", 0.5))
                    if bool(overlay_active_today) and overlay_mode_norm == "tiebreak" and x.get("overlay_score") is not None
                    else 0.0,
                    str(x.get("symbol", "")).lower(),
                )
            )
            # percentage-based selection when momentum_top_pct > 0
            if float(momentum_top_pct) > 0:
                topk_n = max(1, int(len(ranked) * float(momentum_top_pct)))
                # cap at mf_topk if set
                if int(mf_topk) > 0:
                    topk_n = min(topk_n, int(mf_topk))
            else:
                topk_n = max(0, int(mf_topk))
            if topk_n > 0 and topk_n >= int(slots):
                for item in ranked[topk_n:]:
                    forced_not_in_topk_symbols.add(str(item.get("symbol", "")).lower())
                mf_topk_reject_count = int(len(forced_not_in_topk_symbols))
        else:
            # Keep deterministic order if rank is not triggered.
            order = normalize_candidate_order([str(x.get("symbol", "")) for x in ranked])
            order_pos = {s: i for i, s in enumerate(order)}
            ranked.sort(key=lambda x: int(order_pos.get(str(x.get("symbol", "")).lower(), 10**9)))
    else:
        # Stable shared ordering:
        # - no-rank path: symbol asc
        # - strength-rank path: strength desc + symbol asc tie-break
        if enable_strength_rank:
            ranked = sort_by_strength_with_tiebreak(ranked)
        else:
            order = normalize_candidate_order([str(x.get("symbol", "")) for x in ranked])
            order_pos = {s: i for i, s in enumerate(order)}
            ranked.sort(key=lambda x: int(order_pos.get(str(x.get("symbol", "")).lower(), 10**9)))

    _score_weight_scales, _score_weight_scores, _score_weight_raw_scales = _build_score_weight_scale_maps(
        ranked=ranked,
        slots=int(slots),
        weight_mode=str(weight_mode),
        overlay_mode=overlay_mode_norm,
        overlay_active_today=bool(overlay_active_today),
        min_trade_price=float(min_trade_price),
        forced_not_in_topk_symbols=forced_not_in_topk_symbols,
        score_weight_min_scale=float(score_weight_min_scale),
        score_weight_max_scale=float(score_weight_max_scale),
    )

    # ── Sizing denominator with min_positions floor ──
    _min_pos = max(1, int(min_positions))
    _sizing_denom = max(_min_pos, int(max_positions)) if int(max_positions) > 0 else _min_pos
    cfg_order_value = float(base_order_value)
    target_amount = cfg_order_value if cfg_order_value > 0 else (float(nav_close) / float(_sizing_denom) if _sizing_denom > 0 else 0.0)

    # ── Inverse-vol weights (precomputed for all candidates) ──
    _inv_vol_weights: dict[str, float] = {}
    _acm = dict(atr_close_map or {})
    if str(weight_mode).lower() == "inverse_vol" and _acm:
        _inv_sigmas: dict[str, float] = {}
        for _item in ranked:
            _sym = str(_item.get("symbol", "")).lower()
            _pair = _acm.get(_sym)
            if _pair is not None:
                _atr_val, _close_val = float(_pair[0]), float(_pair[1])
                if _close_val > 1e-8 and _atr_val > 1e-8:
                    _sigma = _atr_val / _close_val
                    _inv_sigmas[_sym] = 1.0 / _sigma
        _total_inv = sum(_inv_sigmas.values())
        if _total_inv > 1e-12:
            for _sym, _inv_s in _inv_sigmas.items():
                _inv_vol_weights[_sym] = _inv_s / _total_inv

    cash_aware_search_top_n = max(1, int(cash_aware_search_top_n))
    for idx, item in enumerate(ranked, start=1):
        sym = str(item["symbol"]).lower()
        px = float(item["price"] or 0.0)
        if float(min_trade_price) > 0 and px < float(min_trade_price):
            item["pre_reject_reason"] = "SKIP_MIN_PRICE_AT_ORDER"
            continue
        if sym in forced_not_in_topk_symbols:
            item["pre_reject_reason"] = "NOT_IN_TOPK"
            continue
        sig = item["signal"]
        sig_meta = sig.meta if isinstance(sig.meta, dict) else {}
        order_value_scale = float(item.get("order_value_scale", 1.0) or 1.0)
        mf_rank = int(item.get("mf_rank", idx))
        mf_score_raw = item.get("mf_score", None)
        mf_score = float(mf_score_raw) if mf_score_raw is not None else 0.5
        mf_concentrated = bool(
            bool(mf_enabled_today)
            and int(mf_concentrate_topn) > 0
            and mf_rank <= int(mf_concentrate_topn)
        )
        if mf_concentrated:
            order_value_scale = float(order_value_scale) * float(mf_concentrate_scale)
        mf_rank_tilt_scale = _resolve_mf_rank_tilt_scale(
            weight_mode=str(weight_mode),
            mf_enabled_today=bool(mf_enabled_today),
            mf_rank=int(mf_rank),
            mf_topk=int(mf_topk),
            tilt_strength=float(tilt_strength),
            tilt_top_n=int(tilt_top_n),
            tilt_bottom_n=int(tilt_bottom_n),
        )
        order_value_scale = float(order_value_scale) * float(mf_rank_tilt_scale)
        score_weight_scale = float(_score_weight_scales.get(sym, 1.0))
        score_weight_score = _score_weight_scores.get(sym)
        score_weight_raw_scale = float(_score_weight_raw_scales.get(sym, score_weight_scale))
        order_value_scale = float(order_value_scale) * float(score_weight_scale)
        trend_tier = str(sig_meta.get("trend_tier", "")).upper()
        if order_value_scale <= 0:
            item["pre_reject_reason"] = "BLOCK_WEAK_TIER_DISABLED" if trend_tier == "WEAK" else "SKIP_QTY_ZERO"
            continue
        direct_target_amount = _resolve_direct_target_amount(sig_meta=sig_meta, nav_close=float(nav_close))
        if direct_target_amount is not None:
            target_amount_scaled = float(direct_target_amount) * float(order_value_scale)
        elif risk_amount > 0:
            _atr_v = sig_meta.get("atr_last")
            if _atr_v is not None and float(_atr_v) > 0 and px > 0:
                _stop_dist = float(atr_stop_k) * float(_atr_v)
                _shares_raw = risk_amount / _stop_dist
                target_amount_scaled = _shares_raw * px
                _cap_value = float(nav_close) * 0.2
                if target_amount_scaled > _cap_value:
                    target_amount_scaled = _cap_value
            else:
                target_amount_scaled = float(nav_close) / float(_sizing_denom) if _sizing_denom > 0 else 0.0
        elif sym in _inv_vol_weights:
            target_amount_scaled = float(nav_close) * float(_inv_vol_weights[sym]) * float(order_value_scale)
        else:
            target_amount_scaled = float(target_amount) * float(order_value_scale)
        qty = calc_lot_qty(target_amount_scaled, px, lot_size)
        if qty < lot_size:
            item["pre_reject_reason"] = "SKIP_QTY_ZERO"
            continue
        item["order_value_scale"] = float(order_value_scale)
        item["mf_rank"] = int(mf_rank)
        item["mf_score"] = None if mf_score_raw is None else float(mf_score)
        item["mf_concentrated"] = bool(mf_concentrated)
        item["mf_rank_tilt_scale"] = float(mf_rank_tilt_scale)
        item["score_weight_score"] = None if score_weight_score is None else float(score_weight_score)
        item["score_weight_raw_scale"] = float(score_weight_raw_scale)
        item["score_weight_scale"] = float(score_weight_scale)
        item["target_amount_scaled"] = float(target_amount_scaled)
        item["candidate_qty"] = int(qty)
        item["candidate_cost"] = float(qty) * float(px)
        item["pre_reject_reason"] = ""

    rotation_plan: dict[str, Any] = {"candidate_pool": [], "held_pool": [], "pairs": []}
    if slots <= 0 and bool(rotation_enabled_today):
        rotation_plan = _select_rotation_pairs(
            ranked=ranked,
            future_positions=future_positions,
            next_open=next_open,
            decision_date=decision_date,
            holding_entry_dates=holding_entry_dates,
            mf_score_map=mf_score_map,
            strength_map=strength_map,
            candidate_top_n=int(rotation_replace_candidate_top_n),
            max_swaps_per_day=int(rotation_replace_max_swaps_per_day),
            min_score_gap=float(rotation_replace_min_score_gap),
            rotation_min_hold_days=int(rotation_min_hold_days),
        )
        for pair in list(rotation_plan.get("pairs") or []):
            held_sym = str(pair.get("held_symbol", "")).lower()
            held_qty = int(future_positions.get(held_sym, 0))
            held_px = float(next_open.get(held_sym, 0.0) or 0.0)
            if held_qty <= 0 or held_px <= 0.0:
                continue
            candidate_sym = str(pair.get("candidate_symbol", "")).lower()
            rotation_meta = {
                "rotation_replace": True,
                "rotation_candidate_symbol": candidate_sym,
                "rotation_candidate_score": float(pair.get("candidate_score", 0.0) or 0.0),
                "rotation_held_symbol": held_sym,
                "rotation_held_score": float(pair.get("held_score", 0.0) or 0.0),
                "rotation_score_gap": float(pair.get("score_gap", 0.0) or 0.0),
                "rotation_held_days": pair.get("held_days"),
            }
            orders.append(
                PortfolioOrder(
                    side=Side.SELL,
                    symbol=held_sym,
                    qty=held_qty,
                    reason_code="ROTATION_REPLACE",
                    meta=rotation_meta,
                )
            )
            pair["held_qty"] = int(held_qty)
            pair["held_price"] = float(held_px)
            pair["executed"] = True
            est_cash += float(held_qty) * float(held_px)
            future_positions.pop(held_sym, None)
            candidate_item = pair.get("candidate_item")
            if isinstance(candidate_item, dict):
                candidate_item["rotation_selected"] = True
                candidate_item["rotation_pair"] = dict(rotation_meta)
        positions_after_sell = len([q for q in future_positions.values() if q > 0])
        slots = calc_buy_slots(int(max_positions), int(positions_after_sell))

    cash_aware_selected_symbols: list[str] = []
    cash_aware_reject_symbols: set[str] = set()
    cash_aware_pool_count = 0
    execution_ranked = list(ranked)
    if candidate_plan_mode_norm == "cash_aware":
        planner_pool: list[dict[str, Any]] = []
        for item in ranked:
            if str(item.get("pre_reject_reason", "") or ""):
                continue
            cost = float(item.get("candidate_cost", 0.0) or 0.0)
            if cost <= 0.0 or cost > float(est_cash):
                continue
            planner_pool.append(item)
            if len(planner_pool) >= int(cash_aware_search_top_n):
                break
        cash_aware_pool_count = int(len(planner_pool))
        cash_aware_selected_symbols = _resolve_cash_aware_subset(
            planner_candidates=planner_pool,
            slots=int(slots),
            cash_available=float(est_cash),
        )
        selected_symbol_set = {str(sym).lower() for sym in cash_aware_selected_symbols}
        planner_pool_symbols = {str(item.get("symbol", "")).lower() for item in planner_pool}
        cash_aware_reject_symbols = planner_pool_symbols - selected_symbol_set
        if selected_symbol_set:
            execution_ranked = [
                *[item for item in ranked if str(item.get("symbol", "")).lower() in selected_symbol_set],
                *[item for item in ranked if str(item.get("symbol", "")).lower() not in selected_symbol_set],
            ]

    selected_n = 0
    slot_pass_symbols: list[str] = []
    cash_lot_pass_symbols: list[str] = []
    buy_exec_plan: list[dict[str, Any]] = []
    for idx, item in enumerate(execution_ranked, start=1):
        sig = item["signal"]
        sym = str(item["symbol"]).lower()
        px = float(item["price"] or 0.0)
        pre_reject_reason = str(item.get("pre_reject_reason", "") or "")
        if pre_reject_reason:
            item["reject_reason"] = pre_reject_reason
            reject_reason_counts[item["reject_reason"]] = int(reject_reason_counts.get(item["reject_reason"], 0)) + 1
            continue
        if sym in cash_aware_reject_symbols:
            item["reject_reason"] = "NOT_SELECTED_CASH_AWARE"
            reject_reason_counts[item["reject_reason"]] = int(reject_reason_counts.get(item["reject_reason"], 0)) + 1
            continue
        if selected_n >= slots:
            if (enable_strength_rank and item["strength"] is None) or (
                bool(mf_enabled_today) and item.get("mf_score") is None
            ):
                item["reject_reason"] = "INSUFFICIENT_HISTORY"
            else:
                item["reject_reason"] = "NOT_IN_TOPK"
            reject_reason_counts[item["reject_reason"]] = int(reject_reason_counts.get(item["reject_reason"], 0)) + 1
            continue
        slot_pass_symbols.append(sym)
        sig_meta = sig.meta if isinstance(sig.meta, dict) else {}
        order_value_scale = float(item.get("order_value_scale", 1.0) or 1.0)
        mf_rank = int(item.get("mf_rank", idx))
        mf_score = float(item.get("mf_score", 0.5)) if item.get("mf_score", None) is not None else 0.5
        mf_concentrated = bool(item.get("mf_concentrated", False))
        mf_rank_tilt_scale = float(item.get("mf_rank_tilt_scale", 1.0) or 1.0)
        score_weight_scale = float(item.get("score_weight_scale", 1.0) or 1.0)
        score_weight_score = item.get("score_weight_score")
        score_weight_raw_scale = float(item.get("score_weight_raw_scale", score_weight_scale) or 1.0)
        # ── 仓位计算 ──
        direct_target_amount = _resolve_direct_target_amount(sig_meta=sig_meta, nav_close=float(nav_close))
        if direct_target_amount is not None:
            target_amount_scaled = float(direct_target_amount) * float(order_value_scale)
        elif risk_amount > 0:
            # 风险预算路径：shares = risk_amount / (k × ATR)
            _atr_v = sig_meta.get("atr_last")
            if _atr_v is not None and float(_atr_v) > 0 and px > 0:
                _stop_dist = float(atr_stop_k) * float(_atr_v)
                _shares_raw = risk_amount / _stop_dist
                target_amount_scaled = _shares_raw * px
                # 安全上限：single_stock_cap（默认无上限用 nav）
                _cap_value = float(nav_close) * 0.2  # 单票上限 20%
                if target_amount_scaled > _cap_value:
                    target_amount_scaled = _cap_value
            else:
                # ATR 不可用 → 降级为等权
                target_amount_scaled = float(nav_close) / float(_sizing_denom) if _sizing_denom > 0 else 0.0
        elif sym in _inv_vol_weights:
            # 反波动率加权路径
            target_amount_scaled = float(nav_close) * float(_inv_vol_weights[sym]) * float(order_value_scale)
        else:
            # 等权路径（risk_budget 关闭）
            target_amount_scaled = float(target_amount) * float(order_value_scale)
        qty = calc_lot_qty(target_amount_scaled, px, lot_size)
        if qty < lot_size:
            item["reject_reason"] = "SKIP_QTY_ZERO"
            reject_reason_counts[item["reject_reason"]] = int(reject_reason_counts.get(item["reject_reason"], 0)) + 1
            continue
        cost = qty * px
        item["estimated_qty"] = int(qty)
        item["estimated_amount"] = float(cost)
        item["estimated_price"] = float(px)
        if cost > est_cash:
            item["reject_reason"] = "SKIP_NO_CASH"
            item["cash_available"] = float(est_cash)
            item["cash_blocked_flag"] = True
            item["cash_blocked_reason"] = "SKIP_NO_CASH"
            reject_reason_counts[item["reject_reason"]] = int(reject_reason_counts.get(item["reject_reason"], 0)) + 1
            continue
        cash_lot_pass_symbols.append(sym)
        orders.append(
            PortfolioOrder(
                side=Side.BUY,
                symbol=sym,
                qty=qty,
                reason_code=str(sig.reason_code or sig.reason or "BUY"),
                order_value_scale=float(order_value_scale),
                trend_tier=str(sig_meta.get("trend_tier", "")),
                strong_trend=bool(sig_meta.get("strong_trend", False)),
                meta=(
                    {
                        **(dict(sig.meta) if isinstance(sig.meta, dict) else {}),
                        "mf_score": float(mf_score),
                        "mf_rank": int(mf_rank),
                        "mf_topk_selected": bool(mf_rank_triggered and (int(mf_topk) <= 0 or mf_rank <= int(mf_topk))),
                        "mf_concentrated": bool(mf_concentrated),
                        "mf_rank_tilt_scale": float(mf_rank_tilt_scale),
                        "score_weight_score": None if score_weight_score is None else float(score_weight_score),
                        "score_weight_raw_scale": float(score_weight_raw_scale),
                        "score_weight_scale": float(score_weight_scale),
                        "order_value_final": float(target_amount_scaled),
                        **(
                            dict(item.get("rotation_pair") or {})
                            if isinstance(item.get("rotation_pair"), dict)
                            else {}
                        ),
                    }
                ),
            )
        )
        est_cash -= cost
        buy_exec_plan.append(
            {
                "symbol": sym,
                "qty": int(qty),
                "price": float(px),
                "cost": float(cost),
                "cash_after_each": float(est_cash),
                "order_value_scale": float(order_value_scale),
                "mf_score": float(mf_score),
                "mf_rank": int(mf_rank),
                "mf_concentrated": bool(mf_concentrated),
                "mf_rank_tilt_scale": float(mf_rank_tilt_scale),
                "score_weight_score": None if score_weight_score is None else float(score_weight_score),
                "score_weight_raw_scale": float(score_weight_raw_scale),
                "score_weight_scale": float(score_weight_scale),
            }
        )
        future_positions[sym] = future_positions.get(sym, 0) + qty
        selected_n += 1
        item["selected"] = True
        item["selected_rank"] = selected_n
        if mf_concentrated:
            mf_concentrated_selected_count += 1
    mf_rank_applied = bool(
        bool(mf_enabled_today)
        and (
            bool(mf_rank_triggered)
            or int(mf_topk_reject_count) > 0
            or int(mf_concentrated_selected_count) > 0
        )
    )
    if strength_top_k_mode == "LIMIT_BUY_SLOTS":
        # Reserved for future explicit slot behavior. Keep current semantics unchanged.
        pass
    if candidate_audit is not None:
        for item in ranked:
            sig = item.get("signal")
            meta = sig.meta if isinstance(sig, Signal) and isinstance(sig.meta, dict) else {}
            candidate_audit.append(_build_candidate_audit_row(
                decision_date_s=decision_date_s,
                symbol=str(item["symbol"]),
                strength=(None if item["strength"] is None else float(item["strength"])),
                strength_ma=int(strength_ma),
                selected=bool(item["selected"]),
                selected_rank=item["selected_rank"],
                reject_reason=str(item["reject_reason"]),
                meta=meta,
                is_candidate=True,
                mf_score=_safe_float_or_none(item.get("mf_score")),
                mf_rank=(int(item["mf_rank"]) if item.get("mf_rank") is not None else None),
                overlay_score=_safe_float_or_none(item.get("overlay_score")),
                overlay_gate_on=bool(overlay_active_today),
                overlay_mode=overlay_mode_norm,
                overlay_observation_date=overlay_observation_date,
                overlay_score_source=overlay_score_source,
                cash_available=_safe_float_or_none(item.get("cash_available")),
                estimated_qty=(int(item["estimated_qty"]) if item.get("estimated_qty") is not None else None),
                estimated_amount=_safe_float_or_none(item.get("estimated_amount")),
                estimated_price=_safe_float_or_none(item.get("estimated_price")),
                cash_blocked_flag=bool(item.get("cash_blocked_flag", False)),
                cash_blocked_reason=str(item.get("cash_blocked_reason", "") or ""),
            ))
    if debug_plan is not None:
        debug_plan["buy_candidates_count"] = int(len(ranked))
        debug_plan["buy_slots"] = int(slots)
        debug_plan["selected_symbols"] = [str(x["symbol"]) for x in ranked if bool(x.get("selected"))]
        debug_plan["selected_count"] = int(selected_n)
        debug_plan["after_slot_filter_count"] = int(len(slot_pass_symbols))
        debug_plan["after_cash_lot_count"] = int(len(cash_lot_pass_symbols))
        debug_plan["buys_executed"] = buy_exec_plan
        debug_plan["reject_reason_counts"] = dict(reject_reason_counts)
        debug_plan["selected_order_value_scales"] = [float(x.get("order_value_scale", 1.0)) for x in buy_exec_plan]
        debug_plan["weak_trend_selected_count"] = int(sum(1 for x in ranked if bool(x.get("selected")) and str(getattr(x.get("signal"), "meta", {}).get("trend_tier", "")).upper() == "WEAK"))
        debug_plan["strong_trend_selected_count"] = int(sum(1 for x in ranked if bool(x.get("selected")) and str(getattr(x.get("signal"), "meta", {}).get("trend_tier", "")).upper() == "STRONG"))
        debug_plan["mf_rank_triggered"] = bool(mf_rank_triggered)
        debug_plan["mf_rank_applied"] = bool(mf_rank_applied)
        debug_plan["mf_gate_on"] = bool(mf_enabled_today)
        debug_plan["moneyflow_overlay_enabled"] = bool(overlay_mode_norm in {"shadow", "tiebreak", "soft_weight"})
        debug_plan["moneyflow_overlay_mode"] = overlay_mode_norm
        debug_plan["moneyflow_overlay_gate_on"] = bool(overlay_active_today)
        debug_plan["moneyflow_overlay_observation_date"] = (
            overlay_observation_date.isoformat()
            if isinstance(overlay_observation_date, date)
            else ""
        )
        debug_plan["moneyflow_overlay_score_source"] = str(overlay_score_source or "")
        debug_plan["mf_topk_reject_count"] = int(mf_topk_reject_count)
        debug_plan["mf_concentrated_selected_count"] = int(mf_concentrated_selected_count)
        debug_plan["mf_candidates_when_triggered"] = int(len(ranked)) if bool(mf_rank_triggered) else 0
        debug_plan["mf_rank_tilt_enabled"] = bool(str(weight_mode or "").strip().lower() == "mf_rank_tilt")
        debug_plan["score_weighted_enabled"] = bool(str(weight_mode or "").strip().lower() == "score_weighted")
        debug_plan["score_weight_min_scale"] = float(score_weight_min_scale)
        debug_plan["score_weight_max_scale"] = float(score_weight_max_scale)
        debug_plan["selected_score_weight_scales"] = [float(x.get("score_weight_scale", 1.0)) for x in buy_exec_plan]
        debug_plan["candidate_plan_mode"] = str(candidate_plan_mode_norm)
        debug_plan["cash_aware_enabled"] = bool(candidate_plan_mode_norm == "cash_aware")
        debug_plan["cash_aware_search_top_n"] = int(cash_aware_search_top_n)
        debug_plan["cash_aware_pool_count"] = int(cash_aware_pool_count)
        debug_plan["cash_aware_selected_symbols"] = list(cash_aware_selected_symbols)
        debug_plan["cash_aware_reject_count"] = int(len(cash_aware_reject_symbols))
        debug_plan["rotation_replace_enabled"] = bool(rotation_replace_enabled)
        debug_plan["rotation_replace_active"] = bool(rotation_enabled_today)
        debug_plan["rotation_replace_only_strong_risk_on"] = bool(rotation_replace_only_strong_risk_on)
        debug_plan["rotation_replace_count"] = int(
            sum(1 for pair in list(rotation_plan.get("pairs") or []) if bool(pair.get("executed")))
        )
        debug_plan["rotation_candidate_pool_count"] = int(len(list(rotation_plan.get("candidate_pool") or [])))
        debug_plan["rotation_eligible_held_count"] = int(len(list(rotation_plan.get("held_pool") or [])))
        debug_plan["rotation_replace_pairs"] = [
            {
                "candidate_symbol": str(pair.get("candidate_symbol", "")).lower(),
                "candidate_score": _safe_float_or_none(pair.get("candidate_score")),
                "held_symbol": str(pair.get("held_symbol", "")).lower(),
                "held_score": _safe_float_or_none(pair.get("held_score")),
                "score_gap": _safe_float_or_none(pair.get("score_gap")),
                "held_days": pair.get("held_days"),
            }
            for pair in list(rotation_plan.get("pairs") or [])
            if bool(pair.get("executed"))
        ]

    return orders


def _compute_metrics(
    daily_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    *,
    max_positions: int,
    blocked_by_trend_count: int = 0,
    total_buy_signals: int = 0,
    candidates_df: pd.DataFrame | None = None,
    enable_strength_rank: bool = False,
    strength_ma: int = 120,
) -> dict[str, Any]:
    return compute_backtest_metrics(
        daily_df,
        trades_df,
        max_positions=max_positions,
        blocked_by_trend_count=blocked_by_trend_count,
        total_buy_signals=total_buy_signals,
        candidates_df=candidates_df,
        enable_strength_rank=enable_strength_rank,
        strength_ma=strength_ma,
    )


from backend.core.portfolio.portfolio_loop import run_portfolio_backtest
