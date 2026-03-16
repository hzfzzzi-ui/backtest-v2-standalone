from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from backend.core.config.models import BenchmarkRegimeConfig, CostConfig, MarketFilterConfig, RiskBudgetConfig, SizingConfig
from backend.core.portfolio.portfolio_runtime import build_backtest_price_indices


@dataclass(frozen=True, slots=True)
class RuntimeBootstrap:
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
    tilt_strength: float
    tilt_top_n: int
    tilt_bottom_n: int
    dd_enabled: bool
    dd_reduce_pct: float
    dd_reduce_scale: float
    portfolio_mode: str
    min_trade_price: float
    open_idx: dict[tuple[Any, str], float]
    close_idx: dict[tuple[Any, str], float]
    volume_idx: dict[tuple[Any, str], float]
    amount_idx: dict[tuple[Any, str], float]
    suspended_idx: dict[tuple[Any, str], bool]
    limit_up_idx: dict[tuple[Any, str], float]
    limit_down_idx: dict[tuple[Any, str], float]


@dataclass(slots=True)
class RuntimeLedger:
    cash: float
    positions: dict[str, int] = field(default_factory=dict)
    position_avg_cost: dict[str, float] = field(default_factory=dict)
    holding_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    composition_audit_rows: list[dict[str, Any]] = field(default_factory=list)
    order_reject_reason_counts: dict[str, int] = field(default_factory=dict)
    peak_nav: float = 0.0
    prev_nav: float = 0.0
    trade_rows: list[dict[str, Any]] = field(default_factory=list)
    candidate_rows: list[dict[str, Any]] = field(default_factory=list)
    daily_rows: list[dict[str, Any]] = field(default_factory=list)
    deferred_sell_orders: list[dict[str, Any]] = field(default_factory=list)
    prepared_day_index: int | None = None
    current_day: dict[str, Any] | None = None
    traded_value_today: float = 0.0
    simulation_t0: float = 0.0


@dataclass(slots=True)
class RuntimeCounters:
    market_filter_bull_days: int = 0
    market_filter_bear_days: int = 0
    market_state_trans_down_days: int = 0
    market_state_trans_up_days: int = 0
    trade_mode_main_days: int = 0
    trade_mode_light_days: int = 0
    trade_mode_notrade_days: int = 0


def build_execution_guard_indices(
    history: pd.DataFrame,
) -> tuple[
    dict[tuple[Any, str], float],
    dict[tuple[Any, str], float],
    dict[tuple[Any, str], bool],
    dict[tuple[Any, str], float],
    dict[tuple[Any, str], float],
]:
    hist = history.copy()
    if hist.empty:
        return {}, {}, {}, {}, {}
    hist["date"] = pd.to_datetime(hist["date"]).dt.normalize()
    hist["symbol"] = hist["symbol"].astype(str).str.lower()
    hist = hist.sort_values(["date", "symbol"]).reset_index(drop=True)

    amount_col = "amount" if "amount" in hist.columns else "turnover" if "turnover" in hist.columns else None
    volume_idx: dict[tuple[Any, str], float] = {}
    amount_idx: dict[tuple[Any, str], float] = {}
    suspended_idx: dict[tuple[Any, str], bool] = {}
    limit_up_idx: dict[tuple[Any, str], float] = {}
    limit_down_idx: dict[tuple[Any, str], float] = {}

    for row in hist.itertuples(index=False):
        day = pd.Timestamp(row.date).date()
        symbol = str(row.symbol).lower()
        key = (day, symbol)
        if hasattr(row, "volume"):
            volume = getattr(row, "volume", None)
            if volume is not None and not pd.isna(volume):
                volume_idx[key] = float(volume)
        if amount_col is not None:
            amount = getattr(row, amount_col, None)
            if amount is not None and not pd.isna(amount):
                amount_idx[key] = float(amount)
        if hasattr(row, "is_suspended"):
            suspended = getattr(row, "is_suspended", None)
            if suspended is not None and not pd.isna(suspended):
                suspended_idx[key] = bool(suspended)
        if hasattr(row, "limit_up"):
            limit_up = getattr(row, "limit_up", None)
            if limit_up is not None and not pd.isna(limit_up):
                limit_up_idx[key] = float(limit_up)
        if hasattr(row, "limit_down"):
            limit_down = getattr(row, "limit_down", None)
            if limit_down is not None and not pd.isna(limit_down):
                limit_down_idx[key] = float(limit_down)

    return volume_idx, amount_idx, suspended_idx, limit_up_idx, limit_down_idx


def build_runtime_bootstrap(
    request: Any,
    *,
    market_filter_cfg: MarketFilterConfig | None,
    benchmark_regime_cfg: BenchmarkRegimeConfig | None,
) -> RuntimeBootstrap:
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
    volume_idx, amount_idx, suspended_idx, limit_up_idx, limit_down_idx = build_execution_guard_indices(request.data_bundle.raw_history)
    return RuntimeBootstrap(
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
        tilt_strength=float(sizing_cfg.tilt_strength),
        tilt_top_n=int(sizing_cfg.tilt_top_n),
        tilt_bottom_n=int(sizing_cfg.tilt_bottom_n),
        dd_enabled=bool(risk_budget_cfg.enabled),
        dd_reduce_pct=float(risk_budget_cfg.dd_reduce_pct),
        dd_reduce_scale=float(risk_budget_cfg.dd_reduce_scale),
        portfolio_mode=portfolio_mode,
        min_trade_price=min_trade_price,
        open_idx=open_idx,
        close_idx=close_idx,
        volume_idx=volume_idx,
        amount_idx=amount_idx,
        suspended_idx=suspended_idx,
        limit_up_idx=limit_up_idx,
        limit_down_idx=limit_down_idx,
    )


def initialize_runtime_ledger(initial_cash: float) -> RuntimeLedger:
    initial_cash = float(initial_cash)
    return RuntimeLedger(
        cash=initial_cash,
        peak_nav=initial_cash,
        prev_nav=initial_cash,
        simulation_t0=time.perf_counter(),
    )


def initialize_runtime_counters() -> RuntimeCounters:
    return RuntimeCounters()
