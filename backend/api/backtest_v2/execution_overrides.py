from __future__ import annotations

from typing import Any

from backend.api.shared.json_utils import sanitize_json


def to_int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def request_semantic_blocks(body: Any | None) -> dict[str, Any]:
    if body is None:
        return {}
    payload: dict[str, Any] = {}
    if isinstance(getattr(body, "signal_generation", None), dict):
        payload["signal_generation"] = sanitize_json(dict(body.signal_generation))
    if isinstance(getattr(body, "signal_composition", None), dict):
        payload["signal_composition"] = sanitize_json(dict(body.signal_composition))
    return payload


def semantic_ranking_execution_overrides(wb_cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(wb_cfg, dict):
        return {}
    signal_generation = wb_cfg.get("signal_generation") if isinstance(wb_cfg.get("signal_generation"), dict) else {}
    ranking = signal_generation.get("ranking") if isinstance(signal_generation.get("ranking"), dict) else {}
    overrides: dict[str, Any] = {}
    ranking_mode = str(ranking.get("score_source_mode") or "none").strip().lower()
    if ranking.get("enable_strength_rank") is not None:
        overrides["enable_strength_rank"] = bool(ranking.get("enable_strength_rank"))
    if ranking.get("strength_ma") is not None:
        overrides["strength_ma"] = int(ranking.get("strength_ma"))
    if ranking.get("strength_top_k_mode") is not None:
        overrides["strength_top_k_mode"] = str(ranking.get("strength_top_k_mode"))
    if ranking.get("enable_multifactor_rank") is not None:
        overrides["enable_multifactor_rank"] = bool(ranking.get("enable_multifactor_rank"))
    elif ranking_mode and ranking_mode != "none":
        overrides["enable_multifactor_rank"] = True
    if ranking.get("mf_topk") is not None:
        overrides["mf_topk"] = int(ranking.get("mf_topk"))
    if ranking.get("mf_concentrate_scale") is not None:
        overrides["mf_concentrate_scale"] = float(ranking.get("mf_concentrate_scale"))
    if ranking.get("mf_rank_gate_mode") is not None:
        overrides["mf_rank_gate_mode"] = str(ranking.get("mf_rank_gate_mode"))
    if ranking.get("momentum_top_pct") is not None:
        overrides["momentum_top_pct"] = float(ranking.get("momentum_top_pct"))
    if ranking.get("residual_window") is not None:
        overrides["residual_window"] = int(ranking.get("residual_window"))
    if ranking.get("leadership_route_bucket_count") is not None:
        overrides["leadership_route_bucket_count"] = int(ranking.get("leadership_route_bucket_count"))
    if ranking.get("residual_benchmark_weight") is not None:
        overrides["residual_benchmark_weight"] = float(ranking.get("residual_benchmark_weight"))
    if ranking.get("residual_industry_weight") is not None:
        overrides["residual_industry_weight"] = float(ranking.get("residual_industry_weight"))
    if ranking.get("industry_relative_mode") is not None:
        overrides["industry_relative_mode"] = str(ranking.get("industry_relative_mode"))
    if ranking.get("industry_relative_regime_mode") is not None:
        overrides["industry_relative_regime_mode"] = str(ranking.get("industry_relative_regime_mode"))
    if ranking.get("residual_weight_regime_mode") is not None:
        overrides["residual_weight_regime_mode"] = str(ranking.get("residual_weight_regime_mode"))
    if ranking.get("residual_benchmark_weight_fallback") is not None:
        overrides["residual_benchmark_weight_fallback"] = float(ranking.get("residual_benchmark_weight_fallback"))
    if ranking.get("residual_industry_weight_fallback") is not None:
        overrides["residual_industry_weight_fallback"] = float(ranking.get("residual_industry_weight_fallback"))
    if ranking.get("breakout_quality_gate_min_score") is not None:
        overrides["breakout_quality_gate_min_score"] = float(ranking.get("breakout_quality_gate_min_score"))
    if ranking.get("breakout_quality_margin_cap_pct") is not None:
        overrides["breakout_quality_margin_cap_pct"] = float(ranking.get("breakout_quality_margin_cap_pct"))
    if ranking.get("breakout_quality_fade_cap_pct") is not None:
        overrides["breakout_quality_fade_cap_pct"] = float(ranking.get("breakout_quality_fade_cap_pct"))
    if ranking.get("breakout_quality_open_gap_cap_pct") is not None:
        overrides["breakout_quality_open_gap_cap_pct"] = float(ranking.get("breakout_quality_open_gap_cap_pct"))
    if ranking.get("residual_window_regime_mode") is not None:
        overrides["residual_window_regime_mode"] = str(ranking.get("residual_window_regime_mode"))
    if ranking.get("residual_window_fallback") is not None:
        overrides["residual_window_fallback"] = int(ranking.get("residual_window_fallback"))
    if ranking.get("residual_window_regime_fast_ma") is not None:
        overrides["residual_window_regime_fast_ma"] = int(ranking.get("residual_window_regime_fast_ma"))
    if ranking.get("residual_window_regime_slow_ma") is not None:
        overrides["residual_window_regime_slow_ma"] = int(ranking.get("residual_window_regime_slow_ma"))
    if ranking.get("residual_refine_mode") is not None:
        overrides["residual_refine_mode"] = str(ranking.get("residual_refine_mode"))
    if ranking.get("residual_refine_weight") is not None:
        overrides["residual_refine_weight"] = float(ranking.get("residual_refine_weight"))
    if ranking.get("industry_second_stage_min_industry_score") is not None:
        overrides["industry_second_stage_min_industry_score"] = float(
            ranking.get("industry_second_stage_min_industry_score")
        )
    if ranking.get("residual_weight") is not None:
        overrides["residual_weight"] = float(ranking.get("residual_weight"))
    if ranking.get("sector_weight") is not None:
        overrides["sector_weight"] = float(ranking.get("sector_weight"))
    if ranking.get("quality_weight") is not None:
        overrides["quality_weight"] = float(ranking.get("quality_weight"))
    return sanitize_json(overrides)


def semantic_sizing_execution_overrides(wb_cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(wb_cfg, dict):
        return {}
    sizing = wb_cfg.get("sizing") if isinstance(wb_cfg.get("sizing"), dict) else {}
    if not sizing:
        return {}
    overrides: dict[str, Any] = {}
    if sizing.get("weight_mode") is not None:
        overrides["weight_mode"] = str(sizing.get("weight_mode"))
    if sizing.get("min_positions") is not None:
        overrides["min_positions"] = int(sizing.get("min_positions"))
    if sizing.get("tilt_strength") is not None:
        overrides["tilt_strength"] = float(sizing.get("tilt_strength"))
    if sizing.get("tilt_top_n") is not None:
        overrides["tilt_top_n"] = int(sizing.get("tilt_top_n"))
    if sizing.get("tilt_bottom_n") is not None:
        overrides["tilt_bottom_n"] = int(sizing.get("tilt_bottom_n"))
    if sizing.get("score_weight_min_scale") is not None:
        overrides["score_weight_min_scale"] = float(sizing.get("score_weight_min_scale"))
    if sizing.get("score_weight_max_scale") is not None:
        overrides["score_weight_max_scale"] = float(sizing.get("score_weight_max_scale"))
    if sizing.get("candidate_plan_mode") is not None:
        overrides["candidate_plan_mode"] = str(sizing.get("candidate_plan_mode"))
    if sizing.get("cash_aware_search_top_n") is not None:
        overrides["cash_aware_search_top_n"] = int(sizing.get("cash_aware_search_top_n"))
    if sizing.get("rotation_replace_enabled") is not None:
        overrides["rotation_replace_enabled"] = bool(sizing.get("rotation_replace_enabled"))
    if sizing.get("rotation_replace_only_strong_risk_on") is not None:
        overrides["rotation_replace_only_strong_risk_on"] = bool(sizing.get("rotation_replace_only_strong_risk_on"))
    if sizing.get("rotation_replace_max_swaps_per_day") is not None:
        overrides["rotation_replace_max_swaps_per_day"] = int(sizing.get("rotation_replace_max_swaps_per_day"))
    if sizing.get("rotation_replace_candidate_top_n") is not None:
        overrides["rotation_replace_candidate_top_n"] = int(sizing.get("rotation_replace_candidate_top_n"))
    if sizing.get("rotation_replace_min_score_gap") is not None:
        overrides["rotation_replace_min_score_gap"] = float(sizing.get("rotation_replace_min_score_gap"))
    return sanitize_json(overrides)


def compile_multi_alpha_runtime_payload(wb_cfg: dict[str, Any]) -> dict[str, Any] | None:
    signal_generation = wb_cfg.get("signal_generation") if isinstance(wb_cfg.get("signal_generation"), dict) else {}
    modules = signal_generation.get("modules") if isinstance(signal_generation.get("modules"), list) else []
    if not modules:
        return None

    signal_generation_payload: dict[str, Any] = {"modules": []}
    for raw_module in modules:
        if not isinstance(raw_module, dict):
            continue
        module_name = str(raw_module.get("name") or "").strip().lower()
        if not module_name:
            continue
        module_payload: dict[str, Any] = {
            "name": module_name,
            "alpha_id": str(raw_module.get("alpha_id") or module_name).strip() or module_name,
        }
        if raw_module.get("enabled") is not None:
            module_payload["enabled"] = bool(raw_module.get("enabled"))
        if raw_module.get("family") is not None:
            module_payload["family"] = str(raw_module.get("family"))
        if isinstance(raw_module.get("params"), dict):
            module_payload["params"] = sanitize_json(dict(raw_module.get("params") or {}))
        signal_generation_payload["modules"].append(sanitize_json(module_payload))

    signal_composition = wb_cfg.get("signal_composition") if isinstance(wb_cfg.get("signal_composition"), dict) else {}
    signal_composition_payload: dict[str, Any] = {}
    if signal_composition.get("enabled") is not None:
        signal_composition_payload["enabled"] = bool(signal_composition.get("enabled"))
    if signal_composition.get("compose_mode") is not None:
        signal_composition_payload["compose_mode"] = str(signal_composition.get("compose_mode")).strip().upper()
    if signal_composition.get("same_symbol_policy") is not None:
        signal_composition_payload["same_symbol_policy"] = str(signal_composition.get("same_symbol_policy")).strip().upper()
    if signal_composition.get("holding_ownership") is not None:
        signal_composition_payload["holding_ownership"] = str(signal_composition.get("holding_ownership")).strip().upper()
    if isinstance(signal_composition.get("modules"), list):
        signal_composition_payload["modules"] = sanitize_json(
            [
                {
                    **({"name": str(item.get("name") or "").strip().lower()} if str(item.get("name") or "").strip() else {}),
                    **({"enabled": bool(item.get("enabled"))} if item.get("enabled") is not None else {}),
                    **({"role": str(item.get("role"))} if item.get("role") is not None else {}),
                    **({"weight": float(item.get("weight"))} if item.get("weight") is not None else {}),
                    **({"priority": int(item.get("priority"))} if item.get("priority") is not None else {}),
                }
                for item in signal_composition.get("modules")
                if isinstance(item, dict)
            ]
        )
    if isinstance(signal_composition.get("regime_matrix"), dict):
        signal_composition_payload["regime_matrix"] = sanitize_json(
            {
                str(key): [str(value) for value in values]
                for key, values in signal_composition.get("regime_matrix", {}).items()
                if isinstance(values, list)
            }
        )

    return sanitize_json(
        {
            "enabled": True,
            "signal_generation": signal_generation_payload,
            "signal_composition": signal_composition_payload,
        }
    )
