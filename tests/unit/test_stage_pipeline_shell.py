from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.stage_pipeline import (
    STAGE_EXECUTION_ORDER,
    PortfolioState,
    StageOutputs,
    StagePipelineRequest,
    run_stage_pipeline,
)
from backend.core.tools.data_bundle_builder import DataBundle


def _bundle() -> DataBundle:
    raw_history = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-02"), "symbol": "sh600000", "open": 10.0, "close": 10.2},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "sh600000", "open": 10.3, "close": 10.4},
        ]
    )
    return DataBundle(
        provider=None,  # type: ignore[arg-type]
        universe_mode="CUSTOM",
        symbols=["sh600000"],
        universe_meta={"universe_mode": "CUSTOM"},
        universe_filters_raw={},
        resolve_asof=date(2024, 1, 2),
        dynamic_all_a_entry=False,
        raw_history=raw_history,
        signal_history=raw_history.copy(deep=True),
        benchmark=pd.DataFrame(
            [
                {"date": pd.Timestamp("2024-01-02"), "symbol": "000300.SH", "open": 1.0, "close": 1.0},
                {"date": pd.Timestamp("2024-01-03"), "symbol": "000300.SH", "open": 1.1, "close": 1.1},
            ]
        ),
        trading_days=[date(2024, 1, 2), date(2024, 1, 3)],
        st_history=pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        sector_data={},
        industry_map={"sh600000": "Bank"},
        price_adj_mode="hfq",
        adj_factor_stats={"min": 1.0, "max": 1.0, "null_count": 0},
        summary={"symbols_count": 1},
    )


def test_stage_pipeline_shell_enforces_order_and_t_plus_one_scheduling() -> None:
    bundle = _bundle()
    call_log: list[tuple[date, str]] = []

    def _make_handler(stage_key: str):
        def _handler(day_context, bundle_view, portfolio_state, stage_inputs):
            call_log.append((day_context.trading_day, stage_key))
            payload = {"visible_rows": len(bundle_view.signal_history_view())}
            if stage_key == "S7" and day_context.trading_day == date(2024, 1, 2):
                payload["next_day_orders"] = (
                    {"symbol": "sh600000", "side": "BUY", "signal_day": day_context.trading_day.isoformat()},
                )
            return StageOutputs(
                stage_key=stage_key,
                enabled=True,
                candidate_symbols=("sh600000",),
                buy_symbols=stage_inputs.buy_symbols or ("sh600000",),
                payload=payload,
                summary_fragment={"day": day_context.trading_day.isoformat(), "stage": stage_key},
            )

        return _handler

    request = StagePipelineRequest(
        data_bundle=bundle,
        initial_state=PortfolioState.empty(cash=1000000),
        stage_handlers={stage_key: _make_handler(stage_key) for stage_key in STAGE_EXECUTION_ORDER},
    )
    result = run_stage_pipeline(request)

    assert result.summary["stage_order"] == list(STAGE_EXECUTION_ORDER)
    assert result.summary["enabled_stages"] == list(STAGE_EXECUTION_ORDER)
    assert result.summary["trading_days"] == 2
    assert len(result.daily_results) == 2
    assert result.daily_results[0].stage_order == STAGE_EXECUTION_ORDER
    assert result.daily_results[0].scheduled_for_next_day == (
        {"symbol": "sh600000", "side": "BUY", "signal_day": "2024-01-02"},
    )
    assert result.daily_results[0].filled_orders == ()
    assert result.daily_results[1].filled_orders == (
        {"symbol": "sh600000", "side": "BUY", "signal_day": "2024-01-02"},
    )

    first_day_order = [stage_key for trading_day, stage_key in call_log if trading_day == date(2024, 1, 2)]
    second_day_order = [stage_key for trading_day, stage_key in call_log if trading_day == date(2024, 1, 3)]
    assert first_day_order == list(STAGE_EXECUTION_ORDER)
    assert second_day_order == list(STAGE_EXECUTION_ORDER)


def test_stage_pipeline_shell_keeps_single_path_when_stages_return_neutral_output() -> None:
    bundle = _bundle()

    def _make_handler(stage_key: str):
        def _handler(day_context, bundle_view, portfolio_state, stage_inputs):
            if stage_key in {"S2", "S8"}:
                return StageOutputs.neutral(
                    stage_key,
                    stage_inputs,
                    summary_fragment={"disabled_by_config": True},
                )
            payload = {"visible_rows": len(bundle_view.signal_history_view())}
            if stage_key == "S7" and day_context.trading_day == date(2024, 1, 2):
                payload["next_day_orders"] = (
                    {"symbol": "sh600000", "side": "BUY", "signal_day": day_context.trading_day.isoformat()},
                )
            return StageOutputs(
                stage_key=stage_key,
                enabled=True,
                candidate_symbols=stage_inputs.candidate_symbols or ("sh600000",),
                holding_symbols=stage_inputs.holding_symbols,
                buy_symbols=stage_inputs.buy_symbols or ("sh600000",),
                sell_symbols=stage_inputs.sell_symbols,
                payload=payload,
                summary_fragment={"stage": stage_key},
            )

        return _handler

    result = run_stage_pipeline(
        StagePipelineRequest(
            data_bundle=bundle,
            initial_state=PortfolioState.empty(cash=1000000),
            stage_handlers={stage_key: _make_handler(stage_key) for stage_key in STAGE_EXECUTION_ORDER},
        )
    )

    assert result.summary["stage_order"] == list(STAGE_EXECUTION_ORDER)
    assert result.daily_results[0].stage_order == STAGE_EXECUTION_ORDER
    assert result.daily_results[0].enabled_stages == ("S1", "S3", "S4", "S5", "S6", "S9", "S7")
    assert result.daily_results[0].scheduled_for_next_day == (
        {"symbol": "sh600000", "side": "BUY", "signal_day": "2024-01-02"},
    )
    assert result.daily_results[1].filled_orders == (
        {"symbol": "sh600000", "side": "BUY", "signal_day": "2024-01-02"},
    )
    assert result.daily_results[0].stage_fragments["S2"]["mode"] == "neutral"
    assert result.daily_results[0].stage_fragments["S8"]["mode"] == "neutral"
