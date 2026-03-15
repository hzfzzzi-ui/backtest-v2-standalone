from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.api.backtest_v2 import impl

router = APIRouter(tags=["backtest_v2"])


@router.get("/api/backtest_v2/validate_data")
def validate_backtest_v2_data(
    request: Request,
    preset: str = Query("single"),
    config_id: str | None = Query(default=None),
    fast_mode: bool = Query(False),
):
    return impl.validate_backtest_v2_data(
        request=request,
        preset=preset,
        config_id=config_id,
        fast_mode=fast_mode,
    )
