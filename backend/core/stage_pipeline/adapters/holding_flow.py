from __future__ import annotations

from typing import Any, Mapping

from backend.core.engine_vector.signal_provider import DaySignals
from backend.core.stage_pipeline.contracts import StageInputs, StageOutputs


HOLDING_FLOW_STAGE_KEYS: tuple[str, ...] = ("S9", "S8")


def is_holding_flow_stage(stage_key: str) -> bool:
    return str(stage_key).upper() in HOLDING_FLOW_STAGE_KEYS


def build_holding_stage_output(
    *,
    stage_key: str,
    stage_inputs: StageInputs,
    current_day: Mapping[str, Any],
    enabled: bool,
) -> StageOutputs:
    key = str(stage_key).upper()
    if key not in HOLDING_FLOW_STAGE_KEYS:
        raise ValueError(f"unsupported holding flow stage: {stage_key}")
    if not enabled:
        return StageOutputs.neutral(
            key,
            stage_inputs,
            summary_fragment={"reason": "disabled_or_not_applicable"},
        )

    day_signals: DaySignals = current_day["day_signals"]
    holdings = tuple(current_day.get("holding_symbols") or ())
    sell_symbols = tuple(str(sig.symbol).lower() for sig in day_signals.sell_signals)

    if key == "S9":
        return StageOutputs(
            stage_key=key,
            holding_symbols=holdings,
            sell_symbols=sell_symbols,
            payload=stage_inputs.payload,
            summary_fragment={
                "mode": "legacy_embedded",
                "sell_signal_count": len(sell_symbols),
            },
        )
    return StageOutputs(
        stage_key=key,
        holding_symbols=holdings,
        sell_symbols=stage_inputs.sell_symbols or sell_symbols,
        payload=stage_inputs.payload,
        summary_fragment={
            "mode": "legacy_embedded",
            "effective_max_positions": int(current_day["controls"]["effective_max_positions"]),
        },
    )
