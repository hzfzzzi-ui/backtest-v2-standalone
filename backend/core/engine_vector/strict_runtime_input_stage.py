"""Input/precompute stage for the default vector runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import RiskBudgetConfig
from backend.core.config.models import SizingConfig
from backend.core.engine_vector.data_matrix import build_ohlc_matrices_from_history
from backend.core.engine_vector.features import compute_feature_matrices


@dataclass(slots=True)
class DefaultRuntimeInputStage:
    params: dict[str, Any]
    mx: Any
    feats: Any
    strength: np.ndarray


def prepare_default_runtime_inputs(
    *,
    strategy: Any,
    history: pd.DataFrame,
    trading_days: list[date],
    strength_ma: int,
    st_history: Any = None,
    sizing_cfg: Any = None,
    risk_budget_cfg: Any = None,
) -> DefaultRuntimeInputStage:
    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"])
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    _uf = dict(getattr(strategy, "state", {}).get("universe_filters") or {})
    _min_price = float(_uf.get("min_price", getattr(strategy, "min_price", 0.0)) or 0.0)
    _min_trade_price = float(_min_price)
    _min_list_days = int(_uf.get("min_list_days", 0) or 0)
    _min_avg_turnover_20d = float(_uf.get("min_avg_turnover_20d", 0.0) or 0.0)
    _membership_history = getattr(strategy, "state", {}).get("membership_history")
    mx = build_ohlc_matrices_from_history(
        hist,
        trading_days,
        st_history=st_history,
        membership_history=_membership_history,
        min_price=_min_price,
        min_list_days=_min_list_days,
        min_avg_turnover_20d=_min_avg_turnover_20d,
    )
    t, n = mx.close.shape
    if n == 0:
        raise ValueError("history has no symbols")

    fast = int(getattr(strategy, "fast", 5))
    slow = int(getattr(strategy, "slow", 20))
    trend_fast = int(getattr(strategy, "trend_fast_ma", 120))
    trend_slow = int(getattr(strategy, "trend_slow_ma", 200))
    enable_trend_slope_filter = bool(getattr(strategy, "enable_trend_slope_filter", False))
    slope_lookback = int(getattr(strategy, "slope_lookback", 5))
    enable_trend_continuity_filter = bool(getattr(strategy, "enable_trend_continuity_filter", False))
    continuity_n = int(getattr(strategy, "continuity_n", 10))
    atr_n = int(getattr(strategy, "atr_n", 14))
    entry_buffer = float(getattr(strategy, "entry_buffer", 0.0))
    enable_trend_filter = bool(getattr(strategy, "enable_trend_filter", False))
    enable_trend_tier = bool(getattr(strategy, "enable_trend_tier", True))
    enable_trend_accel = bool(getattr(strategy, "enable_trend_accel", True))
    enable_trend_break_exit = bool(getattr(strategy, "enable_trend_break_exit", True))
    trend_break_confirm_days = int(getattr(strategy, "trend_break_confirm_days", 3))
    trend_break_confirm_gap_pct = float(getattr(strategy, "trend_break_confirm_gap_pct", 0.0))
    trend_break_use_benchmark_regime = bool(getattr(strategy, "trend_break_use_benchmark_regime", False))
    weak_trend_order_scale = float(getattr(strategy, "weak_trend_order_scale", 0.5))
    strong_trend_order_scale = float(getattr(strategy, "strong_trend_order_scale", 1.0))
    enable_atr_stop = bool(getattr(strategy, "enable_atr_stop", False))
    enable_atr_trail = bool(getattr(strategy, "enable_atr_trail", False))
    atr_stop_k = float(getattr(strategy, "atr_stop_k", 2.0))
    atr_trail_k = float(getattr(strategy, "atr_trail_k", 3.0))
    trailing_activate_profit_pct = float(getattr(strategy, "trailing_activate_profit_pct", 0.0) or 0.0)
    enable_take_profit = bool(getattr(strategy, "enable_take_profit", False))
    take_profit_mode = str(getattr(strategy, "take_profit_mode", "pct"))
    take_profit_pct = float(getattr(strategy, "take_profit_pct", 0.10))
    take_profit_atr_k = float(getattr(strategy, "take_profit_atr_k", 3.0))
    enable_fixed_stop_loss = bool(getattr(strategy, "enable_fixed_stop_loss", False))
    fixed_stop_loss_pct = float(getattr(strategy, "fixed_stop_loss_pct", 0.05))
    max_hold_days = int(getattr(strategy, "max_hold_days", 0))
    enable_ma20_exit = bool(getattr(strategy, "enable_ma20_exit", False))
    enable_low10_exit = bool(getattr(strategy, "enable_low10_exit", False))
    order_size = int(getattr(strategy, "order_size", 1000))
    regime_ma = int(getattr(strategy, "regime_ma", 60))
    enable_v2_trend_filter = bool(getattr(strategy, "enable_v2_trend_filter", False))
    v2_trend_short_ma = int(getattr(strategy, "v2_trend_short_ma", 20))
    v2_trend_long_ma = int(getattr(strategy, "v2_trend_long_ma", 60))

    _rbc = risk_budget_cfg if isinstance(risk_budget_cfg, RiskBudgetConfig) else RiskBudgetConfig()
    enable_dd_breaker = bool(_rbc.enabled)
    dd_reduce_pct = float(_rbc.dd_reduce_pct)
    dd_reduce_scale = float(_rbc.dd_reduce_scale)

    _sc = sizing_cfg if isinstance(sizing_cfg, SizingConfig) else SizingConfig()
    weight_mode = str(_sc.weight_mode or "equal")
    min_positions = int(_sc.min_positions)
    tilt_strength = float(_sc.tilt_strength)
    tilt_top_n = int(_sc.tilt_top_n)
    tilt_bottom_n = int(_sc.tilt_bottom_n)
    score_weight_min_scale = float(_sc.score_weight_min_scale)
    score_weight_max_scale = float(_sc.score_weight_max_scale)
    candidate_plan_mode = str(_sc.candidate_plan_mode or "ranked")
    cash_aware_search_top_n = int(_sc.cash_aware_search_top_n)
    rotation_replace_enabled = bool(_sc.rotation_replace_enabled)
    rotation_replace_only_strong_risk_on = bool(_sc.rotation_replace_only_strong_risk_on)
    rotation_replace_max_swaps_per_day = int(_sc.rotation_replace_max_swaps_per_day)
    rotation_replace_candidate_top_n = int(_sc.rotation_replace_candidate_top_n)
    rotation_replace_min_score_gap = float(_sc.rotation_replace_min_score_gap)

    feats = compute_feature_matrices(
        close=mx.close,
        high=mx.high,
        low=mx.low,
        fast=fast,
        slow=slow,
        trend_fast=trend_fast,
        trend_slow=trend_slow,
        atr_n=atr_n,
        strength_ma=int(strength_ma),
        v2_trend_short_ma=v2_trend_short_ma,
        v2_trend_long_ma=v2_trend_long_ma,
    )
    strength = mx.close / feats.strength_ma - 1.0
    strength[np.isnan(feats.strength_ma)] = np.nan

    return DefaultRuntimeInputStage(
        params={
            "min_trade_price": _min_trade_price,
            "fast": fast,
            "slow": slow,
            "trend_fast": trend_fast,
            "trend_slow": trend_slow,
            "enable_trend_slope_filter": enable_trend_slope_filter,
            "slope_lookback": slope_lookback,
            "enable_trend_continuity_filter": enable_trend_continuity_filter,
            "continuity_n": continuity_n,
            "atr_n": atr_n,
            "entry_buffer": entry_buffer,
            "enable_trend_filter": enable_trend_filter,
            "enable_trend_tier": enable_trend_tier,
            "enable_trend_accel": enable_trend_accel,
            "enable_trend_break_exit": enable_trend_break_exit,
            "trend_break_confirm_days": trend_break_confirm_days,
            "trend_break_confirm_gap_pct": trend_break_confirm_gap_pct,
            "trend_break_use_benchmark_regime": trend_break_use_benchmark_regime,
            "weak_trend_order_scale": weak_trend_order_scale,
            "strong_trend_order_scale": strong_trend_order_scale,
            "enable_atr_stop": enable_atr_stop,
            "enable_atr_trail": enable_atr_trail,
            "atr_stop_k": atr_stop_k,
            "atr_trail_k": atr_trail_k,
            "trailing_activate_profit_pct": trailing_activate_profit_pct,
            "enable_take_profit": enable_take_profit,
            "take_profit_mode": take_profit_mode,
            "take_profit_pct": take_profit_pct,
            "take_profit_atr_k": take_profit_atr_k,
            "enable_fixed_stop_loss": enable_fixed_stop_loss,
            "fixed_stop_loss_pct": fixed_stop_loss_pct,
            "max_hold_days": max_hold_days,
            "enable_ma20_exit": enable_ma20_exit,
            "enable_low10_exit": enable_low10_exit,
            "order_size": order_size,
            "regime_ma": regime_ma,
            "enable_v2_trend_filter": enable_v2_trend_filter,
            "v2_trend_short_ma": v2_trend_short_ma,
            "v2_trend_long_ma": v2_trend_long_ma,
            "enable_dd_breaker": enable_dd_breaker,
            "dd_reduce_pct": dd_reduce_pct,
            "dd_reduce_scale": dd_reduce_scale,
            "weight_mode": weight_mode,
            "min_positions": min_positions,
            "tilt_strength": tilt_strength,
            "tilt_top_n": tilt_top_n,
            "tilt_bottom_n": tilt_bottom_n,
            "score_weight_min_scale": score_weight_min_scale,
            "score_weight_max_scale": score_weight_max_scale,
            "candidate_plan_mode": candidate_plan_mode,
            "cash_aware_search_top_n": cash_aware_search_top_n,
            "rotation_replace_enabled": rotation_replace_enabled,
            "rotation_replace_only_strong_risk_on": rotation_replace_only_strong_risk_on,
            "rotation_replace_max_swaps_per_day": rotation_replace_max_swaps_per_day,
            "rotation_replace_candidate_top_n": rotation_replace_candidate_top_n,
            "rotation_replace_min_score_gap": rotation_replace_min_score_gap,
            "enable_sector_gate": bool(getattr(strategy, "enable_sector_gate", False)),
            "sector_rank_window": int(getattr(strategy, "sector_rank_window", 60)),
            "sector_top_pct": float(getattr(strategy, "sector_top_pct", 0.30)),
        },
        mx=mx,
        feats=feats,
        strength=strength,
    )
