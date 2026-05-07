from __future__ import annotations

import numpy as np
import pandas as pd

from backend.research.mainline_breakout_runtime_context import MainlineBreakoutResearchContext
from backend.research.mainline_factor_surface_common import build_factor_score_snapshot, build_factor_snapshot, subset_columns
from backend.research.risk_gate_factor_catalog import get_risk_gate_factor_spec


def _repeat_day_vector(vector: np.ndarray, width: int) -> np.ndarray:
    return np.repeat(np.asarray(vector, dtype=float).reshape(-1, 1), width, axis=1)


def _state_name_vector(context: MainlineBreakoutResearchContext) -> np.ndarray:
    provider = context.provider
    state_arr = getattr(provider, "_market_state_name_arr", np.array([], dtype=object))
    if isinstance(state_arr, np.ndarray) and state_arr.size:
        return np.asarray(state_arr, dtype=object)
    state_arr = getattr(provider, "_market_state_smoothed_name_arr", np.array([], dtype=object))
    if isinstance(state_arr, np.ndarray) and state_arr.size:
        return np.asarray(state_arr, dtype=object)
    return np.full(len(context.dates), "", dtype=object)


def build_risk_gate_factor_snapshots(
    context: MainlineBreakoutResearchContext,
    *,
    factor_ids: list[str],
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    selected_symbols, selected_idx = subset_columns(context.symbols, symbols or [])
    provider = context.provider
    width = len(selected_symbols)
    tradable = np.asarray(context.tradable_matrix[:, selected_idx], dtype=bool)
    risk_on = np.asarray(getattr(provider, "_risk_on"), dtype=bool)
    strong_risk_on = np.asarray(getattr(provider, "_strong_risk_on"), dtype=bool)
    breakout_buy = np.asarray(getattr(provider, "_breakout_buy")[:, selected_idx], dtype=bool)
    pullback_overlap = np.asarray(getattr(provider, "_pullback_overlap")[:, selected_idx], dtype=bool)
    breakout_scope = breakout_buy | pullback_overlap
    breakout_quality_pass = np.asarray(getattr(provider, "_breakout_quality_pass")[:, selected_idx], dtype=bool)
    breakout_quality_score = np.asarray(getattr(provider, "_breakout_quality_score")[:, selected_idx], dtype=float)
    residual_strength_score = np.asarray(getattr(provider, "_residual_strength_score")[:, selected_idx], dtype=float)
    breakout_margin_score = np.asarray(getattr(provider, "_breakout_margin_score")[:, selected_idx], dtype=float)
    benchmark_regime_off = _repeat_day_vector((~risk_on).astype(float), width)
    strong_risk_on_absence = _repeat_day_vector((~strong_risk_on).astype(float), width)
    bull_state = _repeat_day_vector((_state_name_vector(context) == "BULL").astype(float), width)
    quality_gate_floor = float(getattr(provider, "_breakout_quality_gate_min_score", 0.0) or 0.0)
    bull_residual_floor = float(getattr(provider, "_bull_breakout_quality_veto_min_residual_strength_score", 0.0) or 0.0)
    bull_margin_floor = float(getattr(provider, "_bull_breakout_quality_veto_min_breakout_margin_score", 0.0) or 0.0)

    factor_matrices: dict[str, np.ndarray] = {}
    for factor_id in factor_ids:
        _ = get_risk_gate_factor_spec(factor_id)
        if factor_id == "benchmark_regime_off_risk":
            factor_matrices[factor_id] = benchmark_regime_off
        elif factor_id == "strong_risk_on_absence_risk":
            factor_matrices[factor_id] = strong_risk_on_absence
        elif factor_id == "regime_blocked_breakout_risk":
            factor_matrices[factor_id] = np.where(breakout_scope, benchmark_regime_off, 0.0)
        elif factor_id == "breakout_quality_fail_risk":
            factor_matrices[factor_id] = np.where(breakout_scope, (~breakout_quality_pass).astype(float), 0.0)
        elif factor_id == "breakout_quality_gate_shortfall_risk":
            factor_matrices[factor_id] = np.where(breakout_scope, np.maximum(0.0, quality_gate_floor - np.nan_to_num(breakout_quality_score, nan=0.0)), 0.0)
        elif factor_id == "bull_quality_residual_shortfall_risk":
            factor_matrices[factor_id] = np.where((bull_state > 0.5) & breakout_scope, np.maximum(0.0, bull_residual_floor - np.nan_to_num(residual_strength_score, nan=0.0)), 0.0)
        elif factor_id == "bull_quality_margin_shortfall_risk":
            factor_matrices[factor_id] = np.where((bull_state > 0.5) & breakout_scope, np.maximum(0.0, bull_margin_floor - np.nan_to_num(breakout_margin_score, nan=0.0)), 0.0)
        else:
            raise KeyError(f"unsupported risk gate factor: {factor_id}")
    return build_factor_snapshot(
        dates=context.dates,
        symbols=selected_symbols,
        factor_matrices=factor_matrices,
        tradable_matrix=tradable,
    )


def build_risk_gate_factor_score_snapshot(factor_snapshot: pd.DataFrame, *, factor_ids: list[str], factor_weights: dict[str, float]) -> pd.DataFrame:
    return build_factor_score_snapshot(factor_snapshot, factor_ids=factor_ids, factor_weights=factor_weights, score_id="risk_gate_veto_score")
