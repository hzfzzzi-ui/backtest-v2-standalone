from __future__ import annotations

from typing import Any, Mapping

from backend.core.engine_vector.signal_provider import DaySignals
from backend.core.stage_pipeline.contracts import StageInputs, StageOutputs


CANDIDATE_FLOW_STAGE_KEYS: tuple[str, ...] = ("S1", "S2", "S3", "S4", "S5", "S6")


def is_candidate_flow_stage(stage_key: str) -> bool:
    return str(stage_key).upper() in CANDIDATE_FLOW_STAGE_KEYS


def build_candidate_stage_output(
    *,
    stage_key: str,
    stage_inputs: StageInputs,
    current_day: Mapping[str, Any],
    enabled: bool,
) -> StageOutputs:
    key = str(stage_key).upper()
    if key not in CANDIDATE_FLOW_STAGE_KEYS:
        raise ValueError(f"unsupported candidate flow stage: {stage_key}")
    if not enabled:
        return StageOutputs.neutral(
            key,
            stage_inputs,
            summary_fragment={"reason": "disabled_or_not_applicable"},
        )

    day_signals: DaySignals = current_day["day_signals"]
    controls = dict(current_day.get("controls") or {})
    holdings = tuple(current_day.get("holding_symbols") or ())
    candidate_symbols = tuple(str(sig.symbol).lower() for sig in day_signals.buy_signals)

    if key == "S6":
        return StageOutputs(
            stage_key=key,
            candidate_symbols=candidate_symbols,
            holding_symbols=holdings,
            buy_symbols=candidate_symbols,
            sell_symbols=stage_inputs.sell_symbols,
            payload=stage_inputs.payload,
            summary_fragment={
                "mode": "legacy_embedded",
                "buy_signal_count": len(candidate_symbols),
            },
        )
    if key == "S2":
        return StageOutputs(
            stage_key=key,
            candidate_symbols=stage_inputs.candidate_symbols or candidate_symbols,
            holding_symbols=holdings,
            sell_symbols=stage_inputs.sell_symbols,
            payload=stage_inputs.payload,
            summary_fragment={
                "mode": "legacy_embedded",
                "risk_on_today": bool(controls["risk_on_today"]),
                "benchmark_regime_on": bool(controls["benchmark_regime_on"]),
                "market_state": str(controls["market_state"]),
            },
        )
    if key == "S3":
        return StageOutputs(
            stage_key=key,
            candidate_symbols=stage_inputs.candidate_symbols or candidate_symbols,
            holding_symbols=holdings,
            sell_symbols=stage_inputs.sell_symbols,
            payload=stage_inputs.payload,
            summary_fragment={
                "mode": "legacy_embedded",
                "sector_gate_enabled": True,
            },
        )
    return StageOutputs(
        stage_key=key,
        candidate_symbols=stage_inputs.candidate_symbols or candidate_symbols,
        holding_symbols=holdings,
        sell_symbols=stage_inputs.sell_symbols,
        payload=stage_inputs.payload,
        summary_fragment={
            "mode": "legacy_embedded",
            "candidate_count": len(stage_inputs.candidate_symbols or candidate_symbols),
        },
    )
