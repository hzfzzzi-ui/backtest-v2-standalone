"""Default vector runtime façade for non-provider routes."""

from __future__ import annotations

import time
from datetime import date
from typing import Any

import pandas as pd

from backend.core.config.models import CostConfig
from backend.core.engine_vector.strict_runtime_benchmark_stage import (
    build_default_runtime_benchmark_state,
)
from backend.core.engine_vector.strict_runtime_daily_loop import (
    run_default_runtime_daily_loop,
)
from backend.core.engine_vector.strict_runtime_input_stage import (
    prepare_default_runtime_inputs,
)
from backend.core.engine_vector.strict_runtime_result_stage import (
    finalize_default_runtime_result,
)
from backend.core.engine_vector.strict_runtime_signal_stage import (
    build_default_runtime_signal_state,
)
from backend.core.portfolio.types import PortfolioBacktestResult


def run_vector_portfolio_backtest_default_route(
    *,
    strategy: Any,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    trading_days: list[date],
    benchmark_symbol: str,
    initial_cash: float,
    max_positions: int,
    lot_size: int,
    enable_strength_rank: bool = False,
    strength_ma: int = 120,
    strength_top_k_mode: str = "FILL_TO_MAX",
    history_lookback_days: int | None = None,
    fast_mode: bool = False,
    collect_decision_diff: bool = False,
    debug_first_divergence: bool = False,
    enable_multifactor_rank: bool = False,
    mf_topk: int = 10,
    mf_concentrate_topn: int = 3,
    mf_concentrate_scale: float = 1.5,
    mf_rank_gate_mode: str = "ALWAYS_ON",
    momentum_top_pct: float = 0.0,
    cost_cfg: CostConfig | None = None,
    raw_history: pd.DataFrame | None = None,
    # These knobs stay on the runtime contract even when active routes read
    # most values directly from `strategy`.
    exit_cfg: Any = None,
    risk_cfg: Any = None,
    sizing_cfg: Any = None,
    base_order_value: float = 0.0,
    st_history: Any = None,
    sector_data: Any = None,
    industry_map: Any = None,
    industry_history: Any = None,
    risk_budget_cfg: Any = None,
    market_filter_cfg: Any = None,
    benchmark_regime_cfg: Any = None,
    breadth_cfg: Any = None,
) -> PortfolioBacktestResult:
    if history.empty:
        raise ValueError("history is empty")
    if not trading_days:
        raise ValueError("trading_days is empty")

    pre_t0 = time.perf_counter()
    inputs = prepare_default_runtime_inputs(
        strategy=strategy,
        history=history,
        trading_days=trading_days,
        strength_ma=strength_ma,
        st_history=st_history,
        sizing_cfg=sizing_cfg,
        risk_budget_cfg=risk_budget_cfg,
    )
    benchmark_state = build_default_runtime_benchmark_state(
        benchmark=benchmark,
        dates=inputs.mx.dates,
        regime_ma=int(inputs.params["regime_ma"]),
    )
    signal_state = build_default_runtime_signal_state(
        strategy=strategy,
        history=history,
        raw_history=raw_history,
        trading_days=trading_days,
        sector_data=sector_data,
        industry_map=industry_map,
        inputs=inputs,
        benchmark_state=benchmark_state,
    )
    precompute_seconds = float(time.perf_counter() - pre_t0)

    simulation = run_default_runtime_daily_loop(
        strategy=strategy,
        trading_days=trading_days,
        initial_cash=initial_cash,
        max_positions=max_positions,
        lot_size=lot_size,
        enable_strength_rank=enable_strength_rank,
        strength_ma=strength_ma,
        strength_top_k_mode=strength_top_k_mode,
        fast_mode=fast_mode,
        debug_first_divergence=debug_first_divergence,
        enable_multifactor_rank=enable_multifactor_rank,
        mf_topk=mf_topk,
        mf_concentrate_topn=mf_concentrate_topn,
        mf_concentrate_scale=mf_concentrate_scale,
        mf_rank_gate_mode=mf_rank_gate_mode,
        momentum_top_pct=momentum_top_pct,
        cost_cfg=cost_cfg,
        params=inputs.params,
        inputs=inputs,
        benchmark_state=benchmark_state,
        signal_state=signal_state,
    )
    return finalize_default_runtime_result(
        simulation=simulation,
        precompute_seconds=precompute_seconds,
        max_positions=max_positions,
        enable_strength_rank=enable_strength_rank,
        strength_ma=strength_ma,
        collect_decision_diff=collect_decision_diff,
        debug_first_divergence=debug_first_divergence,
    )
