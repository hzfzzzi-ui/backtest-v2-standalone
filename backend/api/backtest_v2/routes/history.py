from __future__ import annotations

from fastapi import APIRouter

from backend.core.services import experiment_compare_service, experiment_query_service

router = APIRouter(tags=["backtest_v2"])


@router.get("/api/backtest_v2/experiments")
def list_experiments():
    return experiment_query_service.list_experiments()


@router.delete("/api/backtest_v2/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    return experiment_query_service.delete_experiment(exp_id)


@router.delete("/api/backtest_v2/experiments")
def clear_all_experiments():
    return experiment_query_service.clear_all_experiments()


@router.post("/api/backtest_v2/experiments/compare")
def compare_experiments(body: dict):
    return experiment_compare_service.compare_experiments(body)
