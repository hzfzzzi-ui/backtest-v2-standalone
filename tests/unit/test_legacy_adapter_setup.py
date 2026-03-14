from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from backend.core.config.models import BenchmarkRegimeConfig, BreadthConfig, CostConfig, MarketFilterConfig, RiskBudgetConfig, SizingConfig
from backend.core.stage_pipeline.adapters.legacy_adapter import LegacyStagePipelineRequest
from backend.core.stage_pipeline.adapters.route_runtime import (
    build_signal_provider,
    initialize_route_controls,
    precompute_signal_provider,
)
from backend.core.stage_pipeline.adapters.runtime_state import (
    build_runtime_bootstrap,
    initialize_runtime_counters,
    initialize_runtime_ledger,
)
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.strategies.regime_router import RegimeRouter
from backend.core.tools.data_bundle_builder import DataBundle


def _bundle(*, periods: int = 260) -> DataBundle:
    days = [ts.date() for ts in pd.bdate_range("2023-01-02", periods=periods)]
    raw_rows = [
        {
            "date": pd.Timestamp(day),
            "symbol": "sh600000",
            "open": 10.0 + idx * 0.01,
            "close": 10.1 + idx * 0.01,
            "volume": 1000.0 + idx,
            "amount": 10000.0 + idx * 10,
            "is_suspended": False,
            "limit_up": 11.0 + idx * 0.01,
            "limit_down": 9.0 + idx * 0.01,
        }
        for idx, day in enumerate(days)
    ]
    benchmark_rows = [
        {"date": pd.Timestamp(day), "symbol": "000300.SH", "open": 100.0 + idx, "close": 100.5 + idx}
        for idx, day in enumerate(days)
    ]
    raw_history = pd.DataFrame(raw_rows)
    return DataBundle(
        provider=None,  # type: ignore[arg-type]
        universe_mode="CUSTOM",
        symbols=["sh600000"],
        universe_meta={"universe_mode": "CUSTOM"},
        universe_filters_raw={},
        resolve_asof=days[0],
        dynamic_all_a_entry=False,
        raw_history=raw_history,
        signal_history=raw_history.copy(deep=True),
        benchmark=pd.DataFrame(benchmark_rows),
        trading_days=days,
        st_history=pd.DataFrame(columns=["ts_code", "start_date", "end_date", "st_type"]),
        sector_data={},
        industry_map={"sh600000": "Bank"},
        price_adj_mode="hfq",
        adj_factor_stats={"min": 1.0, "max": 1.0, "null_count": 0},
        summary={"symbols_count": 1},
    )


def _request(*, strategy, bundle: DataBundle | None = None) -> LegacyStagePipelineRequest:
    return LegacyStagePipelineRequest(
        data_bundle=bundle or _bundle(),
        strategy=strategy,
        initial_cash=500000.0,
        max_positions=8,
        lot_size=100,
        strength_ma=55,
        enable_multifactor_rank=True,
        mf_rank_gate_mode="RISK_ON_ONLY",
        cost_cfg=CostConfig(slippage_bps=5.0, commission_rate=0.0005, commission_min=6.0, stamp_tax_rate=0.001),
        sizing_cfg=SizingConfig(weight_mode="inverse_vol", min_positions=3),
        risk_budget_cfg=RiskBudgetConfig(enabled=True, dd_reduce_pct=0.12, dd_reduce_scale=0.4),
        market_filter_cfg=MarketFilterConfig(enabled=True, slope_window=5, slope_ma_period=20),
        benchmark_regime_cfg=BenchmarkRegimeConfig(enabled=True, fast_period=10, slow_period=30, slope_window=3),
    )


def test_build_signal_provider_maps_strategy_type_to_route() -> None:
    route_id, provider = build_signal_provider(BreakoutTrendStrategy.__new__(BreakoutTrendStrategy))
    assert route_id == "provider_breakout_runtime"
    assert provider.__class__.__name__ == "BreakoutTrendProvider"

    route_id, provider = build_signal_provider(CompositeStrategy.__new__(CompositeStrategy))
    assert route_id == "generic_inline_runtime"
    assert provider.__class__.__name__ == "GenericSignalProvider"

    route_id, provider = build_signal_provider(RegimeRouter.__new__(RegimeRouter))
    assert route_id == "regime_router_inline_runtime"
    assert provider.__class__.__name__ == "RegimeRouterSignalProvider"

    route_id, provider = build_signal_provider(SimpleNamespace())
    assert route_id == "strict_inline_runtime"
    assert provider.__class__.__name__ == "SMASignalProvider"


def test_build_runtime_bootstrap_normalizes_runtime_defaults() -> None:
    strategy = SimpleNamespace(
        state={"universe_filters": {"min_price": 7.5}},
        portfolio_mode="equal_8",
        min_price=0.0,
    )
    request = _request(strategy=strategy)

    bootstrap = build_runtime_bootstrap(
        request,
        market_filter_cfg=request.market_filter_cfg,
        benchmark_regime_cfg=request.benchmark_regime_cfg,
    )

    assert bootstrap.slip_bps == 0.0005
    assert bootstrap.comm_rate == 0.0005
    assert bootstrap.comm_min == 6.0
    assert bootstrap.stamp_rate == 0.001
    assert bootstrap.weight_mode == "inverse_vol"
    assert bootstrap.min_positions_cfg == 3
    assert bootstrap.dd_enabled is True
    assert bootstrap.dd_reduce_pct == 0.12
    assert bootstrap.dd_reduce_scale == 0.4
    assert bootstrap.portfolio_mode == "equal_8"
    assert bootstrap.min_trade_price == 7.5
    assert bootstrap.open_idx[(request.data_bundle.trading_days[0], "sh600000")] > 0
    assert bootstrap.close_idx[(request.data_bundle.trading_days[0], "sh600000")] > 0
    assert bootstrap.volume_idx[(request.data_bundle.trading_days[0], "sh600000")] > 0
    assert bootstrap.amount_idx[(request.data_bundle.trading_days[0], "sh600000")] > 0
    assert bootstrap.suspended_idx[(request.data_bundle.trading_days[0], "sh600000")] is False
    assert bootstrap.limit_up_idx[(request.data_bundle.trading_days[0], "sh600000")] > 0
    assert bootstrap.limit_down_idx[(request.data_bundle.trading_days[0], "sh600000")] > 0


def test_initialize_runtime_state_helpers_start_clean() -> None:
    ledger = initialize_runtime_ledger(123456.0)
    counters = initialize_runtime_counters()

    assert ledger.cash == 123456.0
    assert ledger.peak_nav == 123456.0
    assert ledger.prev_nav == 123456.0
    assert ledger.positions == {}
    assert ledger.trade_rows == []
    assert ledger.order_reject_reason_counts == {}
    assert ledger.simulation_t0 > 0

    assert counters.market_filter_bull_days == 0
    assert counters.trade_mode_main_days == 0
    assert counters.trade_mode_notrade_days == 0


def test_initialize_route_controls_preserves_default_non_breakout_path() -> None:
    bundle = _bundle(periods=40)
    controls = initialize_route_controls(
        route_id="strict_inline_runtime",
        data_bundle=bundle,
        market_filter_cfg=MarketFilterConfig(enabled=True),
        benchmark_regime_cfg=BenchmarkRegimeConfig(enabled=True),
    )

    assert controls.mf_enabled is False
    assert controls.br_enabled is False
    assert controls.breadth_enabled is False
    assert len(controls.mf_state_arr) == 40
    assert len(controls.br_gate_arr) == 40
    assert controls.br_gate_arr.all()


def test_initialize_route_controls_builds_breakout_arrays_from_benchmark_history() -> None:
    bundle = _bundle(periods=260)
    controls = initialize_route_controls(
        route_id="provider_breakout_runtime",
        data_bundle=bundle,
        market_filter_cfg=MarketFilterConfig(enabled=True, slope_window=5, slope_ma_period=20),
        benchmark_regime_cfg=BenchmarkRegimeConfig(enabled=True, fast_period=10, slow_period=30, slope_window=3),
    )

    assert controls.mf_enabled is True
    assert controls.br_enabled is True
    assert len(controls.mf_state_arr) == 260
    assert len(controls.mf_mult_arr) == 260
    assert len(controls.br_gate_arr) == 260
    assert len(controls.breadth_score_arr) == 260
    assert len(controls.breadth_maxpos_arr) == 260
    assert bool(controls.br_gate_arr[-1]) is True
    assert int(controls.mf_state_arr[-1]) == 0


def test_initialize_route_controls_builds_breadth_arrays_from_provider_matrices() -> None:
    bundle = _bundle(periods=40)
    close = pd.DataFrame(
        {
            "a": [10.0 + i * 0.10 for i in range(40)],
            "b": [10.0 + i * 0.05 for i in range(40)],
            "c": [10.0 - i * 0.02 for i in range(40)],
        }
    ).to_numpy(dtype=float)
    tradable = pd.DataFrame(True, index=range(40), columns=range(3)).to_numpy(dtype=bool)
    provider = SimpleNamespace(_mx=SimpleNamespace(close=close, tradable=tradable))

    controls = initialize_route_controls(
        route_id="provider_breakout_runtime",
        data_bundle=bundle,
        market_filter_cfg=MarketFilterConfig(enabled=False),
        benchmark_regime_cfg=BenchmarkRegimeConfig(enabled=False),
        breadth_cfg=BreadthConfig(enabled=True, score_type="combo", min_positions=4, max_positions=8),
        provider=provider,
    )

    assert controls.breadth_enabled is True
    assert len(controls.breadth_score_arr) == 40
    assert len(controls.breadth_maxpos_arr) == 40
    assert int(controls.breadth_maxpos_arr[-1]) >= 4
    assert int(controls.breadth_maxpos_arr[-1]) <= 8


def test_precompute_signal_provider_passes_expected_inputs_to_provider() -> None:
    captured: dict[str, object] = {}

    class _FakeProvider:
        def precompute(self, **kwargs):
            captured.update(kwargs)

    bundle = _bundle(periods=30)
    strategy = SimpleNamespace(regime_filter_cfg={"mode": "off"})
    provider = _FakeProvider()
    mf_cfg = MarketFilterConfig(enabled=True)
    br_cfg = BenchmarkRegimeConfig(enabled=True)
    sizing_cfg = SizingConfig(weight_mode="inverse_vol")
    risk_cfg = RiskBudgetConfig(enabled=True)

    precompute_signal_provider(
        provider,  # type: ignore[arg-type]
        data_bundle=bundle,
        strategy=strategy,
        exit_cfg=None,
        strength_ma=55,
        initial_cash=500000.0,
        max_positions=8,
        history_lookback_days=120,
        enable_multifactor_rank=True,
        mf_rank_gate_mode="RISK_ON_ONLY",
        market_filter_cfg=mf_cfg,
        benchmark_regime_cfg=br_cfg,
        sizing_cfg=sizing_cfg,
        risk_budget_cfg=risk_cfg,
    )

    assert captured["history"] is bundle.signal_history
    assert captured["benchmark"] is bundle.benchmark
    assert captured["raw_history"] is bundle.raw_history
    assert captured["trading_days"] == bundle.trading_days
    assert captured["strength_ma"] == 55
    assert captured["base_order_value"] == 62500.0
    assert captured["market_filter_cfg"] is mf_cfg
    assert captured["benchmark_regime_cfg"] is br_cfg
    assert captured["sizing_cfg"] is sizing_cfg
    assert captured["risk_budget_cfg"] is risk_cfg
    assert captured["regime_filter_cfg"] == {"mode": "off"}
