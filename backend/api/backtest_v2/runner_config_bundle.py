"""Semantic bundle + runtime config façade helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.api.backtest_v2.execution_overrides import (
    request_semantic_blocks as _request_semantic_blocks,
    semantic_ranking_execution_overrides as _semantic_ranking_execution_overrides,
    semantic_sizing_execution_overrides as _semantic_sizing_execution_overrides,
)
from backend.api.backtest_v2.semantic_config_compiler import compile_semantic_config_json
from backend.api.backtest_v2.runner_config_asset import apply_asset_runtime_cfg
from backend.api.backtest_v2.runner_config_risk_exit import apply_risk_exit_runtime_cfg
from backend.api.backtest_v2.runner_config_signal import compile_signal_runtime
from backend.api.backtest_v2.runner_config_universe import apply_universe_runtime_cfg


@dataclass(slots=True)
class _EmptyExperimentRequest:
    start_date: str | None = None
    end_date: str | None = None
    benchmark: str | None = None
    symbols: list[str] | None = None
    signal_generation: dict[str, Any] | None = None
    signal_composition: dict[str, Any] | None = None


def build_runtime_cfg_from_workbench(
    base_cfg: dict[str, Any],
    body: Any,
    wb_cfg: dict[str, Any],
    *,
    use_body_universe_fields: bool = True,
) -> dict[str, Any]:
    cfg = json.loads(json.dumps(base_cfg))
    apply_asset_runtime_cfg(cfg, body, wb_cfg)
    apply_universe_runtime_cfg(
        cfg,
        body,
        wb_cfg,
        use_body_universe_fields=use_body_universe_fields,
    )
    signal_context = compile_signal_runtime(cfg, wb_cfg)
    apply_risk_exit_runtime_cfg(cfg, wb_cfg, signal_context=signal_context)
    return cfg


def compile_semantic_config_bundle(
    *,
    base_cfg: dict[str, Any],
    body: Any | None,
    semantic_cfg: dict[str, Any],
    config_source: str,
    use_body_universe_fields: bool,
) -> dict[str, Any]:
    request_body = body if body is not None else _EmptyExperimentRequest()
    semantic_input = sanitize_json(dict(semantic_cfg or {}))
    request_semantic_blocks = _request_semantic_blocks(request_body)
    if request_semantic_blocks:
        semantic_input = sanitize_json({**semantic_input, **request_semantic_blocks})
    semantic_execution_overrides = {
        **_semantic_ranking_execution_overrides(semantic_input),
        **_semantic_sizing_execution_overrides(semantic_input),
    }
    compiled = compile_semantic_config_json(
        semantic_input,
        compiled_plan_payload={"execution_overrides": semantic_execution_overrides},
        config_source=config_source,
    )
    resolved_semantic_cfg = (
        ((compiled.get("resolved_config") or {}).get("config_json"))
        if isinstance(compiled.get("resolved_config"), dict)
        else None
    )
    runtime_cfg = build_runtime_cfg_from_workbench(
        base_cfg,
        request_body,
        resolved_semantic_cfg if isinstance(resolved_semantic_cfg, dict) else semantic_input,
        use_body_universe_fields=use_body_universe_fields,
    )
    compiled["compiled_plan"] = sanitize_json(
        {
            **dict(compiled.get("compiled_plan") or {}),
            "runtime_config": sanitize_json(dict(runtime_cfg)),
            "execution_overrides": semantic_execution_overrides,
            "asset_context": sanitize_json(dict(runtime_cfg.get("asset_context") or {})),
        }
    )
    compiled["runtime_config"] = sanitize_json(dict(runtime_cfg))
    return compiled
