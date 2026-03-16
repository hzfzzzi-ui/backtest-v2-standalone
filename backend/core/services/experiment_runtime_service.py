from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException

from backend.api.shared.paths import bt_root as _bt_root
from backend.api.backtest_v2.semantic_config_compiler import (
    SEMANTIC_CONFIG_SCHEMA_VERSION,
    validate_semantic_config_json,
)
from backend.api.shared.json_utils import sanitize_json
from backend.core.config.asset_profiles import build_asset_context, canonical_asset_scope
from backend.core.services.experiment_artifact_service import stabilize_experiment_output
from backend.core.tools.locked_candidate_presets import is_locked_candidate_preset
from backend.core.tools.saved_config_access import resolve_runtime_config_source


def _api_module():
    from backend.api.backtest_v2 import impl as api_module

    return api_module


def build_runtime_cfg_from_workbench(
    *,
    base_cfg: dict[str, Any],
    request_payload: dict[str, Any] | None,
    wb_cfg: dict[str, Any],
    use_body_universe_fields: bool = True,
) -> dict[str, Any]:
    api_module = _api_module()
    body = api_module.BacktestV2ExperimentRequest(**dict(request_payload or {}))
    return api_module._build_runtime_cfg_from_workbench(
        base_cfg,
        body,
        wb_cfg,
        use_body_universe_fields=use_body_universe_fields,
    )


def run_experiment_request(
    request_payload: dict[str, Any],
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    api_module = _api_module()
    body = api_module.BacktestV2ExperimentRequest(**dict(request_payload or {}))
    return run_experiment_request_body(body, progress_hook=progress_hook)


def run_experiment_request_body(
    body: Any,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    api_module = _api_module()
    bt_root = _bt_root()
    if not bt_root.exists():
        raise HTTPException(status_code=500, detail=f"backtest_V2 root not found: {bt_root}")

    try:
        from backend.core.tools.experiment_runner import run_experiment  # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to import experiment tools: {exc}")

    requested_preset = str(body.preset or "").strip()
    if is_locked_candidate_preset(requested_preset):
        return api_module._run_locked_candidate_preset_sync(
            body=body,
            bt_root=bt_root,
            run_experiment=run_experiment,
            progress_hook=progress_hook,
        )

    cfg_rel = body.config_path.strip() if (body.config_path or "").strip() else "configs/pams_cn_pg.json"
    cfg_path = (bt_root / cfg_rel).resolve()
    if not cfg_path.exists():
        cfg_path_alt = (bt_root.parent / cfg_rel).resolve()
        if cfg_path_alt.exists():
            cfg_path = cfg_path_alt
        else:
            raise HTTPException(status_code=400, detail=f"config not found: {cfg_path}")

    try:
        base_cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid config json: {cfg_path} ({exc})")

    semantic_cfg_input = validate_semantic_config_json(body.config_json) if isinstance(body.config_json, dict) else None
    semantic_compile: dict[str, Any] | None = None
    if isinstance(semantic_cfg_input, dict):
        coexisting_inputs_present = [
            field
            for field, present in (
                ("config_id", bool(str(body.config_id or "").strip())),
                ("runtime_config_json", isinstance(body.runtime_config_json, dict)),
                ("workbench_config", isinstance(body.workbench_config, dict)),
                ("config_path", bool(str(body.config_path or "").strip())),
            )
            if present
        ]
        effective_wb_cfg = semantic_cfg_input
        config_source = "config_json"
        resolved_config_mode = "semantic_config_run"
        resolved_config_id = ""
        resolved_config_hash = ""
        resolved_config_meta = sanitize_json(
            {
                "source_type": "frontend_semantic",
                "owner": "manual",
                "schema_version": SEMANTIC_CONFIG_SCHEMA_VERSION,
                "config_source": "config_json",
                "coexisting_inputs_present": coexisting_inputs_present,
            }
        )
        use_script_cfg = False
        runtime_config_supplied = False
        conflict_policy = "config_json_preferred"
    else:
        draft_config = body.workbench_config
        resolution = resolve_runtime_config_source(
            config_id=body.config_id,
            runtime_config=body.runtime_config_json,
            draft_config=draft_config,
        )
        effective_wb_cfg = resolution.get("effective_config_json") if isinstance(resolution.get("effective_config_json"), dict) else None
        config_source = str(resolution.get("config_source") or "none")
        resolved_config_mode = str(resolution.get("resolved_config_mode") or "none")
        resolved_config_id = str(resolution.get("resolved_config_id") or body.config_id or "").strip()
        resolved_config_hash = str(resolution.get("resolved_config_hash") or "").strip()
        resolved_config_meta = resolution.get("resolved_config_meta") if isinstance(resolution.get("resolved_config_meta"), dict) else None
        use_script_cfg = resolved_config_mode == "saved_config_run"
        runtime_config_supplied = isinstance(body.runtime_config_json, dict)
        conflict_policy = str(resolution.get("config_conflict_policy") or "none")
        request_semantic_blocks = api_module._request_semantic_blocks(body)
        if request_semantic_blocks:
            if isinstance(effective_wb_cfg, dict) and not api_module._looks_like_backend_runtime_config(effective_wb_cfg):
                effective_wb_cfg = sanitize_json({**dict(effective_wb_cfg), **request_semantic_blocks})
            elif effective_wb_cfg is None:
                effective_wb_cfg = request_semantic_blocks

    overrides: dict[str, Any] = {}
    canonical_scope = canonical_asset_scope(getattr(body, "asset_scope", "cn_a_equity"))
    overrides["asset_scope"] = canonical_scope
    if not use_script_cfg and not runtime_config_supplied and not isinstance(semantic_cfg_input, dict):
        if body.symbols:
            overrides["symbols"] = list(body.symbols)
        if body.start_date:
            overrides["start_date"] = body.start_date
        if body.end_date:
            overrides["end_date"] = body.end_date
        if body.benchmark:
            overrides["benchmark"] = body.benchmark
        if body.compare_symbol:
            overrides["compare_symbol"] = body.compare_symbol
        if body.initial_capital is not None:
            overrides["initial_capital"] = float(body.initial_capital)
        if body.max_positions is not None:
            overrides["max_positions"] = int(body.max_positions)
        if body.base_order_value is not None:
            overrides["base_order_value"] = float(body.base_order_value)
        if body.lot_size is not None:
            overrides["lot_size"] = int(body.lot_size)
        if body.universe_limit is not None:
            overrides["universe_limit"] = int(body.universe_limit)
    if body.fast_mode is not None:
        overrides["fast_mode"] = bool(body.fast_mode)
    if resolved_config_id:
        overrides["config_id"] = resolved_config_id
    overrides["config_source"] = config_source
    overrides["resolved_config_mode"] = resolved_config_mode
    if resolved_config_hash:
        overrides["resolved_config_hash"] = resolved_config_hash
    if resolved_config_meta is not None:
        overrides["resolved_config_meta"] = sanitize_json(dict(resolved_config_meta))
    if conflict_policy != "none":
        overrides["config_conflict_policy"] = conflict_policy
    if body.workbench_mode:
        overrides["workbench_mode"] = str(body.workbench_mode)
    if isinstance(effective_wb_cfg, dict):
        wb_cfg = effective_wb_cfg
        if not api_module._looks_like_backend_runtime_config(wb_cfg):
            overrides.update(api_module._semantic_ranking_execution_overrides(wb_cfg))
            overrides.update(api_module._semantic_sizing_execution_overrides(wb_cfg))
        pos_risk_cfg = wb_cfg.get("position_risk") if isinstance(wb_cfg.get("position_risk"), dict) else {}
        if "max_positions" not in overrides and pos_risk_cfg.get("max_positions") is not None:
            try:
                overrides["max_positions"] = int(pos_risk_cfg.get("max_positions"))
            except Exception:
                pass
        if not api_module._looks_like_backend_runtime_config(wb_cfg):
            semantic_compile = api_module._compile_semantic_config_bundle(
                base_cfg=base_cfg,
                body=body,
                semantic_cfg=wb_cfg,
                config_source=config_source,
                use_body_universe_fields=not (use_script_cfg or runtime_config_supplied or isinstance(semantic_cfg_input, dict)),
            )
            resolved_config_hash = str(semantic_compile.get("config_hash") or resolved_config_hash or "").strip()
            if resolved_config_hash:
                overrides["resolved_config_hash"] = resolved_config_hash
            resolved_config_meta_payload = dict(resolved_config_meta or {})
            resolved_config_meta_payload.setdefault("schema_version", SEMANTIC_CONFIG_SCHEMA_VERSION)
            resolved_config_meta_payload.setdefault("config_source", config_source)
            resolved_config_meta_payload["config_hash"] = resolved_config_hash or resolved_config_meta_payload.get("config_hash")
            resolved_config_meta = sanitize_json(resolved_config_meta_payload)
            overrides["resolved_config_meta"] = resolved_config_meta
        if body.initial_capital is None and wb_cfg.get("initial_capital") is not None:
            try:
                overrides["initial_capital"] = float(wb_cfg.get("initial_capital"))
            except Exception:
                pass
        if isinstance(semantic_compile, dict):
            overrides["workbench_config"] = semantic_compile.get("runtime_config")
            overrides["original_workbench_config"] = semantic_compile.get("input_config")
        else:
            overrides["workbench_config"] = wb_cfg
            overrides["original_workbench_config"] = semantic_cfg_input if isinstance(semantic_cfg_input, dict) else wb_cfg
    effective_wb_cfg_dict = effective_wb_cfg if isinstance(effective_wb_cfg, dict) else {}
    overrides["asset_context"] = sanitize_json(
        build_asset_context(
            canonical_scope,
            config_json=effective_wb_cfg_dict if effective_wb_cfg_dict else base_cfg,
            metadata_scope=(effective_wb_cfg_dict.get("asset_context") or {}).get("asset_scope") if isinstance(effective_wb_cfg_dict.get("asset_context"), dict) else None,
        )
    )
    if use_script_cfg or runtime_config_supplied:
        wb_uni = effective_wb_cfg_dict.get("universe") if isinstance(effective_wb_cfg_dict.get("universe"), dict) else {}
        overrides["universe_mode"] = str(effective_wb_cfg_dict.get("universe_mode") or body.universe_mode or "CUSTOM")
        overrides["industries"] = list(effective_wb_cfg_dict.get("industries") or [])
        overrides["price_adj"] = str(wb_uni.get("price_adj") or body.price_adj or "hfq")
    else:
        wb_uni = effective_wb_cfg_dict.get("universe") if isinstance(effective_wb_cfg_dict.get("universe"), dict) else {}
        wb_universe_mode = str(effective_wb_cfg_dict.get("universe_mode") or "").strip()
        if wb_universe_mode:
            overrides["universe_mode"] = wb_universe_mode
        if isinstance(effective_wb_cfg_dict.get("industries"), list):
            overrides["industries"] = list(effective_wb_cfg_dict.get("industries") or [])
        wb_price_adj = str(wb_uni.get("price_adj") or "").strip()
        if wb_price_adj:
            overrides["price_adj"] = wb_price_adj
        if body.universe_mode and not runtime_config_supplied:
            overrides["universe_mode"] = str(body.universe_mode)
        if body.industries and not runtime_config_supplied:
            overrides["industries"] = list(body.industries)
        if body.price_adj and not runtime_config_supplied:
            overrides["price_adj"] = str(body.price_adj)
        if body.enable_strength_rank is not None and not runtime_config_supplied:
            overrides["enable_strength_rank"] = bool(body.enable_strength_rank)
        if body.strength_ma is not None and not runtime_config_supplied:
            overrides["strength_ma"] = int(body.strength_ma)
        if body.strength_top_k_mode is not None and not runtime_config_supplied:
            overrides["strength_top_k_mode"] = str(body.strength_top_k_mode)
        if body.enable_multifactor_rank is not None and not runtime_config_supplied:
            overrides["enable_multifactor_rank"] = bool(body.enable_multifactor_rank)
        if body.mf_topk is not None and not runtime_config_supplied:
            overrides["mf_topk"] = int(body.mf_topk)
        if body.momentum_top_pct is not None and not runtime_config_supplied:
            overrides["momentum_top_pct"] = float(body.momentum_top_pct)
    if semantic_compile is not None:
        semantic_compile["compiled_plan"] = sanitize_json(
            {
                **dict(semantic_compile.get("compiled_plan") or {}),
                "execution_overrides": api_module._execution_override_snapshot(overrides),
                "asset_context": sanitize_json(dict(overrides.get("asset_context") or {})),
            }
        )

    env_backup = {
        "PAMS_PG_HOST": os.environ.get("PAMS_PG_HOST"),
        "PAMS_PG_PORT": os.environ.get("PAMS_PG_PORT"),
        "PAMS_PG_DBNAME": os.environ.get("PAMS_PG_DBNAME"),
        "PAMS_PG_USER": os.environ.get("PAMS_PG_USER"),
        "PAMS_PG_PASSWORD": os.environ.get("PAMS_PG_PASSWORD"),
    }
    os.environ["PAMS_PG_HOST"] = os.environ.get("PGHOST", env_backup["PAMS_PG_HOST"] or "pams-postgres")
    os.environ["PAMS_PG_PORT"] = os.environ.get("PGPORT", env_backup["PAMS_PG_PORT"] or "5432")
    os.environ["PAMS_PG_DBNAME"] = os.environ.get("PGDATABASE", env_backup["PAMS_PG_DBNAME"] or "pams")
    os.environ["PAMS_PG_USER"] = os.environ.get("PGUSER", env_backup["PAMS_PG_USER"] or "pams")
    os.environ["PAMS_PG_PASSWORD"] = os.environ.get("PGPASSWORD", env_backup["PAMS_PG_PASSWORD"] or "")

    try:
        result = run_experiment(str(cfg_path), requested_preset or "single", overrides, progress_hook=progress_hook)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"experiment run failed: {exc}")
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    try:
        api_module._attach_run_profile_summary(result)
    except Exception:
        pass

    try:
        api_module._write_config_snapshots(
            result=result if isinstance(result, dict) else {},
            input_config=(
                semantic_compile.get("input_config")
                if isinstance(semantic_compile, dict)
                else (body.workbench_config if isinstance(body.workbench_config, dict) else None)
            ),
            resolved_config=(
                semantic_compile.get("resolved_config")
                if isinstance(semantic_compile, dict)
                else effective_wb_cfg
            ),
            compiled_plan=(
                semantic_compile.get("compiled_plan")
                if isinstance(semantic_compile, dict)
                else (overrides.get("workbench_config") if isinstance(overrides.get("workbench_config"), dict) else None)
            ),
        )
    except Exception:
        pass

    try:
        result = stabilize_experiment_output(
            bt_root=bt_root,
            result=result if isinstance(result, dict) else {},
            base_cfg=base_cfg,
            overrides=overrides,
            run_profile_summary=result.get("run_profile_summary") if isinstance(result, dict) else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"artifact stabilization failed: {exc}")

    result.setdefault("exp_id", "")
    result["experiment_id"] = str(result.get("exp_id") or "") or None
    result.setdefault("results_dir", "")
    result.setdefault("status", "OK")
    result["requested_preset"] = requested_preset
    result["resolved_config_mode"] = resolved_config_mode
    result["resolved_config_id"] = resolved_config_id or None
    result["resolved_config_hash"] = resolved_config_hash or None
    result["config_conflict_policy"] = conflict_policy
    if resolved_config_meta is not None:
        result["resolved_config_meta"] = sanitize_json(dict(resolved_config_meta))
        result["resolved_config_source_type"] = str(resolved_config_meta.get("source_type") or "")
        result["resolved_config_owner"] = str(resolved_config_meta.get("owner") or "")
    return api_module._attach_public_experiment_id(result)
