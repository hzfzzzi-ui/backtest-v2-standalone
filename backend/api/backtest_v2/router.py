from __future__ import annotations

from fastapi import APIRouter

from .routes import (
    artifacts_router,
    configs_router,
    execution_preview_router,
    experiment_jobs_router,
    experiments_router,
    history_router,
    market_data_router,
    validation_router,
)

router = APIRouter(tags=["backtest_v2"])
router.include_router(configs_router)
router.include_router(history_router)
router.include_router(experiments_router)
router.include_router(experiment_jobs_router)
router.include_router(market_data_router)
router.include_router(validation_router)
router.include_router(execution_preview_router)
router.include_router(artifacts_router)
