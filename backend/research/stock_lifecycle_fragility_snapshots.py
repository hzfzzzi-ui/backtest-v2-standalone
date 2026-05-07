from __future__ import annotations

import numpy as np
import pandas as pd

from backend.research.mainline_breakout_runtime_context import MainlineBreakoutResearchContext
from backend.research.mainline_factor_surface_common import build_factor_score_snapshot, build_factor_snapshot, subset_columns
from backend.research.stock_lifecycle_fragility_catalog import get_stock_lifecycle_fragility_factor_spec


def _state_penalty(state_text: str) -> float:
    norm = str(state_text or '').strip().upper()
    if norm == 'BULL':
        return 0.0
    if norm == 'TRANS_UP':
        return 0.25
    if norm == 'TRANS_DOWN':
        return 0.75
    if norm in {'RISK_OFF', 'BEAR'}:
        return 1.0
    return 0.5


def _rolling_min_2d(values: np.ndarray, window: int) -> np.ndarray:
    df = pd.DataFrame(np.asarray(values, dtype=float))
    return df.rolling(int(window), min_periods=int(window)).min().to_numpy(dtype=float)


def _build_lifecycle_matrices(context: MainlineBreakoutResearchContext, *, selected_idx: list[int], max_lifecycle_bars: int = 20) -> dict[str, np.ndarray]:
    close = np.asarray(context.close_matrix[:, selected_idx], dtype=float)
    high = np.asarray(context.high_matrix[:, selected_idx], dtype=float)
    low = np.asarray(context.low_matrix[:, selected_idx], dtype=float)
    tradable = np.asarray(context.tradable_matrix[:, selected_idx], dtype=bool)
    t, n = close.shape
    provider = context.provider
    breakout_buy = np.asarray(getattr(provider, '_breakout_buy', np.zeros((t, len(context.symbols)), dtype=bool))[:, selected_idx], dtype=bool)
    pullback_buy = np.asarray(getattr(provider, '_pullback_raw_selected', np.zeros((t, len(context.symbols)), dtype=bool))[:, selected_idx], dtype=bool)
    entry_events = breakout_buy | pullback_buy
    low10_floor = _rolling_min_2d(low, 10)
    effective_state = np.asarray(context.effective_state_5_arr, dtype=object)
    if len(effective_state) != t:
        effective_state = np.full(t, '', dtype=object)

    early_fade_risk = np.full((t, n), np.nan, dtype=float)
    weak_carry_risk = np.full((t, n), np.nan, dtype=float)
    break_floor_risk = np.full((t, n), np.nan, dtype=float)
    pre_profit_failure_context_risk = np.full((t, n), np.nan, dtype=float)
    low10_exit_context_risk = np.full((t, n), np.nan, dtype=float)
    risk_off_exit_context_risk = np.full((t, n), np.nan, dtype=float)

    for col in range(n):
        active = False
        last_entry_idx = -1
        entry_price = np.nan
        peak_high = np.nan
        for i in range(t):
            c = float(close[i, col]) if not np.isnan(close[i, col]) else np.nan
            h = float(high[i, col]) if not np.isnan(high[i, col]) else c
            floor10 = float(low10_floor[i, col]) if not np.isnan(low10_floor[i, col]) else np.nan
            if bool(entry_events[i, col]) and bool(tradable[i, col]) and not np.isnan(c):
                active = True
                last_entry_idx = i
                entry_price = c
                peak_high = h if not np.isnan(h) else c
            elif active and last_entry_idx >= 0:
                if (i - last_entry_idx) > int(max_lifecycle_bars):
                    active = False
                elif not np.isnan(h):
                    peak_high = max(float(peak_high), float(h)) if not np.isnan(peak_high) else float(h)
            if not active or last_entry_idx < 0 or np.isnan(c) or np.isnan(entry_price):
                continue
            age = i - last_entry_idx
            if age <= 0 or age > int(max_lifecycle_bars):
                continue
            entry_ret = (c / entry_price - 1.0) if entry_price > 1e-8 else np.nan
            drawdown_from_peak = max((peak_high - c) / entry_price, 0.0) if entry_price > 1e-8 and not np.isnan(peak_high) else np.nan
            early_fade_risk[i, col] = float(drawdown_from_peak) if 1 <= age <= 5 and not np.isnan(drawdown_from_peak) else np.nan
            weak_carry_risk[i, col] = float(max(0.02 - float(entry_ret), 0.0)) if 5 <= age <= int(max_lifecycle_bars) and not np.isnan(entry_ret) else np.nan
            if not np.isnan(floor10) and floor10 > 1e-8:
                break_floor_risk[i, col] = float(max((floor10 - c) / floor10, 0.0))
                low10_exit_context_risk[i, col] = float(max(((floor10 * 1.01) - c) / (floor10 * 1.01), 0.0))
            if age <= 5 and not np.isnan(entry_ret):
                fade_component = float(drawdown_from_peak) if not np.isnan(drawdown_from_peak) else 0.0
                pre_profit_failure_context_risk[i, col] = float(max(-float(entry_ret), 0.0) + 0.5 * fade_component)
            risk_off_exit_context_risk[i, col] = float(_state_penalty(str(effective_state[i] or '')))

    return {
        'early_fade_risk': early_fade_risk,
        'weak_carry_risk': weak_carry_risk,
        'break_floor_risk': break_floor_risk,
        'pre_profit_failure_context_risk': pre_profit_failure_context_risk,
        'low10_exit_context_risk': low10_exit_context_risk,
        'risk_off_exit_context_risk': risk_off_exit_context_risk,
    }


def build_stock_lifecycle_fragility_snapshots(
    context: MainlineBreakoutResearchContext,
    *,
    factor_ids: list[str],
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    selected_symbols, selected_idx = subset_columns(context.symbols, symbols or [])
    lifecycle_matrices = _build_lifecycle_matrices(context, selected_idx=selected_idx)
    factor_matrices: dict[str, np.ndarray] = {}
    for factor_id in factor_ids:
        _ = get_stock_lifecycle_fragility_factor_spec(factor_id)
        factor_matrices[factor_id] = np.asarray(lifecycle_matrices[factor_id], dtype=float)
    return build_factor_snapshot(
        dates=context.dates,
        symbols=selected_symbols,
        factor_matrices=factor_matrices,
        tradable_matrix=np.asarray(context.tradable_matrix[:, selected_idx], dtype=bool),
    )


def build_stock_lifecycle_fragility_factor_score_snapshot(
    factor_snapshot: pd.DataFrame,
    *,
    factor_ids: list[str],
    factor_weights: dict[str, float],
) -> pd.DataFrame:
    return build_factor_score_snapshot(
        factor_snapshot,
        factor_ids=factor_ids,
        factor_weights=factor_weights,
        invert_for_score=set(),
        score_id='stock_lifecycle_fragility_score',
    )
