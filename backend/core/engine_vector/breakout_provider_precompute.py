"""Breakout provider precompute helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.core.engine_vector import breakout_support as _breakout_support
from backend.core.engine_vector.breakout_support import (
    build_industry_assignment_matrices as _build_industry_assignment_matrices,
    rolling_max_matrix as _rolling_max_matrix,
    rolling_min_matrix as _rolling_min_matrix,
    row_bucket_code as _row_bucket_code,
    row_rank_pct as _row_rank_pct,
    weighted_score as _weighted_score,
)
from backend.core.engine_vector.candidate_index import build_daily_candidate_index


_compute_conditional_tiebreak_matrices = _breakout_support._compute_conditional_tiebreak_matrices
_compute_industry_second_stage_matrices = _breakout_support._compute_industry_second_stage_matrices
_compute_residual_ranking_matrices = _breakout_support._compute_residual_ranking_matrices


def finalize_breakout_provider_precompute(
    provider: Any,
    *,
    raw_history: pd.DataFrame | None,
    mx: Any,
    sector_data: dict[str, Any] | None,
    industry_map: dict[str, Any] | None,
    industry_history: pd.DataFrame | None,
) -> None:
    t, n = mx.close.shape
    feats = provider._feats
    enable_v2_trend_filter = bool(provider._enable_v2_trend_filter)
    (
        provider._residual_strength_raw,
        provider._residual_strength_score,
        provider._residual_vs_bench_raw,
        provider._residual_vs_sector_raw,
        sector_ret_short,
        sector_ret_long,
        sector_trend,
        provider._sector_proxy_residual_raw,
        provider._industry_median_excess_raw,
        provider._sector_beta_tailwind_raw,
    ) = _compute_residual_ranking_matrices(
        close=mx.close,
        bench_close=provider._bench_close,
        tradable=mx.tradable,
        residual_window=int(provider._residual_window),
        residual_benchmark_weight=float(provider._residual_benchmark_weight),
        residual_industry_weight=float(provider._residual_industry_weight),
        sector_data=sector_data if isinstance(sector_data, dict) else None,
        industry_map=industry_map if isinstance(industry_map, dict) else None,
        industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
        symbols=mx.symbols,
        dates=mx.dates,
        sector_strength_window_short=int(provider._sector_strength_window_short),
        sector_strength_window_long=int(provider._sector_strength_window_long),
        industry_relative_mode=str(provider._industry_relative_mode),
    )
    provider._residual_window_effective = np.full(t, int(provider._residual_window), dtype=int)
    provider._residual_benchmark_weight_effective = np.full(
        t,
        float(provider._residual_benchmark_weight),
        dtype=float,
    )
    provider._residual_industry_weight_effective = np.full(
        t,
        float(provider._residual_industry_weight),
        dtype=float,
    )
    provider._industry_relative_mode_effective = np.full(t, str(provider._industry_relative_mode), dtype=object)
    fallback_window = int(provider._residual_window)
    if provider._residual_window_regime_mode == "strong_risk_on":
        fallback_window = int(provider._residual_window_fallback)
    fallback_benchmark_weight = float(provider._residual_benchmark_weight)
    fallback_industry_weight = float(provider._residual_industry_weight)
    if provider._residual_weight_regime_mode == "strong_risk_on":
        fallback_benchmark_weight = float(provider._residual_benchmark_weight_fallback)
        fallback_industry_weight = float(provider._residual_industry_weight_fallback)
    fallback_industry_relative_mode = str(provider._industry_relative_mode)
    if provider._industry_relative_regime_mode == "strong_risk_on":
        fallback_industry_relative_mode = "sector_proxy"
    fallback_window_changed = fallback_window != int(provider._residual_window)
    fallback_weight_changed = (
        abs(fallback_benchmark_weight - float(provider._residual_benchmark_weight)) > 1e-12
        or abs(fallback_industry_weight - float(provider._residual_industry_weight)) > 1e-12
    )
    fallback_industry_mode_changed = fallback_industry_relative_mode != str(provider._industry_relative_mode)
    if provider._enable_residual_ranking and (
        fallback_window_changed or fallback_weight_changed or fallback_industry_mode_changed
    ):
        (
            fallback_raw,
            fallback_score,
            fallback_vs_bench_raw,
            fallback_vs_sector_raw,
            _,
            _,
            _,
            fallback_sector_proxy_raw,
            fallback_industry_median_excess_raw,
            fallback_sector_beta_tailwind_raw,
        ) = _compute_residual_ranking_matrices(
            close=mx.close,
            bench_close=provider._bench_close,
            tradable=mx.tradable,
            residual_window=int(fallback_window),
            residual_benchmark_weight=float(fallback_benchmark_weight),
            residual_industry_weight=float(fallback_industry_weight),
            sector_data=sector_data if isinstance(sector_data, dict) else None,
            industry_map=industry_map if isinstance(industry_map, dict) else None,
            industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
            symbols=mx.symbols,
            dates=mx.dates,
            sector_strength_window_short=int(provider._sector_strength_window_short),
            sector_strength_window_long=int(provider._sector_strength_window_long),
            industry_relative_mode=str(fallback_industry_relative_mode),
        )
        fallback_mask = ~provider._strong_risk_on
        if bool(np.any(fallback_mask)):
            provider._residual_strength_raw[fallback_mask, :] = fallback_raw[fallback_mask, :]
            provider._residual_strength_score[fallback_mask, :] = fallback_score[fallback_mask, :]
            provider._residual_vs_bench_raw[fallback_mask, :] = fallback_vs_bench_raw[fallback_mask, :]
            provider._residual_vs_sector_raw[fallback_mask, :] = fallback_vs_sector_raw[fallback_mask, :]
            provider._sector_proxy_residual_raw[fallback_mask, :] = fallback_sector_proxy_raw[fallback_mask, :]
            provider._industry_median_excess_raw[fallback_mask, :] = fallback_industry_median_excess_raw[fallback_mask, :]
            provider._sector_beta_tailwind_raw[fallback_mask, :] = fallback_sector_beta_tailwind_raw[fallback_mask, :]
            provider._residual_window_effective[fallback_mask] = int(fallback_window)
            provider._residual_benchmark_weight_effective[fallback_mask] = float(fallback_benchmark_weight)
            provider._residual_industry_weight_effective[fallback_mask] = float(fallback_industry_weight)
            provider._industry_relative_mode_effective[fallback_mask] = str(fallback_industry_relative_mode)

    sector_short_rank = _row_rank_pct(sector_ret_short, mx.tradable)
    sector_long_rank = _row_rank_pct(sector_ret_long, mx.tradable)
    provider._sector_strength_score = _weighted_score(
        [(sector_short_rank, 0.4), (sector_long_rank, 0.4), (sector_trend, 0.2)],
        shape=(t, n),
    )

    vol_window = max(5, int(provider._volume_quality_window))
    vol_ma = pd.DataFrame(mx.volume).rolling(vol_window, min_periods=vol_window).mean().to_numpy(dtype=float)
    vol_ratio = np.full((t, n), np.nan, dtype=float)
    valid_vol = ~np.isnan(mx.volume) & ~np.isnan(vol_ma) & (vol_ma > 1e-8)
    vol_ratio[valid_vol] = mx.volume[valid_vol] / vol_ma[valid_vol]
    vol_quality_raw = np.full((t, n), np.nan, dtype=float)
    valid_vr = ~np.isnan(vol_ratio) & (vol_ratio > 1e-8)
    vol_quality_raw[valid_vr] = -np.abs(np.log(vol_ratio[valid_vr] / 1.2))
    atr_pct = np.full((t, n), np.nan, dtype=float)
    valid_atr_pct = ~np.isnan(feats.atr14) & ~np.isnan(mx.close) & (mx.close > 1e-8)
    atr_pct[valid_atr_pct] = feats.atr14[valid_atr_pct] / mx.close[valid_atr_pct]
    range_high = _rolling_max_matrix(mx.high, vol_window)
    range_low = _rolling_min_matrix(mx.low, vol_window)
    range_pct = np.full((t, n), np.nan, dtype=float)
    valid_range = ~np.isnan(range_high) & ~np.isnan(range_low) & ~np.isnan(mx.close) & (mx.close > 1e-8)
    range_pct[valid_range] = (range_high[valid_range] - range_low[valid_range]) / mx.close[valid_range]
    quality_raw = _weighted_score(
        [(vol_quality_raw, 0.5), (-atr_pct, 0.3), (-range_pct, 0.2)],
        shape=(t, n),
    )
    provider._volume_price_quality_score = _row_rank_pct(quality_raw, mx.tradable)

    risk_on_m = np.repeat(provider._risk_on.reshape(-1, 1), n, axis=1)
    common_gate = risk_on_m & mx.tradable & provider._momentum_ok
    provider._breakout_buy = provider._entry_delay_ok & provider._entry_confirm_ok & provider._v2_trend_ok & common_gate
    pullback_gate = provider._entry_confirm_ok & common_gate
    if enable_v2_trend_filter:
        pullback_gate = pullback_gate & provider._v2_trend_ok
    provider._pullback_raw_selected = provider._pullback_raw_selected & pullback_gate
    provider._pullback_overlap = provider._pullback_raw_selected & provider._breakout_buy
    provider._pullback_buy = provider._pullback_raw_selected & ~provider._breakout_buy
    provider._breakout_margin_score = np.full((t, n), np.nan, dtype=float)
    breakout_margin_mask = provider._breakout_buy | provider._pullback_overlap
    if bool(np.any(breakout_margin_mask)):
        breakout_margin_input = np.where(breakout_margin_mask, provider._breakout_margin_raw, np.nan)
        provider._breakout_margin_score = _row_rank_pct(breakout_margin_input, breakout_margin_mask)

    provider._breakout_quality_score = np.full((t, n), np.nan, dtype=float)
    provider._breakout_quality_pass = np.ones((t, n), dtype=bool)
    if bool(np.any(breakout_margin_mask)):
        margin_cap = max(1e-8, float(provider._breakout_quality_margin_cap_pct))
        fade_cap = max(1e-8, float(provider._breakout_quality_fade_cap_pct))
        gap_cap = max(1e-8, float(provider._breakout_quality_open_gap_cap_pct))

        margin_quality_raw = np.full((t, n), np.nan, dtype=float)
        valid_margin_quality = breakout_margin_mask & ~np.isnan(provider._breakout_margin_raw)
        margin_quality_raw[valid_margin_quality] = np.clip(
            1.0 - (provider._breakout_margin_raw[valid_margin_quality] / margin_cap),
            0.0,
            1.0,
        )

        fade_quality_raw = np.full((t, n), np.nan, dtype=float)
        valid_fade_quality = breakout_margin_mask & ~np.isnan(provider._breakout_fade_raw)
        fade_quality_raw[valid_fade_quality] = np.clip(
            1.0 - (provider._breakout_fade_raw[valid_fade_quality] / fade_cap),
            0.0,
            1.0,
        )

        gap_quality_raw = np.full((t, n), np.nan, dtype=float)
        valid_gap_quality = breakout_margin_mask & ~np.isnan(provider._breakout_open_gap_raw)
        gap_quality_raw[valid_gap_quality] = np.clip(
            1.0 - (provider._breakout_open_gap_raw[valid_gap_quality] / gap_cap),
            0.0,
            1.0,
        )

        vp_quality_input = np.where(breakout_margin_mask, provider._volume_price_quality_score, np.nan)
        provider._breakout_quality_score = _weighted_score(
            [
                (margin_quality_raw, 0.35),
                (fade_quality_raw, 0.25),
                (gap_quality_raw, 0.20),
                (vp_quality_input, 0.20),
            ],
            shape=(t, n),
        )
        if provider._ranking_mode == "quality_then_residual":
            gate_floor = min(1.0, max(0.0, float(provider._breakout_quality_gate_min_score)))
            quality_gate_pass = breakout_margin_mask & ~np.isnan(provider._breakout_quality_score) & (
                provider._breakout_quality_score >= gate_floor
            )
            provider._breakout_quality_pass = np.where(breakout_margin_mask, quality_gate_pass, True)

    residual_component = provider._residual_strength_score
    (
        provider._conditional_tiebreak_score,
        provider._conditional_factor_leader_score,
        provider._conditional_institution_proxy_score,
        provider._conditional_crowding_score,
        provider._conditional_recent_limit_hit_3d,
        provider._conditional_near_limit_up,
    ) = _compute_conditional_tiebreak_matrices(
        raw_history=raw_history,
        dates=mx.dates,
        symbols=mx.symbols,
        tradable=mx.tradable,
        adj_close=mx.close,
        breakout_quality_score=provider._breakout_quality_score,
    )
    provider._industry_second_stage_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_not_hot_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_uncrowded_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_breadth_timing_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_persistence_10d = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_active = np.zeros((t, n), dtype=bool)
    if (
        provider._enable_residual_ranking
        and provider._residual_refine_mode in {"industry_second_stage", "industry_second_stage_tiebreak"}
        and (
            provider._residual_refine_mode == "industry_second_stage_tiebreak"
            or provider._residual_refine_weight > 1e-12
        )
    ):
        industry_name_matrix, _ = _build_industry_assignment_matrices(
            industry_map=industry_map if isinstance(industry_map, dict) else None,
            industry_history=industry_history if isinstance(industry_history, pd.DataFrame) else None,
            sector_data=sector_data if isinstance(sector_data, dict) else None,
            symbols=mx.symbols,
            dates=mx.dates,
        )
        (
            provider._industry_second_stage_score,
            provider._industry_second_stage_not_hot_score,
            provider._industry_second_stage_uncrowded_score,
            provider._industry_second_stage_breadth_timing_score,
            provider._industry_second_stage_persistence_10d,
        ) = _compute_industry_second_stage_matrices(
            tradable=mx.tradable,
            adj_close=mx.close,
            industry_map=industry_map if isinstance(industry_map, dict) else None,
            industry_name_matrix=industry_name_matrix,
            symbols=mx.symbols,
            breakout_margin_raw=provider._breakout_margin_raw,
            breakout_quality_score=provider._breakout_quality_score,
            recent_limit_hit_3d=provider._conditional_recent_limit_hit_3d,
            near_limit_up=provider._conditional_near_limit_up,
        )
        min_industry_score = min(1.0, max(0.0, float(provider._industry_second_stage_min_industry_score)))
        provider._industry_second_stage_active = (
            mx.tradable
            & ~np.isnan(provider._residual_strength_score)
            & (provider._residual_strength_score >= min_industry_score)
        )
    provider._leadership_route_score = _weighted_score(
        [
            (provider._conditional_factor_leader_score, 0.5),
            (provider._conditional_institution_proxy_score, 0.5),
        ],
        shape=(t, n),
    )
    provider._leadership_route_score = np.where(np.isnan(provider._leadership_route_score), 0.5, provider._leadership_route_score)
    (
        provider._leadership_route_rank,
        provider._leadership_route_bucket,
    ) = _row_bucket_code(
        provider._leadership_route_score,
        mx.tradable & ~np.isnan(provider._leadership_route_score),
        int(provider._leadership_route_bucket_count),
    )
    if (
        provider._enable_residual_ranking
        and provider._residual_refine_mode == "breakout_margin"
        and provider._residual_refine_weight > 1e-12
    ):
        residual_component = _weighted_score(
            [
                (provider._residual_strength_score, 1.0),
                (provider._breakout_margin_score, float(provider._residual_refine_weight)),
            ],
            shape=(t, n),
        )
    elif (
        provider._enable_residual_ranking
        and provider._residual_refine_mode == "conditional_tiebreak"
        and provider._residual_refine_weight > 1e-12
    ):
        residual_component = _weighted_score(
            [
                (provider._residual_strength_score, 1.0),
                (provider._conditional_tiebreak_score, float(provider._residual_refine_weight)),
            ],
            shape=(t, n),
        )
    elif (
        provider._enable_residual_ranking
        and provider._residual_refine_mode == "industry_second_stage"
        and provider._residual_refine_weight > 1e-12
    ):
        second_stage_effective = np.where(
            provider._industry_second_stage_active,
            provider._industry_second_stage_score,
            np.nan,
        )
        residual_component = _weighted_score(
            [
                (provider._residual_strength_score, 1.0),
                (second_stage_effective, float(provider._residual_refine_weight)),
            ],
            shape=(t, n),
        )

    if provider._enable_residual_ranking or provider._enable_sector_quality_ranking:
        score_components: list[tuple[np.ndarray, float]] = []
        if provider._enable_residual_ranking:
            score_components.append((residual_component, float(provider._residual_weight)))
        if provider._enable_sector_quality_ranking:
            score_components.append((provider._sector_strength_score, float(provider._sector_weight)))
            score_components.append((provider._volume_price_quality_score, float(provider._quality_weight)))
        provider._final_score = _weighted_score(score_components, shape=(t, n))
    else:
        provider._final_score = np.full((t, n), 0.5, dtype=float)
    if provider._ranking_mode == "quality_then_residual" and provider._enable_residual_ranking:
        provider._final_score = np.where(provider._breakout_quality_pass, provider._residual_strength_score, np.nan)
    if provider._ranking_mode == "leadership_then_residual" and provider._enable_residual_ranking:
        residual_safe = np.where(np.isnan(provider._residual_strength_score), 0.5, provider._residual_strength_score)
        route_width = 1.0 / float(max(int(provider._leadership_route_bucket_count), 1))
        bucket_base = np.where(
            provider._leadership_route_bucket >= 0,
            provider._leadership_route_bucket.astype(float) * route_width,
            np.nan,
        )
        provider._final_score = bucket_base + residual_safe * (route_width * 0.999)
    if provider._source_aware_residual_mode in {"pullback_only", "pullback_only_rank"} and provider._enable_residual_ranking:
        residual_safe = np.where(np.isnan(provider._residual_strength_score), 0.5, provider._residual_strength_score)
        breakout_only = provider._breakout_buy & ~provider._pullback_overlap
        provider._final_score[breakout_only] = 2.0
        provider._final_score[provider._pullback_overlap] = 2.1
        provider._final_score[provider._pullback_buy] = residual_safe[provider._pullback_buy]
    buy_base = provider._breakout_buy | provider._pullback_buy
    if provider._ranking_mode == "quality_then_residual":
        breakout_quality_scope = provider._breakout_buy | provider._pullback_overlap
        buy_base = (buy_base & ~breakout_quality_scope) | (
            buy_base & breakout_quality_scope & provider._breakout_quality_pass
        )
    provider._cand_idx = build_daily_candidate_index(buy_base)
    provider._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}

