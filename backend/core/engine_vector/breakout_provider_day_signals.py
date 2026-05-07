"""Breakout provider day-signal helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from backend.core.core.models import Signal
from backend.core.core.types import Side
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

    # ------------------------------------------------------------------
    # day_signals
    # ------------------------------------------------------------------



def build_breakout_day_signals(provider: Any, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
    i = day_idx
    mx = provider._mx
    feats = provider._feats
    positions = ctx.positions
    position_avg_cost = ctx.position_avg_cost
    close_idx = ctx.close_idx
    nav = ctx.nav
    max_positions = ctx.max_positions
    base_order_value = ctx.base_order_value
    n = mx.close.shape[1]
    overlay_snapshot = resolve_moneyflow_overlay_snapshot(getattr(ctx, "asset_context", {}), day=day)
    overlay_score_map = {
        str(symbol).lower(): float(score)
        for symbol, score in dict(overlay_snapshot.score_map or {}).items()
    }

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
        final_score_held = (
            float(provider._final_score[i, col])
            if provider._final_score.size and not np.isnan(provider._final_score[i, col])
            else None
        )
        residual_score_held = (
            float(provider._residual_strength_score[i, col])
            if provider._residual_strength_score.size and not np.isnan(provider._residual_strength_score[i, col])
            else None
        )
        if final_score_held is not None:
            mf_score_map[sym] = float(final_score_held)
        if residual_score_held is not None or final_score_held is not None:
            strength_map[sym] = float(residual_score_held if residual_score_held is not None else final_score_held)

    for c in day_cands:
        sym = mx.symbols[int(c)]
        # 已持有跳过
        if sym in positions and int(positions[sym]) > 0:
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
        residual_score = float(provider._residual_strength_score[i, c]) if provider._residual_strength_score.size and not np.isnan(provider._residual_strength_score[i, c]) else None
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
        final_score = float(provider._final_score[i, c]) if provider._final_score.size and not np.isnan(provider._final_score[i, c]) else 0.5
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

        buy_sigs.append(Signal(
            signal_date=day,
            symbol=sym,
            side=Side.BUY,
            qty=provider._order_size,
            reason=reason,
            reason_code=reason_code,
            meta={
                "owner_system": "cn_stock_trend_alpha_core",
                "formal_reason_codes": [str(reason_code or reason or "BUY")],
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
