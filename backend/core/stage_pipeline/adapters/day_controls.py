from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np


_BULLISH_STATE_NAMES = {"BULL", "BULL_MAIN"}
_TRANS_DOWN_STATE_NAMES = {"TRANS_DOWN", "TURN_WEAK"}
_TRANS_UP_STATE_NAMES = {"TRANS_UP", "TURN_STRONG"}
_BEARISH_STATE_NAMES = {"BEAR", "DEFENSIVE"}


def compute_day_controls(runtime: Any, day_index: int, day: date, drawdown: float) -> dict[str, Any]:
    effective_max_positions = int(runtime.request.max_positions)
    dd_state = "NORMAL"
    market_state = ""
    trade_mode = ""
    benchmark_regime_on = True
    breadth_score = float("nan")
    breadth_max_positions = int(runtime.request.max_positions)
    regime_engine = str(getattr(runtime, "_regime_engine_name", "ma200_legacy") or "ma200_legacy")
    regime_confidence = None
    regime_duration_bars = None
    regime_transition_reason = ""
    feature_availability: dict[str, Any] = {}
    market_state_5 = ""
    market_state_raw = ""
    market_state_smoothed = ""
    market_state_score = None
    risk_budget_multiplier = None
    weekly_observation_flag = False
    if runtime.route_id == "provider_breakout_runtime":
        dynamic_base_positions = int(runtime.request.max_positions)
        if runtime._portfolio_mode == "equal_8":
            dynamic_base_positions = min(int(runtime.request.max_positions), 8)
        elif runtime._portfolio_mode == "equal_6":
            dynamic_base_positions = min(int(runtime.request.max_positions), 6)
        elif runtime._portfolio_mode == "profit_release":
            dynamic_base_positions = int(runtime.request.max_positions)
            for symbol, qty in runtime.positions.items():
                if int(qty) <= 0:
                    continue
                close_v = float(runtime.close_idx.get((day, str(symbol).lower()), 0.0) or 0.0)
                avg_v = float(runtime.position_avg_cost.get(str(symbol).lower(), 0.0) or 0.0)
                if close_v > 0 and avg_v > 0 and ((close_v / avg_v) - 1.0) > 0.20:
                    dynamic_base_positions = int(runtime.request.max_positions) + 1
                    break
        if runtime._dd_enabled and abs(drawdown) >= runtime._dd_reduce_pct:
            effective_max_positions = max(1, int(dynamic_base_positions * runtime._dd_reduce_scale))
            dd_state = "REDUCED"
        else:
            effective_max_positions = int(dynamic_base_positions)
        if runtime._mf_enabled:
            state = int(runtime._mf_state_arr[day_index])
            trade_mode_arr = getattr(runtime, "_mf_trade_mode_arr", None)
            trade_mode_value = int(trade_mode_arr[day_index]) if isinstance(trade_mode_arr, np.ndarray) and day_index < len(trade_mode_arr) else (0 if state == 0 else 1 if state in (1, 2) else 2)
            mult = float(runtime._mf_mult_arr[day_index])
            effective_max_positions = max(0, int(round(float(effective_max_positions) * max(0.0, mult))))
            state_name_arr = getattr(runtime.provider, "_market_state_name_arr", None)
            trade_mode_name_arr = getattr(runtime.provider, "_trade_mode_name_arr", None)
            raw_state_name_arr = getattr(runtime.provider, "_market_state_raw_name_arr", None)
            smoothed_state_name_arr = getattr(runtime.provider, "_market_state_smoothed_name_arr", None)
            state_score_arr = getattr(runtime.provider, "_market_state_score_arr", None)
            risk_budget_arr = getattr(runtime.provider, "_risk_budget_multiplier_arr", None)
            weekly_flag_arr = getattr(runtime.provider, "_weekly_observation_flag_arr", None)
            if isinstance(state_name_arr, np.ndarray) and day_index < len(state_name_arr):
                market_state = str(state_name_arr[day_index] or "")
            else:
                market_state = runtime._MARKET_STATE_NAMES[state]
            if isinstance(trade_mode_name_arr, np.ndarray) and day_index < len(trade_mode_name_arr):
                trade_mode = str(trade_mode_name_arr[day_index] or "")
            else:
                trade_mode = runtime._TRADE_MODE_NAMES[trade_mode_value]
            if isinstance(raw_state_name_arr, np.ndarray) and day_index < len(raw_state_name_arr):
                market_state_raw = str(raw_state_name_arr[day_index] or "")
            if isinstance(smoothed_state_name_arr, np.ndarray) and day_index < len(smoothed_state_name_arr):
                market_state_smoothed = str(smoothed_state_name_arr[day_index] or "")
            if isinstance(state_score_arr, np.ndarray) and day_index < len(state_score_arr):
                value = float(state_score_arr[day_index])
                market_state_score = None if value != value else value
            if isinstance(risk_budget_arr, np.ndarray) and day_index < len(risk_budget_arr):
                risk_budget_multiplier = float(risk_budget_arr[day_index])
            if isinstance(weekly_flag_arr, np.ndarray) and day_index < len(weekly_flag_arr):
                weekly_observation_flag = bool(weekly_flag_arr[day_index])
            market_state_5 = str(market_state_smoothed or market_state or "")
            state_counter_name = str(market_state_5 or market_state or "").strip().upper()
            if state_counter_name in _BULLISH_STATE_NAMES:
                runtime.market_filter_bull_days += 1
            elif state_counter_name in _TRANS_DOWN_STATE_NAMES:
                runtime.market_state_trans_down_days += 1
            elif state_counter_name in _TRANS_UP_STATE_NAMES:
                runtime.market_state_trans_up_days += 1
            elif state_counter_name in _BEARISH_STATE_NAMES:
                runtime.market_filter_bear_days += 1
            trade_mode_counter_name = str(trade_mode or "").strip().upper()
            if trade_mode_counter_name == "TREND_MAIN":
                runtime.trade_mode_main_days += 1
            elif trade_mode_counter_name == "TREND_LIGHT":
                runtime.trade_mode_light_days += 1
            elif trade_mode_counter_name == "NO_TRADE":
                runtime.trade_mode_notrade_days += 1
        else:
            market_state = "BULL"
            trade_mode = "TREND_MAIN"
            market_state_5 = market_state
        benchmark_regime_on = bool(runtime._br_gate_arr[day_index]) if runtime._br_enabled else True
        if bool(getattr(runtime, "_breadth_enabled", False)):
            try:
                breadth_max_positions = int(runtime._breadth_maxpos_arr[day_index])
                breadth_score = float(runtime._breadth_score_arr[day_index])
                effective_max_positions = min(int(effective_max_positions), max(0, int(breadth_max_positions)))
            except Exception:
                breadth_max_positions = int(effective_max_positions)
        risk_on_today = bool(getattr(runtime.provider, "_risk_on", np.ones(len(runtime.request.data_bundle.trading_days), dtype=bool))[day_index])
    else:
        if runtime._dd_enabled and abs(drawdown) >= runtime._dd_reduce_pct:
            effective_max_positions = max(1, int(runtime.request.max_positions * runtime._dd_reduce_scale))
            dd_state = "REDUCED"
        risk_on_today = True
        if hasattr(runtime.provider, "_risk_on"):
            try:
                risk_on_today = bool(runtime.provider._risk_on[day_index])
            except Exception:
                risk_on_today = True
        elif hasattr(runtime.provider, "_risk_on_map"):
            risk_on_today = bool(runtime.provider._risk_on_map.get(day, True))
        diagnostics_market_state = getattr(runtime.provider, "_market_state", None)
        diagnostics_trade_mode = getattr(runtime.provider, "_trade_mode", None)
        if diagnostics_market_state is not None:
            try:
                market_state = runtime._MARKET_STATE_NAMES[int(diagnostics_market_state[day_index])]
            except Exception:
                market_state = ""
        if diagnostics_trade_mode is not None:
            try:
                trade_mode = runtime._TRADE_MODE_NAMES[int(diagnostics_trade_mode[day_index])]
            except Exception:
                trade_mode = ""
    confidence_arr = getattr(runtime, "_regime_confidence_arr", None)
    if confidence_arr is not None and day_index < len(confidence_arr):
        regime_confidence = float(confidence_arr[day_index])
    duration_arr = getattr(runtime, "_regime_duration_bars_arr", None)
    if duration_arr is not None and day_index < len(duration_arr):
        regime_duration_bars = int(duration_arr[day_index])
    reason_arr = getattr(runtime, "_regime_transition_reason_arr", None)
    if reason_arr is not None and day_index < len(reason_arr):
        regime_transition_reason = str(reason_arr[day_index] or "")
    feature_arr = getattr(runtime, "_feature_availability_arr", None)
    if feature_arr is not None and day_index < len(feature_arr):
        raw_feature = feature_arr[day_index]
        feature_availability = dict(raw_feature) if isinstance(raw_feature, dict) else {}
    return {
        "effective_max_positions": int(effective_max_positions),
        "dd_state": dd_state,
        "market_state": market_state,
        "trade_mode": trade_mode,
        "benchmark_regime_on": bool(benchmark_regime_on),
        "risk_on_today": bool(risk_on_today),
        "breadth_score": float(breadth_score) if breadth_score == breadth_score else None,
        "breadth_max_positions": int(breadth_max_positions),
        "regime_engine": regime_engine,
        "regime_confidence": regime_confidence,
        "regime_duration_bars": regime_duration_bars,
        "regime_transition_reason": regime_transition_reason,
        "feature_availability": feature_availability,
        "market_state_5": market_state_5,
        "market_state_raw": market_state_raw,
        "market_state_smoothed": market_state_smoothed,
        "market_state_score": market_state_score,
        "risk_budget_multiplier": risk_budget_multiplier,
        "weekly_observation_flag": bool(weekly_observation_flag),
    }
