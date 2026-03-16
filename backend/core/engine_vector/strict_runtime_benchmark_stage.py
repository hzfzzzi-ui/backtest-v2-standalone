"""Benchmark/regime stage for the default vector runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(slots=True)
class DefaultRuntimeBenchmarkStage:
    bench_close: np.ndarray
    risk_on: np.ndarray
    strong_risk_on: np.ndarray


def build_default_runtime_benchmark_state(
    *,
    benchmark: pd.DataFrame,
    dates: Any,
    regime_ma: int,
) -> DefaultRuntimeBenchmarkStage:
    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date")
    bench_close_s = pd.to_numeric(bench["close"], errors="coerce")
    bench_ma_s = bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()
    bmap_close = {pd.Timestamp(d).normalize(): float(v) for d, v in zip(bench["date"], bench_close_s)}
    bmap_ma = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma_s)}
    bench_close = np.array([bmap_close.get(pd.Timestamp(d).normalize(), np.nan) for d in dates], dtype=float)
    bench_ma = np.array([bmap_ma.get(pd.Timestamp(d).normalize(), np.nan) for d in dates], dtype=float)
    risk_on = np.ones(len(dates), dtype=bool)
    valid_bench = ~np.isnan(bench_close) & ~np.isnan(bench_ma)
    risk_on[valid_bench] = bench_close[valid_bench] > bench_ma[valid_bench]

    bench_ma120_s = bench_close_s.rolling(120, min_periods=120).mean()
    bench_ma200_s = bench_close_s.rolling(200, min_periods=200).mean()
    bmap_ma120 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma120_s)}
    bmap_ma200 = {pd.Timestamp(d).normalize(): (float(v) if pd.notna(v) else np.nan) for d, v in zip(bench["date"], bench_ma200_s)}
    bench_ma120 = np.array([bmap_ma120.get(pd.Timestamp(d).normalize(), np.nan) for d in dates], dtype=float)
    bench_ma200 = np.array([bmap_ma200.get(pd.Timestamp(d).normalize(), np.nan) for d in dates], dtype=float)
    strong_risk_on = np.zeros(len(dates), dtype=bool)
    valid_strong = ~np.isnan(bench_ma120) & ~np.isnan(bench_ma200)
    strong_risk_on[valid_strong] = bench_ma120[valid_strong] > bench_ma200[valid_strong]

    return DefaultRuntimeBenchmarkStage(
        bench_close=bench_close,
        risk_on=risk_on,
        strong_risk_on=strong_risk_on,
    )
