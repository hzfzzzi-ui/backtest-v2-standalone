from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.stage_pipeline import (
    DataBundleView,
    DayContext,
    PortfolioState,
    StageInputs,
    StageOutputs,
    StagePipelineCollector,
)
from backend.core.tools.data_bundle_builder import DataBundle


def _bundle() -> DataBundle:
    raw_history = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-02"), "symbol": "sh600000", "open": 10.0, "close": 10.2},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "sh600000", "open": 10.3, "close": 10.4},
            {"date": pd.Timestamp("2024-01-04"), "symbol": "sh600000", "open": 10.5, "close": 10.6},
        ]
    )
    signal_history = raw_history.copy(deep=True)
    benchmark = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-02"), "symbol": "000300.SH", "open": 1.0, "close": 1.0},
            {"date": pd.Timestamp("2024-01-03"), "symbol": "000300.SH", "open": 1.1, "close": 1.1},
            {"date": pd.Timestamp("2024-01-04"), "symbol": "000300.SH", "open": 1.2, "close": 1.2},
        ]
    )
    st_history = pd.DataFrame(
        [
            {"ts_code": "600000.SH", "start_date": pd.Timestamp("2024-01-04"), "end_date": None, "st_type": "ST"},
        ]
    )
    sector_data = {
        "801010.SI": pd.DataFrame(
            [
                {"trade_date": pd.Timestamp("2024-01-02"), "close": 1.0},
                {"trade_date": pd.Timestamp("2024-01-03"), "close": 1.1},
                {"trade_date": pd.Timestamp("2024-01-04"), "close": 1.2},
            ]
        )
    }
    return DataBundle(
        provider=None,  # type: ignore[arg-type]
        universe_mode="CUSTOM",
        symbols=["sh600000"],
        universe_meta={"universe_mode": "CUSTOM", "filters_config": {"price_min": 5}},
        universe_filters_raw={"price_min": 5},
        resolve_asof=date(2024, 1, 2),
        dynamic_all_a_entry=False,
        raw_history=raw_history,
        signal_history=signal_history,
        benchmark=benchmark,
        trading_days=[date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
        st_history=st_history,
        sector_data=sector_data,
        industry_map={"sh600000": "Bank"},
        price_adj_mode="hfq",
        adj_factor_stats={"min": 1.0, "max": 1.1, "null_count": 0},
        summary={"symbols_count": 1},
    )


def test_day_context_and_portfolio_state_contracts() -> None:
    ctx = DayContext.from_trading_days([date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)], 1)
    assert ctx.trading_day == date(2024, 1, 3)
    assert ctx.previous_trading_day == date(2024, 1, 2)
    assert ctx.next_trading_day == date(2024, 1, 4)
    assert ctx.is_first_day is False
    assert ctx.is_last_day is False
    assert ctx.signal_clock == "POST_CLOSE"
    assert ctx.execution_clock == "NEXT_OPEN"

    state = PortfolioState(
        cash=1000000,
        positions={"sh600000": {"qty": 100}},
        pending_orders={date(2024, 1, 4): [{"symbol": "sh600000", "side": "BUY"}]},
        nav=1005000,
        market_value=5000,
        metadata={"engine_mode": "VECTOR_FAST_STRICT"},
    )
    assert state.cash == 1000000.0
    assert state.nav == 1005000.0
    assert state.market_value == 5000.0
    assert tuple(state.pending_orders.keys()) == (date(2024, 1, 4),)
    assert isinstance(state.pending_orders[date(2024, 1, 4)], tuple)
    try:
        state.metadata["engine_mode"] = "CHANGED"  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("PortfolioState.metadata should be read-only")


def test_data_bundle_view_hides_future_rows_and_returns_copies() -> None:
    bundle = _bundle()
    view = DataBundleView.at(bundle, 1)

    assert view.trading_day == date(2024, 1, 3)
    assert view.visible_trading_days == (date(2024, 1, 2), date(2024, 1, 3))
    assert view.symbols == ("sh600000",)
    assert view.sector_keys == ("801010.SI",)

    raw_view = view.raw_history_view()
    signal_view = view.signal_history_view()
    benchmark_view = view.benchmark_view()
    current_raw = view.current_raw_frame()
    sector_view = view.sector_data_view()
    st_view = view.st_history_view()

    assert len(raw_view) == 2
    assert len(signal_view) == 2
    assert len(benchmark_view) == 2
    assert len(current_raw) == 1
    assert pd.to_datetime(raw_view["date"]).max().date() == date(2024, 1, 3)
    assert pd.to_datetime(benchmark_view["date"]).max().date() == date(2024, 1, 3)
    assert pd.to_datetime(current_raw["date"]).iloc[0].date() == date(2024, 1, 3)
    assert pd.to_datetime(sector_view["801010.SI"]["trade_date"]).max().date() == date(2024, 1, 3)
    assert st_view.empty

    raw_view.loc[0, "close"] = 999.0
    assert float(bundle.raw_history.loc[0, "close"]) == 10.2

    try:
        view.industry_map["sh600000"] = "Changed"  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("DataBundleView.industry_map should be read-only")


def test_stage_contracts_and_collector_summary() -> None:
    stage_inputs = StageInputs(
        candidate_symbols=["sh600000"],
        buy_symbols=["sh600000"],
        payload={"gate": "open"},
        reason_counts={"BUY_SIGNAL": 1},
        warnings=["test-warning"],
    )
    assert stage_inputs.candidate_symbols == ("sh600000",)
    assert stage_inputs.buy_symbols == ("sh600000",)
    try:
        stage_inputs.payload["gate"] = "closed"  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("StageInputs.payload should be read-only")

    neutral = StageOutputs.neutral("S2", stage_inputs, summary_fragment={"stage": "market_gate"})
    assert neutral.stage_key == "S2"
    assert neutral.enabled is False
    assert neutral.candidate_symbols == ("sh600000",)
    assert neutral.summary_fragment["mode"] == "neutral"
    assert neutral.summary_fragment["stage"] == "market_gate"
    assert neutral.reason_counts["BUY_SIGNAL"] == 1

    collector = StagePipelineCollector()
    collector.record(neutral)
    summary = collector.build_summary()
    assert summary["schema_version"] == "stage_pipeline_summary@1"
    assert summary["execution_shell"] == "stage_pipeline_shell"
    assert summary["stage_order"] == ["S2"]
    assert summary["enabled_stages"] == []
    assert summary["warnings"] == ["test-warning"]
