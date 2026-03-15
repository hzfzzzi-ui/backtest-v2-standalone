from __future__ import annotations

from fastapi import APIRouter

from backend.api.backtest_v2 import impl
from backend.api.backtest_v2.contracts.requests import ExecutionPreviewRequest

router = APIRouter(tags=["backtest_v2"])

BacktestV2ExecutionPreviewRequest = ExecutionPreviewRequest


@router.post("/api/backtest_v2/execution/preview")
def preview_backtest_v2_execution(body: BacktestV2ExecutionPreviewRequest):
    return impl.preview_backtest_v2_execution(body)
