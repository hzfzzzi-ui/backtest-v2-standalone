from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.shared.paths import experiments_root as _experiments_root
from backend.core.services import experiment_history_service

router = APIRouter(tags=["backtest_v2"])


@router.get("/api/backtest_v2/experiments")
def list_experiments():
    return experiment_history_service.list_experiments(experiments_root=_experiments_root())


@router.delete("/api/backtest_v2/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    return experiment_history_service.delete_experiment(exp_id, experiments_root=_experiments_root())


@router.delete("/api/backtest_v2/experiments")
def clear_all_experiments():
    return experiment_history_service.clear_all_experiments(experiments_root=_experiments_root())


@router.post("/api/backtest_v2/experiments/compare")
def compare_experiments(body: dict[str, object]):
    return experiment_history_service.compare_experiments(body, experiments_root=_experiments_root())
