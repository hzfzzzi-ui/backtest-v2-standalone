from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.shared.paths import bt_root as _bt_root, results_root as _results_root
from backend.api.shared.json_utils import sanitize_json, sanitize_for_json as _sanitize_for_json
from backend.api.backtest_v2.contracts.requests import PublicExperimentRunRequest as PublicBacktestV2ExperimentRequest
from backend.api.backtest_v2.execution_overrides import (
    compile_multi_alpha_runtime_payload as _compile_multi_alpha_runtime_payload,
    request_semantic_blocks as _request_semantic_blocks,
    semantic_ranking_execution_overrides as _semantic_ranking_execution_overrides,
    semantic_sizing_execution_overrides as _semantic_sizing_execution_overrides,
    to_int_or_default as _to_int_or_default,
)
from backend.api.backtest_v2.semantic_config_compiler import (
    SEMANTIC_CONFIG_SCHEMA_VERSION,
    compile_semantic_config_json,
    validate_semantic_config_json,
)
from backend.core.tools.locked_candidate_presets import (
    build_locked_candidate_cfg,
    is_locked_candidate_preset,
    write_locked_candidate_artifacts,
)
from backend.core.tools.saved_config_access import resolve_runtime_config_source
from backend.core.services.experiment_artifact_service import stabilize_experiment_output
from backend.core.services.experiment_runtime_service import run_experiment_request_body
from backend.api.shared.job_store import (
    JOBS as _JOBS,
    JOBS_LOCK as _JOBS_LOCK,
    create_job as _create_job,
    update_job as _update_job,
    is_cancel_requested as _is_cancel_requested,
    mark_job_canceled as _mark_job_canceled,
    load_job_from_disk as _load_job_from_disk,
    job_payload as _job_payload,
)
from backend.api.backtest_v2.runner_config_helpers import (
    _assert_locked_candidate_request_supported,
    _build_locked_candidate_execution_context,
    _build_runtime_cfg_from_workbench,
    _compile_semantic_config_bundle,
    _execution_override_snapshot,
    _load_base_config,
    _looks_like_backend_runtime_config,
)
from backend.api.backtest_v2.runner_output_helpers import (
    _attach_run_profile_summary,
    _write_config_snapshots,
)
from backend.core.config.asset_profiles import build_asset_context, canonical_asset_scope



def _dump_model(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump(exclude_none=True))
    if hasattr(payload, "dict"):
        return dict(payload.dict(exclude_none=True))
    return {}


def to_internal_experiment_request(payload: Any):
    if isinstance(payload, BacktestV2ExperimentRequest):
        return payload
    return BacktestV2ExperimentRequest(**_dump_model(payload))

router = APIRouter(tags=["backtest_v2"])


class BacktestV2ExperimentRequest(BaseModel):
    preset: str = "G1-G4"
    asset_scope: str = "cn_a_equity"
    config_json: dict[str, Any] | None = None
    signal_generation: dict[str, Any] | None = None
    signal_composition: dict[str, Any] | None = None
    symbols: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    benchmark: str | None = None
    compare_symbol: str | None = None
    initial_capital: float | None = None
    max_positions: int | None = None
    base_order_value: float | None = None
    univote_lot_mode: str | None = None
    lot_size: int | None = None
    universe_limit: int | None = None
    fast_mode: bool | None = None
    config_path: str | None = None
    config_id: str | None = None
    runtime_config_json: dict[str, Any] | None = None
    workbench_mode: str | None = None
    workbench_config: dict[str, Any] | None = None
    universe_mode: str | None = None
    industries: list[str] | None = None
    price_adj: str | None = None
    # 选股排序参数透传
    enable_strength_rank: bool | None = None
    strength_ma: int | None = None
    strength_top_k_mode: str | None = None
    enable_multifactor_rank: bool | None = None
    mf_topk: int | None = None
    momentum_top_pct: float | None = None


def _public_run_rejected_fields(body: BacktestV2ExperimentRequest) -> list[str]:
    rejected: list[str] = []
    candidates = (
        ("symbols", bool(body.symbols)),
        ("start_date", bool(body.start_date)),
        ("end_date", bool(body.end_date)),
        ("benchmark", bool(body.benchmark)),
        ("compare_symbol", bool(body.compare_symbol)),
        ("initial_capital", body.initial_capital is not None),
        ("max_positions", body.max_positions is not None),
        ("base_order_value", body.base_order_value is not None),
        ("univote_lot_mode", body.univote_lot_mode is not None),
        ("lot_size", body.lot_size is not None),
        ("universe_limit", body.universe_limit is not None),
        ("config_path", bool(str(body.config_path or "").strip())),
        ("config_id", bool(str(body.config_id or "").strip())),
        ("runtime_config_json", isinstance(body.runtime_config_json, dict)),
        ("workbench_config", isinstance(body.workbench_config, dict)),
        ("signal_generation", isinstance(body.signal_generation, dict)),
        ("signal_composition", isinstance(body.signal_composition, dict)),
        ("universe_mode", body.universe_mode is not None and str(body.universe_mode or "").strip().upper() != "CUSTOM"),
        ("industries", body.industries is not None and bool(body.industries)),
        ("price_adj", body.price_adj is not None and str(body.price_adj or "").strip().lower() != "hfq"),
        ("enable_strength_rank", body.enable_strength_rank is not None),
        ("strength_ma", body.strength_ma is not None),
        ("strength_top_k_mode", body.strength_top_k_mode is not None),
        ("enable_multifactor_rank", body.enable_multifactor_rank is not None),
        ("mf_topk", body.mf_topk is not None),
        ("momentum_top_pct", body.momentum_top_pct is not None),
    )
    for field, present in candidates:
        if present:
            rejected.append(field)
    return rejected


def _validate_public_run_request(body: BacktestV2ExperimentRequest) -> None:
    if is_locked_candidate_preset(body.preset):
        _assert_locked_candidate_request_supported(body)
        return
    if not isinstance(body.config_json, dict):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "rejected",
                "reason": "config_json_required",
                "message": "public run endpoint requires config_json",
                "required_field": "config_json",
            },
        )
    rejected = _public_run_rejected_fields(body)
    if rejected:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "rejected",
                "reason": "unsupported_config_fields",
                "message": "public run endpoint only accepts config_json as configuration truth",
                "rejected_fields": rejected,
            },
        )


def _attach_public_experiment_id(result: dict[str, Any]) -> dict[str, Any]:
    payload = sanitize_json(dict(result or {}))
    exp_id = str(payload.get("exp_id") or payload.get("experiment_id") or "").strip()
    payload["exp_id"] = exp_id
    payload["experiment_id"] = exp_id or None
    return payload


def _public_experiment_result_response(result: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(result or {})
    exp_id = str(payload.get("exp_id") or payload.get("experiment_id") or "").strip()
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
    return sanitize_json(
        {
            "experiment_id": exp_id or None,
            "exp_id": exp_id or None,
            "status": str(payload.get("status") or "OK"),
            "baseline_compare_status": manifest.get("baseline_compare_status"),
            "endpoints": {
                "manifest": f"/api/backtest_v2/experiments/{exp_id}/manifest" if exp_id else None,
            },
        }
    )


def _run_locked_candidate_preset_sync(
    *,
    body: BacktestV2ExperimentRequest,
    bt_root: Path,
    run_experiment: Callable[..., dict[str, Any]],
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    base_cfg, candidate_meta, overrides, resolved_config_hash, resolved_config_meta = (
        _build_locked_candidate_execution_context(body)
    )
    candidate_asset_scope = canonical_asset_scope(getattr(body, "asset_scope", "cn_a_equity"))
    base_cfg["asset_scope"] = candidate_asset_scope
    base_cfg["asset_context"] = sanitize_json(build_asset_context(candidate_asset_scope, config_json=base_cfg))
    overrides["asset_scope"] = candidate_asset_scope
    overrides["asset_context"] = sanitize_json(dict(base_cfg.get("asset_context") or {}))
    runtime_cfg_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as fh:
            fh.write(json.dumps(base_cfg, ensure_ascii=False, indent=2))
            runtime_cfg_path = Path(fh.name).resolve()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to create locked candidate runtime config: {exc}")

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
        result = run_experiment(str(runtime_cfg_path), "single", overrides, progress_hook=progress_hook)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"experiment run failed: {exc}")
    finally:
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if runtime_cfg_path is not None:
            try:
                runtime_cfg_path.unlink(missing_ok=True)
            except Exception:
                pass

    try:
        _attach_run_profile_summary(result)
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
    result["requested_preset"] = str(body.preset or "").strip()
    result["resolved_config_mode"] = "locked_candidate"
    result["resolved_config_id"] = None
    result["resolved_config_hash"] = resolved_config_hash or None
    result["config_conflict_policy"] = "locked_candidate"
    if resolved_config_meta:
        result["resolved_config_meta"] = sanitize_json(dict(resolved_config_meta))

    results_dir = Path(str(result.get("results_dir") or "")).resolve()
    try:
        candidate_artifacts = write_locked_candidate_artifacts(
            candidate_name=str(body.preset or "").strip().lower(),
            results_dir=results_dir,
            result=result,
            candidate_meta=candidate_meta,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"candidate artifact write failed: {exc}")

    result["candidate"] = sanitize_json(
        {
            "name": str(candidate_meta.get("candidate_name") or ""),
            "status": str(candidate_artifacts.get("status") or "blocked"),
            "source_baseline_exp_id": str(candidate_meta.get("source_baseline_exp_id") or ""),
            "main_change_path": str(candidate_meta.get("main_change_path") or ""),
            "candidate_provenance_path": str(candidate_artifacts.get("candidate_provenance_path") or ""),
            "candidate_summary_json_path": str(candidate_artifacts.get("candidate_summary_json_path") or ""),
            "candidate_summary_path": str(candidate_artifacts.get("candidate_summary_path") or ""),
            "blockers": list(candidate_artifacts.get("blockers") or []),
        }
    )
    if str(candidate_artifacts.get("status") or "").strip().lower() != "ready":
        blockers = ", ".join(str(item) for item in (candidate_artifacts.get("blockers") or []) if str(item).strip())
        raise HTTPException(status_code=500, detail=f"candidate audit blocked: {blockers or 'unknown blockers'}")

    return _attach_public_experiment_id(result)


def _run_backtest_v2_experiment_sync(
    body: BacktestV2ExperimentRequest,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    return run_experiment_request_body(body, progress_hook=progress_hook)

def _run_backtest_v2_experiment_job(job_id: str, body: BacktestV2ExperimentRequest) -> None:
    try:
        preset = str(body.preset or "G1-G4")
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="running", progress_pct=3, message=f"开始实验：{preset}")

        def _progress_cb(pct: int, msg: str) -> None:
            if _is_cancel_requested(job_id):
                return
            _update_job(job_id, status="running", progress_pct=int(max(0, min(99, pct))), message=str(msg))

        payload = _run_backtest_v2_experiment_sync(body, progress_hook=_progress_cb)
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="running", progress_pct=95, message="汇总矩阵与报告")
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="success", progress_pct=100, message="实验完成", result=payload)
    except Exception as exc:
        msg = str(exc)
        if isinstance(exc, HTTPException):
            msg = str(exc.detail)
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="failed", message="实验失败", error=msg)


@router.post("/api/backtest_v2/experiment/run")
def run_backtest_v2_experiment(body: PublicBacktestV2ExperimentRequest):
    internal_body = to_internal_experiment_request(body)
    _validate_public_run_request(internal_body)
    return _public_experiment_result_response(_run_backtest_v2_experiment_sync(internal_body))


@router.post("/api/backtest_v2/experiment/run_async")
def run_backtest_v2_experiment_async(body: PublicBacktestV2ExperimentRequest):
    internal_body = to_internal_experiment_request(body)
    _validate_public_run_request(internal_body)
    preset_key = str(internal_body.preset or "").strip().upper()
    eta = 480
    if is_locked_candidate_preset(internal_body.preset):
        eta = 240
    elif preset_key in {"G1-G4", "REGIME_BUFFER_2X2", "ATR_RISK_2X2", "ATR_PORTFOLIO_VALIDATE_V1", "PORTFOLIO_FILL_VALIDATE_V1", "TREND_FILTER_VALIDATE_V1", "TREND_TIER_VALIDATE_V1", "TREND_ACCEL_BRAKE_VALIDATE_V1", "TREND_BRAKE_CONFIRM_VALIDATE_V1", "STRENGTH_RANK_VALIDATE_V1", "FULL_RANGE_VALIDATE_V1", "CANDIDATE_DIAG_VALIDATE_V1", "SLOT_DEBUG_VALIDATE_V1", "MAX_POSITION_EXPAND_VALIDATE_V1", "STRONG_ONLY_VALIDATE_V1", "MULTIFACTOR_RANKING_VALIDATE_V1", "MULTIFACTOR_RANKING_WALKFORWARD_V1", "MF_RANK_REGIME_GATE_VALIDATE_V1", "MULTIFACTOR_BALANCED_V1", "MULTIFACTOR_FUSION_COMPARE_V1", "MULTIFACTOR_INCREMENTAL_V1", "MULTIFACTOR_INCREMENTAL_V1_6_1A", "EXPERIMENT_6_1A", "6.1A", "MULTIFACTOR_INCREMENTAL_V1_6_1B", "EXPERIMENT_6_1B", "6.1B", "MULTIFACTOR_INCREMENTAL_V1_6_1_LIMIT", "MULTIFACTOR_INCREMENTAL_V1_6_4", "EXPERIMENT_6_4", "6.4", "EXPERIMENT_6_1_LIMIT", "6.1L"}:
        eta = 240
    elif preset_key in {"STRENGTH_RANK_VALIDATE_V2", "STRENGTH_RANK_VALIDATE_V2A", "STRENGTH_RANK_VALIDATE_V2B", "ENGINE_PERF_COMPARE_V1", "ENGINE_PERF_COMPARE_V2"}:
        eta = 180 if bool(internal_body.fast_mode) else 360
    elif preset_key in {"ATR_PARAM_SCAN_V1"}:
        eta = 1200
    elif preset_key in {"ATR_PARAM_VALIDATE_UNIVOTE", "ATR_PARAM_VALIDATE_UNIVOTE_V2"}:
        eta = 900
    job_id = _create_job("experiment", eta_seconds=eta)
    th = threading.Thread(target=_run_backtest_v2_experiment_job, args=(job_id, internal_body), daemon=True)
    th.start()
    return {"job_id": job_id, "status": "queued"}


@router.get("/api/backtest_v2/jobs/{job_id}")
def get_backtest_v2_job(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        disk_job = _load_job_from_disk(job_id)
        if not disk_job:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
        payload = _job_payload(dict(disk_job))
    else:
        payload = _job_payload(dict(job))
    if str(payload.get("status") or "").strip().lower() == "success" and isinstance(payload.get("result"), dict):
        payload["result"] = _public_experiment_result_response(payload.get("result"))
    return _sanitize_for_json(payload)


@router.post("/api/backtest_v2/jobs/{job_id}/cancel")
def cancel_backtest_v2_job(job_id: str):
    job = _mark_job_canceled(job_id, message="用户取消")
    if not job:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return _sanitize_for_json(_job_payload(dict(job)))
