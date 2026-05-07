from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from backend.core.engine_runtime import foundation_shell as mod
from backend.core.portfolio.types import PortfolioBacktestResult
from backend.core.stage_pipeline.adapters import StagePipelineBridgeBacktestResult
from backend.core.stage_pipeline.context import DayContext, PortfolioState
from backend.core.stage_pipeline.shell import StageDayResult, StagePipelineResult


def test_build_foundation_runtime_plan_materializes_legacy_ranking_intent() -> None:
    plan = mod.build_foundation_runtime_plan(
        runtime_config={
            "strategy": {
                "params": {
                    "ranking_mode": "residual_only",
                    "momentum_top_pct": 0.25,
                }
            },
            "mf_topk": 7,
        },
        overrides={},
    )

    assert plan.execution_overrides["enable_multifactor_rank"] is True
    assert plan.execution_overrides["momentum_top_pct"] == 0.25
    assert plan.execution_overrides["mf_topk"] == 7


def test_build_foundation_runtime_plan_keeps_explicit_override_priority() -> None:
    plan = mod.build_foundation_runtime_plan(
        runtime_config={
            "strategy": {
                "params": {
                    "ranking_mode": "residual_only",
                    "enable_residual_ranking": True,
                }
            }
        },
        overrides={"enable_multifactor_rank": False},
    )

    assert plan.execution_overrides["enable_multifactor_rank"] is False


def test_run_foundation_execution_shell_delegates_to_stage_pipeline_adapter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_stage_pipeline_bridge_backtest(request):
        captured["request"] = request
        pipeline_result = StagePipelineResult(
            execution_shell="stage_pipeline_shell_bridge",
            daily_loop_mode="single_day_loop",
            daily_results=(
                StageDayResult(
                    day_context=DayContext(
                        day_index=0,
                        trading_day=date(2026, 3, 2),
                        previous_trading_day=None,
                        next_trading_day=date(2026, 3, 3),
                        is_first_day=True,
                        is_last_day=False,
                    ),
                    filled_orders=(),
                    scheduled_for_next_day=({"symbol": "sh600000"},),
                    stage_order=("S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7"),
                    enabled_stages=("S1", "S2", "S4", "S5", "S6", "S9", "S8", "S7"),
                    stage_fragments={"S7": {"mode": "bridge_order_planner"}},
                    warnings=(),
                ),
                StageDayResult(
                    day_context=DayContext(
                        day_index=1,
                        trading_day=date(2026, 3, 3),
                        previous_trading_day=date(2026, 3, 2),
                        next_trading_day=None,
                        is_first_day=False,
                        is_last_day=True,
                    ),
                    filled_orders=({"symbol": "sh600000"},),
                    scheduled_for_next_day=(),
                    stage_order=("S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7"),
                    enabled_stages=("S1", "S2", "S4", "S5", "S6", "S9", "S8", "S7"),
                    stage_fragments={"S2": {"mode": "inline_stage_flow"}},
                    warnings=("market_filter_warn",),
                ),
            ),
            summary={
                "schema_version": "stage_pipeline_summary@1",
                "execution_shell": "stage_pipeline_shell_bridge",
                "daily_loop_mode": "single_day_loop",
                "stage_order": ["S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7"],
                "enabled_stages": ["S1", "S2", "S4", "S5", "S6", "S9", "S8", "S7"],
                "warnings": ["market_filter_warn"],
                "trading_days": 2,
            },
            final_state=PortfolioState.empty(cash=100000.0),
        )
        return StagePipelineBridgeBacktestResult(
            portfolio_result=PortfolioBacktestResult(
                daily=pd.DataFrame([{"date": "2026-03-02", "nav": 1.0}]),
                trades=pd.DataFrame(columns=["date", "symbol", "side"]),
                candidates=pd.DataFrame(columns=["date", "symbol"]),
                metrics={
                    "total_return": 0.1,
                    "audit": {
                        "accounting_integrity": {
                            "contract_version": "accounting_integrity_audit@1",
                            "status": "PASS",
                            "summary": {
                                "trading_days": 2,
                                "days_with_evidence": 2,
                                "missing_evidence_days": 0,
                                "cash_check_fail": 0,
                                "position_check_fail": 0,
                                "nav_check_fail": 0,
                                "invalid_nav_days": 0,
                                "negative_cash_days": 0,
                                "max_positions_breach_days": 0,
                            },
                            "samples": {},
                        }
                    },
                },
            ),
            pipeline_result=pipeline_result,
            route_id="provider_breakout_runtime",
        )

    monkeypatch.setattr(mod, "run_stage_pipeline_bridge_backtest", _fake_run_stage_pipeline_bridge_backtest)

    request = mod.FoundationExecutionRequest(
        compiled_plan={
            "runtime_config": {
                "initial_capital": 200000.0,
                "execution": {"lot_size": 200, "dividend_cash_timing_mode": "ex_date"},
                "sizing": {"order_value": 25000.0},
            },
            "execution_overrides": {
                "max_positions": 7,
                "fast_mode": True,
                "enable_strength_rank": True,
                "strength_ma": 55,
                "strength_top_k_mode": "TOP_K",
                "enable_multifactor_rank": True,
                "mf_topk": 8,
                "mf_concentrate_topn": 2,
                "mf_concentrate_scale": 1.2,
                "mf_rank_gate_mode": "RISK_ON_ONLY",
                "momentum_top_pct": 0.15,
            },
        },
        data_bundle=SimpleNamespace(),
        cfg_obj=SimpleNamespace(
            initial_capital=100000.0,
            execution=SimpleNamespace(lot_size=100),
            sizing=SimpleNamespace(order_value=10000.0),
            costs=SimpleNamespace(),
            exit=SimpleNamespace(),
            risk=SimpleNamespace(),
            risk_budget=SimpleNamespace(),
            market_filter=SimpleNamespace(),
            benchmark_regime=SimpleNamespace(),
            breadth=SimpleNamespace(),
            regime_engine=SimpleNamespace(),
            universe=SimpleNamespace(benchmark="000300.SH"),
        ),
        strategy=SimpleNamespace(),
    )

    result = mod.run_foundation_execution_shell(request)

    adapter_request = captured["request"]
    assert adapter_request.max_positions == 7
    assert adapter_request.lot_size == 200
    assert adapter_request.base_order_value == 25000.0
    assert adapter_request.dividend_cash_timing_mode == "ex_date"
    assert adapter_request.enable_strength_rank is True
    assert adapter_request.enable_multifactor_rank is True
    assert adapter_request.mf_rank_gate_mode == "RISK_ON_ONLY"
    assert adapter_request.momentum_top_pct == 0.15
    assert adapter_request.breadth_cfg is request.cfg_obj.breadth

    stage_summary = result.metrics["stage_summary"]
    assert stage_summary["route_id"] == "provider_breakout_runtime"
    assert stage_summary["days_with_fills"] == 1
    assert stage_summary["days_with_scheduled_orders"] == 1
    assert stage_summary["days_with_warnings"] == 1
    assert stage_summary["warnings"] == ["market_filter_warn"]

    stage_pipeline = result.metrics["stage_pipeline"]
    assert stage_pipeline["execution_shell"] == "stage_pipeline_shell_bridge"
    assert stage_pipeline["enabled_stages"] == ["S1", "S2", "S4", "S5", "S6", "S9", "S8", "S7"]
    assert result.metrics["audit"]["stage_pipeline"]["route_id"] == "provider_breakout_runtime"
    assert result.metrics["audit"]["accounting_integrity"]["status"] == "PASS"


def test_run_foundation_execution_shell_defaults_stage_base_order_value_to_zero_when_not_explicit(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_stage_pipeline_bridge_backtest(request):
        captured["request"] = request
        pipeline_result = StagePipelineResult(
            execution_shell="stage_pipeline_shell_bridge",
            daily_loop_mode="single_day_loop",
            daily_results=(),
            summary={
                "schema_version": "stage_pipeline_summary@1",
                "execution_shell": "stage_pipeline_shell_bridge",
                "daily_loop_mode": "single_day_loop",
                "stage_order": [],
                "enabled_stages": [],
                "warnings": [],
                "trading_days": 0,
            },
            final_state=PortfolioState.empty(cash=100000.0),
        )
        return StagePipelineBridgeBacktestResult(
            portfolio_result=PortfolioBacktestResult(
                daily=pd.DataFrame(),
                trades=pd.DataFrame(),
                candidates=pd.DataFrame(),
                metrics={},
            ),
            pipeline_result=pipeline_result,
            route_id="provider_breakout_runtime",
        )

    monkeypatch.setattr(mod, "run_stage_pipeline_bridge_backtest", _fake_run_stage_pipeline_bridge_backtest)

    request = mod.FoundationExecutionRequest(
        compiled_plan={
            "runtime_config": {
                "initial_capital": 200000.0,
                "execution": {"lot_size": 200},
                "sizing": {},
            },
            "execution_overrides": {},
        },
        data_bundle=SimpleNamespace(),
        cfg_obj=SimpleNamespace(
            initial_capital=100000.0,
            execution=SimpleNamespace(lot_size=100),
            sizing=SimpleNamespace(order_value=10000.0),
            costs=SimpleNamespace(),
            exit=SimpleNamespace(),
            risk=SimpleNamespace(),
            risk_budget=SimpleNamespace(),
            market_filter=SimpleNamespace(),
            benchmark_regime=SimpleNamespace(),
            breadth=SimpleNamespace(),
            regime_engine=SimpleNamespace(),
            universe=SimpleNamespace(benchmark="000300.SH"),
        ),
        strategy=SimpleNamespace(),
    )

    mod.run_foundation_execution_shell(request)

    adapter_request = captured["request"]
    assert adapter_request.base_order_value == 0.0
    assert adapter_request.dividend_cash_timing_mode == "pay_date"
