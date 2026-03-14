from __future__ import annotations

from typing import Any, Iterable


def is_stage_disabled(disabled_stages: Iterable[str], stage_key: str) -> bool:
    return str(stage_key).upper() in {str(stage).upper() for stage in disabled_stages}


def stage_is_applicable(runtime: Any, stage_key: str) -> bool:
    key = str(stage_key).upper()
    if is_stage_disabled(getattr(runtime.request, "disabled_stages", ()), key):
        return False
    if key == "S2":
        return bool(
            runtime.route_id in {"provider_breakout_runtime", "regime_router_inline_runtime", "multi_alpha_inline_runtime"}
            or (runtime._market_filter_cfg is not None and runtime._market_filter_cfg.enabled)
            or (runtime._benchmark_regime_cfg is not None and runtime._benchmark_regime_cfg.enabled)
        )
    if key == "S3":
        return bool(getattr(runtime.request.strategy, "enable_sector_gate", False))
    if key == "S8":
        return bool(runtime._dd_enabled)
    return True
