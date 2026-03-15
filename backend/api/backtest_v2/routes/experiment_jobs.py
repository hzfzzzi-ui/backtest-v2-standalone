from __future__ import annotations

from fastapi import APIRouter

from backend.api.backtest_v2 import impl
from backend.api.backtest_v2.contracts.requests import PublicExperimentRunRequest

router = APIRouter(tags=["backtest_v2"])


@router.post("/api/backtest_v2/experiment/run_async")
def run_backtest_v2_experiment_async(body: PublicExperimentRunRequest):
    return impl.run_backtest_v2_experiment_async(body)


@router.get("/api/backtest_v2/jobs/{job_id}")
def get_backtest_v2_job(job_id: str):
    return impl.get_backtest_v2_job(job_id)


@router.post("/api/backtest_v2/jobs/{job_id}/cancel")
def cancel_backtest_v2_job(job_id: str):
    return impl.cancel_backtest_v2_job(job_id)
