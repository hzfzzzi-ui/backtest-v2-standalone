from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api.backtest_v2 import impl

router = APIRouter(tags=["backtest_v2"])


@router.get("/api/backtest_v2/industries")
def get_industries():
    return impl.get_industries()


@router.get("/api/backtest_v2/series/benchmark")
def get_benchmark_series(
    symbol: str = Query("000300.SH"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return impl.get_benchmark_series(symbol=symbol, start=start, end=end)


@router.get("/api/backtest_v2/series/symbol")
def get_symbol_series(
    symbol: str = Query(...),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return impl.get_symbol_series(symbol=symbol, start=start, end=end)


@router.post("/api/backtest_v2/stock_names")
def get_stock_names(body: dict):
    return impl.get_stock_names(body)
