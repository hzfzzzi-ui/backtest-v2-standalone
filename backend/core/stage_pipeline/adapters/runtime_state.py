from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from backend.core.config.models import BenchmarkRegimeConfig, CostConfig, MarketFilterConfig, RiskBudgetConfig, SizingConfig
from backend.core.portfolio.portfolio_builder import build_backtest_price_indices


@dataclass(frozen=True, slots=True)
class LegacyRuntimeBootstrap:
    cost_cfg: CostConfig
    sizing_cfg: SizingConfig
    risk_budget_cfg: RiskBudgetConfig
    market_filter_cfg: MarketFilterConfig | None
    benchmark_regime_cfg: BenchmarkRegimeConfig | None
    slip_bps: float
    comm_rate: float
    comm_min: float
    stamp_rate: float
    weight_mode: str
    min_positions_cfg: int
    dd_enabled: bool
    dd_reduce_pct: float
    dd_reduce_scale: float
    portfolio_mode: str
    min_trade_price: float
    open_idx: dict[tuple[Any, str], float]
    close_idx: dict[tuple[Any, str], float]


@dataclass(slots=True)
class LegacyRuntimeLedger:
    cash: float
    positions: dict[str, int] = field(default_factory=dict)
    position_avg_cost: dict[str, float] = field(default_factory=dict)
    peak_nav: float = 0.0
    prev_nav: float = 0.0
    trade_rows: list[dict[str, Any]] = field(default_factory=list)
    candidate_rows: list[dict[str, Any]] = field(default_factory=list)
    daily_rows: list[dict[str, Any]] = field(default_factory=list)
    prepared_day_index: int | None = None
    current_day: dict[str, Any] | None = None
    traded_value_today: float = 0.0
    simulation_t0: float = 0.0


@dataclass(slots=True)
class LegacyRuntimeCounters:
    market_filter_bull_days: int = 0
    market_filter_bear_days: int = 0
    market_state_trans_down_days: int = 0
    market_state_trans_up_days: int = 0
    trade_mode_main_days: int = 0
    trade_mode_light_days: int = 0
    trade_mode_notrade_days: int = 0


def build_runtime_bootstrap(
    request: Any,
    *,
    market_filter_cfg: MarketFilterConfig | None,
    benchmark_regime_cfg: BenchmarkRegimeConfig | None,
) -> LegacyRuntimeBootstrap:
    cost_cfg = request.cost_cfg if request.cost_cfg is not None else CostConfig()
    sizing_cfg = request.sizing_cfg if request.sizing_cfg is not None else SizingConfig()
    risk_budget_cfg = request.risk_budget_cfg if request.risk_budget_cfg is not None else RiskBudgetConfig()
    universe_filters = dict(getattr(request.strategy, "state", {}).get("universe_filters") or {})
    min_trade_price = float(universe_filters.get("min_price", getattr(request.strategy, "min_price", 0.0)) or 0.0)
    portfolio_mode = str(getattr(request.strategy, "portfolio_mode", "equal_10") or "equal_10").strip().lower()
    open_idx, close_idx = build_backtest_price_indices(
        history=request.data_bundle.raw_history,
        trading_days=request.data_bundle.trading_days,
    )
    return LegacyRuntimeBootstrap(
        cost_cfg=cost_cfg,
        sizing_cfg=sizing_cfg,
        risk_budget_cfg=risk_budget_cfg,
        market_filter_cfg=market_filter_cfg,
        benchmark_regime_cfg=benchmark_regime_cfg,
        slip_bps=float(cost_cfg.slippage_bps) / 10000.0,
        comm_rate=float(cost_cfg.commission_rate),
        comm_min=float(cost_cfg.commission_min),
        stamp_rate=float(cost_cfg.stamp_tax_rate),
        weight_mode=str(sizing_cfg.weight_mode or "equal"),
        min_positions_cfg=int(sizing_cfg.min_positions),
        dd_enabled=bool(risk_budget_cfg.enabled),
        dd_reduce_pct=float(risk_budget_cfg.dd_reduce_pct),
        dd_reduce_scale=float(risk_budget_cfg.dd_reduce_scale),
        portfolio_mode=portfolio_mode,
        min_trade_price=min_trade_price,
        open_idx=open_idx,
        close_idx=close_idx,
    )


def initialize_runtime_ledger(initial_cash: float) -> LegacyRuntimeLedger:
    initial_cash = float(initial_cash)
    return LegacyRuntimeLedger(
        cash=initial_cash,
        peak_nav=initial_cash,
        prev_nav=initial_cash,
        simulation_t0=time.perf_counter(),
    )


def initialize_runtime_counters() -> LegacyRuntimeCounters:
    return LegacyRuntimeCounters()
