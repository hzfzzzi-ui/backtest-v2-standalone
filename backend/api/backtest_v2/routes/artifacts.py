from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.backtest_v2 import impl
from backend.core.services import experiment_query_service

router = APIRouter(tags=["backtest_v2"])


@router.get("/api/backtest_v2/experiments/{exp_id}/manifest")
def get_backtest_v2_manifest(exp_id: str):
    return impl.get_backtest_v2_manifest(exp_id)


@router.get("/api/backtest_v2/experiments/{exp_id}/surface")
def get_experiment_surface(exp_id: str):
    return experiment_query_service.get_experiment_surface(exp_id)


@router.get("/api/backtest_v2/experiments/{exp_id}/surface/{section}")
def get_experiment_surface_section(exp_id: str, section: str):
    payload = experiment_query_service.get_experiment_surface_section(exp_id, section)
    if payload is None:
        raise HTTPException(status_code=404, detail="surface section not available")
    return payload
