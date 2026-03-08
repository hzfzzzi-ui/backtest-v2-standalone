from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.audit.experiment_audit import (
    build_stage_pipeline_meta,
    build_stage_summary,
    merge_experiment_audit,
)
from backend.core.config.models import BacktestConfig
from backend.core.portfolio.portfolio_builder import PortfolioBacktestResult
from backend.core.stage_pipeline.adapters import (
    LegacyStagePipelineRequest,
    run_legacy_stage_pipeline_backtest,
)
from backend.core.tools.data_bundle_builder import DataBundle


_EXECUTION_OVERRIDE_KEYS = (
    "max_positions",
    "fast_mode",
    "enable_strength_rank",
    "strength_ma",
    "strength_top_k_mode",
    "enable_multifactor_rank",
    "mf_topk",
    "mf_concentrate_topn",
    "mf_concentrate_scale",
    "mf_rank_gate_mode",
    "momentum_top_pct",
)


@dataclass(slots=True)
class FoundationCompatibilityRequest:
    compiled_plan: dict[str, Any]
    data_bundle: DataBundle
    cfg_obj: BacktestConfig
    strategy: Any


def build_foundation_compiled_plan(
    *,
    runtime_config: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ov = dict(overrides or {})
    execution_overrides = {key: ov[key] for key in _EXECUTION_OVERRIDE_KEYS if key in ov}
    return {
        "runtime_config": dict(runtime_config or {}),
        "execution_overrides": execution_overrides,
    }


def _plan_runtime_config(compiled_plan: dict[str, Any]) -> dict[str, Any]:
    runtime_config = compiled_plan.get("runtime_config")
    return dict(runtime_config) if isinstance(runtime_config, dict) else {}


def _plan_execution_overrides(compiled_plan: dict[str, Any]) -> dict[str, Any]:
    execution_overrides = compiled_plan.get("execution_overrides")
    return dict(execution_overrides) if isinstance(execution_overrides, dict) else {}


def run_foundation_compatibility_shell(request: FoundationCompatibilityRequest):
    runtime_config = _plan_runtime_config(request.compiled_plan)
    execution_overrides = _plan_execution_overrides(request.compiled_plan)

    runtime_execution = runtime_config.get("execution") if isinstance(runtime_config.get("execution"), dict) else {}
    runtime_sizing = runtime_config.get("sizing") if isinstance(runtime_config.get("sizing"), dict) else {}
    adapter_result = run_legacy_stage_pipeline_backtest(
        LegacyStagePipelineRequest(
            data_bundle=request.data_bundle,
            strategy=request.strategy,
            initial_cash=float(runtime_config.get("initial_capital", request.cfg_obj.initial_capital)),
            max_positions=int(execution_overrides.get("max_positions", 10)),
            lot_size=int(runtime_execution.get("lot_size", request.cfg_obj.execution.lot_size)),
            enable_strength_rank=bool(execution_overrides.get("enable_strength_rank", False)),
            strength_ma=int(execution_overrides.get("strength_ma", 120)),
            strength_top_k_mode=str(execution_overrides.get("strength_top_k_mode", "FILL_TO_MAX")),
            fast_mode=bool(execution_overrides.get("fast_mode", True)),
            enable_multifactor_rank=bool(execution_overrides.get("enable_multifactor_rank", False)),
            mf_topk=int(execution_overrides.get("mf_topk", 10)),
            mf_concentrate_topn=int(execution_overrides.get("mf_concentrate_topn", 3)),
            mf_concentrate_scale=float(execution_overrides.get("mf_concentrate_scale", 1.5)),
            mf_rank_gate_mode=str(execution_overrides.get("mf_rank_gate_mode", "ALWAYS_ON")),
            momentum_top_pct=float(execution_overrides.get("momentum_top_pct", 0.0)),
            cost_cfg=request.cfg_obj.costs,
            exit_cfg=request.cfg_obj.exit,
            sizing_cfg=request.cfg_obj.sizing,
            base_order_value=float(runtime_sizing.get("order_value", request.cfg_obj.sizing.order_value)),
            risk_budget_cfg=request.cfg_obj.risk_budget,
            market_filter_cfg=request.cfg_obj.market_filter,
            benchmark_regime_cfg=request.cfg_obj.benchmark_regime,
        )
    )
    base_result = adapter_result.portfolio_result
    metrics = dict(base_result.metrics or {})
    stage_summary = build_stage_summary(
        route_id=adapter_result.route_id,
        pipeline_result=adapter_result.pipeline_result,
    )
    stage_pipeline = build_stage_pipeline_meta(stage_summary)
    audit = merge_experiment_audit(
        metrics.get("audit") if isinstance(metrics.get("audit"), dict) else {},
        stage_pipeline=stage_pipeline,
        stage_summary=stage_summary,
    )
    metrics["stage_summary"] = stage_summary
    metrics["stage_pipeline"] = stage_pipeline
    metrics["audit"] = audit
    return PortfolioBacktestResult(
        daily=base_result.daily,
        trades=base_result.trades,
        candidates=base_result.candidates,
        metrics=metrics,
    )
