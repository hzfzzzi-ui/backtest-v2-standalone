"""Runner request/config compilation façade.

This module preserves the historical helper entry points used by
`runner_impl.py` and tests while the actual logic lives in focused
config-domain modules.
"""

from __future__ import annotations

from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.api.backtest_v2.runner_config_base import (
    assert_locked_candidate_request_supported as _assert_locked_candidate_request_supported,
    build_locked_candidate_execution_context as _build_locked_candidate_execution_context,
    load_base_config as _load_base_config,
)
from backend.api.backtest_v2.runner_config_bundle import (
    build_runtime_cfg_from_workbench as _build_runtime_cfg_from_workbench,
    compile_semantic_config_bundle as _compile_semantic_config_bundle,
)


def _execution_override_snapshot(overrides: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "symbols",
        "start_date",
        "end_date",
        "benchmark",
        "compare_symbol",
        "initial_capital",
        "max_positions",
        "base_order_value",
        "lot_size",
        "universe_limit",
        "fast_mode",
        "asset_scope",
        "universe_mode",
        "industries",
        "price_adj",
        "enable_strength_rank",
        "strength_ma",
        "strength_top_k_mode",
        "enable_multifactor_rank",
        "mf_topk",
        "mf_concentrate_scale",
        "mf_rank_gate_mode",
        "momentum_top_pct",
        "residual_window",
        "residual_benchmark_weight",
        "residual_industry_weight",
        "industry_relative_mode",
        "industry_relative_regime_mode",
        "residual_weight_regime_mode",
        "residual_benchmark_weight_fallback",
        "residual_industry_weight_fallback",
        "breakout_quality_gate_min_score",
        "breakout_quality_margin_cap_pct",
        "breakout_quality_fade_cap_pct",
        "breakout_quality_open_gap_cap_pct",
        "leadership_route_bucket_count",
        "residual_window_regime_mode",
        "residual_window_fallback",
        "residual_window_regime_fast_ma",
        "residual_window_regime_slow_ma",
        "residual_refine_mode",
        "residual_refine_weight",
        "industry_second_stage_min_industry_score",
        "residual_weight",
        "sector_weight",
        "quality_weight",
        "weight_mode",
        "min_positions",
        "tilt_strength",
        "tilt_top_n",
        "tilt_bottom_n",
        "score_weight_min_scale",
        "score_weight_max_scale",
        "candidate_plan_mode",
        "cash_aware_search_top_n",
        "asset_context",
    )
    return sanitize_json({key: overrides.get(key) for key in keys if key in overrides})


def _looks_like_backend_runtime_config(cfg: dict[str, Any] | None) -> bool:
    if not isinstance(cfg, dict):
        return False
    return isinstance(cfg.get("db"), dict) and isinstance(cfg.get("schema_mapping"), dict)


__all__ = [
    "_assert_locked_candidate_request_supported",
    "_build_locked_candidate_execution_context",
    "_build_runtime_cfg_from_workbench",
    "_compile_semantic_config_bundle",
    "_execution_override_snapshot",
    "_load_base_config",
    "_looks_like_backend_runtime_config",
]
