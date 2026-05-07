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
from backend.api.backtest_v2.runner_config_base import normalize_market_data_contract
from backend.api.backtest_v2.semantic_config_compiler import compile_semantic_config_json
from backend.api.backtest_v2.runner_config_asset import apply_asset_runtime_cfg
from backend.api.backtest_v2.runner_config_risk_exit import apply_risk_exit_runtime_cfg
from backend.api.backtest_v2.runner_config_signal import compile_signal_runtime
from backend.api.backtest_v2.runner_config_universe import apply_universe_runtime_cfg
from backend.api.backtest_v2.runner_output_helpers import build_unified_combo_execution_contract
from backend.core.config.etf_beta_contract import (
    CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS,
    CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES,
    CN_ETF_FORMAL_PHASE1_POOL_VERSION,
    normalize_etf_beta_contract,
)
from backend.core.config.models import DataSourceConfig
from backend.core.config.cn_a_governed_mainline import build_governed_a_share_contract
from backend.core.services.account_budget_runtime import build_account_budget_control
from backend.core.tools import baseline_access
from backend.research import study_loader, study_runner

_CN_STOCK_ETF_UNIFIED_FLOW_IDS = {"cn_stock_etf_v1"}
_CN_STOCK_ETF_UNIFIED_STOCK_BASELINE_ID = "baseline_V10_1"
_CN_STOCK_ETF_UNIFIED_ETF_STUDY_ID = "etf/cn_etf_first_wave_core"
_CN_STOCK_ETF_UNIFIED_ETF_WINDOW_KEY = "1626"
_CN_STOCK_ETF_UNIFIED_ETF_VARIANT_NAME = "CORE"


@dataclass(slots=True)
class _EmptyExperimentRequest:
    start_date: str | None = None
    end_date: str | None = None
    benchmark: str | None = None
    symbols: list[str] | None = None
    signal_generation: dict[str, Any] | None = None
    signal_composition: dict[str, Any] | None = None
    asset_scope: str | None = None


def _merge_nested_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested_dict(dict(merged.get(key) or {}), value)
        else:
            merged[key] = value
    return merged


def _apply_regime_engine_cfg(cfg: dict[str, Any], wb_cfg: dict[str, Any]) -> None:
    wb_regime_engine = wb_cfg.get("regime_engine") if isinstance(wb_cfg.get("regime_engine"), dict) else {}
    runtime_regime_engine = dict(cfg.get("regime_engine") or {})
    merged = _merge_nested_dict(runtime_regime_engine, wb_regime_engine)
    runtime_universe = cfg.get("universe") if isinstance(cfg.get("universe"), dict) else {}
    wb_universe = wb_cfg.get("universe") if isinstance(wb_cfg.get("universe"), dict) else {}

    engine = str(merged.get("engine") or "ma200_legacy").strip() or "ma200_legacy"
    benchmark = None
    for present, value in (
        ("benchmark" in merged, merged.get("benchmark")),
        ("benchmark" in wb_universe, wb_universe.get("benchmark")),
        ("benchmark" in runtime_universe, runtime_universe.get("benchmark")),
    ):
        if not present:
            continue
        benchmark = str(value or "").strip()
        break

    fallback = dict(merged.get("fallback") or {})
    required_blocks = fallback.get("required_blocks")
    if not isinstance(required_blocks, list) or not required_blocks:
        required_blocks = ["trend_block", "risk_block"] if engine == "market_regime_framework" else []
    fallback["required_blocks"] = [str(item) for item in required_blocks if str(item or "").strip()]
    fallback["on_feature_unavailable"] = str(
        fallback.get("on_feature_unavailable")
        or ("ma200_legacy" if engine in {"market_regime_framework", "weekly_five_state"} else "disabled")
    ).strip()
    fallback["emit_feature_availability"] = bool(
        fallback.get("emit_feature_availability", engine in {"market_regime_framework", "weekly_five_state"})
    )

    merged["engine"] = engine
    if benchmark is not None:
        merged["benchmark"] = benchmark
    merged["fallback"] = fallback
    cfg["regime_engine"] = sanitize_json(merged)


def _apply_governed_a_share_cfg(cfg: dict[str, Any], wb_cfg: dict[str, Any]) -> None:
    raw = wb_cfg.get("governed_a_share") if isinstance(wb_cfg.get("governed_a_share"), dict) else {}
    runtime_raw = cfg.get("governed_a_share") if isinstance(cfg.get("governed_a_share"), dict) else {}
    merged_raw = _merge_nested_dict(dict(runtime_raw), dict(raw))
    asset_context = cfg.get("asset_context") if isinstance(cfg.get("asset_context"), dict) else {}
    asset_scope = (
        wb_cfg.get("asset_scope")
        or cfg.get("asset_scope")
        or asset_context.get("asset_scope")
        or "cn_a_equity"
    )
    governed = build_governed_a_share_contract(merged_raw, asset_scope=asset_scope)
    if governed is not None:
        cfg["governed_a_share"] = sanitize_json(governed)


def _deepcopy_json_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(payload or {})))


def _raw_unified_etf_beta_config(semantic_cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(semantic_cfg, dict):
        return {}
    governed = semantic_cfg.get("governed_a_share") if isinstance(semantic_cfg.get("governed_a_share"), dict) else {}
    return dict(governed.get("etf_beta") or {}) if isinstance(governed.get("etf_beta"), dict) else {}


def _requested_unified_etf_component_promotion_mode(unified_runtime_seed: dict[str, Any] | None) -> str:
    if not isinstance(unified_runtime_seed, dict):
        return ""
    for key in ("etf_component_promotion_mode", "formal_etf_promotion_mode"):
        value = str(unified_runtime_seed.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _is_explicit_r1_etf_component_semantics(semantic_cfg: dict[str, Any]) -> bool:
    etf_beta = _raw_unified_etf_beta_config(semantic_cfg)
    source_entry_type = str(etf_beta.get("source_entry_type") or "").strip()
    local_policy_mode = str(etf_beta.get("local_policy_mode") or "").strip()
    exposure_policy_family = str(etf_beta.get("exposure_policy_family") or "").strip()
    r1_markers = {
        "cn_etf_broad_based_standalone_mainline_entry",
        "broad_based_rotation_mainline",
        "broad_based_standalone_mainline_v1",
    }
    return (
        source_entry_type in r1_markers
        or local_policy_mode in r1_markers
        or exposure_policy_family in r1_markers
    )


def _build_component_source_contract(
    *,
    combo_mode: str,
    source_template: str,
    config_source: str,
    contract_components: dict[str, Any],
) -> dict[str, Any]:
    runtime_entry_mode = "contract_only"
    return sanitize_json(
        {
            "contract_version": "unified_combo_component_source_contract@1",
            "source_mode": runtime_entry_mode,
            "runtime_entry_mode": runtime_entry_mode,
            "combo_mode": str(combo_mode or "").strip() or "daily_rebalanced_equal_weight_50_50",
            "source_template": str(source_template or "").strip() or "cfg_cn_stock_etf_v1",
            "config_source": str(config_source or "").strip() or "config_json",
            "provenance_role": "formal_component_source",
            "replay_anchor_policy": "contract_managed_source_resolution",
            "components": sanitize_json(_deepcopy_json_dict(contract_components)),
        }
    )


def _project_unified_combo_component_runtime_config(
    runtime_cfg: dict[str, Any],
    *,
    asset_scope: str,
) -> dict[str, Any]:
    payload = sanitize_json(_deepcopy_json_dict(runtime_cfg))
    scope = str(asset_scope or "").strip()
    governed = payload.get("governed_a_share") if isinstance(payload.get("governed_a_share"), dict) else None
    if not isinstance(governed, dict) or not governed:
        return payload
    projected = sanitize_json(_deepcopy_json_dict(governed))
    if scope == "cn_a_equity":
        projected.pop("etf_beta", None)
    elif scope == "cn_etf":
        projected.pop("stock_alpha_core", None)
    payload["governed_a_share"] = projected
    return sanitize_json(payload)


def _build_component_request(body: Any, *, asset_scope: str | None) -> _EmptyExperimentRequest:
    symbols = getattr(body, "symbols", None)
    return _EmptyExperimentRequest(
        start_date=getattr(body, "start_date", None),
        end_date=getattr(body, "end_date", None),
        benchmark=getattr(body, "benchmark", None),
        symbols=list(symbols) if isinstance(symbols, list) else None,
        signal_generation=getattr(body, "signal_generation", None),
        signal_composition=getattr(body, "signal_composition", None),
        asset_scope=str(asset_scope or "").strip() or None,
    )


def _is_unified_cn_stock_etf_template(wb_cfg: dict[str, Any]) -> bool:
    unified_runtime = wb_cfg.get("unified_runtime") if isinstance(wb_cfg.get("unified_runtime"), dict) else {}
    if bool(unified_runtime.get("enabled")):
        return True
    flow_script = wb_cfg.get("flow_script") if isinstance(wb_cfg.get("flow_script"), dict) else {}
    flow_id = str(flow_script.get("script_id") or "").strip().lower()
    governed = wb_cfg.get("governed_a_share") if isinstance(wb_cfg.get("governed_a_share"), dict) else {}
    stock_alpha = governed.get("stock_alpha_core") if isinstance(governed.get("stock_alpha_core"), dict) else {}
    etf_beta = governed.get("etf_beta") if isinstance(governed.get("etf_beta"), dict) else {}
    if flow_id in _CN_STOCK_ETF_UNIFIED_FLOW_IDS:
        return True
    return bool(stock_alpha.get("enabled")) and bool(etf_beta.get("enabled"))


def _coalesce_unified_runtime_seed(wb_cfg: dict[str, Any]) -> dict[str, Any]:
    unified_runtime = wb_cfg.get("unified_runtime") if isinstance(wb_cfg.get("unified_runtime"), dict) else {}
    return sanitize_json(_deepcopy_json_dict(unified_runtime)) if unified_runtime else {}


def _find_study_window(study: Any, *, window_key: str) -> Any:
    for window in tuple(getattr(study, "windows", ()) or ()):
        if str(getattr(window, "key", "") or "").strip() == str(window_key or "").strip():
            return window
    raise RuntimeError(
        f"unified combo ETF anchor window not found: {_CN_STOCK_ETF_UNIFIED_ETF_STUDY_ID}::{window_key}"
    )


def _find_study_variant(study: Any, *, variant_name: str) -> Any:
    for variant in tuple(getattr(study, "variants", ()) or ()):
        if str(getattr(variant, "name", "") or "").strip() == str(variant_name or "").strip():
            return variant
    raise RuntimeError(
        f"unified combo ETF anchor variant not found: {_CN_STOCK_ETF_UNIFIED_ETF_STUDY_ID}::{variant_name}"
    )


def _load_cn_stock_etf_stock_sleeve_anchor() -> tuple[dict[str, Any], dict[str, Any]]:
    record = baseline_access.load_baseline_record(_CN_STOCK_ETF_UNIFIED_STOCK_BASELINE_ID) or {}
    config_json = record.get("config_json") if isinstance(record.get("config_json"), dict) else None
    if not isinstance(config_json, dict) or not config_json:
        raise RuntimeError(
            f"unified combo stock anchor baseline is unavailable: {_CN_STOCK_ETF_UNIFIED_STOCK_BASELINE_ID}"
        )
    universe = config_json.get("universe") if isinstance(config_json.get("universe"), dict) else {}
    source_meta = {
        "source_kind": "baseline_anchor",
        "baseline_id": _CN_STOCK_ETF_UNIFIED_STOCK_BASELINE_ID,
        "linked_exp_id": str(record.get("linked_exp_id") or "").strip() or None,
        "config_hash": str(record.get("config_hash") or "").strip() or None,
        "coverage_start": str(universe.get("start") or "").strip() or None,
        "coverage_end": str(universe.get("end") or "").strip() or None,
    }
    return sanitize_json(_deepcopy_json_dict(config_json)), sanitize_json(source_meta)


def _load_cn_stock_etf_etf_sleeve_anchor() -> tuple[dict[str, Any], dict[str, Any]]:
    study = study_loader.load_study_definition(_CN_STOCK_ETF_UNIFIED_ETF_STUDY_ID)
    window = _find_study_window(study, window_key=_CN_STOCK_ETF_UNIFIED_ETF_WINDOW_KEY)
    variant = _find_study_variant(study, variant_name=_CN_STOCK_ETF_UNIFIED_ETF_VARIANT_NAME)
    request_payload = study_runner.build_request_payload(study, window, variant)
    config_json = request_payload.get("config_json") if isinstance(request_payload.get("config_json"), dict) else None
    if not isinstance(config_json, dict) or not config_json:
        raise RuntimeError(
            f"unified combo ETF anchor could not materialize config_json: {_CN_STOCK_ETF_UNIFIED_ETF_STUDY_ID}"
        )
    universe = config_json.get("universe") if isinstance(config_json.get("universe"), dict) else {}
    source_meta = {
        "source_kind": "study_anchor",
        "study_id": _CN_STOCK_ETF_UNIFIED_ETF_STUDY_ID,
        "window_key": _CN_STOCK_ETF_UNIFIED_ETF_WINDOW_KEY,
        "variant_name": _CN_STOCK_ETF_UNIFIED_ETF_VARIANT_NAME,
        "baseline_id": str(getattr(study, "baseline_id", "") or "").strip() or None,
        "coverage_start": str(universe.get("start") or "").strip() or getattr(window, "start", None),
        "coverage_end": str(universe.get("end") or "").strip() or getattr(window, "end", None),
    }
    return sanitize_json(_deepcopy_json_dict(config_json)), sanitize_json(source_meta)


def _promote_etf_component_semantic_config_to_formal_v1(semantic_cfg: dict[str, Any]) -> dict[str, Any]:
    payload = sanitize_json(_deepcopy_json_dict(semantic_cfg))
    formal_symbols = list(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS) + list(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES)
    universe = payload.get("universe") if isinstance(payload.get("universe"), dict) else {}
    universe = sanitize_json(dict(universe))
    universe["symbols"] = list(formal_symbols)
    universe["etf_symbols"] = list(formal_symbols)
    universe["price_adj"] = "none"
    payload["universe"] = universe
    payload["asset_scope"] = "cn_etf"
    payload["symbols"] = list(formal_symbols)

    governed = payload.get("governed_a_share") if isinstance(payload.get("governed_a_share"), dict) else {}
    governed = sanitize_json(dict(governed))
    raw_etf_beta = governed.get("etf_beta") if isinstance(governed.get("etf_beta"), dict) else {}
    etf_beta = normalize_etf_beta_contract(
        {
            **dict(raw_etf_beta or {}),
            "enabled": True,
            "strategy_role": "strategic_beta_stabilizer",
            "governor_boundary_mode": "consume_governor_sleeve_budget",
            "local_policy_mode": "phase1_bucket_allocation",
            "boundary_policy_mode": "formal_phase1_document_aligned_v1",
            "source_entry_type": "cn_etf_phase1_allocation_entry",
            "research_rule_family": "phase1_allocation_engine_v1",
            "exposure_policy_family": "phase1_governed_allocation_v1",
            "policy_scope": "broad_based_only",
            "broad_based_only": True,
            "phase1_scope_mode": "core_beta_plus_limited_defense",
            "core_beta_symbols": list(CN_ETF_FORMAL_PHASE1_CORE_SYMBOLS),
            "limited_defense_candidates": list(CN_ETF_FORMAL_PHASE1_LIMITED_DEFENSE_CANDIDATES),
            "core_accumulator_symbols": ["510300.SH", "510050.SH"],
            "tactical_satellite_symbols": ["510500.SH", "512100.SH"],
            "defense_asset_weights": {"511010.SH": 1.0},
            "template_asset_pool_version": CN_ETF_FORMAL_PHASE1_POOL_VERSION,
            "template_target_formal_symbols": list(formal_symbols),
            "proxy_replacement_mode": "none",
            "formal_replacement_pairs": None,
            "target_exposure_by_state_5": {},
            "min_deployable_exposure_by_state_5": {},
            "target_selected_count_by_state_5": {},
            "fallback_allowed_by_state_5": {},
            "absolute_filter_profile": None,
            "candidate_pool_profile": None,
            "selection_chain_profile": None,
            "controlled_accumulation_mode": "none",
            "core_slot_symbols": None,
            "growth_slot_symbols": None,
            "growth_seat_symbol": None,
            "fallback_mode": "none",
            "fallback_symbol": None,
            "formal_etf_pool_version": CN_ETF_FORMAL_PHASE1_POOL_VERSION,
        }
    )
    governed["etf_beta"] = sanitize_json(etf_beta)
    payload["governed_a_share"] = governed
    return payload


def _etf_component_requires_phase1_promotion(semantic_cfg: dict[str, Any]) -> bool:
    etf_beta = _raw_unified_etf_beta_config(semantic_cfg)
    source_entry_type = str(etf_beta.get("source_entry_type") or "").strip()
    local_policy_mode = str(etf_beta.get("local_policy_mode") or "").strip()
    exposure_policy_family = str(etf_beta.get("exposure_policy_family") or "").strip()
    if _is_explicit_r1_etf_component_semantics(semantic_cfg):
        return False
    phase1_markers = {
        "cn_etf_phase1_allocation_entry",
        "phase1_bucket_allocation",
        "phase1_governed_allocation_v1",
    }
    if source_entry_type in phase1_markers or local_policy_mode in phase1_markers or exposure_policy_family in phase1_markers:
        return True
    return not bool(source_entry_type or local_policy_mode or exposure_policy_family)


def _should_promote_etf_component_to_formal_v1(
    *,
    unified_runtime_seed: dict[str, Any] | None,
    semantic_cfg: dict[str, Any],
) -> bool:
    promotion_mode = _requested_unified_etf_component_promotion_mode(unified_runtime_seed)
    if promotion_mode in {"formal_phase1", "formal_mainline", "force_phase1"}:
        return True
    if promotion_mode in {"replay_only", "preserve_replay", "anchor_replay"}:
        return False
    return _etf_component_requires_phase1_promotion(semantic_cfg)


def _resolve_unified_etf_component_source_truth(
    *,
    semantic_cfg: dict[str, Any],
    promoted: bool,
) -> dict[str, Any]:
    etf_beta = _raw_unified_etf_beta_config(semantic_cfg)
    if promoted:
        return {
            "formal_alignment_status": "formal_mainline",
            "formal_etf_pool_version": CN_ETF_FORMAL_PHASE1_POOL_VERSION,
            "source_entry_type": "cn_etf_phase1_allocation_entry",
            "strategy_role": "strategic_beta_stabilizer",
            "local_policy_mode": "phase1_bucket_allocation",
            "governor_boundary_mode": "consume_governor_sleeve_budget",
        }
    return {
        "formal_alignment_status": "do_not_promote" if _is_explicit_r1_etf_component_semantics(semantic_cfg) else "research_only",
        "formal_etf_pool_version": str(etf_beta.get("formal_etf_pool_version") or "").strip() or None,
        "source_entry_type": str(etf_beta.get("source_entry_type") or "").strip() or None,
        "strategy_role": str(etf_beta.get("strategy_role") or "").strip() or None,
        "local_policy_mode": str(etf_beta.get("local_policy_mode") or "").strip() or None,
        "governor_boundary_mode": str(etf_beta.get("governor_boundary_mode") or "").strip() or None,
    }


def _runtime_execution_overrides_from_strategy_params(runtime_cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(runtime_cfg, dict):
        return {}
    strategy = runtime_cfg.get("strategy") if isinstance(runtime_cfg.get("strategy"), dict) else {}
    params = strategy.get("params") if isinstance(strategy.get("params"), dict) else {}
    overrides: dict[str, Any] = {}
    ranking_mode = str(params.get("ranking_mode") or "").strip().lower()
    if ranking_mode and ranking_mode not in {"none", "off", "disabled"}:
        overrides["enable_multifactor_rank"] = True
    elif bool(params.get("enable_residual_ranking")):
        overrides["enable_multifactor_rank"] = True
    if params.get("momentum_top_pct") is not None:
        try:
            overrides["momentum_top_pct"] = float(params.get("momentum_top_pct"))
        except Exception:
            pass
    for key in ("enable_strength_rank", "strength_ma", "strength_top_k_mode", "mf_topk"):
        if runtime_cfg.get(key) is not None:
            overrides[key] = runtime_cfg.get(key)
    return sanitize_json(overrides)


def _component_execution_overrides(
    *,
    semantic_cfg: dict[str, Any] | None,
    runtime_cfg: dict[str, Any] | None,
    existing_overrides: dict[str, Any] | None,
    allow_rank_derivation: bool = True,
) -> dict[str, Any]:
    if isinstance(existing_overrides, dict) and existing_overrides:
        return sanitize_json(dict(existing_overrides))
    if not allow_rank_derivation:
        return {}
    semantic_overrides: dict[str, Any] = {}
    if isinstance(semantic_cfg, dict):
        semantic_overrides = {
            **_semantic_ranking_execution_overrides(semantic_cfg),
            **_semantic_sizing_execution_overrides(semantic_cfg),
        }
    if semantic_overrides:
        return sanitize_json(semantic_overrides)
    return _runtime_execution_overrides_from_strategy_params(runtime_cfg)


def _build_cn_stock_etf_unified_runtime_payload(
    *,
    base_cfg: dict[str, Any],
    body: Any,
    wb_cfg: dict[str, Any],
    config_source: str,
    use_body_universe_fields: bool,
) -> dict[str, Any] | None:
    if not _is_unified_cn_stock_etf_template(wb_cfg):
        return None
    unified_runtime_seed = _coalesce_unified_runtime_seed(wb_cfg)
    stock_cfg, stock_source_meta = _load_cn_stock_etf_stock_sleeve_anchor()
    etf_cfg, etf_source_meta = _load_cn_stock_etf_etf_sleeve_anchor()
    request_universe = wb_cfg.get("universe") if isinstance(wb_cfg.get("universe"), dict) else {}
    source_contract_seed = (
        unified_runtime_seed.get("component_source_contract")
        if isinstance(unified_runtime_seed.get("component_source_contract"), dict)
        else {}
    )
    execution_contract_seed = (
        unified_runtime_seed.get("execution_contract")
        if isinstance(unified_runtime_seed.get("execution_contract"), dict)
        else {}
    )
    contract_components = (
        source_contract_seed.get("components")
        if isinstance(source_contract_seed.get("components"), dict)
        else {}
    )
    execution_components_seed = (
        execution_contract_seed.get("components")
        if isinstance(execution_contract_seed.get("components"), dict)
        else {}
    )
    combo_policy_seed = (
        execution_contract_seed.get("combo_policy")
        if isinstance(execution_contract_seed.get("combo_policy"), dict)
        else {}
    )

    def _apply_combo_window(anchor_cfg: dict[str, Any]) -> dict[str, Any]:
        payload = sanitize_json(_deepcopy_json_dict(anchor_cfg))
        universe = payload.get("universe") if isinstance(payload.get("universe"), dict) else {}
        if not universe:
            return payload
        if str(request_universe.get("start") or "").strip():
            universe["start"] = str(request_universe.get("start")).strip()
        if str(request_universe.get("end") or "").strip():
            universe["end"] = str(request_universe.get("end")).strip()
        payload["universe"] = universe
        return payload

    def _extract_sleeve_semantic_config(
        sleeve_key: str, component_key: str, default_cfg: dict[str, Any], default_source_meta: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        contract_entry = contract_components.get(component_key) if isinstance(contract_components.get(component_key), dict) else {}
        execution_entry = execution_components_seed.get(component_key) if isinstance(execution_components_seed.get(component_key), dict) else {}
        compile_input = contract_entry.get("compile_input") if isinstance(contract_entry.get("compile_input"), dict) else {}
        contract_semantic_cfg = compile_input.get("semantic_config") if isinstance(compile_input.get("semantic_config"), dict) else None
        contract_runtime_cfg = compile_input.get("runtime_config") if isinstance(compile_input.get("runtime_config"), dict) else None
        execution_runtime_cfg = execution_entry.get("runtime_config") if isinstance(execution_entry.get("runtime_config"), dict) else None
        execution_overrides_cfg = (
            execution_entry.get("execution_overrides")
            if isinstance(execution_entry.get("execution_overrides"), dict)
            else None
        )
        contract_source_meta = contract_entry.get("source") if isinstance(contract_entry.get("source"), dict) else None
        semantic_input = (
            sanitize_json(_deepcopy_json_dict(contract_semantic_cfg))
            if isinstance(contract_semantic_cfg, dict) and contract_semantic_cfg
            else sanitize_json(_deepcopy_json_dict(default_cfg))
        )
        source = (
            sanitize_json(_deepcopy_json_dict(contract_source_meta))
            if isinstance(contract_source_meta, dict)
            else default_source_meta
        )
        runtime_input = (
            sanitize_json(_deepcopy_json_dict(execution_runtime_cfg))
            if isinstance(execution_runtime_cfg, dict)
            else sanitize_json(_deepcopy_json_dict(contract_runtime_cfg))
            if isinstance(contract_runtime_cfg, dict)
            else {}
        )
        execution_overrides_input = (
            sanitize_json(_deepcopy_json_dict(execution_overrides_cfg))
            if isinstance(execution_overrides_cfg, dict)
            else {}
        )
        return semantic_input, source, runtime_input, execution_overrides_input

    stock_semantic_cfg, stock_source_meta, stock_existing_runtime, stock_existing_execution_overrides = _extract_sleeve_semantic_config(
        "stock_alpha_core",
        "stock_component",
        stock_cfg,
        stock_source_meta,
    )
    etf_semantic_cfg, etf_source_meta, etf_existing_runtime, etf_existing_execution_overrides = _extract_sleeve_semantic_config(
        "etf_beta",
        "etf_component",
        etf_cfg,
        etf_source_meta,
    )
    etf_component_promoted = _should_promote_etf_component_to_formal_v1(
        unified_runtime_seed=unified_runtime_seed,
        semantic_cfg=etf_semantic_cfg,
    )
    if etf_component_promoted:
        etf_semantic_cfg = _promote_etf_component_semantic_config_to_formal_v1(etf_semantic_cfg)
        # Promotion to the formal Phase 1 ETF sleeve must rebuild runtime truth from the
        # promoted semantic config instead of inheriting a stale research-only runtime seed.
        etf_existing_runtime = {}
    etf_source_truth = _resolve_unified_etf_component_source_truth(
        semantic_cfg=etf_semantic_cfg,
        promoted=etf_component_promoted,
    )
    etf_source_meta = sanitize_json({**dict(etf_source_meta or {}), **etf_source_truth})
    stock_runtime_input = _apply_combo_window(stock_semantic_cfg)
    etf_runtime_input = _apply_combo_window(etf_semantic_cfg)
    stock_runtime_body = _build_component_request(body, asset_scope=stock_runtime_input.get("asset_scope"))
    etf_runtime_body = _build_component_request(body, asset_scope=etf_runtime_input.get("asset_scope"))

    def _resolve_component_weight(component_key: str, default_weight: float) -> float:
        execution_entry = execution_components_seed.get(component_key) if isinstance(execution_components_seed.get(component_key), dict) else {}
        try:
            return float(execution_entry.get("weight"))
        except (TypeError, ValueError):
            pass
        component_entry = contract_components.get(component_key) if isinstance(contract_components.get(component_key), dict) else {}
        try:
            return float(component_entry.get("weight"))
        except (TypeError, ValueError):
            return default_weight

    stock_runtime = build_runtime_cfg_from_workbench(
        base_cfg,
        stock_runtime_body,
        stock_runtime_input,
        use_body_universe_fields=use_body_universe_fields,
    )
    etf_runtime = build_runtime_cfg_from_workbench(
        base_cfg,
        etf_runtime_body,
        etf_runtime_input,
        use_body_universe_fields=use_body_universe_fields,
    )
    stock_runtime_resolved = _project_unified_combo_component_runtime_config(
        stock_existing_runtime or sanitize_json(dict(stock_runtime)),
        asset_scope=str(stock_runtime_input.get("asset_scope") or "cn_a_equity"),
    )
    etf_runtime_resolved = _project_unified_combo_component_runtime_config(
        etf_existing_runtime or sanitize_json(dict(etf_runtime)),
        asset_scope=str(etf_runtime_input.get("asset_scope") or "cn_etf"),
    )
    stock_execution_overrides = _component_execution_overrides(
        semantic_cfg=stock_semantic_cfg,
        runtime_cfg=stock_runtime_resolved,
        existing_overrides=stock_existing_execution_overrides,
        allow_rank_derivation=True,
    )
    etf_execution_overrides = _component_execution_overrides(
        semantic_cfg=etf_semantic_cfg,
        runtime_cfg=etf_runtime_resolved,
        existing_overrides=etf_existing_execution_overrides,
        allow_rank_derivation=False,
    )
    combo_weights = {
        "cn_stock_trend_alpha_core": _resolve_component_weight("stock_component", 0.5),
        "cn_etf_beta": _resolve_component_weight("etf_component", 0.5),
    }
    account_budget_control_seed = (
        unified_runtime_seed.get("account_budget_control")
        if isinstance(unified_runtime_seed.get("account_budget_control"), dict)
        else {}
    )
    account_budget_control = build_account_budget_control(
        enabled=bool(account_budget_control_seed.get("enabled", True)),
        fallback_weights=combo_weights,
    )
    account_budget_control = sanitize_json(
        {
            **account_budget_control,
            "state_budget_role_map": dict(account_budget_control.get("state_budget_role_map") or {}),
        }
    )
    combo_mode = str(
        combo_policy_seed.get("mode")
        or source_contract_seed.get("combo_mode")
        or "daily_rebalanced_equal_weight_50_50"
    )
    combo_benchmark = str(
        combo_policy_seed.get("benchmark")
        or "CN_STOCK_ETF_50_50"
    )
    source_template = str(source_contract_seed.get("source_template") or "cfg_cn_stock_etf_v1")
    execution_contract = build_unified_combo_execution_contract(
        combo_mode=combo_mode,
        benchmark=combo_benchmark,
        weights=combo_weights,
        stock_runtime_config=stock_runtime_resolved,
        etf_runtime_config=etf_runtime_resolved,
        stock_execution_overrides=stock_execution_overrides,
        etf_execution_overrides=etf_execution_overrides,
        account_budget_control=account_budget_control,
    )
    contract_components = {
        "stock_component": {
            "sleeve_id": "cn_stock_trend_alpha_core",
            "asset_scope": "cn_a_equity",
            "weight": float(combo_weights.get("cn_stock_trend_alpha_core") or 0.5),
            "source": stock_source_meta,
            "compile_input": {
                "semantic_config": sanitize_json(_deepcopy_json_dict(stock_semantic_cfg)),
                "config_source": str(config_source or "config_json"),
            },
        },
        "etf_component": {
            "sleeve_id": "cn_etf_beta",
            "asset_scope": "cn_etf",
            "weight": float(combo_weights.get("cn_etf_beta") or 0.5),
            "formal_alignment_status": etf_source_truth.get("formal_alignment_status"),
            "formal_etf_pool_version": etf_source_truth.get("formal_etf_pool_version"),
            "source_entry_type": etf_source_truth.get("source_entry_type"),
            "strategy_role": etf_source_truth.get("strategy_role"),
            "local_policy_mode": etf_source_truth.get("local_policy_mode"),
            "governor_boundary_mode": etf_source_truth.get("governor_boundary_mode"),
            "source": etf_source_meta,
            "compile_input": {
                "semantic_config": sanitize_json(_deepcopy_json_dict(etf_semantic_cfg)),
                "config_source": str(config_source or "config_json"),
            },
        },
    }
    component_source_contract = _build_component_source_contract(
        combo_mode=combo_mode,
        source_template=source_template,
        config_source=str(config_source or "config_json"),
        contract_components=contract_components,
    )
    combo_context = sanitize_json(
        {
            "enabled": True,
            "contract_version": "cn_stock_etf_unified_runtime@1",
            "system_asset_scope": "cn_a_multi_sleeve",
            "combo_mode": combo_mode,
            "weights": combo_weights,
            "source_template": source_template,
            "config_source": str(config_source or "config_json"),
            "runtime_truth_source": "account_allocator",
            "account_budget_control": account_budget_control,
            "account_allocation_runtime": {
                "contract_version": "account_allocator_runtime_input@1",
                "runtime_truth_source": "account_allocator",
                "budget_owner": str(account_budget_control.get("budget_owner") or "account_allocator"),
                "budget_basis": str(account_budget_control.get("budget_basis") or "share_of_total_nav"),
                "source_mode": str(account_budget_control.get("source_mode") or "account_state_budget_map"),
                "state_source": str(account_budget_control.get("state_source") or "account_layer_state_machine"),
                "state_budget_map": dict(account_budget_control.get("state_budget_map") or {}),
                "state_budget_role_map": dict(account_budget_control.get("state_budget_role_map") or {}),
                "state_transition_policy": dict(account_budget_control.get("state_transition_policy") or {}),
                "state_edge_cash_release_policy": dict(account_budget_control.get("state_edge_cash_release_policy") or {}),
            "reference_combo": {
                "benchmark": "CN_STOCK_ETF_50_50",
                "combo_mode": combo_mode,
                "weights": combo_weights,
                "reference_only": True,
                "narrative_role": "reference_zone",
            },
            },
            "execution_contract": execution_contract,
            "component_source_contract": component_source_contract,
        }
    )
    return sanitize_json(
        {
            "enabled": bool(unified_runtime_seed.get("enabled", True)),
            "weights": dict(combo_context.get("weights") or {}),
            "runtime_truth_source": "account_allocator",
            "account_budget_control": account_budget_control,
            "account_allocation_runtime": dict(combo_context.get("account_allocation_runtime") or {}),
            "execution_contract": execution_contract,
            "component_source_contract": component_source_contract,
            "combo_context": combo_context,
        }
    )


def build_runtime_cfg_from_workbench(
    base_cfg: dict[str, Any],
    body: Any,
    wb_cfg: dict[str, Any],
    *,
    use_body_universe_fields: bool = True,
) -> dict[str, Any]:
    cfg = normalize_market_data_contract(json.loads(json.dumps(base_cfg)))
    if wb_cfg.get("universe_mode") is not None:
        cfg["universe_mode"] = str(wb_cfg.get("universe_mode") or "")
    if isinstance(wb_cfg.get("industries"), list):
        cfg["industries"] = list(wb_cfg.get("industries") or [])
    apply_asset_runtime_cfg(cfg, body, wb_cfg)
    apply_universe_runtime_cfg(
        cfg,
        body,
        wb_cfg,
        use_body_universe_fields=use_body_universe_fields,
    )
    signal_context = compile_signal_runtime(cfg, wb_cfg)
    apply_risk_exit_runtime_cfg(cfg, wb_cfg, signal_context=signal_context)
    _apply_regime_engine_cfg(cfg, wb_cfg)
    _apply_governed_a_share_cfg(cfg, wb_cfg)
    wb_data_source = wb_cfg.get("data_source") if isinstance(wb_cfg.get("data_source"), dict) else {}
    runtime_data_source = dict(cfg.get("data_source") or {})
    if wb_data_source:
        for key, value in wb_data_source.items():
            if value is None:
                continue
            runtime_data_source[key] = value
    cfg["data_source"] = sanitize_json(runtime_data_source)
    cfg = normalize_market_data_contract(cfg)
    ds_cfg = DataSourceConfig(**dict(cfg.get("data_source") or {}))
    schema_mapping = dict(cfg.get("schema_mapping") or {})
    base_mapping = dict(schema_mapping.get(ds_cfg.stocks_table) or {})
    resolved_mapping_table = str(ds_cfg.resolved_stocks_mapping_table() or "")
    resolved_stocks_table = str(ds_cfg.resolved_stocks_table() or "")
    if resolved_mapping_table and resolved_mapping_table not in schema_mapping and base_mapping:
        schema_mapping[resolved_mapping_table] = dict(base_mapping)
    if resolved_stocks_table and resolved_stocks_table not in schema_mapping:
        mapping_for_runtime = dict(schema_mapping.get(resolved_mapping_table) or base_mapping)
        if mapping_for_runtime:
            schema_mapping[resolved_stocks_table] = mapping_for_runtime
    cfg["schema_mapping"] = sanitize_json(schema_mapping)
    return sanitize_json(cfg)


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
    unified_runtime = _build_cn_stock_etf_unified_runtime_payload(
        base_cfg=base_cfg,
        body=request_body,
        wb_cfg=resolved_semantic_cfg if isinstance(resolved_semantic_cfg, dict) else semantic_input,
        config_source=config_source,
        use_body_universe_fields=use_body_universe_fields,
    )
    compiled["compiled_plan"] = sanitize_json(
        {
            **dict(compiled.get("compiled_plan") or {}),
            "runtime_config": sanitize_json(dict(runtime_cfg)),
            "execution_overrides": semantic_execution_overrides,
            "asset_context": sanitize_json(dict(runtime_cfg.get("asset_context") or {})),
            "unified_runtime": unified_runtime,
        }
    )
    compiled["runtime_config"] = sanitize_json(dict(runtime_cfg))
    if unified_runtime is not None:
        compiled["unified_runtime"] = unified_runtime
    return compiled
