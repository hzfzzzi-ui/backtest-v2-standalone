"""Breakout provider precompute helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.core.engine_vector import breakout_support as _breakout_support
from backend.core.engine_vector.breakout_support import (
    build_industry_assignment_matrices as _build_industry_assignment_matrices,
    return_matrix as _return_matrix,
    rolling_log_trend_r2_matrix as _rolling_log_trend_r2_matrix,
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


def _runtime_optimization_section(provider: Any, key: str) -> dict[str, Any]:
    raw_root = getattr(provider, "_runtime_optimization", {})
    if not isinstance(raw_root, dict):
        return {}
    raw = raw_root.get(key)
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _active_set_sparse_scoring_enabled(provider: Any) -> bool:
    cfg = _runtime_optimization_section(provider, "active_set_sparse_scoring")
    return bool(cfg.get("enabled", False))


def _rolling_log_trend_slope_matrix(values: np.ndarray, window: int) -> np.ndarray:
    shape = values.shape
    out = np.full(shape, np.nan, dtype=float)
    w = int(window)
    if w < 3 or shape[0] < w:
        return out

    safe_values = np.where(values > 1e-8, values, np.nan)
    y = np.log(safe_values)
    row_idx = np.arange(shape[0], dtype=float).reshape(-1, 1)
    jy = y * row_idx

    sum_y = pd.DataFrame(y).rolling(w, min_periods=w).sum().to_numpy(dtype=float)
    sum_jy = pd.DataFrame(jy).rolling(w, min_periods=w).sum().to_numpy(dtype=float)

    local_x_sum = float(w * (w - 1) / 2.0)
    local_x2_sum = float(w * (w - 1) * (2 * w - 1) / 6.0)
    ss_x = local_x2_sum - (local_x_sum * local_x_sum / float(w))
    window_start = (np.arange(shape[0], dtype=float) - float(w - 1)).reshape(-1, 1)
    sum_xy = sum_jy - window_start * sum_y
    cov_xy = sum_xy - (local_x_sum * sum_y / float(w))

    valid = np.isfinite(cov_xy) & (ss_x > 1e-16)
    out[valid] = cov_xy[valid] / ss_x
    return out


def _apply_trend_quality_soft_score(provider: Any, *, mx: Any, buy_base: np.ndarray) -> None:
    shape = mx.close.shape
    provider._trend_quality_soft_score = np.full(shape, np.nan, dtype=float)
    provider._trend_quality_r2_60_rank = np.full(shape, np.nan, dtype=float)
    provider._trend_quality_slope60_rank = np.full(shape, np.nan, dtype=float)
    provider._trend_quality_ret60_vol_adj_rank = np.full(shape, np.nan, dtype=float)
    provider._trend_quality_ret60_dd_adj_rank = np.full(shape, np.nan, dtype=float)
    if not bool(getattr(provider, "_trend_quality_soft_score_enabled", False)):
        provider._wide_runtime_optimization_notes.append("skip_trend_quality_soft_score")
        return
    if not bool(np.any(buy_base)):
        provider._wide_runtime_optimization_notes.append("skip_trend_quality_soft_score:no_buy_base")
        return

    close = mx.close
    candidate_mask = buy_base & mx.tradable
    r2_60 = _rolling_log_trend_r2_matrix(close, 60)
    slope60 = _rolling_log_trend_slope_matrix(close, 60)
    ret60 = _return_matrix(close, 60)
    ret1 = _return_matrix(close, 1)
    vol60 = pd.DataFrame(ret1).rolling(60, min_periods=60).std().to_numpy(dtype=float)
    ret60_vol_adj = np.full(shape, np.nan, dtype=float)
    valid_vol = np.isfinite(ret60) & np.isfinite(vol60) & (vol60 > 1e-8)
    ret60_vol_adj[valid_vol] = ret60[valid_vol] / vol60[valid_vol]

    high60 = _rolling_max_matrix(close, 60)
    drawdown_from_high60 = np.full(shape, np.nan, dtype=float)
    valid_high = np.isfinite(close) & np.isfinite(high60) & (high60 > 1e-8)
    drawdown_from_high60[valid_high] = close[valid_high] / high60[valid_high] - 1.0
    ret60_dd_adj = np.full(shape, np.nan, dtype=float)
    valid_dd = np.isfinite(ret60) & np.isfinite(drawdown_from_high60)
    dd_den = np.maximum(np.abs(drawdown_from_high60[valid_dd]), 0.01)
    ret60_dd_adj[valid_dd] = ret60[valid_dd] / dd_den

    provider._trend_quality_r2_60_rank = _row_rank_pct(r2_60, candidate_mask)
    provider._trend_quality_slope60_rank = _row_rank_pct(slope60, candidate_mask)
    provider._trend_quality_ret60_vol_adj_rank = _row_rank_pct(ret60_vol_adj, candidate_mask)
    provider._trend_quality_ret60_dd_adj_rank = _row_rank_pct(ret60_dd_adj, candidate_mask)
    provider._trend_quality_soft_score = _weighted_score(
        [
            (provider._trend_quality_r2_60_rank, float(provider._trend_quality_r2_60_weight)),
            (provider._trend_quality_slope60_rank, float(provider._trend_quality_slope60_weight)),
            (provider._trend_quality_ret60_vol_adj_rank, float(provider._trend_quality_ret60_vol_adj_weight)),
            (provider._trend_quality_ret60_dd_adj_rank, float(provider._trend_quality_ret60_dd_adj_weight)),
        ],
        shape=shape,
    )

    final_score = getattr(provider, "_final_score", np.array([]))
    if not getattr(final_score, "size", 0):
        provider._wide_runtime_optimization_notes.append("skip_trend_quality_soft_score:no_final_score")
        return
    blend_weight = min(1.0, max(0.0, float(getattr(provider, "_trend_quality_soft_score_weight", 0.30))))
    if blend_weight <= 1e-12:
        provider._wide_runtime_optimization_notes.append("skip_trend_quality_soft_score:zero_weight")
        return
    valid_blend = np.isfinite(final_score) & np.isfinite(provider._trend_quality_soft_score)
    blended = np.array(final_score, copy=True)
    blended[valid_blend] = (
        blended[valid_blend] * (1.0 - blend_weight)
        + provider._trend_quality_soft_score[valid_blend] * blend_weight
    )
    provider._final_score = blended
    provider._wide_runtime_optimization_notes.append("apply_trend_quality_soft_score")


def _apply_risk_archetype_soft_deprioritize(
    provider: Any,
    *,
    raw_history: pd.DataFrame | None,
    mx: Any,
    buy_base: np.ndarray,
) -> None:
    shape = mx.close.shape
    provider._risk_archetype_score_scale = np.ones(shape, dtype=float)
    provider._risk_archetype_original_final_score = np.array([], dtype=float)
    provider._risk_archetype_pre_ret20_rank = np.full(shape, np.nan, dtype=float)
    provider._risk_archetype_dist_ma60_rank = np.full(shape, np.nan, dtype=float)
    provider._risk_archetype_vol60_rank = np.full(shape, np.nan, dtype=float)
    provider._risk_archetype_turnover20_rank = np.full(shape, np.nan, dtype=float)
    provider._risk_archetype_fade_rank = np.full(shape, np.nan, dtype=float)
    provider._risk_archetype_open_gap_rank = np.full(shape, np.nan, dtype=float)
    provider._risk_archetype_hot_crowded = np.zeros(shape, dtype=bool)
    provider._risk_archetype_high_volatility_chase = np.zeros(shape, dtype=bool)
    provider._risk_archetype_flag_count = np.zeros(shape, dtype=int)
    provider.risk_archetype_soft_deprioritize_count = 0
    provider.risk_archetype_hot_crowded_count = 0
    provider.risk_archetype_high_volatility_chase_count = 0
    soft_enabled = bool(getattr(provider, "_risk_archetype_soft_deprioritize_enabled", False))
    sizing_enabled = bool(getattr(provider, "_entry_risk_position_sizing_enabled", False))
    if not (soft_enabled or sizing_enabled):
        provider._wide_runtime_optimization_notes.append("skip_risk_archetype_soft_deprioritize")
        return
    if not bool(np.any(buy_base)):
        provider._wide_runtime_optimization_notes.append("skip_risk_archetype_soft_deprioritize:no_buy_base")
        return

    final_score = getattr(provider, "_final_score", np.array([]))
    if soft_enabled and not getattr(final_score, "size", 0):
        provider._wide_runtime_optimization_notes.append("skip_risk_archetype_soft_deprioritize:no_final_score")
        return

    close = mx.close
    candidate_mask = buy_base & mx.tradable
    ret20 = _return_matrix(close, 20)
    ma60 = pd.DataFrame(close).rolling(60, min_periods=60).mean().to_numpy(dtype=float)
    dist_ma60 = np.full(shape, np.nan, dtype=float)
    valid_ma60 = np.isfinite(close) & np.isfinite(ma60) & (ma60 > 1e-8)
    dist_ma60[valid_ma60] = close[valid_ma60] / ma60[valid_ma60] - 1.0
    ret1 = _return_matrix(close, 1)
    vol60 = pd.DataFrame(ret1).rolling(60, min_periods=60).std().to_numpy(dtype=float)

    normalized_history = _breakout_support.normalize_history_like(raw_history)
    turnover_f = _breakout_support.aligned_numeric_matrix(
        normalized_history,
        dates=mx.dates,
        symbols=mx.symbols,
        column="turnover_rate_f",
    )
    turnover = _breakout_support.aligned_numeric_matrix(
        normalized_history,
        dates=mx.dates,
        symbols=mx.symbols,
        column="turnover_rate",
    )
    turnover_input = np.where(np.isfinite(turnover_f), turnover_f, turnover)
    turnover20 = pd.DataFrame(turnover_input).rolling(20, min_periods=20).mean().to_numpy(dtype=float)

    provider._risk_archetype_pre_ret20_rank = _row_rank_pct(ret20, candidate_mask)
    provider._risk_archetype_dist_ma60_rank = _row_rank_pct(dist_ma60, candidate_mask)
    provider._risk_archetype_vol60_rank = _row_rank_pct(vol60, candidate_mask)
    provider._risk_archetype_turnover20_rank = _row_rank_pct(turnover20, candidate_mask)
    provider._risk_archetype_fade_rank = _row_rank_pct(
        getattr(provider, "_breakout_fade_raw", np.full(shape, np.nan, dtype=float)),
        candidate_mask,
    )
    provider._risk_archetype_open_gap_rank = _row_rank_pct(
        getattr(provider, "_breakout_open_gap_raw", np.full(shape, np.nan, dtype=float)),
        candidate_mask,
    )

    q = min(0.99, max(0.50, float(getattr(provider, "_risk_archetype_soft_deprioritize_quantile", 0.80) or 0.80)))
    overheat = provider._risk_archetype_pre_ret20_rank >= q
    overextended = provider._risk_archetype_dist_ma60_rank >= q
    high_vol = provider._risk_archetype_vol60_rank >= q
    crowded = provider._risk_archetype_turnover20_rank >= q
    late = (provider._risk_archetype_fade_rank >= q) | (provider._risk_archetype_open_gap_rank >= q)
    provider._risk_archetype_hot_crowded = candidate_mask & overheat & crowded
    provider._risk_archetype_high_volatility_chase = candidate_mask & high_vol
    provider._risk_archetype_flag_count = (
        overheat.astype(int)
        + overextended.astype(int)
        + high_vol.astype(int)
        + crowded.astype(int)
        + late.astype(int)
    )

    hot_penalty = min(0.80, max(0.0, float(getattr(provider, "_risk_archetype_hot_crowded_penalty", 0.20) or 0.0)))
    high_vol_penalty = min(
        0.80,
        max(0.0, float(getattr(provider, "_risk_archetype_high_volatility_penalty", 0.15) or 0.0)),
    )
    scale = np.ones(shape, dtype=float)
    scale[provider._risk_archetype_hot_crowded] *= 1.0 - hot_penalty
    scale[provider._risk_archetype_high_volatility_chase] *= 1.0 - high_vol_penalty
    provider._risk_archetype_score_scale = scale
    provider.risk_archetype_hot_crowded_count = int(np.sum(provider._risk_archetype_hot_crowded))
    provider.risk_archetype_high_volatility_chase_count = int(np.sum(provider._risk_archetype_high_volatility_chase))
    if not soft_enabled:
        provider._wide_runtime_optimization_notes.append(
            "apply_risk_archetype_features:"
            f"hot_crowded={provider.risk_archetype_hot_crowded_count},"
            f"high_volatility={provider.risk_archetype_high_volatility_chase_count}"
        )
        return

    provider._risk_archetype_original_final_score = np.array(final_score, copy=True)
    valid = candidate_mask & np.isfinite(final_score) & np.isfinite(scale) & (scale < 1.0 - 1e-12)
    adjusted = np.array(final_score, copy=True)
    adjusted[valid] = adjusted[valid] * scale[valid]
    provider._final_score = adjusted
    provider.risk_archetype_soft_deprioritize_count = int(np.sum(valid))
    provider._wide_runtime_optimization_notes.append(
        "apply_risk_archetype_soft_deprioritize:"
        f"adjusted={provider.risk_archetype_soft_deprioritize_count},"
        f"hot_crowded={provider.risk_archetype_hot_crowded_count},"
        f"high_volatility={provider.risk_archetype_high_volatility_chase_count}"
    )


def _can_defer_residual_score(provider: Any) -> tuple[bool, str]:
    if not _active_set_sparse_scoring_enabled(provider):
        return False, "active_set_sparse_scoring_disabled"
    if bool(getattr(provider, "_trend_quality_soft_score_enabled", False)):
        return False, "trend_quality_soft_score_enabled"
    if bool(getattr(provider, "_risk_archetype_soft_deprioritize_enabled", False)):
        return False, "risk_archetype_soft_deprioritize_enabled"
    if not bool(provider._enable_residual_ranking):
        return False, "residual_ranking_disabled"
    if str(provider._ranking_mode) != "residual_only":
        return False, "ranking_mode_not_residual_only"
    if bool(provider._enable_sector_quality_ranking):
        return False, "sector_quality_ranking_enabled"
    if str(provider._residual_refine_mode) not in {"", "off", "none"}:
        return False, "residual_refine_enabled"
    if str(provider._source_aware_residual_mode) not in {"", "off", "none"}:
        return False, "source_aware_residual_enabled"
    if bool(provider._bull_breakout_quality_veto_enabled):
        return False, "bull_breakout_quality_veto_enabled"
    if bool(provider._enable_profit_decay_exit):
        return False, "profit_decay_exit_needs_residual_score_matrix"
    if str(provider._residual_window_regime_mode) not in {"", "off", "none"}:
        return False, "residual_window_regime_enabled"
    if str(provider._residual_weight_regime_mode) not in {"", "off", "none"}:
        return False, "residual_weight_regime_enabled"
    if str(provider._industry_relative_regime_mode) not in {"", "off", "none"}:
        return False, "industry_relative_regime_enabled"
    return True, "residual_only_safe_subset"


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
    provider._wide_runtime_optimization_notes = []
    needs_sector_quality_score = bool(provider._enable_sector_quality_ranking)
    defer_residual_score, defer_reason = _can_defer_residual_score(provider)
    provider._deferred_residual_score_enabled = bool(defer_residual_score)
    if defer_residual_score:
        provider._wide_runtime_optimization_notes.append("defer_residual_score_row_rank")
    else:
        provider._wide_runtime_optimization_notes.append(f"no_deferred_residual_score:{defer_reason}")
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
        materialize_residual_score=not bool(defer_residual_score),
        materialize_diagnostics=not bool(defer_residual_score),
        need_sector_quality_components=bool(needs_sector_quality_score),
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

    needs_breakout_quality = (
        bool(provider._enable_sector_quality_ranking)
        or str(provider._ranking_mode) == "quality_then_residual"
        or bool(provider._bull_breakout_quality_veto_enabled)
        or str(provider._residual_refine_mode) in {
            "conditional_tiebreak",
            "industry_second_stage",
            "industry_second_stage_tiebreak",
        }
        or str(provider._ranking_mode) == "leadership_then_residual"
    )
    needs_conditional_tiebreak = (
        str(provider._residual_refine_mode) in {
            "conditional_tiebreak",
            "industry_second_stage",
            "industry_second_stage_tiebreak",
        }
        or str(provider._ranking_mode) == "leadership_then_residual"
    )
    needs_industry_second_stage = (
        provider._enable_residual_ranking
        and provider._residual_refine_mode in {"industry_second_stage", "industry_second_stage_tiebreak"}
        and (
            provider._residual_refine_mode == "industry_second_stage_tiebreak"
            or provider._residual_refine_weight > 1e-12
        )
    )
    needs_leadership_route = str(provider._ranking_mode) == "leadership_then_residual"

    if needs_sector_quality_score:
        sector_short_rank = _row_rank_pct(sector_ret_short, mx.tradable)
        sector_long_rank = _row_rank_pct(sector_ret_long, mx.tradable)
        provider._sector_strength_score = _weighted_score(
            [(sector_short_rank, 0.4), (sector_long_rank, 0.4), (sector_trend, 0.2)],
            shape=(t, n),
        )
    else:
        provider._sector_strength_score = np.full((t, n), np.nan, dtype=float)
        provider._wide_runtime_optimization_notes.append("skip_sector_strength_score")

    if needs_breakout_quality:
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
    else:
        provider._volume_price_quality_score = np.full((t, n), np.nan, dtype=float)
        provider._wide_runtime_optimization_notes.append("skip_volume_price_quality_score")

    risk_on_m = np.repeat(provider._risk_on.reshape(-1, 1), n, axis=1)
    common_gate = risk_on_m & mx.tradable & provider._momentum_ok
    provider._breakout_buy = provider._entry_delay_ok & provider._entry_confirm_ok & provider._v2_trend_ok & common_gate
    provider._bad_breakout_quality_ret5 = np.array([], dtype=float)
    provider._bad_breakout_quality_r2_60 = np.array([], dtype=float)
    provider._bad_breakout_quality_ret5_rank = np.array([], dtype=float)
    provider._bad_breakout_quality_r2_60_rank = np.array([], dtype=float)
    provider._bad_breakout_quality_veto_mask = np.zeros((t, n), dtype=bool)
    provider.bad_breakout_quality_veto_block_count = 0
    if bool(getattr(provider, "_bad_breakout_quality_veto_enabled", False)) and bool(np.any(provider._breakout_buy)):
        provider._bad_breakout_quality_ret5 = _return_matrix(mx.close, 5)
        provider._bad_breakout_quality_r2_60 = _rolling_log_trend_r2_matrix(mx.close, 60)
        provider._bad_breakout_quality_ret5_rank = _row_rank_pct(
            provider._bad_breakout_quality_ret5,
            provider._breakout_buy & ~np.isnan(provider._bad_breakout_quality_ret5),
        )
        provider._bad_breakout_quality_r2_60_rank = _row_rank_pct(
            provider._bad_breakout_quality_r2_60,
            provider._breakout_buy & ~np.isnan(provider._bad_breakout_quality_r2_60),
        )
        ret5_rank_min = min(1.0, max(0.0, float(getattr(provider, "_bad_breakout_quality_ret5_rank_min", 0.80))))
        r2_rank_max = min(1.0, max(0.0, float(getattr(provider, "_bad_breakout_quality_r2_60_rank_max", 0.20))))
        provider._bad_breakout_quality_veto_mask = (
            provider._breakout_buy
            & ~np.isnan(provider._bad_breakout_quality_ret5_rank)
            & ~np.isnan(provider._bad_breakout_quality_r2_60_rank)
            & (provider._bad_breakout_quality_ret5_rank >= ret5_rank_min)
            & (provider._bad_breakout_quality_r2_60_rank <= r2_rank_max)
        )
        provider.bad_breakout_quality_veto_block_count = int(np.sum(provider._bad_breakout_quality_veto_mask))
        if provider.bad_breakout_quality_veto_block_count > 0:
            provider._breakout_buy = provider._breakout_buy & ~provider._bad_breakout_quality_veto_mask
            provider.diag_reason_counts["BAD_BREAKOUT_QUALITY_VETO"] = (
                int(provider.diag_reason_counts.get("BAD_BREAKOUT_QUALITY_VETO", 0))
                + int(provider.bad_breakout_quality_veto_block_count)
            )
    else:
        provider._wide_runtime_optimization_notes.append("skip_bad_breakout_quality_veto")
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
    if needs_breakout_quality and bool(np.any(breakout_margin_mask)):
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
    elif not needs_breakout_quality:
        provider._wide_runtime_optimization_notes.append("skip_breakout_quality_score")

    residual_component = provider._residual_strength_score
    if needs_conditional_tiebreak:
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
    else:
        provider._conditional_tiebreak_score = np.full((t, n), np.nan, dtype=float)
        provider._conditional_factor_leader_score = np.full((t, n), np.nan, dtype=float)
        provider._conditional_institution_proxy_score = np.full((t, n), np.nan, dtype=float)
        provider._conditional_crowding_score = np.full((t, n), np.nan, dtype=float)
        provider._conditional_recent_limit_hit_3d = np.zeros((t, n), dtype=bool)
        provider._conditional_near_limit_up = np.zeros((t, n), dtype=bool)
        provider._wide_runtime_optimization_notes.append("skip_conditional_tiebreak_score")
    provider._industry_second_stage_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_not_hot_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_uncrowded_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_breadth_timing_score = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_persistence_10d = np.full((t, n), 0.5, dtype=float)
    provider._industry_second_stage_active = np.zeros((t, n), dtype=bool)
    if needs_industry_second_stage:
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
    if needs_leadership_route:
        provider._leadership_route_score = _weighted_score(
            [
                (provider._conditional_factor_leader_score, 0.5),
                (provider._conditional_institution_proxy_score, 0.5),
            ],
            shape=(t, n),
        )
        provider._leadership_route_score = np.where(
            np.isnan(provider._leadership_route_score),
            0.5,
            provider._leadership_route_score,
        )
        (
            provider._leadership_route_rank,
            provider._leadership_route_bucket,
        ) = _row_bucket_code(
            provider._leadership_route_score,
            mx.tradable & ~np.isnan(provider._leadership_route_score),
            int(provider._leadership_route_bucket_count),
        )
    else:
        provider._leadership_route_score = np.full((t, n), np.nan, dtype=float)
        provider._leadership_route_rank = np.full((t, n), np.nan, dtype=float)
        provider._leadership_route_bucket = np.full((t, n), -1, dtype=int)
        provider._wide_runtime_optimization_notes.append("skip_leadership_route_score")
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

    if defer_residual_score:
        provider._final_score = np.array([], dtype=float)
        provider._wide_runtime_optimization_notes.append("defer_final_score_row_rank")
    elif provider._enable_residual_ranking or provider._enable_sector_quality_ranking:
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
    _apply_trend_quality_soft_score(provider, mx=mx, buy_base=buy_base)
    _apply_risk_archetype_soft_deprioritize(provider, raw_history=raw_history, mx=mx, buy_base=buy_base)
    if provider._ranking_mode == "quality_then_residual":
        breakout_quality_scope = provider._breakout_buy | provider._pullback_overlap
        buy_base = (buy_base & ~breakout_quality_scope) | (
            buy_base & breakout_quality_scope & provider._breakout_quality_pass
        )
    provider._cand_idx = build_daily_candidate_index(buy_base)
    provider._sym_to_col = {s: idx for idx, s in enumerate(mx.symbols)}

