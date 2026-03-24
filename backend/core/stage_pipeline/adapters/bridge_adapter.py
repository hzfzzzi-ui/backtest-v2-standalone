"""Stage-pipeline bridge for the current execution path.

Provider logic belongs in `backend/core/engine_vector/*_signal_provider.py`.
Bus logic belongs in `backend/core/stage_pipeline/builtins/*` and related
adapters. This module should stay focused on adapting runtime state into the
stage pipeline contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Sequence

from backend.core.config.models import (
    BenchmarkRegimeConfig,
    BreadthConfig,
    CostConfig,
    ExitConfig,
    MarketFilterConfig,
    RegimeEngineConfig,
    RiskBudgetConfig,
    SizingConfig,
)
from backend.core.engine_vector.signal_provider import DayContext as ProviderDayContext
from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.portfolio.types import PortfolioBacktestResult
from backend.core.stage_pipeline.adapters.candidate_flow import build_candidate_stage_output, is_candidate_flow_stage
from backend.core.stage_pipeline.adapters.daily_accounting import apply_daily_decision_diagnostics, prepare_daily_snapshot
from backend.core.stage_pipeline.adapters.day_controls import compute_day_controls
from backend.core.stage_pipeline.adapters.fill_accounting import apply_open_fills
from backend.core.stage_pipeline.adapters.holding_flow import build_holding_stage_output, is_holding_flow_stage
from backend.core.stage_pipeline.adapters.order_planning import build_s7_order_stage_output
from backend.core.stage_pipeline.adapters.result_bridge import build_portfolio_backtest_result
from backend.core.stage_pipeline.adapters.lineage import attach_signal_lineage
from backend.core.stage_pipeline.adapters.route_runtime import (
    build_signal_provider,
    coerce_benchmark_regime_cfg,
    coerce_market_filter_cfg,
    initialize_route_controls,
    precompute_signal_provider,
)
from backend.core.stage_pipeline.adapters.runtime_state import (
    build_runtime_bootstrap,
    initialize_runtime_counters,
    initialize_runtime_ledger,
)
from backend.core.stage_pipeline.adapters.signal_postprocess import postprocess_day_signals
from backend.core.stage_pipeline.adapters.stage_applicability import is_stage_disabled, stage_is_applicable
from backend.core.stage_pipeline.context import DataBundleView, DayContext, PortfolioState
from backend.core.stage_pipeline.contracts import StageInputs, StageOutputs
from backend.core.stage_pipeline.shell import StageHandler, StagePipelineRequest, StagePipelineResult, run_stage_pipeline
from backend.core.tools.data_bundle_builder import DataBundle


@dataclass(frozen=True, slots=True)
class StagePipelineBridgeRequest:
    data_bundle: DataBundle
    strategy: Any
    initial_cash: float
    max_positions: int
    lot_size: int
    enable_strength_rank: bool = False
    strength_ma: int = 120
    strength_top_k_mode: str = "FILL_TO_MAX"
    history_lookback_days: int | None = None
    fast_mode: bool = False
    enable_multifactor_rank: bool = False
    mf_topk: int = 10
    mf_concentrate_topn: int = 3
    mf_concentrate_scale: float = 1.5
    mf_rank_gate_mode: str = "ALWAYS_ON"
    momentum_top_pct: float = 0.0
    cost_cfg: CostConfig | None = None
    exit_cfg: ExitConfig | None = None
    sizing_cfg: SizingConfig | None = None
    base_order_value: float = 0.0
    risk_budget_cfg: RiskBudgetConfig | None = None
    market_filter_cfg: MarketFilterConfig | None = None
    benchmark_regime_cfg: BenchmarkRegimeConfig | None = None
    breadth_cfg: BreadthConfig | None = None
    regime_engine_cfg: RegimeEngineConfig | None = None
    asset_context: Mapping[str, Any] = field(default_factory=dict)
    governed_a_share: Mapping[str, Any] = field(default_factory=dict)
    disabled_stages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_cash", float(self.initial_cash))
        object.__setattr__(self, "max_positions", int(self.max_positions))
        object.__setattr__(self, "lot_size", int(self.lot_size))
        object.__setattr__(self, "strength_ma", int(self.strength_ma))
        object.__setattr__(self, "mf_topk", int(self.mf_topk))
        object.__setattr__(self, "mf_concentrate_topn", int(self.mf_concentrate_topn))
        object.__setattr__(self, "mf_concentrate_scale", float(self.mf_concentrate_scale))
        object.__setattr__(self, "momentum_top_pct", float(self.momentum_top_pct))
        object.__setattr__(self, "base_order_value", float(self.base_order_value))
        object.__setattr__(
            self,
            "disabled_stages",
            tuple(sorted({str(stage).upper() for stage in self.disabled_stages})),
        )
        object.__setattr__(self, "asset_context", dict(self.asset_context or {}))
        object.__setattr__(self, "governed_a_share", dict(self.governed_a_share or {}))


@dataclass(frozen=True, slots=True)
class StagePipelineBridgeBacktestResult:
    portfolio_result: PortfolioBacktestResult
    pipeline_result: StagePipelineResult
    route_id: str


class StagePipelineBridgeRuntime:
    _MARKET_STATE_NAMES = ("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR")
    _TRADE_MODE_NAMES = ("TREND_MAIN", "TREND_LIGHT", "NO_TRADE")

    def __init__(self, request: StagePipelineBridgeRequest) -> None:
        self.request = request
        self.route_id, self.provider = build_signal_provider(request.strategy, asset_context=dict(request.asset_context or {}))
        self._market_filter_cfg = coerce_market_filter_cfg(request.market_filter_cfg)
        self._benchmark_regime_cfg = coerce_benchmark_regime_cfg(request.benchmark_regime_cfg)
        bootstrap = build_runtime_bootstrap(
            request,
            market_filter_cfg=self._market_filter_cfg,
            benchmark_regime_cfg=self._benchmark_regime_cfg,
        )
        self._cc = bootstrap.cost_cfg
        self._slip_bps = float(bootstrap.slip_bps)
        self._comm_rate = float(bootstrap.comm_rate)
        self._comm_min = float(bootstrap.comm_min)
        self._stamp_rate = float(bootstrap.stamp_rate)
        self._sizing_cfg = bootstrap.sizing_cfg
        self._weight_mode = str(bootstrap.weight_mode)
        self._min_positions_cfg = int(bootstrap.min_positions_cfg)
        self._tilt_strength = float(bootstrap.tilt_strength)
        self._tilt_top_n = int(bootstrap.tilt_top_n)
        self._tilt_bottom_n = int(bootstrap.tilt_bottom_n)
        self._risk_budget_cfg = bootstrap.risk_budget_cfg
        self._dd_enabled = bool(bootstrap.dd_enabled)
        self._dd_reduce_pct = float(bootstrap.dd_reduce_pct)
        self._dd_reduce_scale = float(bootstrap.dd_reduce_scale)
        self._portfolio_mode = str(bootstrap.portfolio_mode)
        self._min_trade_price = float(bootstrap.min_trade_price)
        self.open_idx = bootstrap.open_idx
        self.close_idx = bootstrap.close_idx
        self.hfq_close_idx = bootstrap.hfq_close_idx
        self.adj_factor_idx = bootstrap.adj_factor_idx
        self.volume_idx = bootstrap.volume_idx
        self.amount_idx = bootstrap.amount_idx
        self.suspended_idx = bootstrap.suspended_idx
        self.limit_up_idx = bootstrap.limit_up_idx
        self.limit_down_idx = bootstrap.limit_down_idx

        ledger = initialize_runtime_ledger(request.initial_cash)
        self.cash = float(ledger.cash)
        self.positions = ledger.positions
        self.position_avg_cost = ledger.position_avg_cost
        self.position_entry_adj = ledger.position_entry_adj
        self.holding_sources = ledger.holding_sources
        self.composition_audit_rows = ledger.composition_audit_rows
        self.accounting_audit_rows = ledger.accounting_audit_rows
        self.execution_lineage_records = ledger.execution_lineage_records
        self.order_reject_reason_counts = ledger.order_reject_reason_counts
        self.peak_nav = float(ledger.peak_nav)
        self.prev_nav = float(ledger.prev_nav)
        self.trade_rows = ledger.trade_rows
        self.candidate_rows = ledger.candidate_rows
        self.daily_rows = ledger.daily_rows
        self.deferred_sell_orders = ledger.deferred_sell_orders
        self._prepared_day_index = ledger.prepared_day_index
        self._current_day = ledger.current_day
        self._traded_value_today = float(ledger.traded_value_today)
        self._simulation_t0 = float(ledger.simulation_t0)
        self._last_accounting_snapshot = None
        self._last_trade_rows_today: tuple[dict[str, Any], ...] = ()

        counters = initialize_runtime_counters()
        self.market_filter_bull_days = int(counters.market_filter_bull_days)
        self.market_filter_bear_days = int(counters.market_filter_bear_days)
        self.market_state_trans_down_days = int(counters.market_state_trans_down_days)
        self.market_state_trans_up_days = int(counters.market_state_trans_up_days)
        self.trade_mode_main_days = int(counters.trade_mode_main_days)
        self.trade_mode_light_days = int(counters.trade_mode_light_days)
        self.trade_mode_notrade_days = int(counters.trade_mode_notrade_days)

        self._provider_precompute()
        route_controls = initialize_route_controls(
            route_id=self.route_id,
            data_bundle=self.request.data_bundle,
            market_filter_cfg=self._market_filter_cfg,
            benchmark_regime_cfg=self._benchmark_regime_cfg,
            breadth_cfg=self.request.breadth_cfg,
            provider=self.provider,
        )
        self._mf_enabled = bool(route_controls.mf_enabled)
        self._mf_state_arr = route_controls.mf_state_arr
        self._mf_trade_mode_arr = route_controls.mf_trade_mode_arr
        self._mf_mult_arr = route_controls.mf_mult_arr
        self._br_enabled = bool(route_controls.br_enabled)
        self._br_gate_arr = route_controls.br_gate_arr
        self._breadth_enabled = bool(route_controls.breadth_enabled)
        self._breadth_score_arr = route_controls.breadth_score_arr
        self._breadth_maxpos_arr = route_controls.breadth_maxpos_arr
        self._regime_engine_name = str(getattr(self.provider, "_regime_engine_name", "ma200_legacy") or "ma200_legacy")
        self._regime_confidence_arr = getattr(self.provider, "_regime_confidence_arr", [])
        self._regime_duration_bars_arr = getattr(self.provider, "_regime_duration_bars_arr", [])
        self._regime_transition_reason_arr = getattr(self.provider, "_regime_transition_reason_arr", [])
        self._feature_availability_arr = getattr(self.provider, "_feature_availability_arr", [])

    def is_stage_disabled(self, stage_key: str) -> bool:
        return is_stage_disabled(self.request.disabled_stages, stage_key)

    def stage_is_applicable(self, stage_key: str) -> bool:
        return stage_is_applicable(self, stage_key)

    def build_portfolio_state(self) -> PortfolioState:
        return PortfolioState(
            cash=self.cash,
            positions=dict(self.positions),
            nav=self._current_day.get("nav") if self._current_day else None,
            market_value=self._current_day.get("market_value") if self._current_day else None,
            metadata={
                "route_id": self.route_id,
                "prepared_day_index": self._prepared_day_index,
            },
        )

    def ensure_day(self, day_context: DayContext, fills_today: Sequence[Any]) -> None:
        if self._prepared_day_index == day_context.day_index:
            return

        self._traded_value_today = 0.0
        self._apply_open_fills(day_context.trading_day, fills_today)
        snapshot = prepare_daily_snapshot(
            self,
            day_index=day_context.day_index,
            day=day_context.trading_day,
        )
        nav = float(snapshot.nav)
        market_value = float(snapshot.market_value)
        controls = dict(snapshot.controls)

        if day_context.is_last_day:
            day_signals = DaySignals(
                sell_signals=[],
                buy_signals=[],
                exit_syms=set(),
                strength_map={},
                mf_score_map={},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            )
            next_open: dict[str, float] = {}
        else:
            request_asset_context = dict(getattr(getattr(self, "request", None), "asset_context", {}) or {})
            provider_ctx = ProviderDayContext(
                positions=self.positions,
                position_avg_cost=self.position_avg_cost,
                cash=self.cash,
                nav=nav,
                base_order_value=self._provider_base_order_value(nav, int(controls["effective_max_positions"])),
                max_positions=int(controls["effective_max_positions"]),
                close_idx=self.close_idx,
                open_idx=self.open_idx,
                next_day=day_context.next_trading_day,
                holding_sources=self.holding_sources,
                asset_context=request_asset_context,
                risk_on=bool(controls["risk_on_today"]),
                market_state=str(controls.get("market_state", "") or ""),
            )
            day_signals = self.provider.day_signals(day_context.trading_day, day_context.day_index, provider_ctx)
            day_signals = self._postprocess_day_signals(day_context.day_index, day_signals, controls)
            attach_signal_lineage(day_signals)
            next_open = {
                symbol: float(self.open_idx.get((day_context.next_trading_day, symbol), 0.0) or 0.0)
                for symbol in set(
                    [str(sig.symbol).lower() for sig in day_signals.sell_signals + day_signals.buy_signals]
                    + list(self.positions.keys())
                )
            }

        self._current_day = {
            "day": day_context.trading_day,
            "nav": float(nav),
            "market_value": float(market_value),
            "controls": controls,
            "accounting_snapshot": getattr(snapshot, "accounting_snapshot", None),
            "day_signals": day_signals,
            "next_open": next_open,
            "next_trading_day": day_context.next_trading_day,
            "holding_symbols": tuple(sorted(sym for sym, qty in self.positions.items() if int(qty) > 0)),
        }
        if not hasattr(self, "accounting_audit_rows") or self.accounting_audit_rows is None:
            self.accounting_audit_rows = []
        request_max_positions = int(
            getattr(getattr(self, "request", None), "max_positions", controls["effective_max_positions"])
        )
        snapshot_accounting = getattr(snapshot, "accounting_snapshot", None)
        self.accounting_audit_rows.append(
            {
                "day": day_context.trading_day.isoformat(),
                "cash_after": float(getattr(snapshot_accounting, "cash", self.cash)),
                "positions_after": {
                    str(symbol).lower(): int(qty)
                    for symbol, qty in dict(getattr(snapshot_accounting, "positions", {}) or {}).items()
                    if int(qty or 0) > 0
                },
                "filled_orders": [dict(item) for item in list(getattr(snapshot_accounting, "filled_orders", ()) or ())],
                "trade_rows": [dict(item) for item in list(getattr(snapshot_accounting, "trade_rows", ()) or ())],
                "nav": float(nav),
                "market_value": float(market_value),
                "max_positions": request_max_positions,
                "hard_max_positions": request_max_positions,
                "effective_max_positions": int(controls["effective_max_positions"]),
            }
        )
        self._prepared_day_index = day_context.day_index

    def stage_output(self, stage_key: str, stage_inputs: StageInputs) -> StageOutputs:
        if self._current_day is None:
            raise RuntimeError("current day is not prepared")

        key = str(stage_key).upper()
        enabled = self.stage_is_applicable(key)
        if is_candidate_flow_stage(key):
            return build_candidate_stage_output(
                stage_key=key,
                stage_inputs=stage_inputs,
                current_day=self._current_day,
                enabled=enabled,
            )
        if is_holding_flow_stage(key):
            return build_holding_stage_output(
                stage_key=key,
                stage_inputs=stage_inputs,
                current_day=self._current_day,
                enabled=enabled,
            )
        return StageOutputs.neutral(
            key,
            stage_inputs,
            summary_fragment={"reason": "unsupported_stage"},
        )

    def plan_orders(self) -> StageOutputs:
        return build_s7_order_stage_output(self)

    def to_backtest_result(self) -> PortfolioBacktestResult:
        return build_portfolio_backtest_result(self)

    def _provider_precompute(self) -> None:
        precompute_signal_provider(
            self.provider,
            data_bundle=self.request.data_bundle,
            strategy=self.request.strategy,
            exit_cfg=self.request.exit_cfg if self.request.exit_cfg is not None else ExitConfig(),
            strength_ma=int(self.request.strength_ma),
            initial_cash=float(self.request.initial_cash),
            max_positions=int(self.request.max_positions),
            history_lookback_days=self.request.history_lookback_days,
            enable_multifactor_rank=bool(self.request.enable_multifactor_rank),
            mf_rank_gate_mode=str(self.request.mf_rank_gate_mode or "ALWAYS_ON"),
            market_filter_cfg=self._market_filter_cfg,
            benchmark_regime_cfg=self._benchmark_regime_cfg,
            regime_engine_cfg=self.request.regime_engine_cfg,
            sizing_cfg=self.request.sizing_cfg,
            risk_budget_cfg=self.request.risk_budget_cfg,
            governed_a_share=self.request.governed_a_share,
        )

    def _apply_open_fills(self, day: date, fills_today: Sequence[Any]) -> None:
        apply_open_fills(self, day, fills_today)

    def _compute_day_controls(self, day_index: int, day: date, drawdown: float) -> dict[str, Any]:
        return compute_day_controls(self, day_index, day, drawdown)

    def _provider_base_order_value(self, nav: float, effective_max_positions: int) -> float:
        if float(self.request.base_order_value) > 0:
            return float(self.request.base_order_value)
        return float(nav) / float(max(effective_max_positions, 1))

    def _postprocess_day_signals(
        self,
        day_index: int,
        day_signals: DaySignals,
        controls: Mapping[str, Any],
    ) -> DaySignals:
        return postprocess_day_signals(
            self,
            day_index=day_index,
            day_signals=day_signals,
            controls=controls,
        )

    def _apply_daily_decision_diagnostics(self, *, day_signals: DaySignals, debug_plan: Mapping[str, Any]) -> None:
        apply_daily_decision_diagnostics(self, day_signals=day_signals, debug_plan=debug_plan)


def build_stage_bridge_handlers(runtime: StagePipelineBridgeRuntime) -> Mapping[str, StageHandler]:
    def _ensure(day_context: DayContext, stage_inputs: StageInputs) -> None:
        fills_today = stage_inputs.payload.get("fills_today") if isinstance(stage_inputs.payload, Mapping) else ()
        runtime.ensure_day(day_context, list(fills_today or ()))

    def _make_stage_handler(stage_key: str) -> StageHandler:
        if stage_key == "S7":
            def _handler(day_context: DayContext, _bundle_view: DataBundleView, _state: PortfolioState, stage_inputs: StageInputs) -> StageOutputs:
                _ensure(day_context, stage_inputs)
                return runtime.plan_orders()
            return _handler

        def _handler(day_context: DayContext, _bundle_view: DataBundleView, _state: PortfolioState, stage_inputs: StageInputs) -> StageOutputs:
            _ensure(day_context, stage_inputs)
            return runtime.stage_output(stage_key, stage_inputs)

        return _handler

    return {stage_key: _make_stage_handler(stage_key) for stage_key in ("S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7")}


def run_stage_pipeline_bridge_backtest(request: StagePipelineBridgeRequest) -> StagePipelineBridgeBacktestResult:
    runtime = StagePipelineBridgeRuntime(request)
    pipeline_result = run_stage_pipeline(
        StagePipelineRequest(
            data_bundle=request.data_bundle,
            initial_state=PortfolioState.empty(cash=request.initial_cash),
            stage_handlers=build_stage_bridge_handlers(runtime),
            execution_shell="stage_pipeline_shell_bridge",
            daily_loop_mode="single_day_loop",
        )
    )
    return StagePipelineBridgeBacktestResult(
        portfolio_result=runtime.to_backtest_result(),
        pipeline_result=pipeline_result,
        route_id=runtime.route_id,
    )
