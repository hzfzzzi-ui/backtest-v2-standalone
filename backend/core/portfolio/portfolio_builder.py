from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from math import floor, sqrt
from typing import Any

import pandas as pd

from backend.core.config.models import BenchmarkRegimeConfig, BreadthConfig, CostConfig, ExitConfig, MarketFilterConfig, RiskBudgetConfig, RiskConfig, SizingConfig
from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from backend.core.strategies.base import Strategy
from backend.core.portfolio.selection_order import normalize_candidate_order, sort_by_strength_with_tiebreak


@dataclass(slots=True)
class PortfolioOrder:
    side: Side
    symbol: str
    qty: int
    reason_code: str
    order_value_scale: float = 1.0
    trend_tier: str = ""
    strong_trend: bool = False
    meta: dict[str, Any] | None = None


@dataclass(slots=True)
class PortfolioBacktestResult:
    daily: pd.DataFrame
    trades: pd.DataFrame
    candidates: pd.DataFrame
    metrics: dict[str, Any]


def build_backtest_price_indices(
    *,
    history: pd.DataFrame,
    trading_days: list[date],
) -> tuple[dict[tuple[date, str], float], dict[tuple[date, str], float]]:
    """Build execution open lookup plus valuation close lookup.

    Execution keeps raw per-day opens. Valuation closes use same-symbol forward fill
    over the trading calendar, but never extend past the last real bar.
    """
    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"]).dt.normalize()
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    open_idx: dict[tuple[date, str], float] = {}
    for row in hist.itertuples(index=False):
        d = pd.Timestamp(row.date).date()
        s = str(row.symbol).lower()
        open_idx[(d, s)] = float(row.open)

    if hist.empty or not trading_days:
        return open_idx, {}

    cal = pd.DatetimeIndex(pd.to_datetime([pd.Timestamp(d).normalize() for d in trading_days]))
    close_wide = (
        hist.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
        .sort_index()
        .reindex(cal)
        .ffill()
    )
    last_dates = hist.groupby("symbol", sort=False)["date"].max()
    for sym, last_dt in last_dates.items():
        close_wide.loc[close_wide.index > pd.Timestamp(last_dt), str(sym).lower()] = pd.NA

    close_idx: dict[tuple[date, str], float] = {}
    stacked = close_wide.stack()
    stacked = stacked[stacked.notna()]
    for (dt, sym), value in stacked.items():
        close_idx[(pd.Timestamp(dt).date(), str(sym).lower())] = float(value)
    return open_idx, close_idx


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
    _use_hfq = hfq_close_idx is not None and position_entry_adj is not None
    _val_idx = hfq_close_idx if _use_hfq else close_idx
    _entry_adj = position_entry_adj or {}
    market_value = 0.0
    pos_values: list[tuple[str, float]] = []
    for sym, qty in positions.items():
        c = float(_val_idx.get((day, sym), 0.0) or 0.0)
        if _use_hfq:
            ea = _entry_adj.get(sym, 1.0)
            v = c / ea * qty if ea > 1e-8 else c * qty
        else:
            v = c * qty
        market_value += v
        pos_values.append((sym, v))
    nav = float(cash) + float(market_value)
    return nav, market_value, pos_values


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
    max_pos = max(0, int(max_positions))
    pos_cnt = max(0, int(positions_after_sell))
    return max(0, max_pos - pos_cnt)


def calc_lot_qty(target_amount: float, open_price: float, lot_size: int) -> int:
    if target_amount <= 0 or open_price <= 0 or lot_size <= 0:
        return 0
    raw = floor(target_amount / open_price)
    return int(raw // lot_size * lot_size)


def resolve_mf_gate_on_today(
    *,
    enable_multifactor_rank: bool,
    mf_rank_gate_mode: str,
    risk_on_today: bool,
    strong_risk_on_today: bool,
    market_state_today: str = "",
) -> bool:
    if not bool(enable_multifactor_rank):
        return False
    mode = str(mf_rank_gate_mode or "ALWAYS_ON").upper()
    market_state = str(market_state_today or "").upper()
    if mode in {"ALWAYS", "ALWAYS_ON"}:
        return True
    if mode in {"ONLY_RISK_ON", "RISK_ON_ONLY"}:
        return bool(risk_on_today)
    if mode in {"STRONG_RISK_ON", "ONLY_STRONG_RISK_ON"}:
        return bool(strong_risk_on_today)
    if mode == "BULL_ONLY":
        return market_state == "BULL"
    if mode == "TRANS_UP_OR_BULL":
        return market_state in {"TRANS_UP", "BULL"}
    return False


def _safe_float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_date_or_none(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None or value == "":
        return None
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def _resolve_rotation_score(
    *,
    symbol: str,
    item: dict[str, Any] | None = None,
    mf_score_map: dict[str, float | None] | None = None,
    strength_map: dict[str, float | None] | None = None,
) -> float | None:
    sym = str(symbol).lower()
    score = _safe_float_or_none(dict(mf_score_map or {}).get(sym))
    if score is not None:
        return score
    score = _safe_float_or_none(dict(strength_map or {}).get(sym))
    if score is not None:
        return score
    if isinstance(item, dict):
        score = _safe_float_or_none(item.get("mf_score"))
        if score is not None:
            return score
        score = _safe_float_or_none(item.get("strength"))
        if score is not None:
            return score
    return None


def _select_rotation_pairs(
    *,
    ranked: list[dict[str, Any]],
    future_positions: dict[str, int],
    next_open: dict[str, float],
    decision_date: date | None,
    holding_entry_dates: dict[str, date | None] | None,
    mf_score_map: dict[str, float | None] | None,
    strength_map: dict[str, float | None] | None,
    candidate_top_n: int,
    max_swaps_per_day: int,
    min_score_gap: float,
    rotation_min_hold_days: int,
) -> dict[str, Any]:
    candidate_pool: list[dict[str, Any]] = []
    for item in ranked:
        if str(item.get("pre_reject_reason", "") or ""):
            continue
        sym = str(item.get("symbol", "")).lower()
        score = _resolve_rotation_score(
            symbol=sym,
            item=item,
            mf_score_map=mf_score_map,
            strength_map=strength_map,
        )
        if score is None:
            continue
        candidate_pool.append(
            {
                "symbol": sym,
                "score": float(score),
                "item": item,
            }
        )
        if len(candidate_pool) >= max(1, int(candidate_top_n)):
            break

    entry_date_map = {str(k).lower(): _safe_date_or_none(v) for k, v in dict(holding_entry_dates or {}).items()}
    held_pool: list[dict[str, Any]] = []
    for raw_sym, raw_qty in dict(future_positions or {}).items():
        sym = str(raw_sym).lower()
        qty = int(raw_qty)
        if qty <= 0:
            continue
        if float(next_open.get(sym, 0.0) or 0.0) <= 0.0:
            continue
        held_days: int | None = None
        if int(rotation_min_hold_days) > 0:
            if not isinstance(decision_date, date):
                continue
            entry_dt = entry_date_map.get(sym)
            if entry_dt is None:
                continue
            held_days = int((decision_date - entry_dt).days)
            if held_days < int(rotation_min_hold_days):
                continue
        score = _resolve_rotation_score(
            symbol=sym,
            mf_score_map=mf_score_map,
            strength_map=strength_map,
        )
        if score is None:
            continue
        held_pool.append(
            {
                "symbol": sym,
                "score": float(score),
                "qty": qty,
                "held_days": held_days,
            }
        )

    candidate_pool.sort(key=lambda item: (-float(item["score"]), str(item["symbol"])))
    held_pool.sort(key=lambda item: (float(item["score"]), str(item["symbol"])))

    swap_cap = max(0, int(max_swaps_per_day))
    score_gap_floor = max(0.0, float(min_score_gap))
    pairs: list[dict[str, Any]] = []
    max_pairs = min(swap_cap, len(candidate_pool), len(held_pool))
    for idx in range(max_pairs):
        candidate = candidate_pool[idx]
        held = held_pool[idx]
        score_gap = float(candidate["score"]) - float(held["score"])
        if score_gap < score_gap_floor:
            break
        pairs.append(
            {
                "candidate_symbol": str(candidate["symbol"]).lower(),
                "candidate_score": float(candidate["score"]),
                "candidate_item": candidate["item"],
                "held_symbol": str(held["symbol"]).lower(),
                "held_score": float(held["score"]),
                "held_qty": int(held["qty"]),
                "held_days": held.get("held_days"),
                "score_gap": float(score_gap),
            }
        )
    return {
        "candidate_pool": candidate_pool,
        "held_pool": held_pool,
        "pairs": pairs,
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


def _resolve_mf_rank_tilt_scale(
    *,
    weight_mode: str,
    mf_enabled_today: bool,
    mf_rank: int,
    mf_topk: int,
    tilt_strength: float,
    tilt_top_n: int,
    tilt_bottom_n: int,
) -> float:
    if str(weight_mode or "").strip().lower() != "mf_rank_tilt":
        return 1.0
    if not bool(mf_enabled_today):
        return 1.0
    strength = max(0.0, float(tilt_strength))
    if strength <= 0.0:
        return 1.0
    rank = max(1, int(mf_rank))
    top_n = max(0, int(tilt_top_n))
    bottom_n = max(0, int(tilt_bottom_n))
    topk_band = max(0, int(mf_topk))
    if topk_band <= 0 or rank > topk_band:
        return 1.0
    if top_n > 0 and rank <= top_n:
        return 1.0 + strength
    if bottom_n > 0 and rank > max(0, topk_band - bottom_n):
        return max(0.0, 1.0 - strength)
    return 1.0


def _resolve_score_weight_scale(
    *,
    weight_mode: str,
    score_value: float | None,
    min_scale: float,
    max_scale: float,
) -> float:
    if str(weight_mode or "").strip().lower() != "score_weighted":
        return 1.0
    lo = max(1e-8, float(min_scale))
    hi = max(1e-8, float(max_scale))
    if hi < lo:
        lo, hi = hi, lo
    score = 0.5 if score_value is None else float(score_value)
    score = min(1.0, max(0.0, score))
    return lo + (hi - lo) * score


def _resolve_score_weight_score(item: dict[str, Any]) -> float | None:
    score = _safe_float_or_none(item.get("mf_score"))
    if score is not None:
        return score
    sig = item.get("signal")
    meta = sig.meta if isinstance(sig, Signal) and isinstance(sig.meta, dict) else {}
    for key in ("final_score", "residual_strength_score", "strength"):
        score = _safe_float_or_none(meta.get(key))
        if score is not None:
            return score
    return _safe_float_or_none(item.get("strength"))


def _build_score_weight_scale_maps(
    *,
    ranked: list[dict[str, Any]],
    slots: int,
    weight_mode: str,
    min_trade_price: float,
    forced_not_in_topk_symbols: set[str],
    score_weight_min_scale: float,
    score_weight_max_scale: float,
) -> tuple[dict[str, float], dict[str, float | None], dict[str, float]]:
    if str(weight_mode or "").strip().lower() != "score_weighted":
        return {}, {}, {}
    planned: list[tuple[str, float | None, float]] = []
    for item in ranked:
        sym = str(item.get("symbol", "")).lower()
        px = float(item.get("price", 0.0) or 0.0)
        if float(min_trade_price) > 0 and px < float(min_trade_price):
            continue
        if sym in forced_not_in_topk_symbols:
            continue
        if len(planned) >= max(0, int(slots)):
            break
        score_value = _resolve_score_weight_score(item)
        raw_scale = _resolve_score_weight_scale(
            weight_mode=str(weight_mode),
            score_value=score_value,
            min_scale=float(score_weight_min_scale),
            max_scale=float(score_weight_max_scale),
        )
        planned.append((sym, score_value, raw_scale))
    if not planned:
        return {}, {}, {}
    mean_raw_scale = float(sum(scale for _, _, scale in planned) / float(len(planned)))
    if mean_raw_scale <= 0.0:
        mean_raw_scale = 1.0
    normalized_scale_map = {
        sym: float(raw_scale) / float(mean_raw_scale)
        for sym, _, raw_scale in planned
    }
    score_map = {sym: score_value for sym, score_value, _ in planned}
    raw_scale_map = {sym: float(raw_scale) for sym, _, raw_scale in planned}
    return normalized_scale_map, score_map, raw_scale_map


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
        "mf_score": None if mf_score is None else float(mf_score),
        "mf_rank": None if mf_rank is None else int(mf_rank),
    }


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
                ))
            continue
        close_v = float(meta.get("close", 0.0) or 0.0)
        slow_v = float(meta.get("slow_ma", 0.0) or 0.0)
        legacy_strength = (close_v / slow_v - 1.0) if slow_v > 0 else -1e9
        strength = strength_map.get(sym) if enable_strength_rank else legacy_strength
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
                "legacy_strength": legacy_strength,
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
            key=lambda x: (-float(x.get("mf_score", 0.5)), str(x.get("symbol", "")).lower()),
        )
        for idx, item in enumerate(rank_sorted, start=1):
            item["mf_rank"] = int(idx)
        if len(ranked) > int(slots):
            mf_rank_triggered = True
            ranked.sort(key=lambda x: (-float(x.get("mf_score", 0.5)), str(x.get("symbol", "")).lower()))
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
        if risk_amount > 0:
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
        if risk_amount > 0:
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
        if cost > est_cash:
            item["reject_reason"] = "SKIP_NO_CASH"
            reject_reason_counts[item["reject_reason"]] = int(reject_reason_counts.get(item["reject_reason"], 0)) + 1
            continue
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
            ))
    if debug_plan is not None:
        debug_plan["buy_candidates_count"] = int(len(ranked))
        debug_plan["buy_slots"] = int(slots)
        debug_plan["selected_symbols"] = [str(x["symbol"]) for x in ranked if bool(x.get("selected"))]
        debug_plan["buys_executed"] = buy_exec_plan
        debug_plan["reject_reason_counts"] = dict(reject_reason_counts)
        debug_plan["selected_order_value_scales"] = [float(x.get("order_value_scale", 1.0)) for x in buy_exec_plan]
        debug_plan["weak_trend_selected_count"] = int(sum(1 for x in ranked if bool(x.get("selected")) and str(getattr(x.get("signal"), "meta", {}).get("trend_tier", "")).upper() == "WEAK"))
        debug_plan["strong_trend_selected_count"] = int(sum(1 for x in ranked if bool(x.get("selected")) and str(getattr(x.get("signal"), "meta", {}).get("trend_tier", "")).upper() == "STRONG"))
        debug_plan["mf_rank_triggered"] = bool(mf_rank_triggered)
        debug_plan["mf_rank_applied"] = bool(mf_rank_applied)
        debug_plan["mf_gate_on"] = bool(mf_enabled_today)
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


def run_portfolio_backtest(
    *,
    strategy: Strategy,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    trading_days: list[date],
    benchmark_symbol: str,
    initial_cash: float,
    max_positions: int,
    lot_size: int,
    enable_strength_rank: bool = False,
    strength_ma: int = 120,
    strength_top_k_mode: str = "FILL_TO_MAX",
    history_lookback_days: int | None = None,
    engine_mode: str = "SLOW_AUDIT",
    fast_mode: bool = False,
    debug_first_divergence: bool = False,
    enable_multifactor_rank: bool = False,
    mf_topk: int = 10,
    mf_concentrate_topn: int = 3,
    mf_concentrate_scale: float = 1.5,
    mf_rank_gate_mode: str = "ALWAYS_ON",
    momentum_top_pct: float = 0.0,
    cost_cfg: CostConfig | None = None,
    exit_cfg: ExitConfig | None = None,
    risk_cfg: RiskConfig | None = None,
    sizing_cfg: SizingConfig | None = None,
    raw_history: pd.DataFrame | None = None,
    base_order_value: float = 0.0,
    st_history: pd.DataFrame | None = None,
    sector_data: dict[str, pd.DataFrame] | None = None,
    industry_map: dict[str, str] | None = None,
    industry_history: pd.DataFrame | None = None,
    risk_budget_cfg: RiskBudgetConfig | None = None,
    market_filter_cfg: MarketFilterConfig | None = None,
    benchmark_regime_cfg: BenchmarkRegimeConfig | None = None,
    breadth_cfg: BreadthConfig | None = None,
) -> PortfolioBacktestResult:
    if str(engine_mode).upper() == "VECTOR_FAST_STRICT":
        from backend.core.engine_vector.portfolio_simulator_strict import run_vector_portfolio_backtest_strict

        return run_vector_portfolio_backtest_strict(
            strategy=strategy,
            history=history,
            benchmark=benchmark,
            trading_days=trading_days,
            benchmark_symbol=benchmark_symbol,
            initial_cash=initial_cash,
            max_positions=max_positions,
            lot_size=lot_size,
            enable_strength_rank=enable_strength_rank,
            strength_ma=strength_ma,
            strength_top_k_mode=strength_top_k_mode,
            history_lookback_days=history_lookback_days,
            fast_mode=bool(fast_mode),
            debug_first_divergence=bool(debug_first_divergence),
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_topk=int(mf_topk),
            mf_concentrate_topn=int(mf_concentrate_topn),
            mf_concentrate_scale=float(mf_concentrate_scale),
            mf_rank_gate_mode=str(mf_rank_gate_mode),
            momentum_top_pct=float(momentum_top_pct),
            cost_cfg=cost_cfg,
            exit_cfg=exit_cfg,
            risk_cfg=risk_cfg,
            sizing_cfg=sizing_cfg,
            raw_history=raw_history,
            base_order_value=float(base_order_value),
            st_history=st_history,
            sector_data=sector_data,
            industry_map=industry_map,
            industry_history=industry_history,
            risk_budget_cfg=risk_budget_cfg,
            market_filter_cfg=market_filter_cfg,
            benchmark_regime_cfg=benchmark_regime_cfg,
            breadth_cfg=breadth_cfg,
        )
    if history.empty:
        raise ValueError("history is empty")
    if not trading_days:
        raise ValueError("trading_days is empty")

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    bench = benchmark.copy()
    if not bench.empty:
        bench["date"] = pd.to_datetime(bench["date"])
        bench["symbol"] = f"BENCH:{benchmark_symbol}"
        bench = bench.sort_values(["date"]).reset_index(drop=True)
    # Build one combined history table once, avoid per-day concat in main loop.
    if not bench.empty:
        combined = pd.concat([hist, bench], ignore_index=True)
        combined = combined.sort_values(["date", "symbol"]).reset_index(drop=True)
    else:
        combined = hist
    combined_date_series = combined["date"]

    open_idx, close_idx = build_backtest_price_indices(
        history=hist,
        trading_days=trading_days,
    )

    pending: dict[date, list[PortfolioOrder]] = {}
    positions: dict[str, int] = {}
    position_avg_cost: dict[str, float] = {}
    cash = float(initial_cash)
    peak_nav = float(initial_cash)
    prev_nav = float(initial_cash)
    blocked_by_trend_count = 0
    total_buy_signals = 0
    trade_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    debug_trace: dict[str, Any] = {}
    _sc_cfg = sizing_cfg if isinstance(sizing_cfg, SizingConfig) else SizingConfig()
    _weight_mode_cfg = str(_sc_cfg.weight_mode or "equal")
    _min_positions_cfg = int(_sc_cfg.min_positions)
    _tilt_strength_cfg = float(_sc_cfg.tilt_strength)
    _tilt_top_n_cfg = int(_sc_cfg.tilt_top_n)
    _tilt_bottom_n_cfg = int(_sc_cfg.tilt_bottom_n)
    _score_weight_min_scale_cfg = float(_sc_cfg.score_weight_min_scale)
    _score_weight_max_scale_cfg = float(_sc_cfg.score_weight_max_scale)
    _candidate_plan_mode_cfg = str(_sc_cfg.candidate_plan_mode or "ranked")
    _cash_aware_search_top_n_cfg = int(_sc_cfg.cash_aware_search_top_n)
    _rotation_replace_enabled_cfg = bool(_sc_cfg.rotation_replace_enabled)
    _rotation_replace_only_strong_risk_on_cfg = bool(_sc_cfg.rotation_replace_only_strong_risk_on)
    _rotation_replace_max_swaps_per_day_cfg = int(_sc_cfg.rotation_replace_max_swaps_per_day)
    _rotation_replace_candidate_top_n_cfg = int(_sc_cfg.rotation_replace_candidate_top_n)
    _rotation_replace_min_score_gap_cfg = float(_sc_cfg.rotation_replace_min_score_gap)

    day_list = list(trading_days)
    # Precompute per-day slice end offsets to avoid repeated full DataFrame scans.
    day_slice_end_combined: dict[pd.Timestamp, int] = {}
    day_slice_start_combined: dict[pd.Timestamp, int] = {}
    use_lookback = isinstance(history_lookback_days, int) and int(history_lookback_days) > 0
    lookback_n = int(history_lookback_days) if use_lookback else 0
    for day in day_list:
        day_ts = pd.Timestamp(day)
        day_slice_end_combined[day_ts] = int(combined_date_series.searchsorted(day_ts, side="right"))
    if use_lookback:
        for i, day in enumerate(day_list):
            day_ts = pd.Timestamp(day)
            start_day = day_list[max(0, i - lookback_n)]
            start_ts = pd.Timestamp(start_day)
            day_slice_start_combined[day_ts] = int(combined_date_series.searchsorted(start_ts, side="left"))
    else:
        for day in day_list:
            day_slice_start_combined[pd.Timestamp(day)] = 0

    # Precompute strength(close/MA-1) lookup by (date, symbol) once.
    strength_lookup: dict[tuple[pd.Timestamp, str], float | None] = {}
    if enable_strength_rank:
        strength_src = hist[["date", "symbol", "close"]].copy()
        strength_src["close"] = pd.to_numeric(strength_src["close"], errors="coerce")
        strength_src["strength_ma"] = (
            strength_src.groupby("symbol", sort=False)["close"]
            .transform(lambda s: s.rolling(int(strength_ma)).mean())
        )
        strength_src["strength"] = (
            strength_src["close"] / strength_src["strength_ma"] - 1.0
        )
        for row in strength_src.itertuples(index=False):
            key = (pd.Timestamp(row.date), str(row.symbol))
            val = None
            try:
                if pd.notna(row.strength):
                    val = float(row.strength)
            except Exception:
                val = None
            strength_lookup[key] = val

    for i, day in enumerate(day_list):
        traded_value = 0.0
        for od in pending.pop(day, []):
            px = float(open_idx.get((day, od.symbol), 0.0) or 0.0)
            if px <= 0:
                continue
            if od.side == Side.SELL:
                held = int(positions.get(od.symbol, 0))
                qty = min(held, int(od.qty))
                if qty <= 0:
                    continue
                value = qty * px
                cash += value
                traded_value += value
                positions[od.symbol] = held - qty
                if positions[od.symbol] <= 0:
                    positions.pop(od.symbol, None)
                    position_avg_cost.pop(od.symbol, None)
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od.symbol,
                        "side": "SELL",
                        "price": px,
                        "qty": qty,
                        "value": value,
                        "reason_code": od.reason_code,
                        "triggered_rule": str((od.meta or {}).get("triggered_rule", "")),
                        "break_streak": int((od.meta or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.meta or {}, ensure_ascii=False),
                    }
                )
            else:
                qty = int(od.qty)
                value = qty * px
                if qty <= 0 or value > cash:
                    continue
                cash -= value
                traded_value += value
                prev_qty = int(positions.get(od.symbol, 0))
                prev_avg = float(position_avg_cost.get(od.symbol, 0.0))
                new_qty = prev_qty + qty
                new_avg = ((prev_qty * prev_avg) + (qty * px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[od.symbol] = new_qty
                position_avg_cost[od.symbol] = float(new_avg)
                trade_rows.append(
                    {
                        "date": day.isoformat(),
                        "symbol": od.symbol,
                        "side": "BUY",
                        "price": px,
                        "qty": qty,
                        "value": value,
                        "reason_code": od.reason_code,
                        "triggered_rule": str((od.meta or {}).get("triggered_rule", "")),
                        "break_streak": int((od.meta or {}).get("break_streak", 0) or 0),
                        "meta_json": json.dumps(od.meta or {}, ensure_ascii=False),
                    }
                )

        nav, market_value, pos_values = compute_nav_snapshot(cash=cash, positions=positions, close_idx=close_idx, day=day)
        peak_nav = max(peak_nav, nav)
        daily_ret = (nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
        drawdown = (nav / peak_nav - 1.0) if peak_nav > 0 else 0.0
        gross_exposure = (market_value / nav) if nav > 0 else 0.0
        turnover_pct = (traded_value / prev_nav) if prev_nav > 0 else 0.0
        top5 = [{"symbol": s, "value": round(v, 2)} for s, v in sorted(pos_values, key=lambda x: x[1], reverse=True)[:5]]
        daily_rows.append(
            {
                "date": day.isoformat(),
                "nav": nav,
                "cash": cash,
                "positions_count": len(positions),
                "daily_return": daily_ret,
                "drawdown": drawdown,
                "gross_exposure": gross_exposure,
                "turnover_pct": turnover_pct,
                "top5_positions_json": json.dumps(top5, ensure_ascii=False),
                "candidates_count": 0,
                "selected_count": 0,
                "top5_selected_strength_json": "[]",
                "top5_rejected_strength_json": "[]",
                "buy_slots_before_buy": 0,
                "mean_order_value_scale": 0.0,
                "weak_trend_buy_rate": 0.0,
                "strong_trend_buy_rate": 0.0,
            }
        )
        prev_nav = nav

        if i >= len(day_list) - 1:
            continue
        next_day = day_list[i + 1]

        day_ts = pd.Timestamp(day)
        history_view = combined.iloc[day_slice_start_combined[day_ts] : day_slice_end_combined[day_ts]]

        strategy_positions = {
            sym: Position(symbol=sym, total_qty=int(q), sellable_qty=int(q), avg_cost=float(position_avg_cost.get(sym, 0.0)))
            for sym, q in positions.items()
            if int(q) > 0
        }
        strategy.state["base_order_value"] = float(nav) / float(max_positions) if int(max_positions) > 0 else 0.0
        sigs = strategy.generate_signals(day, history_view, strategy_positions)
        sell_sigs: list[Signal] = []
        buy_sigs: list[Signal] = []
        day_gate_by_symbol: dict[str, dict[str, Any]] = {}
        raw_buy_candidates: list[str] = []
        for sig in sigs:
            sig_side = str(sig.side.value).upper()
            sig_action = str(sig.action or sig.side.value).upper()
            if sig_side == "BUY":
                sym_k = str(sig.symbol).lower()
                raw_buy_candidates.append(sym_k)
                meta_d = dict(sig.meta) if isinstance(sig.meta, dict) else {}
                day_gate_by_symbol[sym_k] = {
                    "cross_up": str(sig.reason_code or sig.reason or "").upper()
                    in {
                        "SMA_CROSS_UP",
                        "EMA_CROSS_UP",
                        "SMA_CROSS_UP_BLOCKED",
                        "EMA_CROSS_UP_BLOCKED",
                        "ENTRY_BUFFER_BLOCKED",
                        "BUY_BLOCKED_TREND_FILTER",
                    },
                    "entry_buffer_ok": bool(meta_d.get("buffer_ok")) if "buffer_ok" in meta_d else None,
                    "trend_ok": bool(meta_d.get("trend_ok")) if "trend_ok" in meta_d else None,
                    "regime_ok": bool(meta_d.get("regime_on")) if "regime_on" in meta_d else None,
                    "tradable": None,
                    "ma_is_valid": (meta_d.get("slow_ma") is not None and meta_d.get("fast_ma") is not None),
                    "close": meta_d.get("close"),
                    "fast_ma": meta_d.get("fast_ma"),
                    "slow_ma": meta_d.get("slow_ma"),
                    "fast_ma_prev": meta_d.get("fast_ma_prev"),
                    "slow_ma_prev": meta_d.get("slow_ma_prev"),
                    "ma120": meta_d.get("ma120", meta_d.get("trend_fast_value")),
                    "ma200": meta_d.get("ma200", meta_d.get("trend_slow_value")),
                    "trend_fast": meta_d.get("trend_fast_value"),
                    "trend_slow": meta_d.get("trend_slow_value"),
                    "reason_code": str(sig.reason_code or sig.reason or ""),
                }
            if sig.side == Side.BUY:
                total_buy_signals += 1
                if str(sig.action or "").upper() == "BLOCKED" and str(sig.reason_code or "") == "BUY_BLOCKED_TREND_FILTER":
                    blocked_by_trend_count += 1
            if sig_action == "BLOCKED":
                continue
            if sig.side == Side.SELL:
                sell_sigs.append(sig)
            elif sig.side == Side.BUY:
                buy_sigs.append(sig)
        buy_slots_before_buy = _estimate_buy_slots_after_sell(
            positions=positions,
            sell_signals=sell_sigs,
            max_positions=max_positions,
        )

        next_open = {
            sym: float(open_idx.get((next_day, sym), 0.0) or 0.0)
            for sym in set([str(s.symbol).lower() for s in sell_sigs + buy_sigs] + list(positions.keys()))
        }
        for sym in raw_buy_candidates:
            g = day_gate_by_symbol.setdefault(sym, {})
            px = float(next_open.get(sym, 0.0) or 0.0)
            g["open_next"] = px
            g["tradable"] = bool(px > 0)
            rc = str((g.get("reason_code") or "")).upper()
            if not rc:
                # derive from signals list
                for s in sigs:
                    if str(s.symbol).lower() == sym and str(s.side.value).upper() == "BUY":
                        rc = str(s.reason_code or s.reason or "").upper()
                        break
            g["buy_raw_ok"] = rc in {"SMA_CROSS_UP", "EMA_CROSS_UP"}
        strength_map: dict[str, float | None] = {}
        if enable_strength_rank and buy_sigs:
            for sig in buy_sigs:
                sym_l = str(sig.symbol).lower()
                strength_map[sym_l] = strength_lookup.get((day_ts, sym_l))
        day_candidate_rows: list[dict[str, Any]] = []
        debug_plan: dict[str, Any] = {}
        regime_on_today = bool(strategy.state.get("regime_on", True))
        strong_risk_on_today = bool(strategy.state.get("strong_risk_on", regime_on_today))
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_rank_gate_mode=str(mf_rank_gate_mode or "ALWAYS_ON"),
            risk_on_today=bool(regime_on_today),
            strong_risk_on_today=bool(strong_risk_on_today),
        )
        orders = build_rebalance_orders(
            positions=positions,
            cash_available=cash,
            nav_close=nav,
            max_positions=max_positions,
            lot_size=lot_size,
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            next_open=next_open,
            enable_strength_rank=bool(enable_strength_rank),
            strength_ma=int(strength_ma),
            strength_top_k_mode=str(strength_top_k_mode),
            strength_map=strength_map,
            enable_multifactor_rank=bool(enable_multifactor_rank),
            mf_topk=int(mf_topk),
            mf_concentrate_topn=int(mf_concentrate_topn),
            mf_concentrate_scale=float(mf_concentrate_scale),
            mf_gate_on_today=bool(mf_gate_on_today),
            mf_score_map={},
            decision_date=day,
            candidate_audit=day_candidate_rows,
            debug_plan=debug_plan,
            weight_mode=_weight_mode_cfg,
            min_positions=_min_positions_cfg,
            tilt_strength=_tilt_strength_cfg,
            tilt_top_n=_tilt_top_n_cfg,
            tilt_bottom_n=_tilt_bottom_n_cfg,
            min_trade_price=float(getattr(strategy, "min_price", 0.0) or 0.0),
            decision_close_map={
                str(sig.symbol).lower(): float(close_idx.get((day, str(sig.symbol).lower()), 0.0) or 0.0)
                for sig in buy_sigs
            },
            enable_entry_gap_guard=bool(getattr(strategy, "enable_entry_gap_guard", False)),
            entry_gap_guard_pct=float(getattr(strategy, "entry_gap_guard_pct", 0.0) or 0.0),
            score_weight_min_scale=_score_weight_min_scale_cfg,
            score_weight_max_scale=_score_weight_max_scale_cfg,
            candidate_plan_mode=_candidate_plan_mode_cfg,
            cash_aware_search_top_n=_cash_aware_search_top_n_cfg,
            holding_entry_dates=dict(getattr(strategy, "entry_day", {}) or {}),
            strong_risk_on_today=bool(strong_risk_on_map.get(day, False)),
            rotation_replace_enabled=_rotation_replace_enabled_cfg,
            rotation_replace_only_strong_risk_on=_rotation_replace_only_strong_risk_on_cfg,
            rotation_replace_max_swaps_per_day=_rotation_replace_max_swaps_per_day_cfg,
            rotation_replace_candidate_top_n=_rotation_replace_candidate_top_n_cfg,
            rotation_replace_min_score_gap=_rotation_replace_min_score_gap_cfg,
            rotation_min_hold_days=int(getattr(strategy, "min_hold_days", 0) or 0),
        )
        if debug_first_divergence:
            rank_pos_map: dict[str, int] = {}
            for idx_rank, row in enumerate([r for r in day_candidate_rows if bool(r.get("is_candidate"))], start=1):
                rank_pos_map[str(row.get("symbol", "")).lower()] = int(idx_rank)
                gate = day_gate_by_symbol.setdefault(str(row.get("symbol", "")).lower(), {})
                gate["rank_position"] = int(idx_rank)
                gate["strength_value"] = row.get("strength")
            sell_list: list[dict[str, Any]] = []
            held_before = {str(k): int(v) for k, v in positions.items() if int(v) > 0}
            for sig in sell_sigs:
                sym = str(sig.symbol).lower()
                qh = int(held_before.get(sym, 0))
                q = qh if int(sig.qty) <= 0 else min(qh, int(sig.qty))
                if q <= 0:
                    continue
                sell_list.append(
                    {
                        "symbol": sym,
                        "reason": str(sig.reason_code or sig.reason or "SELL"),
                        "next_open_price": float(next_open.get(sym, 0.0) or 0.0),
                        "qty": int(q),
                    }
                )
            debug_trace[day.isoformat()] = {
                "cash_before": float(cash),
                "held_symbols_before": held_before,
                "sell_list": sell_list,
                "buy_candidates_raw": sorted(list(set(raw_buy_candidates))),
                "buy_gate_by_symbol": day_gate_by_symbol,
                "buy_candidates_count": int((debug_plan or {}).get("buy_candidates_count", 0)),
                "buy_slots": int((debug_plan or {}).get("buy_slots", 0)),
                "sorting_triggered": bool(int((debug_plan or {}).get("buy_candidates_count", 0)) > int((debug_plan or {}).get("buy_slots", 0))),
                "sorted_selected_symbols": list((debug_plan or {}).get("selected_symbols", [])),
                "selected_symbols": list((debug_plan or {}).get("selected_symbols", [])),
                "buys_executed": list((debug_plan or {}).get("buys_executed", [])),
                "positions_after": {str(k): int(v) for k, v in positions.items() if int(v) > 0},
                "nav_end_of_day": float(nav),
            }
        candidate_rows.extend(day_candidate_rows)
        if daily_rows:
            candidates_only = [r for r in day_candidate_rows if bool(r.get("is_candidate"))]
            selected = [r for r in candidates_only if bool(r.get("selected"))]
            rejected = [r for r in candidates_only if not bool(r.get("selected"))]
            selected_sorted = sorted(
                selected,
                key=lambda x: (x.get("strength") is not None, float(x.get("strength") or -1e18)),
                reverse=True,
            )[:5]
            rejected_sorted = sorted(
                rejected,
                key=lambda x: (x.get("strength") is not None, float(x.get("strength") or -1e18)),
                reverse=True,
            )[:5]
            daily_rows[-1]["candidates_count"] = int(len(candidates_only))
            daily_rows[-1]["selected_count"] = int(len(selected))
            daily_rows[-1]["top5_selected_strength_json"] = json.dumps(
                [{"symbol": r.get("symbol"), "strength": r.get("strength")} for r in selected_sorted],
                ensure_ascii=False,
            )
            daily_rows[-1]["top5_rejected_strength_json"] = json.dumps(
                [{"symbol": r.get("symbol"), "strength": r.get("strength"), "reason": r.get("reject_reason")} for r in rejected_sorted],
                ensure_ascii=False,
            )
            daily_rows[-1]["buy_slots_before_buy"] = int(buy_slots_before_buy)
            selected_scales = list((debug_plan or {}).get("selected_order_value_scales", []) or [])
            weak_selected_count = int((debug_plan or {}).get("weak_trend_selected_count", 0) or 0)
            strong_selected_count = int((debug_plan or {}).get("strong_trend_selected_count", 0) or 0)
            selected_n_dbg = int(len((debug_plan or {}).get("selected_symbols", []) or []))
            daily_rows[-1]["mean_order_value_scale"] = (
                float(sum(float(x) for x in selected_scales) / len(selected_scales))
                if len(selected_scales) > 0
                else 0.0
            )
            daily_rows[-1]["weak_trend_buy_rate"] = (
                float(weak_selected_count) / float(selected_n_dbg)
                if selected_n_dbg > 0
                else 0.0
            )
            daily_rows[-1]["strong_trend_buy_rate"] = (
                float(strong_selected_count) / float(selected_n_dbg)
                if selected_n_dbg > 0
                else 0.0
            )
            daily_rows[-1]["mf_rank_triggered"] = 1 if bool((debug_plan or {}).get("mf_rank_triggered", False)) else 0
            daily_rows[-1]["mf_rank_applied"] = 1 if bool((debug_plan or {}).get("mf_rank_applied", False)) else 0
            daily_rows[-1]["mf_candidates_when_triggered"] = int((debug_plan or {}).get("mf_candidates_when_triggered", 0) or 0)
            daily_rows[-1]["mf_topk_reject_count"] = int((debug_plan or {}).get("mf_topk_reject_count", 0) or 0)
            daily_rows[-1]["mf_concentrated_selected_count"] = int((debug_plan or {}).get("mf_concentrated_selected_count", 0) or 0)
            daily_rows[-1]["mf_gate_on"] = 1 if bool((debug_plan or {}).get("mf_gate_on", False)) else 0
            daily_rows[-1]["strong_risk_on"] = 1 if bool(strong_risk_on_today) else 0
            cands_now = int((debug_plan or {}).get("buy_candidates_count", 0) or 0)
            slots_now = int((debug_plan or {}).get("buy_slots", 0) or 0)
            daily_rows[-1]["mf_rank_suppressed_by_strong_gate"] = (
                1
                if bool(enable_multifactor_rank) and (not bool(mf_gate_on_today)) and (cands_now > slots_now)
                else 0
            )
        if orders:
            pending[next_day] = orders

    daily_df = pd.DataFrame(daily_rows)
    trades_df = pd.DataFrame(trade_rows)
    candidates_df = pd.DataFrame(candidate_rows)
    metrics = _compute_metrics(
        daily_df,
        trades_df,
        max_positions=max_positions,
        blocked_by_trend_count=blocked_by_trend_count,
        total_buy_signals=total_buy_signals,
        candidates_df=candidates_df,
        enable_strength_rank=bool(enable_strength_rank),
        strength_ma=int(strength_ma),
    )
    if debug_first_divergence:
        metrics["debug_trace"] = debug_trace
    return PortfolioBacktestResult(daily=daily_df, trades=trades_df, candidates=candidates_df, metrics=metrics)


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
    if daily_df.empty:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "vol_annual": 0.0,
            "max_daily_drawdown": 0.0,
            "trades": 0,
            "avg_positions": 0.0,
            "turnover_avg": 0.0,
            "max_positions": int(max_positions),
            "blocked_by_trend_count": int(blocked_by_trend_count),
            "trend_filter_block_rate": 0.0,
            "not_in_topk_reject_count": 0,
            "avg_candidates_per_day": 0.0,
            "avg_selected_per_day": 0.0,
            "avg_buys_per_day": 0.0,
            "avg_buy_slots_per_day": 0.0,
            "trigger_when_slots_small_rate": 0.0,
            "mean_order_value_scale": 0.0,
            "WEAK_TREND_BUY_RATE": 0.0,
            "STRONG_TREND_BUY_RATE": 0.0,
            "TREND_BREAK_EXIT_RATE": 0.0,
            "TREND_BREAK_EXIT_COUNT": 0,
            "mean_break_streak_at_exit": 0.0,
            "days_held_median": 0.0,
            "rank_trigger_days": 0,
            "rank_trigger_rate": 0.0,
            "mf_rank_trigger_days": 0,
            "mf_rank_trigger_rate": 0.0,
            "mf_rank_applied_days": 0,
            "mf_rank_applied_rate": 0.0,
            "mf_avg_candidates_when_triggered": 0.0,
            "mf_topk_reject_count": 0,
            "mf_concentrated_buy_rate": 0.0,
            "mf_gate_on_days": 0,
            "mf_gate_on_rate": 0.0,
            "strong_risk_on_days": 0,
            "strong_risk_on_rate": 0.0,
            "mf_rank_suppressed_by_strong_gate_days": 0,
            "trend_slope_block_count": 0,
            "trend_continuity_block_count": 0,
            "avg_trend_on_rate": 0.0,
            "avg_quality_trend_on_rate": 0.0,
            "strength_rank_enabled": bool(enable_strength_rank),
            "strength_ma": int(strength_ma),
        }
    nav0 = float(daily_df["nav"].iloc[0])
    nav1 = float(daily_df["nav"].iloc[-1])
    total_return = (nav1 / nav0 - 1.0) if nav0 > 0 else 0.0
    n = int(len(daily_df))
    years = max(n / 252.0, 1e-9)
    cagr = (nav1 / nav0) ** (1.0 / years) - 1.0 if nav0 > 0 and nav1 > 0 else 0.0
    max_drawdown = float(daily_df["drawdown"].min())
    daily_ret = pd.to_numeric(daily_df["daily_return"], errors="coerce").fillna(0.0)
    vol_annual = float(daily_ret.std(ddof=0) * sqrt(252.0))
    sharpe = float((daily_ret.mean() / daily_ret.std(ddof=0)) * sqrt(252.0)) if float(daily_ret.std(ddof=0)) > 0 else 0.0
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown != 0 else 0.0
    max_daily_drawdown = float(daily_ret.min())
    avg_positions = float(pd.to_numeric(daily_df["positions_count"], errors="coerce").fillna(0.0).mean())
    turnover_avg = float(pd.to_numeric(daily_df["turnover_pct"], errors="coerce").fillna(0.0).mean())
    not_in_topk_reject_count = 0
    rank_trigger_days = 0
    if candidates_df is not None and not candidates_df.empty and "reject_reason" in candidates_df.columns:
        rr = candidates_df["reject_reason"].astype(str)
        not_in_topk_reject_count = int(rr.eq("NOT_IN_TOPK").sum())
    if "candidates_count" in daily_df.columns and "buy_slots_before_buy" in daily_df.columns:
        # Use the same daily aggregate definition for both slow/vector to keep strict comparability.
        cc = pd.to_numeric(daily_df["candidates_count"], errors="coerce").fillna(0.0)
        bs = pd.to_numeric(daily_df["buy_slots_before_buy"], errors="coerce").fillna(0.0)
        rank_trigger_days = int((cc > bs).sum())
    mf_rank_trigger_days = 0
    mf_avg_candidates_when_triggered = 0.0
    if "mf_rank_triggered" in daily_df.columns:
        mtr = pd.to_numeric(daily_df["mf_rank_triggered"], errors="coerce").fillna(0.0)
        mf_rank_trigger_days = int((mtr > 0).sum())
        if "mf_candidates_when_triggered" in daily_df.columns:
            mfc = pd.to_numeric(daily_df["mf_candidates_when_triggered"], errors="coerce").fillna(0.0)
            picked = mfc[mtr > 0]
            if len(picked) > 0:
                mf_avg_candidates_when_triggered = float(picked.mean())
    mf_rank_applied_days = 0
    mf_rank_applied_rate = 0.0
    if "mf_rank_applied" in daily_df.columns:
        mra = pd.to_numeric(daily_df["mf_rank_applied"], errors="coerce").fillna(0.0)
        mf_rank_applied_days = int((mra > 0).sum())
        mf_rank_applied_rate = float((mra > 0).mean()) if len(mra) > 0 else 0.0
    mf_topk_reject_count = int(
        pd.to_numeric(daily_df.get("mf_topk_reject_count"), errors="coerce").fillna(0.0).sum()
    ) if "mf_topk_reject_count" in daily_df.columns else 0
    mf_concentrated_buy_rate = 0.0
    if "mf_concentrated_selected_count" in daily_df.columns and "selected_count" in daily_df.columns:
        mfc_sel = float(pd.to_numeric(daily_df["mf_concentrated_selected_count"], errors="coerce").fillna(0.0).sum())
        msel = float(pd.to_numeric(daily_df["selected_count"], errors="coerce").fillna(0.0).sum())
        mf_concentrated_buy_rate = (mfc_sel / msel) if msel > 0 else 0.0
    mf_gate_on_days = 0
    mf_gate_on_rate = 0.0
    if "mf_gate_on" in daily_df.columns:
        mg = pd.to_numeric(daily_df["mf_gate_on"], errors="coerce").fillna(0.0)
        mf_gate_on_days = int((mg > 0).sum())
        mf_gate_on_rate = float((mg > 0).mean()) if len(mg) > 0 else 0.0
    strong_risk_on_days = 0
    strong_risk_on_rate = 0.0
    if "strong_risk_on" in daily_df.columns:
        sro = pd.to_numeric(daily_df["strong_risk_on"], errors="coerce").fillna(0.0)
        strong_risk_on_days = int((sro > 0).sum())
        strong_risk_on_rate = float((sro > 0).mean()) if len(sro) > 0 else 0.0
    mf_rank_suppressed_by_strong_gate_days = 0
    if "mf_rank_suppressed_by_strong_gate" in daily_df.columns:
        mssg = pd.to_numeric(daily_df["mf_rank_suppressed_by_strong_gate"], errors="coerce").fillna(0.0)
        mf_rank_suppressed_by_strong_gate_days = int((mssg > 0).sum())
    trend_slope_block_count = int(pd.to_numeric(daily_df.get("trend_slope_block_count"), errors="coerce").fillna(0.0).sum()) if "trend_slope_block_count" in daily_df.columns else 0
    trend_continuity_block_count = int(pd.to_numeric(daily_df.get("trend_continuity_block_count"), errors="coerce").fillna(0.0).sum()) if "trend_continuity_block_count" in daily_df.columns else 0
    avg_trend_on_rate = float(pd.to_numeric(daily_df.get("base_trend_on_rate"), errors="coerce").fillna(0.0).mean()) if "base_trend_on_rate" in daily_df.columns else 0.0
    avg_quality_trend_on_rate = float(pd.to_numeric(daily_df.get("quality_trend_on_rate"), errors="coerce").fillna(0.0).mean()) if "quality_trend_on_rate" in daily_df.columns else 0.0
    avg_candidates_per_day = float(pd.to_numeric(daily_df.get("candidates_count"), errors="coerce").fillna(0.0).mean()) if "candidates_count" in daily_df.columns else 0.0
    avg_selected_per_day = float(pd.to_numeric(daily_df.get("selected_count"), errors="coerce").fillna(0.0).mean()) if "selected_count" in daily_df.columns else 0.0
    avg_buys_per_day = float(avg_selected_per_day)
    buy_slots_series = pd.to_numeric(daily_df.get("buy_slots_before_buy"), errors="coerce").fillna(0.0) if "buy_slots_before_buy" in daily_df.columns else pd.Series([0.0] * len(daily_df))
    avg_buy_slots_per_day = float(buy_slots_series.mean()) if len(buy_slots_series) > 0 else 0.0
    trigger_when_slots_small_rate = float((buy_slots_series <= 1).mean()) if len(buy_slots_series) > 0 else 0.0
    mean_order_value_scale = float(pd.to_numeric(daily_df.get("mean_order_value_scale"), errors="coerce").fillna(0.0).mean()) if "mean_order_value_scale" in daily_df.columns else 0.0
    weak_trend_buy_rate = float(pd.to_numeric(daily_df.get("weak_trend_buy_rate"), errors="coerce").fillna(0.0).mean()) if "weak_trend_buy_rate" in daily_df.columns else 0.0
    strong_trend_buy_rate = float(pd.to_numeric(daily_df.get("strong_trend_buy_rate"), errors="coerce").fillna(0.0).mean()) if "strong_trend_buy_rate" in daily_df.columns else 0.0
    trend_break_exit_rate = 0.0
    trend_break_exit_count = 0
    mean_break_streak_at_exit = 0.0
    days_held_median = 0.0
    if not trades_df.empty and "side" in trades_df.columns and "reason_code" in trades_df.columns:
        sell_part = trades_df[trades_df["side"].astype(str).str.upper() == "SELL"].copy()
        if not sell_part.empty:
            rc = sell_part["reason_code"].astype(str).str.upper()
            trend_break_exit_count = int((rc == "TREND_BREAK_EXIT").sum())
            trend_break_exit_rate = float(trend_break_exit_count / len(sell_part))
            if "break_streak" in sell_part.columns:
                bsv = pd.to_numeric(sell_part.loc[rc == "TREND_BREAK_EXIT", "break_streak"], errors="coerce").dropna()
                if len(bsv) > 0:
                    mean_break_streak_at_exit = float(bsv.mean())
            if "hold_days" in sell_part.columns:
                hd = pd.to_numeric(sell_part["hold_days"], errors="coerce").dropna()
                if len(hd) > 0:
                    days_held_median = float(hd.median())
    trading_days = int(len(daily_df))
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "calmar": calmar,
        "vol_annual": vol_annual,
        "max_daily_drawdown": max_daily_drawdown,
        "trades": int(len(trades_df)),
        "avg_positions": avg_positions,
        "turnover_avg": turnover_avg,
        "max_positions": int(max_positions),
        "blocked_by_trend_count": int(blocked_by_trend_count),
        "trend_filter_block_rate": (float(blocked_by_trend_count) / float(total_buy_signals)) if total_buy_signals > 0 else 0.0,
        "not_in_topk_reject_count": int(not_in_topk_reject_count),
        "avg_candidates_per_day": float(avg_candidates_per_day),
        "avg_selected_per_day": float(avg_selected_per_day),
        "avg_buys_per_day": float(avg_buys_per_day),
        "avg_buy_slots_per_day": float(avg_buy_slots_per_day),
        "trigger_when_slots_small_rate": float(trigger_when_slots_small_rate),
        "mean_order_value_scale": float(mean_order_value_scale),
        "WEAK_TREND_BUY_RATE": float(weak_trend_buy_rate),
        "STRONG_TREND_BUY_RATE": float(strong_trend_buy_rate),
        "TREND_BREAK_EXIT_RATE": float(trend_break_exit_rate),
        "TREND_BREAK_EXIT_COUNT": int(trend_break_exit_count),
        "mean_break_streak_at_exit": float(mean_break_streak_at_exit),
        "days_held_median": float(days_held_median),
        "rank_trigger_days": int(rank_trigger_days),
        "rank_trigger_rate": (float(rank_trigger_days) / float(trading_days)) if trading_days > 0 else 0.0,
        "mf_rank_trigger_days": int(mf_rank_trigger_days),
        "mf_rank_trigger_rate": (float(mf_rank_trigger_days) / float(trading_days)) if trading_days > 0 else 0.0,
        "mf_rank_applied_days": int(mf_rank_applied_days),
        "mf_rank_applied_rate": float(mf_rank_applied_rate),
        "mf_avg_candidates_when_triggered": float(mf_avg_candidates_when_triggered),
        "mf_topk_reject_count": int(mf_topk_reject_count),
        "mf_concentrated_buy_rate": float(mf_concentrated_buy_rate),
        "mf_gate_on_days": int(mf_gate_on_days),
        "mf_gate_on_rate": float(mf_gate_on_rate),
        "strong_risk_on_days": int(strong_risk_on_days),
        "strong_risk_on_rate": float(strong_risk_on_rate),
        "mf_rank_suppressed_by_strong_gate_days": int(mf_rank_suppressed_by_strong_gate_days),
        "trend_slope_block_count": int(trend_slope_block_count),
        "trend_continuity_block_count": int(trend_continuity_block_count),
        "avg_trend_on_rate": float(avg_trend_on_rate),
        "avg_quality_trend_on_rate": float(avg_quality_trend_on_rate),
        "trend_filter_block_rate": (
            (float(int(blocked_by_trend_count) + trend_slope_block_count + trend_continuity_block_count) / float(total_buy_signals))
            if total_buy_signals > 0
            else 0.0
        ),
        "strength_rank_enabled": bool(enable_strength_rank),
        "strength_ma": int(strength_ma),
        "total_buy_signals": int(total_buy_signals),
        "blocked_signals": int(blocked_by_trend_count),
    }
