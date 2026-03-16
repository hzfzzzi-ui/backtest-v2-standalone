"""Vector runtime entrypoint and route dispatch.

Route selection belongs in `route_registry.py`, and formal execution flow
belongs in `foundation_shell.py` plus `stage_pipeline/*`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from backend.core.config.models import CostConfig
from backend.core.engine_vector.route_registry import resolve_runtime_route_id
from backend.core.engine_vector.strict_runtime_breakout import (
    _run_vector_portfolio_backtest_breakout,
)
from backend.core.engine_vector.strict_runtime_default import (
    run_vector_portfolio_backtest_default_route,
)
from backend.core.engine_vector.strict_runtime_generic import (
    _run_vector_portfolio_backtest_generic_signals,
)
from backend.core.portfolio.types import PortfolioBacktestResult


def _resolve_runtime_route_id(strategy: Any) -> str:
    return resolve_runtime_route_id(strategy)


def run_vector_portfolio_backtest(
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
    route_id = _resolve_runtime_route_id(strategy)

    if route_id == "provider_breakout_runtime":
        return _run_vector_portfolio_backtest_breakout(
            strategy=strategy,
            history=history,
            benchmark=benchmark,
            trading_days=trading_days,
            initial_cash=initial_cash,
            max_positions=max_positions,
            lot_size=lot_size,
            enable_strength_rank=enable_strength_rank,
            strength_ma=strength_ma,
            strength_top_k_mode=strength_top_k_mode,
            fast_mode=fast_mode,
            enable_multifactor_rank=enable_multifactor_rank,
            mf_topk=mf_topk,
            mf_concentrate_topn=mf_concentrate_topn,
            mf_concentrate_scale=mf_concentrate_scale,
            mf_rank_gate_mode=mf_rank_gate_mode,
            momentum_top_pct=momentum_top_pct,
            cost_cfg=cost_cfg,
            raw_history=raw_history,
            exit_cfg=exit_cfg,
            st_history=st_history,
            sector_data=sector_data,
            industry_map=industry_map,
            industry_history=industry_history,
            risk_budget_cfg=risk_budget_cfg,
            sizing_cfg=sizing_cfg,
            market_filter_cfg=market_filter_cfg,
            benchmark_regime_cfg=benchmark_regime_cfg,
        )

    if route_id == "generic_inline_runtime":
        return _run_vector_portfolio_backtest_generic_signals(
            strategy=strategy,
            history=history,
            benchmark=benchmark,
            trading_days=trading_days,
            initial_cash=initial_cash,
            max_positions=max_positions,
            lot_size=lot_size,
            enable_strength_rank=enable_strength_rank,
            strength_ma=strength_ma,
            strength_top_k_mode=strength_top_k_mode,
            history_lookback_days=history_lookback_days,
            fast_mode=fast_mode,
            debug_first_divergence=debug_first_divergence,
            enable_multifactor_rank=enable_multifactor_rank,
            mf_topk=mf_topk,
            mf_concentrate_topn=mf_concentrate_topn,
            mf_concentrate_scale=mf_concentrate_scale,
            mf_rank_gate_mode=mf_rank_gate_mode,
            momentum_top_pct=momentum_top_pct,
            cost_cfg=cost_cfg,
            raw_history=raw_history,
            sector_data=sector_data,
            industry_map=industry_map,
            industry_history=industry_history,
        )

    return run_vector_portfolio_backtest_default_route(
        strategy=strategy,
        history=history,
        benchmark=benchmark,
        trading_days=trading_days,
        benchmark_symbol=benchmark_symbol,
        initial_cash=initial_cash,
        max_positions=max_positions,
        lot_size=lot_size,
        enable_strength_rank=enable_strength_rank,
        strength_ma=strength_ma,
        strength_top_k_mode=strength_top_k_mode,
        history_lookback_days=history_lookback_days,
        fast_mode=fast_mode,
        collect_decision_diff=collect_decision_diff,
        debug_first_divergence=debug_first_divergence,
        enable_multifactor_rank=enable_multifactor_rank,
        mf_topk=mf_topk,
        mf_concentrate_topn=mf_concentrate_topn,
        mf_concentrate_scale=mf_concentrate_scale,
        mf_rank_gate_mode=mf_rank_gate_mode,
        momentum_top_pct=momentum_top_pct,
        cost_cfg=cost_cfg,
        raw_history=raw_history,
        exit_cfg=exit_cfg,
        risk_cfg=risk_cfg,
        sizing_cfg=sizing_cfg,
        base_order_value=base_order_value,
        st_history=st_history,
        sector_data=sector_data,
        industry_map=industry_map,
        industry_history=industry_history,
        risk_budget_cfg=risk_budget_cfg,
        market_filter_cfg=market_filter_cfg,
        benchmark_regime_cfg=benchmark_regime_cfg,
        breadth_cfg=breadth_cfg,
    )
