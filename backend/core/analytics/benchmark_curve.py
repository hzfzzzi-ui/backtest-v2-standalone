from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def build_benchmark_curve(
    results_dir: str | Path,
    equity: pd.DataFrame,
    benchmark: pd.DataFrame,
    benchmark_symbol: str,
) -> tuple[pd.DataFrame, list[str]]:
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    cols = ["date", "benchmark_symbol", "benchmark_close", "benchmark_nav", "strategy_nav", "excess_nav"]
    if equity.empty:
        df = pd.DataFrame(columns=cols)
        df.to_csv(out_dir / "benchmark_curve.csv", index=False)
        warnings.append("BENCHMARK_CURVE_EMPTY_EQUITY")
        return df, warnings

    eq = equity.copy()
    eq["date"] = pd.to_datetime(eq["date"]).dt.normalize()
    eq = eq.sort_values("date")
    first_equity = float(eq.iloc[0]["equity"]) if float(eq.iloc[0]["equity"]) != 0 else 1.0
    eq["strategy_nav"] = eq["equity"].astype(float) / first_equity
    merged = eq[["date", "strategy_nav"]].copy()

    if benchmark.empty:
        warnings.append("BENCHMARK_CURVE_EMPTY_BENCHMARK")
        merged["benchmark_symbol"] = benchmark_symbol
        merged["benchmark_close"] = pd.NA
        merged["benchmark_nav"] = pd.NA
        merged["excess_nav"] = pd.NA
    else:
        bench = benchmark.copy()
        bench["date"] = pd.to_datetime(bench["date"]).dt.normalize()
        bench = bench.sort_values("date")
        bench = bench[["date", "close"]].rename(columns={"close": "benchmark_close"})
        merged = merged.merge(bench, on="date", how="left")
        missing_before = int(merged["benchmark_close"].isna().sum())
        merged["benchmark_close"] = merged["benchmark_close"].ffill()
        missing_after = int(merged["benchmark_close"].isna().sum())
        if missing_before > 0:
            warnings.append(
                f"BENCHMARK_CURVE_FORWARD_FILL: missing_before={missing_before} missing_after={missing_after}"
            )

        first_close_series = merged["benchmark_close"].dropna()
        if first_close_series.empty or float(first_close_series.iloc[0]) == 0.0:
            merged["benchmark_nav"] = pd.NA
            merged["excess_nav"] = pd.NA
            warnings.append("BENCHMARK_CURVE_MISSING_BASE_CLOSE")
        else:
            base_close = float(first_close_series.iloc[0])
            merged["benchmark_nav"] = merged["benchmark_close"].astype(float) / base_close
            merged["excess_nav"] = merged["strategy_nav"] / merged["benchmark_nav"]
        merged["benchmark_symbol"] = benchmark_symbol

    out = merged[cols].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)
    out.to_csv(out_dir / "benchmark_curve.csv", index=False)
    return out, warnings


def summarize_benchmark_chart(
    benchmark_curve: pd.DataFrame,
    compare_symbol: str,
) -> dict[str, Any]:
    return {
        "benchmark_compare_symbol": compare_symbol,
        "equity_curve_csv": "equity_curve.csv",
        "benchmark_curve_csv": "benchmark_curve.csv",
        "points": int(len(benchmark_curve)),
    }
