"""Breakout provider day-signal helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.breakout_support import row_rank_pct as _row_rank_pct
from backend.core.engine_vector.moneyflow_overlay import resolve_moneyflow_overlay_snapshot
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
    evaluate_engine_exits,
)


def evaluate_profit_decay_exits(
    provider: Any,
    *,
    day: date,
    day_idx: int,
    positions: dict[str, int],
    position_avg_cost: dict[str, float],
    close_idx: dict[tuple[date, str], float],
    exit_syms: set[str],
    exit_counts: ExitCounts,
) -> list[Signal]:
    if not provider._enable_profit_decay_exit:
        return []

    mx = provider._mx
    feats = provider._feats
    exits: list[Signal] = []
    for sym, qty in list(positions.items()):
        if int(qty) <= 0 or sym in exit_syms:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        raw_close = float(close_idx.get((day, sym), 0.0) or 0.0)
        avg_cost = float(position_avg_cost.get(sym, 0.0) or 0.0)
        if raw_close <= 0.0 or avg_cost <= 0.0:
            continue
        pnl_pct = raw_close / avg_cost - 1.0
        if pnl_pct < provider._profit_decay_exit_profit_pct:
            continue
        entry_idx = provider.entry_bar_index.get(sym)
        if entry_idx is None:
            continue
        bars_since_entry = int(day_idx) - int(entry_idx)
        if bars_since_entry < provider._profit_decay_exit_min_hold_bars:
            continue
        residual_score = (
            float(provider._residual_strength_score[day_idx, col])
            if provider._residual_strength_score.size and not np.isnan(provider._residual_strength_score[day_idx, col])
            else None
        )
        if residual_score is None or residual_score > provider._profit_decay_exit_residual_score_threshold:
            continue
        close_val = float(mx.close[day_idx, col]) if not np.isnan(mx.close[day_idx, col]) else None
        sma20_val = float(feats.sma20[day_idx, col]) if not np.isnan(feats.sma20[day_idx, col]) else None
        if close_val is None or sma20_val is None or close_val >= sma20_val:
            continue

        exit_syms.add(sym)
        exit_counts.profit_decay_exit += 1
        exits.append(
            Signal(
                signal_date=day,
                symbol=sym,
                side=Side.SELL,
                qty=int(qty),
                reason="PROFIT_DECAY_EXIT",
                reason_code="PROFIT_DECAY_EXIT",
                meta={
                    "triggered_rule": "PROFIT_DECAY_EXIT",
                    "avg_cost": avg_cost,
                    "pnl_pct": float(pnl_pct),
                    "bars_since_entry": int(bars_since_entry),
                    "residual_strength_score": float(residual_score),
                    "profit_decay_exit_profit_pct": float(provider._profit_decay_exit_profit_pct),
                    "profit_decay_exit_min_hold_bars": int(provider._profit_decay_exit_min_hold_bars),
                    "profit_decay_exit_residual_score_threshold": float(provider._profit_decay_exit_residual_score_threshold),
                    "close": float(close_val),
                    "sma20": float(sma20_val),
                },
            )
        )
    return exits


def _resolve_partial_exit_qty(held_qty: int, exit_pct: float) -> int:
    held = max(int(held_qty), 0)
    if held <= 0:
        return 0
    pct = float(exit_pct)
    if pct <= 0.0:
        return 0
    if pct >= 1.0:
        return held
    lot_size = 100
    if held <= lot_size:
        return held
    planned = int(held * pct)
    qty = max((planned // lot_size) * lot_size, lot_size)
    qty = min(qty, held)
    remain = held - qty
    if 0 < remain < lot_size:
        return held
    return max(qty, lot_size)


def evaluate_peak_giveback_ma20_exits(
    provider: Any,
    *,
    day: date,
    day_idx: int,
    positions: dict[str, int],
    position_avg_cost: dict[str, float],
    close_idx: dict[tuple[date, str], float],
    exit_syms: set[str],
) -> list[Signal]:
    if not bool(getattr(provider, "_enable_peak_giveback_ma20_exit", False)):
        return []

    mx = provider._mx
    feats = provider._feats
    min_peak_profit = float(getattr(provider, "_peak_giveback_ma20_min_peak_profit_pct", 0.20) or 0.20)
    min_giveback = float(getattr(provider, "_peak_giveback_ma20_min_giveback_pct", 0.25) or 0.25)
    min_hold_bars = max(0, int(getattr(provider, "_peak_giveback_ma20_min_hold_bars", 10) or 10))
    exit_pct = float(getattr(provider, "_peak_giveback_ma20_exit_pct", 0.5) or 0.5)
    exits: list[Signal] = []
    for sym, qty in list(positions.items()):
        if int(qty) <= 0 or sym in exit_syms:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        raw_close = float(close_idx.get((day, sym), 0.0) or 0.0)
        avg_cost = float(position_avg_cost.get(sym, 0.0) or 0.0)
        if raw_close <= 0.0 or avg_cost <= 0.0:
            continue
        entry_idx = provider.entry_bar_index.get(sym)
        if entry_idx is None:
            continue
        bars_since_entry = int(day_idx) - int(entry_idx)
        if bars_since_entry < min_hold_bars:
            continue
        peak_close = float(provider._peak_close_state.get(sym, raw_close) or raw_close)
        if peak_close <= 0.0:
            continue
        peak_profit_pct = peak_close / avg_cost - 1.0
        giveback_from_peak_pct = peak_close / raw_close - 1.0
        if peak_profit_pct < min_peak_profit or giveback_from_peak_pct < min_giveback:
            continue
        close_val = float(mx.close[day_idx, col]) if not np.isnan(mx.close[day_idx, col]) else None
        sma20_val = float(feats.sma20[day_idx, col]) if not np.isnan(feats.sma20[day_idx, col]) else None
        if close_val is None or sma20_val is None or close_val >= sma20_val:
            continue
        exit_qty = _resolve_partial_exit_qty(int(qty), exit_pct)
        if exit_qty <= 0:
            continue
        exit_syms.add(sym)
        exits.append(
            Signal(
                signal_date=day,
                symbol=sym,
                side=Side.SELL,
                qty=int(exit_qty),
                reason="PEAK_GIVEBACK_MA20_EXIT",
                reason_code="PEAK_GIVEBACK_MA20_EXIT",
                meta={
                    "triggered_rule": "PEAK_GIVEBACK_MA20_EXIT",
                    "avg_cost": avg_cost,
                    "close": float(raw_close),
                    "adjusted_close": float(close_val),
                    "sma20": float(sma20_val),
                    "peak_close": float(peak_close),
                    "peak_profit_pct": float(peak_profit_pct),
                    "giveback_from_peak_pct": float(giveback_from_peak_pct),
                    "bars_since_entry": int(bars_since_entry),
                    "peak_giveback_ma20_min_peak_profit_pct": float(min_peak_profit),
                    "peak_giveback_ma20_min_giveback_pct": float(min_giveback),
                    "peak_giveback_ma20_min_hold_bars": int(min_hold_bars),
                    "peak_giveback_ma20_exit_pct": float(exit_pct),
                    "partial_exit": bool(exit_qty < int(qty)),
                },
            )
        )
    return exits


def _restore_state_dict(provider: Any) -> dict[str, dict[str, Any]]:
    state = getattr(provider, "_mfe_mae_restore_state", None)
    if not isinstance(state, dict):
        state = {}
        provider._mfe_mae_restore_state = state
    return state


def _restore_scope_matches(provider: Any, high_chase: dict[str, Any]) -> bool:
    scope = str(getattr(provider, "_mfe_mae_restore_candidate_scope", "high_chase") or "high_chase").strip().lower()
    if scope in {"", "all"}:
        return True
    if scope == "high_chase":
        return bool(high_chase.get("high_chase_bool"))
    return False


def _mfe_mae_restore_arm_meta(
    provider: Any,
    *,
    day: date,
    day_idx: int,
    sym: str,
    held_qty: int,
    exit_qty: int,
    reason_code: str,
    high_chase: dict[str, Any],
) -> dict[str, Any]:
    if not bool(getattr(provider, "_enable_mfe_mae_restore_candidate", False)):
        return {}
    if int(exit_qty) <= 0 or int(exit_qty) >= int(held_qty):
        return {}
    if not _restore_scope_matches(provider, high_chase):
        return {}
    return {
        "mfe_mae_restore_candidate_arm_on_fill": True,
        "mfe_mae_restore_candidate_source": "mfe_mae_confirmation_exit",
        "mfe_mae_restore_candidate_source_reason_code": str(reason_code),
        "mfe_mae_restore_candidate_scope": str(
            getattr(provider, "_mfe_mae_restore_candidate_scope", "high_chase") or "high_chase"
        ).strip().lower(),
        "mfe_mae_restore_candidate_arm_decision_date": day.isoformat(),
        "mfe_mae_restore_candidate_arm_decision_bar_index": int(day_idx),
        "mfe_mae_restore_candidate_max_bars": int(
            getattr(provider, "_mfe_mae_restore_candidate_max_bars", 40) or 40
        ),
    }


def _active_mfe_mae_restore_candidate(
    provider: Any,
    *,
    sym: str,
    day_idx: int,
) -> dict[str, Any] | None:
    if not bool(getattr(provider, "_enable_mfe_mae_restore_candidate", False)):
        return None
    state = _restore_state_dict(provider)
    payload = state.get(str(sym).lower())
    if not isinstance(payload, dict):
        return None
    if not _restore_scope_matches(provider, payload):
        return None
    max_bars = max(1, int(getattr(provider, "_mfe_mae_restore_candidate_max_bars", 40) or 40))
    armed_idx_raw = payload.get("armed_bar_index", payload.get("arm_fill_bar_index", payload.get("arm_decision_bar_index", day_idx)))
    try:
        armed_idx = int(armed_idx_raw)
    except Exception:
        armed_idx = int(day_idx)
    if int(day_idx) - armed_idx > max_bars:
        state.pop(str(sym).lower(), None)
        provider.diag_reason_counts["MFE_MAE_RESTORE_EXPIRED"] = int(
            provider.diag_reason_counts.get("MFE_MAE_RESTORE_EXPIRED", 0)
        ) + 1
        return None
    return dict(payload)


def _matrix_float(matrix: Any, row: int, col: int) -> float | None:
    if matrix is None or not getattr(matrix, "size", 0):
        return None
    try:
        value = float(matrix[int(row), int(col)])
    except Exception:
        return None
    return value if np.isfinite(value) else None


def _lookback_return(close: np.ndarray, row: int, col: int, lookback: int) -> float | None:
    start = int(row) - int(lookback)
    if start < 0:
        return None
    start_close = _matrix_float(close, start, col)
    end_close = _matrix_float(close, row, col)
    if start_close is None or start_close <= 0.0 or end_close is None:
        return None
    return float(end_close / start_close - 1.0)


def _flag_ge(value: float | None, threshold: float) -> bool:
    return value is not None and np.isfinite(value) and float(value) >= float(threshold)


def _flag_le(value: float | None, threshold: float) -> bool:
    return value is not None and np.isfinite(value) and float(value) <= float(threshold)


def _entry_high_chase_payload(provider: Any, *, entry_idx: int, col: int) -> dict[str, Any]:
    decision_idx = max(int(entry_idx) - 1, 0)
    mx = provider._mx
    feats = provider._feats
    close_val = _matrix_float(mx.close, decision_idx, col)
    ma20 = _matrix_float(feats.sma20, decision_idx, col)
    ma60 = _matrix_float(feats.sma60, decision_idx, col)
    atr14 = _matrix_float(feats.atr14, decision_idx, col)
    ret5 = _lookback_return(mx.close, decision_idx, col, 5)
    ret10 = _lookback_return(mx.close, decision_idx, col, 10)
    ret20 = _lookback_return(mx.close, decision_idx, col, 20)
    ma20_ext = None if close_val is None or ma20 is None or ma20 <= 0.0 else close_val / ma20 - 1.0
    ma60_ext = None if close_val is None or ma60 is None or ma60 <= 0.0 else close_val / ma60 - 1.0
    atr_ext = None if close_val is None or ma20 is None or atr14 is None or atr14 <= 0.0 else (close_val - ma20) / atr14
    breakout_margin = _matrix_float(getattr(provider, "_breakout_margin_raw", None), decision_idx, col)
    open_gap = _matrix_float(getattr(provider, "_breakout_open_gap_raw", None), decision_idx, col)
    fade = _matrix_float(getattr(provider, "_breakout_fade_raw", None), decision_idx, col)
    breakout_quality = _matrix_float(getattr(provider, "_breakout_quality_score", None), decision_idx, col)
    volume_price_quality = _matrix_float(getattr(provider, "_volume_price_quality_score", None), decision_idx, col)

    short_heat = (
        _flag_ge(ret5, float(provider._mfe_mae_high_chase_ret5_pct))
        or _flag_ge(ret10, float(provider._mfe_mae_high_chase_ret10_pct))
        or _flag_ge(ret20, float(provider._mfe_mae_high_chase_ret20_pct))
    )
    extension_heat = (
        _flag_ge(ma20_ext, float(provider._mfe_mae_high_chase_ma20_extension_pct))
        or _flag_ge(ma60_ext, float(provider._mfe_mae_high_chase_ma60_extension_pct))
        or _flag_ge(atr_ext, float(provider._mfe_mae_high_chase_atr_extension))
    )
    breakout_stretch = (
        _flag_ge(breakout_margin, float(provider._mfe_mae_high_chase_breakout_margin_pct))
        or _flag_ge(open_gap, float(provider._mfe_mae_high_chase_open_gap_pct))
    )
    weak_quality = (
        _flag_le(breakout_quality, float(provider._mfe_mae_high_chase_breakout_quality_max))
        or _flag_le(volume_price_quality, float(provider._mfe_mae_high_chase_volume_price_quality_max))
        or _flag_ge(fade, float(provider._mfe_mae_high_chase_fade_pct))
    )
    core_count = int(short_heat) + int(extension_heat) + int(breakout_stretch)
    high_chase = core_count >= max(1, int(provider._mfe_mae_high_chase_min_core_flags))
    reasons = []
    if short_heat:
        reasons.append("short_heat")
    if extension_heat:
        reasons.append("extension_heat")
    if breakout_stretch:
        reasons.append("breakout_stretch")
    if weak_quality:
        reasons.append("weak_breakout_quality")
    return {
        "entry_decision_bar_index": int(decision_idx),
        "high_chase_bool": bool(high_chase),
        "high_chase_core_count": int(core_count),
        "high_chase_reasons": ";".join(reasons),
        "short_heat_bool": bool(short_heat),
        "extension_heat_bool": bool(extension_heat),
        "breakout_stretch_bool": bool(breakout_stretch),
        "weak_breakout_quality_bool": bool(weak_quality),
        "pre_entry_ret5": ret5,
        "pre_entry_ret10": ret10,
        "pre_entry_ret20": ret20,
        "entry_close_vs_prev_ma20": ma20_ext,
        "entry_close_vs_prev_ma60": ma60_ext,
        "entry_atr14_extension": atr_ext,
        "entry_breakout_margin_raw": breakout_margin,
        "entry_breakout_open_gap_raw": open_gap,
        "entry_breakout_fade_raw": fade,
        "entry_breakout_quality_score": breakout_quality,
        "entry_volume_price_quality_score": volume_price_quality,
    }


def _close_path_metrics(mx: Any, *, entry_idx: int, day_idx: int, col: int) -> dict[str, float] | None:
    entry_close = _matrix_float(mx.close, entry_idx, col)
    current_close = _matrix_float(mx.close, day_idx, col)
    if entry_close is None or entry_close <= 0.0 or current_close is None or current_close <= 0.0:
        return None
    close_path = np.asarray(mx.close[int(entry_idx) : int(day_idx) + 1, int(col)], dtype=float)
    close_path = close_path[np.isfinite(close_path)]
    if close_path.size == 0:
        return None
    returns = close_path / entry_close - 1.0
    close_mfe = float(np.nanmax(returns))
    close_mae = float(np.nanmin(returns))
    if not np.isfinite(close_mfe) or not np.isfinite(close_mae):
        return None
    return {
        "entry_close": float(entry_close),
        "current_close": float(current_close),
        "current_return": float(current_close / entry_close - 1.0),
        "close_mfe": float(close_mfe),
        "close_mae": float(close_mae),
    }


def _append_mfe_mae_sell_signal(
    exits: list[Signal],
    *,
    day: date,
    sym: str,
    held_qty: int,
    exit_qty: int,
    reason_code: str,
    bars_since_entry: int,
    entry_idx: int,
    path: dict[str, float],
    min_mfe_pct: float,
    max_mae_pct: float,
    exit_pct: float,
    high_chase: dict[str, Any],
    extra_meta: dict[str, Any] | None = None,
) -> None:
    meta = {
        "triggered_rule": reason_code,
        "partial_exit": bool(exit_qty < held_qty),
        "bars_since_entry": int(bars_since_entry),
        "entry_bar_index": int(entry_idx),
        "entry_close": float(path["entry_close"]),
        "current_close": float(path["current_close"]),
        "current_return_pct": float(path["current_return"]),
        "close_mfe_pct": float(path["close_mfe"]),
        "close_mae_pct": float(path["close_mae"]),
        "mfe_mae_confirmation_lookahead_bars": int(bars_since_entry),
        "mfe_mae_confirmation_min_mfe_pct": float(min_mfe_pct),
        "mfe_mae_confirmation_max_mae_pct": float(max_mae_pct),
        "mfe_mae_confirmation_exit_pct": float(exit_pct),
        "mfe_mae_confirmation_scope": str(high_chase.get("scope", "all")),
        "mfe_mae_confirmation_action": str(high_chase.get("action", "exit")),
        "held_qty_before_exit": int(held_qty),
        **{k: v for k, v in high_chase.items() if k not in {"scope", "action"}},
    }
    if extra_meta:
        meta.update(extra_meta)
    exits.append(
        Signal(
            signal_date=day,
            symbol=sym,
            side=Side.SELL,
            qty=int(exit_qty),
            reason=reason_code,
            reason_code=reason_code,
            meta=meta,
        )
    )


def evaluate_mfe_mae_confirmation_exits(
    provider: Any,
    *,
    day: date,
    day_idx: int,
    positions: dict[str, int],
    exit_syms: set[str],
    exit_counts: ExitCounts,
) -> list[Signal]:
    if not provider._enable_mfe_mae_confirmation_exit:
        return []

    mx = provider._mx
    lookahead_bars = max(1, int(provider._mfe_mae_confirmation_lookahead_bars))
    min_mfe_pct = float(provider._mfe_mae_confirmation_min_mfe_pct)
    max_mae_pct = float(provider._mfe_mae_confirmation_max_mae_pct)
    exit_pct = float(provider._mfe_mae_confirmation_exit_pct)
    scope = str(getattr(provider, "_mfe_mae_confirmation_scope", "all") or "all").strip().lower()
    action = str(getattr(provider, "_mfe_mae_confirmation_action", "exit") or "exit").strip().lower()
    if scope not in {"all", "high_chase"}:
        scope = "all"
    if action not in {"exit", "watch_day10"}:
        action = "exit"
    watch_state = getattr(provider, "_mfe_mae_confirmation_watch_state", None)
    if not isinstance(watch_state, dict):
        watch_state = {}
        provider._mfe_mae_confirmation_watch_state = watch_state

    exits: list[Signal] = []

    review_bars = max(lookahead_bars + 1, int(getattr(provider, "_mfe_mae_watch_review_bars", 10) or 10))
    for sym, state in list(watch_state.items()):
        if sym in exit_syms:
            continue
        held_qty = int(positions.get(sym, 0) or 0)
        if held_qty <= 0:
            watch_state.pop(sym, None)
            continue
        col = provider._sym_to_col.get(sym)
        entry_idx_raw = provider.entry_bar_index.get(sym)
        if col is None or entry_idx_raw is None:
            continue
        entry_idx = int(entry_idx_raw)
        bars_since_entry = int(day_idx) - entry_idx
        if bars_since_entry < review_bars:
            continue
        path = _close_path_metrics(mx, entry_idx=entry_idx, day_idx=int(day_idx), col=int(col))
        if path is None:
            continue
        unrepaired = (
            path["close_mfe"] < float(getattr(provider, "_mfe_mae_watch_review_min_mfe_pct", min_mfe_pct))
            and path["current_return"] <= float(getattr(provider, "_mfe_mae_watch_review_max_current_return_pct", 0.0))
            and path["close_mae"] <= float(getattr(provider, "_mfe_mae_watch_review_max_mae_pct", max_mae_pct))
        )
        if not unrepaired:
            watch_state.pop(sym, None)
            continue
        exit_qty = _resolve_partial_exit_qty(held_qty, exit_pct)
        if exit_qty <= 0:
            continue
        high_chase_meta = dict(state)
        high_chase_meta["scope"] = scope
        high_chase_meta["action"] = action
        exit_syms.add(sym)
        exit_counts.mfe_mae_confirmation_exit += 1
        watch_state.pop(sym, None)
        _append_mfe_mae_sell_signal(
            exits,
            day=day,
            sym=sym,
            held_qty=held_qty,
            exit_qty=exit_qty,
            reason_code="MFE_MAE_CONFIRMATION_WATCH_EXIT",
            bars_since_entry=bars_since_entry,
            entry_idx=entry_idx,
            path=path,
            min_mfe_pct=min_mfe_pct,
            max_mae_pct=max_mae_pct,
            exit_pct=exit_pct,
            high_chase=high_chase_meta,
            extra_meta={
                "mfe_mae_watch_review_bars": int(review_bars),
                "mfe_mae_watch_unrepaired": True,
                **_mfe_mae_restore_arm_meta(
                    provider,
                    day=day,
                    day_idx=int(day_idx),
                    sym=sym,
                    held_qty=held_qty,
                    exit_qty=exit_qty,
                    reason_code="MFE_MAE_CONFIRMATION_WATCH_EXIT",
                    high_chase=high_chase_meta,
                ),
            },
        )

    for sym, qty in list(positions.items()):
        held_qty = int(qty)
        if held_qty <= 0 or sym in exit_syms:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        entry_idx = provider.entry_bar_index.get(sym)
        if entry_idx is None:
            continue
        entry_idx = int(entry_idx)
        bars_since_entry = int(day_idx) - entry_idx
        if bars_since_entry != lookahead_bars or entry_idx < 0:
            continue
        path = _close_path_metrics(mx, entry_idx=entry_idx, day_idx=int(day_idx), col=int(col))
        if path is None:
            continue
        if path["close_mfe"] >= min_mfe_pct or path["close_mae"] > max_mae_pct:
            continue
        high_chase_meta = {"scope": scope, "action": action}
        if scope == "high_chase":
            high_chase_meta.update(_entry_high_chase_payload(provider, entry_idx=entry_idx, col=int(col)))
            if not bool(high_chase_meta.get("high_chase_bool")):
                continue
        else:
            high_chase_meta.update({"high_chase_bool": False, "high_chase_core_count": 0, "high_chase_reasons": ""})

        if action == "watch_day10":
            deep_mae = float(getattr(provider, "_mfe_mae_watch_deep_mae_immediate_pct", -0.08))
            if path["close_mae"] > deep_mae:
                watch_state[sym] = {
                    **high_chase_meta,
                    "watch_start_bar_index": int(day_idx),
                    "watch_start_bars_since_entry": int(bars_since_entry),
                    "watch_start_close_mfe_pct": float(path["close_mfe"]),
                    "watch_start_close_mae_pct": float(path["close_mae"]),
                    "watch_start_current_return_pct": float(path["current_return"]),
                }
                provider.diag_reason_counts["MFE_MAE_CONFIRMATION_WATCH"] = int(
                    provider.diag_reason_counts.get("MFE_MAE_CONFIRMATION_WATCH", 0)
                ) + 1
                continue

        exit_qty = _resolve_partial_exit_qty(held_qty, exit_pct)
        if exit_qty <= 0:
            continue

        exit_syms.add(sym)
        exit_counts.mfe_mae_confirmation_exit += 1
        _append_mfe_mae_sell_signal(
            exits,
            day=day,
            sym=sym,
            held_qty=held_qty,
            exit_qty=exit_qty,
            reason_code="MFE_MAE_CONFIRMATION_EXIT",
            bars_since_entry=bars_since_entry,
            entry_idx=entry_idx,
            path=path,
            min_mfe_pct=min_mfe_pct,
            max_mae_pct=max_mae_pct,
            exit_pct=exit_pct,
            high_chase=high_chase_meta,
            extra_meta=_mfe_mae_restore_arm_meta(
                provider,
                day=day,
                day_idx=int(day_idx),
                sym=sym,
                held_qty=held_qty,
                exit_qty=exit_qty,
                reason_code="MFE_MAE_CONFIRMATION_EXIT",
                high_chase=high_chase_meta,
            ),
        )
    return exits

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------



def _score_from_row(row: np.ndarray | None, col: int) -> float | None:
    if row is None or row.size == 0:
        return None
    try:
        value = float(row[int(col)])
    except Exception:
        return None
    return value if np.isfinite(value) else None


def _residual_score_row(provider: Any, day_idx: int) -> np.ndarray:
    full = getattr(provider, "_residual_strength_score", np.array([]))
    if getattr(full, "size", 0):
        return full[int(day_idx), :]
    raw = getattr(provider, "_residual_strength_raw", np.array([]))
    mx = provider._mx
    if not getattr(raw, "size", 0):
        return np.array([], dtype=float)
    row = raw[int(day_idx) : int(day_idx) + 1, :]
    valid = mx.tradable[int(day_idx) : int(day_idx) + 1, :]
    ranked = _row_rank_pct(row, valid)
    return ranked[0, :] if ranked.size else np.array([], dtype=float)


def _final_score_row(provider: Any, day_idx: int, residual_score_row: np.ndarray) -> np.ndarray:
    full = getattr(provider, "_final_score", np.array([]))
    if getattr(full, "size", 0):
        return full[int(day_idx), :]
    if bool(getattr(provider, "_deferred_residual_score_enabled", False)):
        return residual_score_row
    return np.array([], dtype=float)


def _resolve_entry_risk_position_payload(
    provider: Any,
    *,
    flag_count: int,
    target_basis: str | None,
) -> dict[str, Any]:
    enabled = bool(getattr(provider, "_entry_risk_position_sizing_enabled", False))
    if not enabled:
        return {}
    count = max(int(flag_count), 0)
    if count <= 0:
        tier = "0_low"
        multiplier = 1.0
    elif count == 1:
        tier = "1_watch"
        multiplier = float(getattr(provider, "_entry_risk_position_watch_scale", 0.80) or 0.0)
    elif count == 2:
        tier = "2_high"
        multiplier = float(getattr(provider, "_entry_risk_position_high_scale", 0.50) or 0.0)
    else:
        tier = "3_plus_extreme"
        multiplier = float(getattr(provider, "_entry_risk_position_extreme_scale", 1.0 / 3.0) or 0.0)
    multiplier = min(1.0, max(0.0, float(multiplier)))
    preserve_existing_target = bool(str(target_basis or "").strip())
    payload: dict[str, Any] = {
        "entry_risk_position_sizing_enabled": True,
        "entry_risk_position_preserve_existing_target": bool(preserve_existing_target),
        "entry_risk_position_tier": tier,
        "entry_risk_position_flag_count": int(count),
        "entry_risk_position_multiplier": float(multiplier),
    }
    return payload


def build_breakout_day_signals(provider: Any, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
    i = day_idx
    mx = provider._mx
    feats = provider._feats
    positions = ctx.positions
    position_avg_cost = ctx.position_avg_cost
    close_idx = ctx.close_idx
    max_positions = ctx.max_positions
    n = mx.close.shape[1]
    overlay_snapshot = resolve_moneyflow_overlay_snapshot(getattr(ctx, "asset_context", {}), day=day)
    overlay_score_map = {
        str(symbol).lower(): float(score)
        for symbol, score in dict(overlay_snapshot.score_map or {}).items()
    }
    residual_score_row = _residual_score_row(provider, i)
    final_score_row = _final_score_row(provider, i, residual_score_row)

    # ── 卖出信号: engine 级退出规则 ──
    def _get_atr(sym: str, d: date) -> float | None:
        col = provider._sym_to_col.get(sym)
        if col is None:
            return None
        v = float(feats.atr14[i, col])
        return v if not np.isnan(v) else None

    def _check_ma20(sym: str) -> bool:
        col = provider._sym_to_col.get(sym)
        if col is None:
            return False
        adj_c = float(mx.close[i, col])
        sma20_v = float(feats.sma20[i, col])
        if np.isnan(adj_c) or np.isnan(sma20_v):
            return False
        return adj_c < sma20_v

    def _check_low10(sym: str) -> bool:
        col = provider._sym_to_col.get(sym)
        if col is None:
            return False
        adj_c = float(mx.close[i, col])
        low10_v = float(feats.low_min10[i, col])
        if np.isnan(adj_c) or np.isnan(low10_v):
            return False
        return adj_c < low10_v

    sell_sigs, exit_syms, exit_counts, fragility_diagnostics = evaluate_engine_exits(
        positions=positions,
        day=day,
        close_idx=close_idx,
        position_avg_cost=position_avg_cost,
        peak_state=provider._peak_close_state,
        entry_day=provider.entry_day,
        entry_bar_index=provider.entry_bar_index,
        current_bar_index=i,
        entry_breakout_floor=provider.entry_breakout_floor_raw,
        exit_cfg=provider._ec,
        get_atr=_get_atr,
        risk_on=bool(provider._risk_on[i]),
        enable_risk_off_exit=provider._enable_risk_off_exit,
        risk_off_exit_mode=provider._risk_off_exit_mode,
        risk_off_exit_partial_pct=provider._risk_off_exit_partial_pct,
        risk_off_exit_partial_mode=provider._risk_off_exit_partial_mode,
        risk_off_exit_partial_only_if_profitable=provider._risk_off_exit_partial_only_if_profitable,
        risk_off_partial_state=provider._risk_off_partial_state,
        market_state=str(getattr(ctx, "market_state", "") or ""),
        max_hold_days=provider._max_hold_days,
        atr_stop_k=provider._atr_stop_k,
        check_ma20_exit=_check_ma20,
        check_low10_exit=_check_low10,
        asset_context=getattr(ctx, "asset_context", {}),
    )
    sell_sigs.extend(
        provider._evaluate_profit_decay_exits(
            day=day,
            day_idx=i,
            positions=positions,
            position_avg_cost=position_avg_cost,
            close_idx=close_idx,
            exit_syms=exit_syms,
            exit_counts=exit_counts,
        )
    )
    sell_sigs.extend(
        evaluate_peak_giveback_ma20_exits(
            provider,
            day=day,
            day_idx=i,
            positions=positions,
            position_avg_cost=position_avg_cost,
            close_idx=close_idx,
            exit_syms=exit_syms,
        )
    )
    sell_sigs.extend(
        provider._evaluate_mfe_mae_confirmation_exits(
            day=day,
            day_idx=i,
            positions=positions,
            exit_syms=exit_syms,
            exit_counts=exit_counts,
        )
    )
    for _ss in sell_sigs:
        _rc = str(_ss.reason_code)
        provider.diag_reason_counts[_rc] = int(provider.diag_reason_counts.get(_rc, 0)) + 1

    # ── 买入信号 ──
    day_cands = provider._cand_idx[i]
    buy_sigs: list[Signal] = []
    mf_score_map: dict[str, float] = {}
    strength_map: dict[str, float] = {}
    breakout_count = 0
    pullback_count = 0
    overlap_count = 0
    bull_breakout_quality_veto_applied = bool(
        provider._bull_breakout_quality_veto_enabled
        and bool(ctx.risk_on)
        and str(getattr(ctx, "market_state", "") or "").upper() == "BULL"
    )
    bull_breakout_quality_veto_block_count = 0
    bull_breakout_quality_veto_residual_block_count = 0
    bull_breakout_quality_veto_margin_block_count = 0
    provider.total_buy_signals += int(len(day_cands))

    # Keep score maps available for held symbols too, so downstream order planning
    # can compare incumbent holdings vs. new candidates without peeking into t+1 data.
    for held_sym, held_qty in dict(positions or {}).items():
        sym = str(held_sym).lower()
        if int(held_qty) <= 0:
            continue
        col = provider._sym_to_col.get(sym)
        if col is None:
            continue
        final_score_held = _score_from_row(final_score_row, col)
        residual_score_held = _score_from_row(residual_score_row, col)
        if final_score_held is not None:
            mf_score_map[sym] = float(final_score_held)
        if residual_score_held is not None or final_score_held is not None:
            strength_map[sym] = float(residual_score_held if residual_score_held is not None else final_score_held)

    for c in day_cands:
        sym = mx.symbols[int(c)]
        # 已持有跳过
        restore_candidate_payload: dict[str, Any] | None = None
        if sym in positions and int(positions[sym]) > 0:
            restore_candidate_payload = _active_mfe_mae_restore_candidate(
                provider,
                sym=sym,
                day_idx=int(i),
            )
            if restore_candidate_payload is None:
                continue
        # min_hold 约束
        if provider._min_hold_days > 0 and sym in provider.entry_day:
            held = (day - provider.entry_day[sym]).days
            if held < provider._min_hold_days:
                provider.min_hold_block_count += 1
                continue
        # cooldown 约束
        if provider._cooldown_days > 0 and provider.last_sell_day and sym in provider.last_sell_day:
            since_sell = (day - provider.last_sell_day[sym]).days
            if since_sell < provider._cooldown_days:
                provider.cooldown_block_count += 1
                continue
        if provider._enable_entry_above_slow_ma and not bool(provider._entry_above_slow_ma[i, c]):
            provider.entry_above_slow_ma_block_count += 1
            continue
        if provider._enable_entry_slow_ma_slope and not bool(provider._entry_slow_ma_slope_pos[i, c]):
            provider.entry_slope_block_count += 1
            continue

        close_val = float(mx.close[i, c]) if not np.isnan(mx.close[i, c]) else None
        raw_close_val = float(close_idx.get((day, sym), 0.0) or 0.0)
        slow_ma_val = float(feats.sma60[i, c]) if not np.isnan(feats.sma60[i, c]) else None
        atr_val = float(feats.atr14[i, c]) if not np.isnan(feats.atr14[i, c]) else None
        hmax_prev_main = float(provider._high_max_main[i - 1, c]) if (i > 0 and not np.isnan(provider._high_max_main[i - 1, c])) else None
        hmax_prev_short = float(provider._high_max_short[i - 1, c]) if (i > 0 and not np.isnan(provider._high_max_short[i - 1, c])) else None
        hmax_prev_long = float(provider._high_max_long[i - 1, c]) if (i > 0 and not np.isnan(provider._high_max_long[i - 1, c])) else None
        hit_short = bool(provider._breakout_up_short[i, c]) if provider._breakout_up_short.size else False
        hit_long = bool(provider._breakout_up_long[i, c]) if provider._breakout_up_long.size else False
        from_breakout = bool(provider._breakout_buy[i, c]) if provider._breakout_buy.size else False
        from_pullback = bool(provider._pullback_buy[i, c]) if provider._pullback_buy.size else False
        is_overlap = bool(provider._pullback_overlap[i, c]) if provider._pullback_overlap.size else False
        if from_breakout:
            breakout_count += 1
        if from_pullback:
            pullback_count += 1
        if is_overlap:
            overlap_count += 1
        breakout_margin_raw = float(provider._breakout_margin_raw[i, c]) if provider._breakout_margin_raw.size and not np.isnan(provider._breakout_margin_raw[i, c]) else None
        breakout_margin_score = float(provider._breakout_margin_score[i, c]) if provider._breakout_margin_score.size and not np.isnan(provider._breakout_margin_score[i, c]) else None
        breakout_fade_raw = float(provider._breakout_fade_raw[i, c]) if provider._breakout_fade_raw.size and not np.isnan(provider._breakout_fade_raw[i, c]) else None
        breakout_open_gap_raw = float(provider._breakout_open_gap_raw[i, c]) if provider._breakout_open_gap_raw.size and not np.isnan(provider._breakout_open_gap_raw[i, c]) else None
        breakout_quality_score = float(provider._breakout_quality_score[i, c]) if provider._breakout_quality_score.size and not np.isnan(provider._breakout_quality_score[i, c]) else None
        breakout_quality_pass = bool(provider._breakout_quality_pass[i, c]) if provider._breakout_quality_pass.size else True
        residual_raw = float(provider._residual_strength_raw[i, c]) if provider._residual_strength_raw.size and not np.isnan(provider._residual_strength_raw[i, c]) else None
        residual_score = _score_from_row(residual_score_row, int(c))
        sector_score = float(provider._sector_strength_score[i, c]) if provider._sector_strength_score.size and not np.isnan(provider._sector_strength_score[i, c]) else None
        quality_score = float(provider._volume_price_quality_score[i, c]) if provider._volume_price_quality_score.size and not np.isnan(provider._volume_price_quality_score[i, c]) else None
        conditional_tiebreak_score = float(provider._conditional_tiebreak_score[i, c]) if provider._conditional_tiebreak_score.size and not np.isnan(provider._conditional_tiebreak_score[i, c]) else None
        conditional_factor_leader_score = float(provider._conditional_factor_leader_score[i, c]) if provider._conditional_factor_leader_score.size and not np.isnan(provider._conditional_factor_leader_score[i, c]) else None
        conditional_institution_proxy_score = float(provider._conditional_institution_proxy_score[i, c]) if provider._conditional_institution_proxy_score.size and not np.isnan(provider._conditional_institution_proxy_score[i, c]) else None
        conditional_crowding_score = float(provider._conditional_crowding_score[i, c]) if provider._conditional_crowding_score.size and not np.isnan(provider._conditional_crowding_score[i, c]) else None
        industry_second_stage_score = float(provider._industry_second_stage_score[i, c]) if provider._industry_second_stage_score.size and not np.isnan(provider._industry_second_stage_score[i, c]) else None
        industry_second_stage_not_hot_score = float(provider._industry_second_stage_not_hot_score[i, c]) if provider._industry_second_stage_not_hot_score.size and not np.isnan(provider._industry_second_stage_not_hot_score[i, c]) else None
        industry_second_stage_uncrowded_score = float(provider._industry_second_stage_uncrowded_score[i, c]) if provider._industry_second_stage_uncrowded_score.size and not np.isnan(provider._industry_second_stage_uncrowded_score[i, c]) else None
        industry_second_stage_breadth_timing_score = float(provider._industry_second_stage_breadth_timing_score[i, c]) if provider._industry_second_stage_breadth_timing_score.size and not np.isnan(provider._industry_second_stage_breadth_timing_score[i, c]) else None
        industry_second_stage_persistence_10d = float(provider._industry_second_stage_persistence_10d[i, c]) if provider._industry_second_stage_persistence_10d.size and not np.isnan(provider._industry_second_stage_persistence_10d[i, c]) else None
        industry_second_stage_active = bool(provider._industry_second_stage_active[i, c]) if provider._industry_second_stage_active.size else False
        include_industry_second_stage_meta = str(provider._residual_refine_mode) in {
            "industry_second_stage",
            "industry_second_stage_tiebreak",
        }
        leadership_route_score = float(provider._leadership_route_score[i, c]) if provider._leadership_route_score.size and not np.isnan(provider._leadership_route_score[i, c]) else None
        leadership_route_rank = float(provider._leadership_route_rank[i, c]) if provider._leadership_route_rank.size and not np.isnan(provider._leadership_route_rank[i, c]) else None
        leadership_route_bucket = int(provider._leadership_route_bucket[i, c]) if provider._leadership_route_bucket.size and int(provider._leadership_route_bucket[i, c]) >= 0 else None
        final_score_value = _score_from_row(final_score_row, int(c))
        final_score = float(final_score_value) if final_score_value is not None else 0.5
        trend_quality_soft_score = _matrix_float(getattr(provider, "_trend_quality_soft_score", None), i, c)
        trend_quality_r2_60_rank = _matrix_float(getattr(provider, "_trend_quality_r2_60_rank", None), i, c)
        trend_quality_slope60_rank = _matrix_float(getattr(provider, "_trend_quality_slope60_rank", None), i, c)
        trend_quality_ret60_vol_adj_rank = _matrix_float(
            getattr(provider, "_trend_quality_ret60_vol_adj_rank", None),
            i,
            c,
        )
        trend_quality_ret60_dd_adj_rank = _matrix_float(
            getattr(provider, "_trend_quality_ret60_dd_adj_rank", None),
            i,
            c,
        )
        risk_archetype_original_final_score = _matrix_float(
            getattr(provider, "_risk_archetype_original_final_score", None),
            i,
            c,
        )
        risk_archetype_score_scale = _matrix_float(getattr(provider, "_risk_archetype_score_scale", None), i, c)
        risk_archetype_pre_ret20_rank = _matrix_float(
            getattr(provider, "_risk_archetype_pre_ret20_rank", None),
            i,
            c,
        )
        risk_archetype_dist_ma60_rank = _matrix_float(
            getattr(provider, "_risk_archetype_dist_ma60_rank", None),
            i,
            c,
        )
        risk_archetype_vol60_rank = _matrix_float(getattr(provider, "_risk_archetype_vol60_rank", None), i, c)
        risk_archetype_turnover20_rank = _matrix_float(
            getattr(provider, "_risk_archetype_turnover20_rank", None),
            i,
            c,
        )
        risk_archetype_fade_rank = _matrix_float(getattr(provider, "_risk_archetype_fade_rank", None), i, c)
        risk_archetype_open_gap_rank = _matrix_float(getattr(provider, "_risk_archetype_open_gap_rank", None), i, c)
        risk_archetype_hot_crowded = (
            bool(provider._risk_archetype_hot_crowded[i, c])
            if getattr(provider, "_risk_archetype_hot_crowded", np.array([], dtype=bool)).size
            else False
        )
        risk_archetype_high_volatility_chase = (
            bool(provider._risk_archetype_high_volatility_chase[i, c])
            if getattr(provider, "_risk_archetype_high_volatility_chase", np.array([], dtype=bool)).size
            else False
        )
        risk_archetype_flag_count = (
            int(provider._risk_archetype_flag_count[i, c])
            if getattr(provider, "_risk_archetype_flag_count", np.array([], dtype=int)).size
            else 0
        )
        high_chase_a2_feature_meta: dict[str, Any] = {}
        if bool(getattr(provider, "_high_chase_a2_emit_features", False)):
            a2_pre_ret_20d = _matrix_float(getattr(provider, "_high_chase_a2_pre_ret_20d", None), i, c)
            a2_turnover20 = _matrix_float(getattr(provider, "_high_chase_a2_avg_turnover_rate_f_20d", None), i, c)
            a2_volume20v60 = _matrix_float(getattr(provider, "_high_chase_a2_volume_20d_vs_60d", None), i, c)
            high_chase_a2_feature_meta = {
                "pre_ret_20d": a2_pre_ret_20d,
                "avg_turnover_rate_f_20d": a2_turnover20,
                "volume_20d_vs_60d": a2_volume20v60,
                "high_chase_a2_pre_ret_20d": a2_pre_ret_20d,
                "high_chase_a2_avg_turnover_rate_f_20d": a2_turnover20,
                "high_chase_a2_volume_20d_vs_60d": a2_volume20v60,
            }
        hot_amount_turnover_feature_meta: dict[str, Any] = {}
        if bool(getattr(provider, "_hot_amount_turnover_emit_features", False)):
            hot_amount20 = _matrix_float(getattr(provider, "_hot_amount_turnover_amount20", None), i, c)
            hot_turnover20 = _matrix_float(getattr(provider, "_hot_amount_turnover_turnover_rate20", None), i, c)
            hot_amount_turnover_feature_meta = {
                "amount20": hot_amount20,
                "turnover_rate20": hot_turnover20,
                "hot_amount_turnover_amount20": hot_amount20,
                "hot_amount_turnover_turnover_rate20": hot_turnover20,
            }
        mf_score_map[sym] = float(final_score)
        strength_map[sym] = float(residual_score if residual_score is not None else final_score)
        pullback_variant = ""
        if provider._pullback_tight1.size and bool(provider._pullback_tight1[i, c]) and provider._pullback_tight2.size and bool(provider._pullback_tight2[i, c]):
            pullback_variant = "pb_tight_combo"
        elif provider._pullback_tight1.size and bool(provider._pullback_tight1[i, c]):
            pullback_variant = "pb_tight_reclaim"
        elif provider._pullback_tight2.size and bool(provider._pullback_tight2[i, c]):
            pullback_variant = "pb_tight_box"
        elif provider._pullback_pb1.size and bool(provider._pullback_pb1[i, c]):
            pullback_variant = "pb_reclaim_ma20"
        elif provider._pullback_pb2.size and bool(provider._pullback_pb2[i, c]):
            pullback_variant = "pb_reversal_near_low"
        elif provider._pullback_pb3.size and bool(provider._pullback_pb3[i, c]):
            pullback_variant = "pb_box_break"
        alpha_source = "breakout"
        reason = "BREAKOUT_DUAL_OR" if provider._enable_dual_breakout else "BREAKOUT_HIGH"
        if provider._enable_dual_breakout and provider._dual_breakout_mode == "slow_gate_fast_trigger":
            reason = "BREAKOUT_SLOW_GATE_FAST_TRIGGER"
        reason_code = reason
        if is_overlap and from_breakout:
            alpha_source = "pullback_overlap"
            reason = "BREAKOUT_PULLBACK_CONFLUENCE"
            reason_code = "BREAKOUT_PULLBACK_CONFLUENCE"
        elif from_pullback:
            alpha_source = "pullback_only"
            reason = "PULLBACK_TREND"
            reason_code = "PULLBACK_TREND"
        else:
            pullback_variant = ""
        entry_breakout_floor_raw = None
        if (
            hmax_prev_main is not None
            and close_val is not None
            and close_val > 0.0
            and raw_close_val > 0.0
        ):
            entry_breakout_floor_raw = float(hmax_prev_main) * float(raw_close_val) / float(close_val)
        if bull_breakout_quality_veto_applied and alpha_source in {"breakout", "pullback_overlap"}:
            residual_veto = (
                provider._bull_breakout_quality_veto_min_residual_strength_score > 0.0
                and residual_score is not None
                and residual_score < provider._bull_breakout_quality_veto_min_residual_strength_score
            )
            margin_veto = (
                provider._bull_breakout_quality_veto_min_breakout_margin_score > 0.0
                and breakout_margin_score is not None
                and breakout_margin_score < provider._bull_breakout_quality_veto_min_breakout_margin_score
            )
            if residual_veto or margin_veto:
                provider.bull_breakout_quality_veto_block_count += 1
                bull_breakout_quality_veto_block_count += 1
                if residual_veto:
                    provider.bull_breakout_quality_veto_residual_block_count += 1
                    bull_breakout_quality_veto_residual_block_count += 1
                if margin_veto:
                    provider.bull_breakout_quality_veto_margin_block_count += 1
                    bull_breakout_quality_veto_margin_block_count += 1
                provider.diag_reason_counts["BLOCK_BULL_QUALITY_VETO"] = int(
                    provider.diag_reason_counts.get("BLOCK_BULL_QUALITY_VETO", 0)
                ) + 1
                continue

        original_reason = str(reason or "BUY")
        original_reason_code = str(reason_code or original_reason)
        formal_reason_codes = [original_reason_code]
        restore_buy_meta: dict[str, Any] = {}
        if restore_candidate_payload is not None:
            reason = "MFE_MAE_RESTORE_CANDIDATE"
            reason_code = "MFE_MAE_RESTORE_CANDIDATE"
            formal_reason_codes = [str(reason_code), original_reason_code]
            restore_buy_meta = {
                "restore_candidate": True,
                "mfe_mae_restore_candidate": True,
                "restore_candidate_source": "mfe_mae_confirmation_exit",
                "restore_candidate_original_reason": original_reason,
                "restore_candidate_original_reason_code": original_reason_code,
                "restore_candidate_source_reason_code": str(
                    restore_candidate_payload.get("source_reason_code")
                    or restore_candidate_payload.get("mfe_mae_restore_candidate_source_reason_code")
                    or ""
                ),
                "restore_candidate_arm_date": str(restore_candidate_payload.get("armed_date") or ""),
                "restore_candidate_arm_bar_index": restore_candidate_payload.get("armed_bar_index"),
                "target_weight_basis": "delta_restore_gap",
                "restore_target_basis": str(
                    getattr(provider, "_mfe_mae_restore_candidate_target_basis", "original_target")
                    or "original_target"
                ),
                "restore_clear_on_fill": bool(
                    getattr(provider, "_mfe_mae_restore_candidate_clear_on_fill", True)
                ),
                "allow_existing_holding_top_up": True,
            }
            provider.diag_reason_counts["MFE_MAE_RESTORE_CANDIDATE"] = int(
                provider.diag_reason_counts.get("MFE_MAE_RESTORE_CANDIDATE", 0)
            ) + 1
        entry_risk_position_payload = _resolve_entry_risk_position_payload(
            provider,
            flag_count=int(risk_archetype_flag_count),
            target_basis=restore_buy_meta.get("target_weight_basis"),
        )

        buy_sigs.append(Signal(
            signal_date=day,
            symbol=sym,
            side=Side.BUY,
            qty=provider._order_size,
            reason=reason,
            reason_code=reason_code,
            meta={
                "owner_system": "cn_stock_trend_alpha_core",
                "formal_reason_codes": formal_reason_codes,
                "close": close_val,
                "slow_ma": slow_ma_val,
                "atr_last": atr_val,
                "alpha_source": alpha_source,
                "overlap_flag": bool(is_overlap),
                "pullback_variant": pullback_variant,
                "breakout_margin_raw": breakout_margin_raw,
                "breakout_margin_score": breakout_margin_score,
                "breakout_fade_raw": breakout_fade_raw,
                "breakout_open_gap_raw": breakout_open_gap_raw,
                "breakout_quality_score": breakout_quality_score,
                "breakout_quality_pass": bool(breakout_quality_pass),
                "bull_breakout_quality_veto_applied": bool(
                    bull_breakout_quality_veto_applied and alpha_source in {"breakout", "pullback_overlap"}
                ),
                "bull_breakout_quality_veto_min_residual_strength_score": float(
                    provider._bull_breakout_quality_veto_min_residual_strength_score
                ),
                "bull_breakout_quality_veto_min_breakout_margin_score": float(
                    provider._bull_breakout_quality_veto_min_breakout_margin_score
                ),
                "ranking_mode": str(provider._ranking_mode),
                "breakout_quality_gate_min_score": float(provider._breakout_quality_gate_min_score),
                "breakout_quality_margin_cap_pct": float(provider._breakout_quality_margin_cap_pct),
                "breakout_quality_fade_cap_pct": float(provider._breakout_quality_fade_cap_pct),
                "breakout_quality_open_gap_cap_pct": float(provider._breakout_quality_open_gap_cap_pct),
                "residual_vs_bench_raw": (
                    float(provider._residual_vs_bench_raw[i, c])
                    if provider._residual_vs_bench_raw.size and np.isfinite(provider._residual_vs_bench_raw[i, c])
                    else None
                ),
                "residual_vs_sector_raw": (
                    float(provider._residual_vs_sector_raw[i, c])
                    if provider._residual_vs_sector_raw.size and np.isfinite(provider._residual_vs_sector_raw[i, c])
                    else None
                ),
                "sector_proxy_residual_raw": (
                    float(provider._sector_proxy_residual_raw[i, c])
                    if provider._sector_proxy_residual_raw.size and np.isfinite(provider._sector_proxy_residual_raw[i, c])
                    else None
                ),
                "industry_median_excess_raw": (
                    float(provider._industry_median_excess_raw[i, c])
                    if provider._industry_median_excess_raw.size and np.isfinite(provider._industry_median_excess_raw[i, c])
                    else None
                ),
                "sector_beta_tailwind_raw": (
                    float(provider._sector_beta_tailwind_raw[i, c])
                    if provider._sector_beta_tailwind_raw.size and np.isfinite(provider._sector_beta_tailwind_raw[i, c])
                    else None
                ),
                "residual_strength_raw": residual_raw,
                "residual_strength_score": residual_score,
                "residual_benchmark_weight": float(provider._residual_benchmark_weight),
                "residual_industry_weight": float(provider._residual_industry_weight),
                "industry_relative_mode": str(provider._industry_relative_mode),
                "industry_relative_regime_mode": str(provider._industry_relative_regime_mode),
                "residual_weight_regime_mode": str(provider._residual_weight_regime_mode),
                "residual_benchmark_weight_fallback": float(provider._residual_benchmark_weight_fallback),
                "residual_industry_weight_fallback": float(provider._residual_industry_weight_fallback),
                "residual_benchmark_weight_effective": float(provider._residual_benchmark_weight_effective[i])
                if provider._residual_benchmark_weight_effective.size
                else float(provider._residual_benchmark_weight),
                "residual_industry_weight_effective": float(provider._residual_industry_weight_effective[i])
                if provider._residual_industry_weight_effective.size
                else float(provider._residual_industry_weight),
                "industry_relative_mode_effective": str(provider._industry_relative_mode_effective[i])
                if provider._industry_relative_mode_effective.size
                else str(provider._industry_relative_mode),
                "residual_window_configured": int(provider._residual_window),
                "residual_window_effective": int(provider._residual_window_effective[i]) if provider._residual_window_effective.size else int(provider._residual_window),
                "residual_window_regime_mode": str(provider._residual_window_regime_mode),
                "residual_window_fallback": int(provider._residual_window_fallback),
                "residual_window_regime_fast_ma": int(provider._residual_window_regime_fast_ma),
                "residual_window_regime_slow_ma": int(provider._residual_window_regime_slow_ma),
                "residual_window_conditional_active": bool(
                    provider._residual_window_regime_mode == "strong_risk_on"
                    and bool(provider._strong_risk_on[i])
                    and int(provider._residual_window_fallback) != int(provider._residual_window)
                ),
                "residual_weight_conditional_active": bool(
                    provider._residual_weight_regime_mode == "strong_risk_on"
                    and bool(provider._strong_risk_on[i])
                    and (
                        abs(float(provider._residual_benchmark_weight_fallback) - float(provider._residual_benchmark_weight)) > 1e-12
                        or abs(float(provider._residual_industry_weight_fallback) - float(provider._residual_industry_weight)) > 1e-12
                    )
                ),
                "industry_relative_conditional_active": bool(
                    provider._industry_relative_regime_mode == "strong_risk_on"
                    and bool(provider._strong_risk_on[i])
                    and str(provider._industry_relative_mode) != "sector_proxy"
                ),
                "sector_strength_score": sector_score,
                "volume_price_quality_score": quality_score,
                "final_score": final_score,
                "trend_quality_soft_score_enabled": bool(
                    getattr(provider, "_trend_quality_soft_score_enabled", False)
                ),
                "trend_quality_soft_score_weight": float(
                    getattr(provider, "_trend_quality_soft_score_weight", 0.0) or 0.0
                ),
                "trend_quality_soft_score": trend_quality_soft_score,
                "trend_quality_r2_60_rank": trend_quality_r2_60_rank,
                "trend_quality_slope60_rank": trend_quality_slope60_rank,
                "trend_quality_ret60_vol_adj_rank": trend_quality_ret60_vol_adj_rank,
                "trend_quality_ret60_dd_adj_rank": trend_quality_ret60_dd_adj_rank,
                "risk_archetype_soft_deprioritize_enabled": bool(
                    getattr(provider, "_risk_archetype_soft_deprioritize_enabled", False)
                ),
                "risk_archetype_soft_deprioritize_quantile": float(
                    getattr(provider, "_risk_archetype_soft_deprioritize_quantile", 0.80) or 0.80
                ),
                "risk_archetype_original_final_score": risk_archetype_original_final_score,
                "risk_archetype_score_scale": risk_archetype_score_scale,
                "risk_archetype_hot_crowded": bool(risk_archetype_hot_crowded),
                "risk_archetype_high_volatility_chase": bool(risk_archetype_high_volatility_chase),
                "risk_archetype_flag_count": int(risk_archetype_flag_count),
                "risk_archetype_pre_ret20_rank": risk_archetype_pre_ret20_rank,
                "risk_archetype_dist_ma60_rank": risk_archetype_dist_ma60_rank,
                "risk_archetype_vol60_rank": risk_archetype_vol60_rank,
                "risk_archetype_turnover20_rank": risk_archetype_turnover20_rank,
                "risk_archetype_fade_rank": risk_archetype_fade_rank,
                "risk_archetype_open_gap_rank": risk_archetype_open_gap_rank,
                **entry_risk_position_payload,
                "moneyflow_overlay_score": overlay_score_map.get(sym),
                "moneyflow_overlay_gate_on": bool(overlay_snapshot.gate_on),
                "moneyflow_overlay_mode": str(overlay_snapshot.mode or "off"),
                "moneyflow_overlay_observation_date": (
                    overlay_snapshot.observation_date.isoformat()
                    if isinstance(overlay_snapshot.observation_date, date)
                    else ""
                ),
                "moneyflow_overlay_score_source": str(overlay_snapshot.score_source or ""),
                "source_aware_residual_mode": str(provider._source_aware_residual_mode),
                "residual_refine_mode": str(provider._residual_refine_mode),
                "residual_refine_weight": float(provider._residual_refine_weight),
                "conditional_tiebreak_score": conditional_tiebreak_score,
                "conditional_factor_leader_score": conditional_factor_leader_score,
                "conditional_institution_proxy_score": conditional_institution_proxy_score,
                "conditional_crowding_score": conditional_crowding_score,
                "conditional_recent_limit_hit_3d": bool(provider._conditional_recent_limit_hit_3d[i, c]) if provider._conditional_recent_limit_hit_3d.size else False,
                "conditional_near_limit_up": bool(provider._conditional_near_limit_up[i, c]) if provider._conditional_near_limit_up.size else False,
                **(
                    {
                        "industry_second_stage_min_industry_score": float(provider._industry_second_stage_min_industry_score),
                        "industry_second_stage_score": industry_second_stage_score,
                        "industry_second_stage_not_hot_score": industry_second_stage_not_hot_score,
                        "industry_second_stage_uncrowded_score": industry_second_stage_uncrowded_score,
                        "industry_second_stage_breadth_timing_score": industry_second_stage_breadth_timing_score,
                        "industry_second_stage_persistence_10d": industry_second_stage_persistence_10d,
                        "industry_second_stage_active": bool(industry_second_stage_active),
                    }
                    if include_industry_second_stage_meta
                    else {}
                ),
                "leadership_route_score": leadership_route_score,
                "leadership_route_rank": leadership_route_rank,
                "leadership_route_bucket": leadership_route_bucket,
                "leadership_route_bucket_count": int(provider._leadership_route_bucket_count),
                "breakout_window_main": int(provider._breakout_window),
                "high_max_main_prev": hmax_prev_main,
                "breakout_window_short": int(provider._breakout_window_short),
                "breakout_window_long": int(provider._breakout_window_long),
                "dual_breakout_mode": str(provider._dual_breakout_mode),
                "dual_breakout_gate_ma_window": int(provider._dual_breakout_gate_ma_window),
                "dual_breakout_gate_slope_lookback": int(provider._dual_breakout_gate_slope_lookback),
                "breakout_entry_buffer_pct": float(provider._breakout_entry_buffer_pct),
                "entry_confirm_mode": str(provider._entry_confirm_mode),
                "entry_delay_mode": str(provider._entry_delay_mode),
                "entry_above_slow_ma": bool(provider._entry_above_slow_ma[i, c]),
                "slow_ma_slope_pos": bool(provider._entry_slow_ma_slope_pos[i, c]),
                "high_max_short_prev": hmax_prev_short,
                "high_max_long_prev": hmax_prev_long,
                "entry_breakout_floor_raw": entry_breakout_floor_raw,
                "breakout_hit_short": hit_short,
                "breakout_hit_long": hit_long,
                "slow_gate_ok": bool(provider._dual_breakout_slow_gate_ok[i, c]) if provider._dual_breakout_slow_gate_ok.size else True,
                "v2_trend_ok": bool(provider._v2_trend_ok[i, c]),
                "regime_on": bool(provider._risk_on[i]),
                "strong_risk_on": bool(provider._strong_risk_on[i]),
                **high_chase_a2_feature_meta,
                **hot_amount_turnover_feature_meta,
                **restore_buy_meta,
            },
        ))

    return DaySignals(
        sell_signals=sell_sigs,
        buy_signals=buy_sigs,
        exit_syms=exit_syms,
        strength_map=strength_map,
        mf_score_map=mf_score_map,
        mf_gate_on_today=False,
        overlay_score_map=overlay_score_map,
        overlay_gate_on_today=bool(overlay_snapshot.gate_on),
        overlay_mode=str(overlay_snapshot.mode or "off"),
        overlay_band_limit=int(getattr(overlay_snapshot, "band_limit", 0) or 0),
        overlay_observation_date=overlay_snapshot.observation_date,
        overlay_score_source=str(overlay_snapshot.score_source or ""),
        strong_risk_on=bool(provider._strong_risk_on[i]) if provider._strong_risk_on.size else False,
        exit_counts=exit_counts,
        diagnostics={
            "raw_buy_signal_count": int(len(day_cands)),
            "buy_candidate_count": int(len(day_cands)),
            "after_held_filter_count": int(len(buy_sigs)),
            "breakout_candidates": int(max(breakout_count - overlap_count, 0)),
            "pullback_candidates": int(pullback_count),
            "pullback_overlap_candidates": int(overlap_count),
            "pullback_total_candidates": int(pullback_count + overlap_count),
            "buy_signals_generated": int(len(buy_sigs)),
            "risk_archetype_soft_deprioritize_enabled": bool(
                getattr(provider, "_risk_archetype_soft_deprioritize_enabled", False)
            ),
            "risk_archetype_soft_deprioritize_count": int(
                getattr(provider, "risk_archetype_soft_deprioritize_count", 0) or 0
            ),
            "risk_archetype_hot_crowded_count": int(
                getattr(provider, "risk_archetype_hot_crowded_count", 0) or 0
            ),
            "risk_archetype_high_volatility_chase_count": int(
                getattr(provider, "risk_archetype_high_volatility_chase_count", 0) or 0
            ),
            "bull_breakout_quality_veto_applied": bool(bull_breakout_quality_veto_applied),
            "bull_breakout_quality_veto_block_count": int(bull_breakout_quality_veto_block_count),
            "bull_breakout_quality_veto_residual_block_count": int(bull_breakout_quality_veto_residual_block_count),
            "bull_breakout_quality_veto_margin_block_count": int(bull_breakout_quality_veto_margin_block_count),
            "strong_risk_on_today": bool(provider._strong_risk_on[i]) if provider._strong_risk_on.size else False,
            "residual_window_effective": int(provider._residual_window_effective[i]) if provider._residual_window_effective.size else int(provider._residual_window),
            "residual_benchmark_weight_effective": float(provider._residual_benchmark_weight_effective[i])
            if provider._residual_benchmark_weight_effective.size
            else float(provider._residual_benchmark_weight),
            "residual_industry_weight_effective": float(provider._residual_industry_weight_effective[i])
            if provider._residual_industry_weight_effective.size
            else float(provider._residual_industry_weight),
            "residual_window_regime_fast_ma": int(provider._residual_window_regime_fast_ma),
            "residual_window_regime_slow_ma": int(provider._residual_window_regime_slow_ma),
            "moneyflow_overlay_enabled": bool(overlay_snapshot.enabled),
            "moneyflow_overlay_gate_on": bool(overlay_snapshot.gate_on),
            "moneyflow_overlay_mode": str(overlay_snapshot.mode or "off"),
            "moneyflow_overlay_band_limit": int(getattr(overlay_snapshot, "band_limit", 0) or 0),
            "moneyflow_overlay_observation_date": (
                overlay_snapshot.observation_date.isoformat()
                if isinstance(overlay_snapshot.observation_date, date)
                else ""
            ),
            "moneyflow_overlay_gate_status": str(overlay_snapshot.gate_status or ""),
            "moneyflow_overlay_gate_reason": str(overlay_snapshot.gate_reason or ""),
            "moneyflow_overlay_score_source": str(overlay_snapshot.score_source or ""),
            **dict(fragility_diagnostics or {}),
        },
    )
