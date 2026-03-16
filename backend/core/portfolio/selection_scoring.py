from __future__ import annotations

from datetime import date
from typing import Any

from backend.core.core.models import Signal


def safe_float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def safe_date_or_none(value: Any) -> date | None:
    from pandas import Timestamp, isna

    if isinstance(value, date):
        return value
    if value is None or value == "":
        return None
    try:
        ts = Timestamp(value)
    except Exception:
        return None
    if isna(ts):
        return None
    return ts.date()


def resolve_rotation_score(
    *,
    symbol: str,
    item: dict[str, Any] | None = None,
    mf_score_map: dict[str, float | None] | None = None,
    strength_map: dict[str, float | None] | None = None,
) -> float | None:
    sym = str(symbol).lower()
    score = safe_float_or_none(dict(mf_score_map or {}).get(sym))
    if score is not None:
        return score
    score = safe_float_or_none(dict(strength_map or {}).get(sym))
    if score is not None:
        return score
    if isinstance(item, dict):
        score = safe_float_or_none(item.get("mf_score"))
        if score is not None:
            return score
        score = safe_float_or_none(item.get("strength"))
        if score is not None:
            return score
    return None


def select_rotation_pairs(
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
        score = resolve_rotation_score(
            symbol=sym,
            item=item,
            mf_score_map=mf_score_map,
            strength_map=strength_map,
        )
        if score is None:
            continue
        candidate_pool.append({"symbol": sym, "score": float(score), "item": item})
        if len(candidate_pool) >= max(1, int(candidate_top_n)):
            break

    entry_date_map = {str(k).lower(): safe_date_or_none(v) for k, v in dict(holding_entry_dates or {}).items()}
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
        score = resolve_rotation_score(
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


def resolve_mf_rank_tilt_scale(
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


def resolve_score_weight_scale(
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


def resolve_score_weight_score(item: dict[str, Any]) -> float | None:
    score = safe_float_or_none(item.get("mf_score"))
    if score is not None:
        return score
    sig = item.get("signal")
    meta = sig.meta if isinstance(sig, Signal) and isinstance(sig.meta, dict) else {}
    for key in ("final_score", "residual_strength_score", "strength"):
        score = safe_float_or_none(meta.get(key))
        if score is not None:
            return score
    return safe_float_or_none(item.get("strength"))


def build_score_weight_scale_maps(
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
        score_value = resolve_score_weight_score(item)
        raw_scale = resolve_score_weight_scale(
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
    normalized_scale_map = {sym: float(raw_scale) / float(mean_raw_scale) for sym, _, raw_scale in planned}
    score_map = {sym: score_value for sym, score_value, _ in planned}
    raw_scale_map = {sym: float(raw_scale) for sym, _, raw_scale in planned}
    return normalized_scale_map, score_map, raw_scale_map
