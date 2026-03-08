from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, Callable, Mapping

from backend.core.tools.data_bundle_builder import DataBundle

from .collector import STAGE_SUMMARY_SCHEMA_VERSION, StagePipelineCollector
from .context import DataBundleView, DayContext, PortfolioState
from .contracts import StageInputs, StageOutputs


STAGE_EXECUTION_ORDER: tuple[str, ...] = ("S1", "S2", "S3", "S4", "S5", "S6", "S9", "S8", "S7")
StageHandler = Callable[[DayContext, DataBundleView, PortfolioState, StageInputs], StageOutputs]


@dataclass(frozen=True, slots=True)
class StagePipelineRequest:
    data_bundle: DataBundle
    initial_state: PortfolioState = field(default_factory=PortfolioState.empty)
    stage_handlers: Mapping[str, StageHandler] = field(default_factory=dict)
    execution_shell: str = "stage_pipeline_shell"
    daily_loop_mode: str = "single_day_loop"


@dataclass(frozen=True, slots=True)
class StageDayResult:
    day_context: DayContext
    filled_orders: tuple[Any, ...]
    scheduled_for_next_day: tuple[Any, ...]
    stage_order: tuple[str, ...]
    enabled_stages: tuple[str, ...]
    stage_fragments: Mapping[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StagePipelineResult:
    execution_shell: str
    daily_loop_mode: str
    daily_results: tuple[StageDayResult, ...]
    summary: Mapping[str, Any]
    final_state: PortfolioState


def _freeze_stage_handlers(raw: Mapping[str, StageHandler] | None = None) -> Mapping[str, StageHandler]:
    return MappingProxyType(dict(raw or {}))


def _stage_inputs_from_output(output: StageOutputs) -> StageInputs:
    return StageInputs(
        candidate_symbols=output.candidate_symbols,
        holding_symbols=output.holding_symbols,
        buy_symbols=output.buy_symbols,
        sell_symbols=output.sell_symbols,
        payload=output.payload,
        reason_counts=output.reason_counts,
        warnings=output.warnings,
    )


def _schedule_for_next_day(
    pending_orders: dict[date, list[Any]],
    next_trading_day: date | None,
    stage_output: StageOutputs,
) -> tuple[Any, ...]:
    scheduled = tuple(stage_output.payload.get("next_day_orders") or ())
    if not scheduled or next_trading_day is None:
        return scheduled
    pending_orders.setdefault(next_trading_day, []).extend(scheduled)
    return scheduled


def run_stage_pipeline(request: StagePipelineRequest) -> StagePipelineResult:
    handlers = _freeze_stage_handlers(request.stage_handlers)
    state = request.initial_state
    pending_orders: dict[date, list[Any]] = {
        key: list(value)
        for key, value in dict(request.initial_state.pending_orders).items()
    }
    daily_results: list[StageDayResult] = []
    overall_enabled: list[str] = []
    overall_warnings: list[str] = []

    for day_index, trading_day in enumerate(request.data_bundle.trading_days):
        day_context = DayContext.from_trading_days(request.data_bundle.trading_days, day_index)
        if trading_day != day_context.trading_day:
            raise ValueError("trading_day sequence mismatch while building stage pipeline day context")
        bundle_view = DataBundleView.at(request.data_bundle, day_index)
        fills_today = tuple(pending_orders.pop(day_context.trading_day, ()))
        stage_inputs = StageInputs(payload={"fills_today": fills_today})
        collector = StagePipelineCollector()

        for stage_key in STAGE_EXECUTION_ORDER:
            handler = handlers.get(stage_key)
            if handler is None:
                output = StageOutputs.neutral(
                    stage_key,
                    stage_inputs,
                    summary_fragment={"auto": "missing_stage_handler"},
                )
            else:
                output = handler(day_context, bundle_view, state, stage_inputs)
                if output.stage_key != stage_key:
                    raise ValueError(f"stage handler returned mismatched stage key: expected={stage_key} actual={output.stage_key}")
            collector.record(output)
            stage_inputs = _stage_inputs_from_output(output)

        s7_output = collector.records[-1]
        scheduled = _schedule_for_next_day(pending_orders, day_context.next_trading_day, s7_output)
        day_summary = collector.build_summary(
            execution_shell=request.execution_shell,
            daily_loop_mode=request.daily_loop_mode,
        )
        overall_enabled.extend([stage for stage in day_summary["enabled_stages"] if stage not in overall_enabled])
        overall_warnings.extend(day_summary["warnings"])

        state = PortfolioState(
            cash=state.cash,
            positions=state.positions,
            pending_orders={key: tuple(value) for key, value in pending_orders.items()},
            nav=state.nav,
            market_value=state.market_value,
            metadata={
                "last_trading_day": day_context.trading_day.isoformat(),
                "fills_today": len(fills_today),
                "scheduled_for_next_day": len(scheduled),
            },
        )
        daily_results.append(
            StageDayResult(
                day_context=day_context,
                filled_orders=fills_today,
                scheduled_for_next_day=scheduled,
                stage_order=tuple(day_summary["stage_order"]),
                enabled_stages=tuple(day_summary["enabled_stages"]),
                stage_fragments=MappingProxyType(dict(day_summary["stage_fragments"])),
                warnings=tuple(day_summary["warnings"]),
            )
        )

    summary = {
        "schema_version": STAGE_SUMMARY_SCHEMA_VERSION,
        "execution_shell": request.execution_shell,
        "daily_loop_mode": request.daily_loop_mode,
        "stage_order": list(STAGE_EXECUTION_ORDER),
        "enabled_stages": list(overall_enabled),
        "warnings": list(overall_warnings),
        "trading_days": len(daily_results),
    }
    return StagePipelineResult(
        execution_shell=request.execution_shell,
        daily_loop_mode=request.daily_loop_mode,
        daily_results=tuple(daily_results),
        summary=MappingProxyType(summary),
        final_state=state,
    )
