from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from backend.core.config.cn_a_governed_mainline import build_governor_budget_snapshot


_BULLISH_STATE_NAMES = {"BULL", "BULL_MAIN"}
_LIGHT_STATE_NAMES = {"LIGHT", "LIGHT_TREND"}
_TRANS_DOWN_STATE_NAMES = {"TRANS_DOWN", "TURN_WEAK"}
_TRANS_UP_STATE_NAMES = {"TRANS_UP", "TURN_STRONG"}
_BEARISH_STATE_NAMES = {"BEAR", "DEFENSIVE", "RISK_OFF"}


def _resolve_runtime_asset_scope(runtime: Any) -> str:
    request = getattr(runtime, "request", None)
    asset_scope = str(getattr(request, "asset_scope", "") or "").strip()
    if asset_scope:
        return asset_scope
    request_asset_context = getattr(request, "asset_context", None)
    if isinstance(request_asset_context, dict):
        asset_scope = str(request_asset_context.get("asset_scope") or "").strip()
        if asset_scope:
            return asset_scope
    asset_context = getattr(request, "asset_context", None)
    if isinstance(asset_context, dict):
        asset_scope = str(asset_context.get("asset_scope") or "").strip()
        if asset_scope:
            return asset_scope
    runtime_asset_context = getattr(runtime, "asset_context", None)
    if isinstance(runtime_asset_context, dict):
        asset_scope = str(runtime_asset_context.get("asset_scope") or "").strip()
        if asset_scope:
            return asset_scope
    data_bundle = getattr(request, "data_bundle", None)
    universe_meta = getattr(data_bundle, "universe_meta", None)
    if isinstance(universe_meta, dict):
        asset_scope = str(universe_meta.get("asset_scope") or "").strip()
        if asset_scope:
            return asset_scope
    provider = getattr(runtime, "provider", None)
    if provider is not None and hasattr(provider, "_etf_beta_slot_cap_arr"):
        return "cn_etf"
    return "cn_a_equity"


def compute_day_controls(runtime: Any, day_index: int, day: date, drawdown: float) -> dict[str, Any]:
    asset_scope = _resolve_runtime_asset_scope(runtime)
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
    base_state_5 = ""
    effective_state_5 = ""
    coarse_state = ""
    effective_coarse_state = ""
    reason_codes: list[str] = []
    block_scores: dict[str, Any] = {}
    subscores: dict[str, Any] = {}
    manual_override: dict[str, Any] = {}
    state_stability_metrics: dict[str, Any] = {}
    defense_bias = None
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
            formal_risk_budget_arr = getattr(runtime.provider, "_regime_risk_budget_multiplier_arr", None)
            weekly_flag_arr = getattr(runtime.provider, "_weekly_observation_flag_arr", None)
            base_state_arr = getattr(runtime.provider, "_base_state_5_arr", None)
            effective_state_arr = getattr(runtime.provider, "_effective_state_5_arr", None)
            coarse_state_arr = getattr(runtime.provider, "_coarse_state_arr", None)
            effective_coarse_state_arr = getattr(runtime.provider, "_effective_coarse_state_arr", None)
            reason_codes_arr = getattr(runtime.provider, "_reason_codes_arr", None)
            block_scores_arr = getattr(runtime.provider, "_block_scores_arr", None)
            subscores_arr = getattr(runtime.provider, "_subscores_arr", None)
            manual_override_arr = getattr(runtime.provider, "_manual_override_arr", None)
            state_stability_arr = getattr(runtime.provider, "_state_stability_metrics_arr", None)
            defense_bias_arr = getattr(runtime.provider, "_defense_bias_arr", None)
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
            if isinstance(formal_risk_budget_arr, np.ndarray) and day_index < len(formal_risk_budget_arr):
                risk_budget_multiplier = float(formal_risk_budget_arr[day_index])
            if isinstance(weekly_flag_arr, np.ndarray) and day_index < len(weekly_flag_arr):
                weekly_observation_flag = bool(weekly_flag_arr[day_index])
            if isinstance(base_state_arr, np.ndarray) and day_index < len(base_state_arr):
                base_state_5 = str(base_state_arr[day_index] or "")
            if isinstance(effective_state_arr, np.ndarray) and day_index < len(effective_state_arr):
                effective_state_5 = str(effective_state_arr[day_index] or "")
            if isinstance(coarse_state_arr, np.ndarray) and day_index < len(coarse_state_arr):
                coarse_state = str(coarse_state_arr[day_index] or "")
            if isinstance(effective_coarse_state_arr, np.ndarray) and day_index < len(effective_coarse_state_arr):
                effective_coarse_state = str(effective_coarse_state_arr[day_index] or "")
            if isinstance(reason_codes_arr, np.ndarray) and day_index < len(reason_codes_arr):
                raw_reason_codes = reason_codes_arr[day_index]
                if isinstance(raw_reason_codes, (list, tuple)):
                    reason_codes = [str(item).strip() for item in raw_reason_codes if str(item).strip()]
            if isinstance(block_scores_arr, np.ndarray) and day_index < len(block_scores_arr):
                raw_block_scores = block_scores_arr[day_index]
                block_scores = dict(raw_block_scores) if isinstance(raw_block_scores, dict) else {}
            if isinstance(subscores_arr, np.ndarray) and day_index < len(subscores_arr):
                raw_subscores = subscores_arr[day_index]
                subscores = dict(raw_subscores) if isinstance(raw_subscores, dict) else {}
            if isinstance(manual_override_arr, np.ndarray) and day_index < len(manual_override_arr):
                raw_manual_override = manual_override_arr[day_index]
                manual_override = dict(raw_manual_override) if isinstance(raw_manual_override, dict) else {}
            if isinstance(state_stability_arr, np.ndarray) and day_index < len(state_stability_arr):
                raw_state_stability = state_stability_arr[day_index]
                state_stability_metrics = dict(raw_state_stability) if isinstance(raw_state_stability, dict) else {}
            if isinstance(defense_bias_arr, np.ndarray) and day_index < len(defense_bias_arr):
                defense_bias = float(defense_bias_arr[day_index])
            market_state_5 = str(effective_state_5 or market_state_smoothed or market_state or "")
            state_counter_name = str(market_state_5 or market_state or "").strip().upper()
            if state_counter_name in _BULLISH_STATE_NAMES:
                runtime.market_filter_bull_days += 1
            elif state_counter_name in _LIGHT_STATE_NAMES:
                pass
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
        etf_slot_cap_arr = getattr(runtime.provider, "_etf_beta_slot_cap_arr", None)
        if asset_scope == "cn_etf" and isinstance(etf_slot_cap_arr, np.ndarray) and day_index < len(etf_slot_cap_arr):
            etf_slot_cap = max(0, int(etf_slot_cap_arr[day_index]))
            effective_max_positions = min(int(effective_max_positions), int(etf_slot_cap))
            breadth_max_positions = min(int(breadth_max_positions), int(etf_slot_cap))
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
    governor_budget = build_governor_budget_snapshot(
        asset_scope=asset_scope,
        hard_max_positions=getattr(runtime.request, "max_positions", 0),
        effective_max_positions=effective_max_positions,
        risk_budget_multiplier=risk_budget_multiplier,
        drawdown=drawdown,
        drawdown_state=dd_state,
        regime_transition_reason=regime_transition_reason,
        base_state_5=base_state_5 or market_state_5,
        effective_state_5=effective_state_5 or market_state_5,
        coarse_state=coarse_state,
        effective_coarse_state=effective_coarse_state,
        reason_codes=reason_codes,
        defense_bias=defense_bias,
        manual_override=manual_override,
        breadth_max_positions=breadth_max_positions,
        positions_after_sell=sum(1 for qty in getattr(runtime, "positions", {}).values() if int(qty) > 0),
    )
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
        "base_state_5": base_state_5 or market_state_5,
        "effective_state_5": effective_state_5 or market_state_5,
        "coarse_state": coarse_state,
        "effective_coarse_state": effective_coarse_state,
        "reason_codes": reason_codes,
        "block_scores": block_scores,
        "subscores": subscores,
        "manual_override": manual_override,
        "state_stability_metrics": state_stability_metrics,
        "defense_bias": defense_bias,
        "weekly_observation_flag": bool(weekly_observation_flag),
        "governor_budget": governor_budget,
    }
