from __future__ import annotations

from fastapi import APIRouter

from backend.api.backtest_v2 import impl
from backend.api.backtest_v2.contracts.requests import PublicExperimentRunRequest

router = APIRouter(tags=["backtest_v2"])


@router.post("/api/backtest_v2/experiment/run")
def run_backtest_v2_experiment(body: PublicExperimentRunRequest):
    return impl.run_backtest_v2_experiment(body)
