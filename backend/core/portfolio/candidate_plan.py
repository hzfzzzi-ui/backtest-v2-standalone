from __future__ import annotations

from datetime import date
import math
from types import SimpleNamespace
from typing import Any

from backend.core.core.models import Signal
from backend.core.portfolio.order_sizing import build_sizing_context, resolve_order_sizing
from backend.core.portfolio.selection_order import normalize_candidate_order, sort_by_strength_with_tiebreak
from backend.core.portfolio.selection_scoring import (
    build_score_weight_scale_maps as _build_score_weight_scale_maps,
    resolve_mf_rank_tilt_scale as _resolve_mf_rank_tilt_scale,
    safe_float_or_none as _safe_float_or_none,
    select_rotation_pairs as _select_rotation_pairs,
)
from backend.core.portfolio.sizing import calc_buy_slots


def _allow_existing_holding_top_up(meta: dict[str, Any] | None) -> bool:
    payload = dict(meta or {})
    if bool(payload.get("trans_up_recovery_confirmed_scale_up_active", False)):
        return True
    sleeve_id = str(payload.get("sleeve_id", "") or "").strip().lower()
    alpha_id = str(payload.get("alpha_id", "") or "").strip().lower()
    strategy_role = str(payload.get("strategy_role", "") or "").strip().lower()
    execution_path = str(payload.get("execution_path", "") or "").strip().lower()
    target_weight_basis = str(payload.get("target_weight_basis", "") or "").strip().lower()
    if sleeve_id != "cn_etf_beta" and alpha_id != "cn_etf_beta":
        return False
    if strategy_role != "governed_broad_based_standalone_mainline":
        return False
    if target_weight_basis != "delta_deploy_gap":
        return False
    return execution_path in {
        "bull_inter_rebalance_deploy",
        "trans_up_inter_rebalance_deploy",
        "risk_off_core_accumulation_deploy",
        "riskoff_cash_drip_topup",
        "riskoff_account_budget_materialization",
        "weak_state_inter_rebalance_defense_redeploy",
        "shared_risk_on_to_defensive_transition_defense_establish",
    }


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


def _resolve_overlay_veto_bottom_pct(mode: str) -> float:
    text = str(mode or "").strip().lower()
    prefix = "veto_bottom"
    if not text.startswith(prefix):
        return 0.0
    suffix = text[len(prefix):].strip()
    if not suffix:
        return 0.0
    try:
        pct = float(suffix)
    except Exception:
        return 0.0
    if pct <= 0.0:
        return 0.0
    return min(1.0, float(pct) / 100.0)


def _overlay_mode_supported(mode: str) -> bool:
    text = str(mode or "").strip().lower()
    return text in {
        "shadow",
        "tiebreak",
        "soft_weight",
        "bull_only_tiebreak",
        "band_rerank",
        "bull_only_band_rerank",
        "bull_trans_up_band_rerank",
    } or _resolve_overlay_veto_bottom_pct(text) > 0.0


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
    mf_score: float | None = None,
    mf_rank: int | None = None,
    final_score_value: float | None = None,
    final_score_rank: int | None = None,
    overlay_score: float | None = None,
    overlay_gate_on: bool = False,
    overlay_mode: str = "off",
    overlay_observation_date: date | None = None,
    overlay_score_source: str = "",
    estimated_qty: int | None = None,
    estimated_amount: float | None = None,
    estimated_price: float | None = None,
) -> dict[str, Any]:
    _meta = dict(meta or {})
    canonical_final_score_value = (
        final_score_value
        if final_score_value is not None
        else (
            mf_score
            if mf_score is not None
            else _safe_float_or_none(_meta.get("final_score"))
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
        "reject_reason": str(reject_reason),
        "owner_system": str(
            _meta.get("owner_system")
            or _meta.get("sleeve_id")
            or _meta.get("alpha_id")
            or ""
        ),
        "decision_layer": "candidate_plan",
        "alpha_source": str(_meta.get("alpha_source", "") or ""),
        "final_score": _safe_float_or_none(_meta.get("final_score")),
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
        "estimated_qty": None if estimated_qty is None else int(estimated_qty),
        "estimated_amount": None if estimated_amount is None else float(estimated_amount),
        "estimated_price": None if estimated_price is None else float(estimated_price),
        "cash_blocked_flag": False,
        "cash_blocked_reason": "",
    }

def build_candidate_plan(
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
    base_order_value: float = 0.0,
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
) -> dict[str, Any]:
    future_positions = {str(k).lower(): int(v) for k, v in dict(positions or {}).items() if int(v) > 0}
    est_cash = float(cash_available)
    for sig in list(sell_signals or ()):
        sym = str(sig.symbol).lower()
        held = int(future_positions.get(sym, 0))
        if held <= 0:
            continue
        sig_qty = int(getattr(sig, "qty", 0) or 0)
        qty = held if sig_qty <= 0 else min(held, sig_qty)
        px = float(next_open.get(sym, 0.0) or 0.0)
        if qty <= 0 or px <= 0:
            continue
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

    strength_map = dict(strength_map or {})
    mf_score_map = dict(mf_score_map or {})
    overlay_score_map = dict(overlay_score_map or {})
    decision_close_map = {str(k).lower(): float(v) for k, v in dict(decision_close_map or {}).items()}
    overlay_mode_norm = str(overlay_mode or "off").strip().lower() or "off"
    overlay_band_limit = max(0, int(overlay_band_limit or 0))
    overlay_veto_bottom_pct = _resolve_overlay_veto_bottom_pct(overlay_mode_norm)
    market_state_today_norm = str(market_state_today or "").strip().upper()
    overlay_bull_only = overlay_mode_norm in {"bull_only_tiebreak", "bull_only_band_rerank"}
    overlay_bull_trans_up = overlay_mode_norm == "bull_trans_up_band_rerank"
    overlay_state_gate_mode = (
        "bull_only"
        if bool(overlay_bull_only)
        else ("bull_trans_up" if bool(overlay_bull_trans_up) else "")
    )
    overlay_bull_gate_on = bool(overlay_bull_only) and market_state_today_norm == "BULL"
    overlay_bull_trans_up_gate_on = bool(overlay_bull_trans_up) and market_state_today_norm in {"BULL", "TRANS_UP"}
    overlay_state_gate_on = (
        bool(overlay_bull_gate_on)
        if bool(overlay_bull_only)
        else (bool(overlay_bull_trans_up_gate_on) if bool(overlay_bull_trans_up) else True)
    )
    overlay_active_today = (
        bool(overlay_gate_on_today)
        and _overlay_mode_supported(overlay_mode_norm)
        and bool(overlay_state_gate_on)
    )
    decision_date_s = decision_date.isoformat() if isinstance(decision_date, date) else ""
    planning_rows: list[dict[str, Any]] = []
    reject_reason_counts: dict[str, int] = {}

    ranked: list[dict[str, Any]] = []
    for sig in list(buy_signals or ()):
        sym = str(sig.symbol).lower()
        raw_meta = getattr(sig, "meta", {})
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        if sym in future_positions and int(future_positions.get(sym, 0)) > 0 and not _allow_existing_holding_top_up(meta):
            reject_reason_counts["ALREADY_HELD"] = int(reject_reason_counts.get("ALREADY_HELD", 0)) + 1
            planning_rows.append(
                _build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="ALREADY_HELD",
                    meta=meta,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                )
            )
            continue
        px = float(next_open.get(sym, 0.0) or 0.0)
        if px <= 0.0:
            reject_reason_counts["NOT_TRADABLE"] = int(reject_reason_counts.get("NOT_TRADABLE", 0)) + 1
            planning_rows.append(
                _build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="NOT_TRADABLE",
                    meta=meta,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                )
            )
            continue
        if float(min_trade_price) > 0.0 and px < float(min_trade_price):
            reject_reason_counts["SKIP_MIN_PRICE_AT_ORDER"] = int(reject_reason_counts.get("SKIP_MIN_PRICE_AT_ORDER", 0)) + 1
            planning_rows.append(
                _build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="SKIP_MIN_PRICE_AT_ORDER",
                    meta=meta,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                )
            )
            continue
        decision_close = _safe_float_or_none(decision_close_map.get(sym))
        if _entry_gap_guard_hit(
            enable_entry_gap_guard=bool(enable_entry_gap_guard),
            entry_gap_guard_pct=float(entry_gap_guard_pct),
            next_open_price=float(px),
            decision_close_price=decision_close,
        ):
            reject_reason_counts["SKIP_ENTRY_GAP_GUARD"] = int(reject_reason_counts.get("SKIP_ENTRY_GAP_GUARD", 0)) + 1
            planning_rows.append(
                _build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=None,
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="SKIP_ENTRY_GAP_GUARD",
                    meta=meta,
                    overlay_score=_safe_float_or_none(overlay_score_map.get(sym)),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                )
            )
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
                "baseline_strength": baseline_strength,
                "overlay_score": _safe_float_or_none(overlay_score_map.get(sym)),
                "overlay_gate_on": bool(overlay_active_today),
                "overlay_mode": overlay_mode_norm,
                "overlay_observation_date": overlay_observation_date,
                "overlay_score_source": str(overlay_score_source or ""),
                "order_value_scale": float(meta.get("order_value_scale", 1.0) or 1.0),
                "selected": False,
                "selected_rank": None,
                "reject_reason": "",
            }
        )

    buy_candidates_count = int(len(ranked))
    forced_not_in_topk_symbols: set[str] = set()
    mf_rank_triggered = False
    mf_topk_reject_count = 0
    overlay_rerank_count = 0
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
            item["final_score_value"] = float(score_val)
        if len(ranked) < 5:
            for item in ranked:
                item["mf_score"] = 0.5
                item["final_score_value"] = 0.5
        rank_sorted = sorted(
            ranked,
            key=lambda x: (
                -float(x.get("mf_score", 0.5)),
                -float(x.get("overlay_score", 0.5))
                if bool(overlay_active_today)
                and overlay_mode_norm in {"tiebreak", "bull_only_tiebreak"}
                and x.get("overlay_score") is not None
                else 0.0,
                str(x.get("symbol", "")).lower(),
            ),
        )
        for idx, item in enumerate(rank_sorted, start=1):
            item["mf_rank"] = int(idx)
            item["final_score_rank"] = int(idx)
        if bool(overlay_active_today) and overlay_mode_norm in {"band_rerank", "bull_only_band_rerank", "bull_trans_up_band_rerank"} and int(overlay_band_limit) > 1:
            band_limit = min(len(rank_sorted), int(overlay_band_limit))
            if band_limit > 1:
                prefix = list(rank_sorted[:band_limit])
                suffix = list(rank_sorted[band_limit:])
                reranked_prefix = sorted(
                    prefix,
                    key=lambda x: (
                        1 if x.get("overlay_score") is None else 0,
                        -(float(x.get("overlay_score")) if x.get("overlay_score") is not None else 0.0),
                        int(x.get("mf_rank", 10**9) or 10**9),
                        str(x.get("symbol", "")).lower(),
                    ),
                )
                overlay_rerank_count = int(
                    sum(
                        1
                        for before, after in zip(prefix, reranked_prefix)
                        if str(before.get("symbol", "")).lower() != str(after.get("symbol", "")).lower()
                    )
                )
                rank_sorted = reranked_prefix + suffix
                for idx, item in enumerate(rank_sorted, start=1):
                    item["final_score_rank"] = int(idx)
        if len(ranked) > int(slots):
            mf_rank_triggered = True
            ranked = list(rank_sorted)
            if float(momentum_top_pct) > 0:
                topk_n = max(1, int(len(ranked) * float(momentum_top_pct)))
                if int(mf_topk) > 0:
                    topk_n = min(topk_n, int(mf_topk))
            else:
                topk_n = max(0, int(mf_topk))
            if topk_n > 0 and topk_n >= int(slots):
                for item in ranked[topk_n:]:
                    forced_not_in_topk_symbols.add(str(item.get("symbol", "")).lower())
                mf_topk_reject_count = int(len(forced_not_in_topk_symbols))
        else:
            order = normalize_candidate_order([str(x.get("symbol", "")) for x in ranked])
            order_pos = {s: i for i, s in enumerate(order)}
            ranked.sort(key=lambda x: int(order_pos.get(str(x.get("symbol", "")).lower(), 10**9)))
    else:
        if enable_strength_rank:
            ranked = sort_by_strength_with_tiebreak(ranked)
        else:
            order = normalize_candidate_order([str(x.get("symbol", "")) for x in ranked])
            order_pos = {s: i for i, s in enumerate(order)}
            ranked.sort(key=lambda x: int(order_pos.get(str(x.get("symbol", "")).lower(), 10**9)))

    forced_overlay_veto_symbols: set[str] = set()
    if bool(overlay_active_today) and float(overlay_veto_bottom_pct) > 0.0:
        veto_pool = [
            item
            for item in ranked
            if item.get("overlay_score") is not None
        ]
        if veto_pool:
            veto_count = min(
                len(veto_pool),
                max(1, int(math.ceil(float(len(veto_pool)) * float(overlay_veto_bottom_pct)))),
            )
            veto_sorted = sorted(
                veto_pool,
                key=lambda x: (
                    float(x.get("overlay_score", 0.0) or 0.0),
                    str(x.get("symbol", "")).lower(),
                ),
            )
            forced_overlay_veto_symbols = {
                str(item.get("symbol", "")).lower()
                for item in veto_sorted[:veto_count]
            }

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
    sizing_context = build_sizing_context(
        items=ranked,
        nav_close=float(nav_close),
        max_positions=int(max_positions),
        min_positions=int(min_positions),
        base_order_value=float(base_order_value),
        weight_mode=str(weight_mode),
        atr_close_map=atr_close_map,
    )

    for idx, item in enumerate(ranked, start=1):
        sym = str(item.get("symbol", "")).lower()
        px = float(item.get("price", 0.0) or 0.0)
        if float(min_trade_price) > 0.0 and px < float(min_trade_price):
            item["pre_reject_reason"] = "SKIP_MIN_PRICE_AT_ORDER"
            continue
        if sym in forced_overlay_veto_symbols:
            item["pre_reject_reason"] = "MONEYFLOW_OVERLAY_VETO"
            continue
        if sym in forced_not_in_topk_symbols:
            item["pre_reject_reason"] = "NOT_IN_TOPK"
            continue
        sig = item["signal"]
        raw_sig_meta = getattr(sig, "meta", {})
        sig_meta = raw_sig_meta if isinstance(raw_sig_meta, dict) else {}
        order_value_scale = float(item.get("order_value_scale", 1.0) or 1.0)
        mf_rank = int(item.get("mf_rank", idx))
        mf_score_raw = item.get("mf_score", None)
        mf_score = float(mf_score_raw) if mf_score_raw is not None else 0.5
        final_score_rank = int(item.get("final_score_rank", mf_rank))
        final_score_value_raw = item.get("final_score_value", mf_score_raw)
        final_score_value = (
            float(final_score_value_raw) if final_score_value_raw is not None else mf_score
        )
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
        score_weight_raw_scale = float(_score_weight_raw_scales.get(sym, score_weight_scale) or 1.0)
        order_value_scale = float(order_value_scale) * float(score_weight_scale)
        trend_tier = str(sig_meta.get("trend_tier", "")).upper()
        if order_value_scale <= 0:
            item["pre_reject_reason"] = "BLOCK_WEAK_TIER_DISABLED" if trend_tier == "WEAK" else "SKIP_QTY_ZERO"
            continue
        sizing = resolve_order_sizing(
            sig_meta=sig_meta,
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
        if qty < lot_size:
            item["pre_reject_reason"] = "SKIP_QTY_ZERO"
            continue
        item["order_value_scale"] = float(order_value_scale)
        item["mf_rank"] = int(mf_rank)
        item["mf_score"] = None if mf_score_raw is None else float(mf_score)
        item["final_score_rank"] = int(final_score_rank)
        item["final_score_value"] = float(final_score_value)
        item["mf_concentrated"] = bool(mf_concentrated)
        item["mf_rank_tilt_scale"] = float(mf_rank_tilt_scale)
        item["score_weight_score"] = None if score_weight_score is None else float(score_weight_score)
        item["score_weight_raw_scale"] = float(score_weight_raw_scale)
        item["score_weight_scale"] = float(score_weight_scale)
        item["target_amount_scaled"] = float(target_amount_scaled)
        item["candidate_qty"] = int(qty)
        item["candidate_cost"] = float(sizing["cost"])
        item["pre_reject_reason"] = ""

    rotation_plan: dict[str, Any] = {"candidate_pool": [], "held_pool": [], "pairs": []}
    planned_rotation_sell_signals: list[Any] = []
    rotation_pair_meta_by_symbol: dict[str, dict[str, Any]] = {}
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
            planned_rotation_sell_signals.append(
                SimpleNamespace(
                    symbol=held_sym,
                    qty=held_qty,
                    reason="ROTATION_REPLACE",
                    reason_code="ROTATION_REPLACE",
                    meta=rotation_meta,
                )
            )
            future_positions.pop(held_sym, None)
            est_cash += float(held_qty) * float(held_px)
            rotation_pair_meta_by_symbol[candidate_sym] = dict(rotation_meta)
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
            if len(planner_pool) >= int(max(1, int(cash_aware_search_top_n))):
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

    planned_items: list[dict[str, Any]] = []
    for item in execution_ranked:
        sym = str(item.get("symbol", "")).lower()
        sig = item.get("signal")
        raw_meta = getattr(sig, "meta", {}) if sig is not None else {}
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        if str(item.get("pre_reject_reason", "") or ""):
            reject_reason = str(item.get("pre_reject_reason", "") or "")
            reject_reason_counts[reject_reason] = int(reject_reason_counts.get(reject_reason, 0)) + 1
            planning_rows.append(
                _build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=(None if item.get("strength") is None else float(item.get("strength"))),
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason=reject_reason,
                    meta=meta,
                    mf_score=_safe_float_or_none(item.get("mf_score")),
                    mf_rank=(int(item["mf_rank"]) if item.get("mf_rank") is not None else None),
                    final_score_value=_safe_float_or_none(item.get("final_score_value")),
                    final_score_rank=(int(item["final_score_rank"]) if item.get("final_score_rank") is not None else None),
                    overlay_score=_safe_float_or_none(item.get("overlay_score")),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                    estimated_qty=(int(item["candidate_qty"]) if item.get("candidate_qty") is not None else None),
                    estimated_amount=_safe_float_or_none(item.get("candidate_cost")),
                    estimated_price=_safe_float_or_none(item.get("price")),
                )
            )
            continue
        if sym in cash_aware_reject_symbols:
            reject_reason_counts["NOT_SELECTED_CASH_AWARE"] = int(reject_reason_counts.get("NOT_SELECTED_CASH_AWARE", 0)) + 1
            planning_rows.append(
                _build_candidate_audit_row(
                    decision_date_s=decision_date_s,
                    symbol=sym,
                    strength=(None if item.get("strength") is None else float(item.get("strength"))),
                    strength_ma=int(strength_ma),
                    selected=False,
                    selected_rank=None,
                    reject_reason="NOT_SELECTED_CASH_AWARE",
                    meta=meta,
                    mf_score=_safe_float_or_none(item.get("mf_score")),
                    mf_rank=(int(item["mf_rank"]) if item.get("mf_rank") is not None else None),
                    final_score_value=_safe_float_or_none(item.get("final_score_value")),
                    final_score_rank=(int(item["final_score_rank"]) if item.get("final_score_rank") is not None else None),
                    overlay_score=_safe_float_or_none(item.get("overlay_score")),
                    overlay_gate_on=bool(overlay_active_today),
                    overlay_mode=overlay_mode_norm,
                    overlay_observation_date=overlay_observation_date,
                    overlay_score_source=overlay_score_source,
                    estimated_qty=(int(item["candidate_qty"]) if item.get("candidate_qty") is not None else None),
                    estimated_amount=_safe_float_or_none(item.get("candidate_cost")),
                    estimated_price=_safe_float_or_none(item.get("price")),
                )
            )
            continue
        planned_item = dict(item)
        if sym in rotation_pair_meta_by_symbol:
            planned_item["rotation_pair"] = dict(rotation_pair_meta_by_symbol[sym])
        planned_items.append(planned_item)

    return {
        "plan_mode": str(candidate_plan_mode_norm),
        "planned_items": planned_items,
        "planned_buy_signals": [item["signal"] for item in planned_items if item.get("signal") is not None],
        "planned_rotation_sell_signals": planned_rotation_sell_signals,
        "planned_rotation_sell_symbols": [str(getattr(sig, "symbol", "")).lower() for sig in planned_rotation_sell_signals],
        "rotation_pair_meta_by_symbol": rotation_pair_meta_by_symbol,
        "candidate_rows": planning_rows,
        "reject_reason_counts": reject_reason_counts,
        "debug_plan": {
            "buy_candidates_count": int(buy_candidates_count),
            "candidate_plan_mode": str(candidate_plan_mode_norm),
            "cash_aware_enabled": bool(candidate_plan_mode_norm == "cash_aware"),
            "cash_aware_search_top_n": int(max(1, int(cash_aware_search_top_n))),
            "cash_aware_pool_count": int(cash_aware_pool_count),
            "cash_aware_selected_symbols": list(cash_aware_selected_symbols),
            "cash_aware_reject_count": int(len(cash_aware_reject_symbols)),
            "final_score_rank_triggered": bool(mf_rank_triggered),
            "final_score_rank_applied": bool(bool(mf_enabled_today) and (bool(mf_rank_triggered) or int(mf_topk_reject_count) > 0)),
            "final_score_rank_gate_on": bool(mf_enabled_today),
            "final_score_topk_reject_count": int(mf_topk_reject_count),
            "final_score_candidates_when_triggered": int(len(ranked)) if bool(mf_rank_triggered) else 0,
            "final_score_rank_tilt_enabled": bool(str(weight_mode or "").strip().lower() == "mf_rank_tilt"),
            "mf_rank_triggered": bool(mf_rank_triggered),
            "mf_rank_applied": bool(bool(mf_enabled_today) and (bool(mf_rank_triggered) or int(mf_topk_reject_count) > 0)),
            "mf_gate_on": bool(mf_enabled_today),
            "mf_topk_reject_count": int(mf_topk_reject_count),
            "mf_candidates_when_triggered": int(len(ranked)) if bool(mf_rank_triggered) else 0,
            "mf_rank_tilt_enabled": bool(str(weight_mode or "").strip().lower() == "mf_rank_tilt"),
            "score_weighted_enabled": bool(str(weight_mode or "").strip().lower() == "score_weighted"),
            "score_weight_min_scale": float(score_weight_min_scale),
            "score_weight_max_scale": float(score_weight_max_scale),
            "moneyflow_overlay_enabled": bool(_overlay_mode_supported(overlay_mode_norm)),
            "moneyflow_overlay_mode": overlay_mode_norm,
            "moneyflow_overlay_gate_on": bool(overlay_active_today),
            "moneyflow_overlay_band_limit": int(overlay_band_limit),
            "moneyflow_overlay_rerank_count": int(overlay_rerank_count),
            "moneyflow_overlay_state_gate_mode": str(overlay_state_gate_mode or ""),
            "moneyflow_overlay_state_gate_on": bool(overlay_state_gate_on),
            "moneyflow_overlay_bull_only": bool(overlay_bull_only),
            "moneyflow_overlay_bull_gate_on": bool(overlay_bull_gate_on),
            "moneyflow_overlay_bull_trans_up": bool(overlay_bull_trans_up),
            "moneyflow_overlay_bull_trans_up_gate_on": bool(overlay_bull_trans_up_gate_on),
            "moneyflow_overlay_bull_suppressed": bool(overlay_bull_only) and not bool(overlay_bull_gate_on),
            "moneyflow_overlay_veto_bottom_pct": float(overlay_veto_bottom_pct),
            "moneyflow_overlay_veto_count": int(len(forced_overlay_veto_symbols)),
            "moneyflow_overlay_observation_date": (
                overlay_observation_date.isoformat()
                if isinstance(overlay_observation_date, date)
                else ""
            ),
            "moneyflow_overlay_score_source": str(overlay_score_source or ""),
            "rotation_replace_enabled": bool(rotation_replace_enabled),
            "rotation_replace_active": bool(rotation_enabled_today),
            "rotation_replace_only_strong_risk_on": bool(rotation_replace_only_strong_risk_on),
            "rotation_replace_count": int(len(planned_rotation_sell_signals)),
            "rotation_candidate_pool_count": int(len(list(rotation_plan.get("candidate_pool") or []))),
            "rotation_eligible_held_count": int(len(list(rotation_plan.get("held_pool") or []))),
            "rotation_replace_pairs": [
                {
                    "candidate_symbol": str(pair.get("candidate_symbol", "")).lower(),
                    "candidate_score": _safe_float_or_none(pair.get("candidate_score")),
                    "held_symbol": str(pair.get("held_symbol", "")).lower(),
                    "held_score": _safe_float_or_none(pair.get("held_score")),
                    "score_gap": _safe_float_or_none(pair.get("score_gap")),
                    "held_days": pair.get("held_days"),
                }
                for pair in list(rotation_plan.get("pairs") or [])
                if str(pair.get("held_symbol", "")).strip()
            ],
            "candidate_plan_reject_count": int(sum(int(v or 0) for v in reject_reason_counts.values())),
            "candidate_plan_selected_symbols": [str(item.get("symbol", "")).lower() for item in planned_items],
        },
    }
