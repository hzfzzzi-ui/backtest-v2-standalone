from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from backend.core.engine_vector.signal_provider import DaySignals


def postprocess_day_signals(
    runtime: Any,
    *,
    day_index: int,
    day_signals: DaySignals,
    controls: Mapping[str, Any],
) -> DaySignals:
    if runtime.route_id != "provider_breakout_runtime":
        return day_signals
    buy_signals = list(day_signals.buy_signals)
    if runtime._br_enabled and not bool(controls["benchmark_regime_on"]):
        buy_signals = []
    if runtime._mf_enabled and int(runtime._mf_state_arr[day_index]) == 3:
        buy_signals = []
    return replace(day_signals, buy_signals=buy_signals)
