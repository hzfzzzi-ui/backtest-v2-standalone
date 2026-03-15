from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.backtest_v2 import impl
from backend.api.backtest_v2.contracts.requests import ArtifactReadRequest
from backend.core.services import experiment_query_service

router = APIRouter(tags=["backtest_v2"])

BacktestV2ArtifactReadRequest = ArtifactReadRequest


@router.get("/api/backtest_v2/experiments/{exp_id}/manifest")
def get_backtest_v2_manifest(exp_id: str):
    return impl.get_backtest_v2_manifest(exp_id)


@router.get("/api/backtest_v2/experiments/{exp_id}/artifacts/{rel_path:path}")
def get_backtest_v2_artifact(exp_id: str, rel_path: str):
    return impl.get_backtest_v2_artifact(exp_id, rel_path)


@router.post("/api/backtest_v2/artifacts/read")
def read_backtest_v2_artifact(body: BacktestV2ArtifactReadRequest):
    return impl.read_backtest_v2_artifact(body)


@router.get("/api/backtest_v2/experiments/{exp_id}/surface")
def get_experiment_surface(exp_id: str):
    return experiment_query_service.get_experiment_surface(exp_id)


@router.get("/api/backtest_v2/experiments/{exp_id}/surface/{section}")
def get_experiment_surface_section(exp_id: str, section: str):
    payload = experiment_query_service.get_experiment_surface_section(exp_id, section)
    if payload is None:
        raise HTTPException(status_code=404, detail="surface section not available")
    return payload
