from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np


def compute_day_controls(runtime: Any, day_index: int, day: date, drawdown: float) -> dict[str, Any]:
    effective_max_positions = int(runtime.request.max_positions)
    dd_state = "NORMAL"
    market_state = ""
    trade_mode = ""
    benchmark_regime_on = True
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
            mult = float(runtime._mf_mult_arr[day_index])
            effective_max_positions = max(0, int(round(float(effective_max_positions) * max(0.0, mult))))
            market_state = runtime._MARKET_STATE_NAMES[state]
            trade_mode = runtime._TRADE_MODE_NAMES[0 if state == 0 else 1 if state in (1, 2) else 2]
            if state == 0:
                runtime.market_filter_bull_days += 1
                runtime.trade_mode_main_days += 1
            elif state == 1:
                runtime.market_state_trans_down_days += 1
                runtime.trade_mode_light_days += 1
            elif state == 2:
                runtime.market_state_trans_up_days += 1
                runtime.trade_mode_light_days += 1
            else:
                runtime.market_filter_bear_days += 1
                runtime.trade_mode_notrade_days += 1
        else:
            market_state = "BULL"
            trade_mode = "TREND_MAIN"
        benchmark_regime_on = bool(runtime._br_gate_arr[day_index]) if runtime._br_enabled else True
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
    return {
        "effective_max_positions": int(effective_max_positions),
        "dd_state": dd_state,
        "market_state": market_state,
        "trade_mode": trade_mode,
        "benchmark_regime_on": bool(benchmark_regime_on),
        "risk_on_today": bool(risk_on_today),
    }
