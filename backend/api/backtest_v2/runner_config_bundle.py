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
from backend.core.config.models import DataSourceConfig
from backend.core.config.cn_a_governed_mainline import build_governed_a_share_contract

_CN_STOCK_ETF_UNIFIED_FLOW_IDS = {"cn_stock_etf_v1"}


@dataclass(slots=True)
class _EmptyExperimentRequest:
    start_date: str | None = None
    end_date: str | None = None
    benchmark: str | None = None
    symbols: list[str] | None = None
    signal_generation: dict[str, Any] | None = None
    signal_composition: dict[str, Any] | None = None


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


def _is_unified_cn_stock_etf_template(wb_cfg: dict[str, Any]) -> bool:
    flow_script = wb_cfg.get("flow_script") if isinstance(wb_cfg.get("flow_script"), dict) else {}
    flow_id = str(flow_script.get("script_id") or "").strip().lower()
    governed = wb_cfg.get("governed_a_share") if isinstance(wb_cfg.get("governed_a_share"), dict) else {}
    stock_alpha = governed.get("stock_alpha_core") if isinstance(governed.get("stock_alpha_core"), dict) else {}
    etf_beta = governed.get("etf_beta") if isinstance(governed.get("etf_beta"), dict) else {}
    if flow_id in _CN_STOCK_ETF_UNIFIED_FLOW_IDS:
        return True
    return bool(stock_alpha.get("enabled")) and bool(etf_beta.get("enabled"))


def _build_cn_stock_etf_stock_sleeve_cfg(wb_cfg: dict[str, Any]) -> dict[str, Any]:
    sleeve_cfg = _deepcopy_json_dict(wb_cfg)
    sleeve_cfg["asset_scope"] = "cn_a_equity"
    governed = sleeve_cfg.get("governed_a_share") if isinstance(sleeve_cfg.get("governed_a_share"), dict) else {}
    stock_alpha = governed.get("stock_alpha_core") if isinstance(governed.get("stock_alpha_core"), dict) else {}
    etf_beta = governed.get("etf_beta") if isinstance(governed.get("etf_beta"), dict) else {}
    stock_alpha["enabled"] = True
    etf_beta["enabled"] = False
    governed["stock_alpha_core"] = stock_alpha
    governed["etf_beta"] = etf_beta
    sleeve_cfg["governed_a_share"] = governed
    flow_script = sleeve_cfg.get("flow_script") if isinstance(sleeve_cfg.get("flow_script"), dict) else {}
    if flow_script:
        flow_script["script_id"] = f"{str(flow_script.get('script_id') or 'cn_stock_etf_v1').strip()}_stock_sleeve"
        sleeve_cfg["flow_script"] = flow_script
    return sanitize_json(sleeve_cfg)


def _build_cn_stock_etf_etf_sleeve_cfg(wb_cfg: dict[str, Any]) -> dict[str, Any]:
    sleeve_cfg = _deepcopy_json_dict(wb_cfg)
    sleeve_cfg["asset_scope"] = "cn_etf"
    sleeve_cfg["universe_mode"] = "CUSTOM"
    universe = sleeve_cfg.get("universe") if isinstance(sleeve_cfg.get("universe"), dict) else {}
    universe["benchmark"] = ""
    universe["price_adj"] = "none"
    universe["symbols"] = ["cn_etf_first_wave_core"]
    sleeve_cfg["universe"] = universe
    data_source = sleeve_cfg.get("data_source") if isinstance(sleeve_cfg.get("data_source"), dict) else {}
    data_source["stocks_table"] = "pams_cn_etf_daily"
    data_source["data_role"] = str(data_source.get("data_role") or "v1")
    sleeve_cfg["data_source"] = data_source
    governed = sleeve_cfg.get("governed_a_share") if isinstance(sleeve_cfg.get("governed_a_share"), dict) else {}
    stock_alpha = governed.get("stock_alpha_core") if isinstance(governed.get("stock_alpha_core"), dict) else {}
    etf_beta = governed.get("etf_beta") if isinstance(governed.get("etf_beta"), dict) else {}
    stock_alpha["enabled"] = False
    etf_beta["enabled"] = True
    governed["stock_alpha_core"] = stock_alpha
    governed["etf_beta"] = etf_beta
    sleeve_cfg["governed_a_share"] = governed
    flow_script = sleeve_cfg.get("flow_script") if isinstance(sleeve_cfg.get("flow_script"), dict) else {}
    if flow_script:
        flow_script["script_id"] = f"{str(flow_script.get('script_id') or 'cn_stock_etf_v1').strip()}_etf_sleeve"
        sleeve_cfg["flow_script"] = flow_script
    return sanitize_json(sleeve_cfg)


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
    stock_cfg = _build_cn_stock_etf_stock_sleeve_cfg(wb_cfg)
    etf_cfg = _build_cn_stock_etf_etf_sleeve_cfg(wb_cfg)
    stock_runtime = build_runtime_cfg_from_workbench(
        base_cfg,
        body,
        stock_cfg,
        use_body_universe_fields=use_body_universe_fields,
    )
    etf_runtime = build_runtime_cfg_from_workbench(
        base_cfg,
        body,
        etf_cfg,
        use_body_universe_fields=use_body_universe_fields,
    )
    combo_context = sanitize_json(
        {
            "enabled": True,
            "contract_version": "cn_stock_etf_unified_runtime@1",
            "system_asset_scope": "cn_a_multi_sleeve",
            "combo_mode": "daily_rebalanced_equal_weight_50_50",
            "weights": {
                "cn_stock_trend_alpha_core": 0.5,
                "cn_etf_beta": 0.5,
            },
            "source_template": "cfg_cn_stock_etf_v1",
            "config_source": str(config_source or "config_json"),
            "combo_components": {
                "stock_component": {
                    "sleeve_id": "cn_stock_trend_alpha_core",
                    "asset_scope": "cn_a_equity",
                    "weight": 0.5,
                },
                "etf_component": {
                    "sleeve_id": "cn_etf_beta",
                    "asset_scope": "cn_etf",
                    "weight": 0.5,
                },
            },
        }
    )
    return sanitize_json(
        {
            "enabled": True,
            "combo_context": combo_context,
            "sleeves": {
                "stock_alpha_core": {
                    "sleeve_id": "cn_stock_trend_alpha_core",
                    "asset_scope": "cn_a_equity",
                    "semantic_config": stock_cfg,
                    "runtime_config": sanitize_json(dict(stock_runtime)),
                },
                "etf_beta": {
                    "sleeve_id": "cn_etf_beta",
                    "asset_scope": "cn_etf",
                    "semantic_config": etf_cfg,
                    "runtime_config": sanitize_json(dict(etf_runtime)),
                },
            },
        }
    )


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
    _apply_regime_engine_cfg(cfg, wb_cfg)
    _apply_governed_a_share_cfg(cfg, wb_cfg)
    wb_data_source = wb_cfg.get("data_source") if isinstance(wb_cfg.get("data_source"), dict) else {}
    if wb_data_source:
        runtime_data_source = dict(cfg.get("data_source") or {})
        for key, value in wb_data_source.items():
            if value is None:
                continue
            runtime_data_source[key] = value
        cfg["data_source"] = sanitize_json(runtime_data_source)
        ds_cfg = DataSourceConfig(**cfg["data_source"])
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
