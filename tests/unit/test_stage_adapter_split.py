from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters.candidate_flow import build_candidate_stage_output
from backend.core.stage_pipeline.adapters.holding_flow import build_holding_stage_output
from backend.core.stage_pipeline.adapters.order_planning import build_s7_order_stage_output
from backend.core.stage_pipeline.adapters.route_runtime import build_signal_provider, initialize_route_controls
from backend.core.stage_pipeline.adapters.runtime_state import build_runtime_bootstrap, initialize_runtime_ledger
from backend.core.stage_pipeline.contracts import StageInputs
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.composite_strategy import CompositeStrategy
from backend.core.strategies.regime_router import RegimeRouter


def _minimal_bundle() -> SimpleNamespace:
    raw_history = pd.DataFrame(
        [
            {"date": "2026-03-02", "symbol": "sh600000", "open": 10.0, "close": 10.2},
            {"date": "2026-03-03", "symbol": "sh600000", "open": 10.3, "close": 10.4},
        ]
    )
    return SimpleNamespace(
        raw_history=raw_history,
        trading_days=[date(2026, 3, 2), date(2026, 3, 3)],
        benchmark=pd.DataFrame(columns=["date", "close"]),
    )


def test_build_signal_provider_resolves_known_routes() -> None:
    breakout = BreakoutTrendStrategy.__new__(BreakoutTrendStrategy)
    composite = CompositeStrategy.__new__(CompositeStrategy)
    regime_router = RegimeRouter.__new__(RegimeRouter)

    breakout_route, _ = build_signal_provider(breakout)
    composite_route, _ = build_signal_provider(composite)
    regime_route, _ = build_signal_provider(regime_router)
    strict_route, _ = build_signal_provider(SimpleNamespace())

    assert breakout_route == "provider_breakout_runtime"
    assert composite_route == "generic_inline_runtime"
    assert regime_route == "regime_router_inline_runtime"
    assert strict_route == "strict_inline_runtime"


def test_build_runtime_bootstrap_and_ledger_preserve_existing_defaults() -> None:
    request = SimpleNamespace(
        cost_cfg=None,
        sizing_cfg=None,
        risk_budget_cfg=None,
        data_bundle=_minimal_bundle(),
        strategy=SimpleNamespace(
            state={"universe_filters": {"min_price": 5.0}},
            min_price=3.0,
            portfolio_mode="equal_8",
        ),
    )

    bootstrap = build_runtime_bootstrap(
        request,
        market_filter_cfg=None,
        benchmark_regime_cfg=None,
    )
    ledger = initialize_runtime_ledger(100000.0)

    assert bootstrap.min_trade_price == 5.0
    assert bootstrap.portfolio_mode == "equal_8"
    assert bootstrap.weight_mode == "equal"
    assert bootstrap.dd_enabled is False
    assert bootstrap.open_idx[(date(2026, 3, 2), "sh600000")] == 10.0
    assert bootstrap.close_idx[(date(2026, 3, 3), "sh600000")] == 10.4

    assert ledger.cash == 100000.0
    assert ledger.peak_nav == 100000.0
    assert ledger.prev_nav == 100000.0
    assert ledger.positions == {}
    assert ledger.trade_rows == []


def test_initialize_route_controls_returns_default_arrays_for_non_breakout_routes() -> None:
    controls = initialize_route_controls(
        route_id="strict_inline_runtime",
        data_bundle=_minimal_bundle(),
        market_filter_cfg=None,
        benchmark_regime_cfg=None,
    )

    assert controls.mf_enabled is False
    assert controls.br_enabled is False
    assert np.array_equal(controls.mf_state_arr, np.zeros(2, dtype=np.int8))
    assert np.array_equal(controls.mf_mult_arr, np.ones(2, dtype=float))
    assert np.array_equal(controls.br_gate_arr, np.ones(2, dtype=bool))


def _sample_current_day() -> dict[str, object]:
    return {
        "controls": {
            "risk_on_today": True,
            "benchmark_regime_on": True,
            "market_state": "BULL",
            "effective_max_positions": 5,
        },
        "holding_symbols": ("sh600001",),
        "day_signals": DaySignals(
            sell_signals=[SimpleNamespace(symbol="SH600001")],
            buy_signals=[SimpleNamespace(symbol="SH600000"), SimpleNamespace(symbol="SZ000001")],
            exit_syms={"sh600001"},
            strength_map={"sh600000": 1.2},
            mf_score_map={"sh600000": 3.0},
            mf_gate_on_today=True,
            strong_risk_on=False,
            exit_counts=ExitCounts(),
            diagnostics={},
        ),
    }


def test_candidate_flow_module_preserves_candidate_stage_shape() -> None:
    current_day = _sample_current_day()

    s2 = build_candidate_stage_output(
        stage_key="S2",
        stage_inputs=StageInputs(),
        current_day=current_day,
        enabled=True,
    )
    s6 = build_candidate_stage_output(
        stage_key="S6",
        stage_inputs=StageInputs(sell_symbols=("sh600001",)),
        current_day=current_day,
        enabled=True,
    )
    neutral = build_candidate_stage_output(
        stage_key="S3",
        stage_inputs=StageInputs(candidate_symbols=("sh600000",)),
        current_day=current_day,
        enabled=False,
    )

    assert s2.summary_fragment["market_state"] == "BULL"
    assert s2.candidate_symbols == ("sh600000", "sz000001")
    assert s6.buy_symbols == ("sh600000", "sz000001")
    assert s6.sell_symbols == ("sh600001",)
    assert neutral.enabled is False
    assert neutral.summary_fragment["mode"] == "neutral"


def test_holding_flow_module_preserves_holding_stage_shape() -> None:
    current_day = _sample_current_day()

    s9 = build_holding_stage_output(
        stage_key="S9",
        stage_inputs=StageInputs(),
        current_day=current_day,
        enabled=True,
    )
    s8 = build_holding_stage_output(
        stage_key="S8",
        stage_inputs=StageInputs(sell_symbols=("sh600001",)),
        current_day=current_day,
        enabled=True,
    )
    neutral = build_holding_stage_output(
        stage_key="S8",
        stage_inputs=StageInputs(),
        current_day=current_day,
        enabled=False,
    )

    assert s9.sell_symbols == ("sh600001",)
    assert s8.summary_fragment["effective_max_positions"] == 5
    assert neutral.enabled is False
    assert neutral.summary_fragment["mode"] == "neutral"


def test_order_planning_module_preserves_s7_shape(monkeypatch) -> None:
    current_day = {
        "day": date(2026, 3, 2),
        "controls": {"effective_max_positions": 5, "risk_on_today": True},
        "day_signals": DaySignals(
            sell_signals=[SimpleNamespace(symbol="SH600001")],
            buy_signals=[SimpleNamespace(symbol="SH600000")],
            exit_syms=set(),
            strength_map={"sh600000": 1.0},
            mf_score_map={"sh600000": 2.0},
            mf_gate_on_today=True,
            strong_risk_on=False,
            exit_counts=ExitCounts(),
            diagnostics={},
        ),
        "next_open": {"sh600000": 10.0, "sh600001": 9.8},
        "nav": 100000.0,
        "holding_symbols": ("sh600001",),
    }

    def _fake_gate(**_kwargs):
        return True

    def _fake_build_rebalance_orders(**kwargs):
        kwargs["candidate_audit"].append({"symbol": "sh600000", "selected": True})
        kwargs["debug_plan"]["reject_reason_counts"] = {"NO_CASH": 1}
        return [
            SimpleNamespace(side=Side.SELL, symbol="SH600001", qty=100, reason_code="EXIT", meta={"rank": 1}),
            SimpleNamespace(side=Side.BUY, symbol="SH600000", qty=100, reason_code="ENTRY", meta={"rank": 2}),
        ]

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.resolve_mf_gate_on_today",
        _fake_gate,
    )
    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_rebalance_orders",
        _fake_build_rebalance_orders,
    )

    diag_calls: list[dict[str, object]] = []
    runtime = SimpleNamespace(
        _current_day=current_day,
        request=SimpleNamespace(
            enable_multifactor_rank=True,
            mf_rank_gate_mode="ALWAYS_ON",
            fast_mode=False,
            lot_size=100,
            enable_strength_rank=False,
            strength_ma=120,
            strength_top_k_mode="FILL_TO_MAX",
            mf_topk=10,
            mf_concentrate_topn=3,
            mf_concentrate_scale=1.5,
            momentum_top_pct=0.0,
        ),
        provider=SimpleNamespace(_feats=None, _mx=None, _sym_to_col={}),
        positions={"sh600001": 100},
        cash=100000.0,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _min_trade_price=5.0,
        candidate_rows=[],
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **kwargs: diag_calls.append(kwargs),
    )

    output = build_s7_order_stage_output(runtime)

    assert output.stage_key == "S7"
    assert output.buy_symbols == ("sh600000",)
    assert output.sell_symbols == ("sh600001",)
    assert output.reason_counts["NO_CASH"] == 1
    assert output.summary_fragment["buy_orders_count"] == 1
    assert output.summary_fragment["sell_orders_count"] == 1
    assert runtime.candidate_rows == [{"symbol": "sh600000", "selected": True}]
    assert len(diag_calls) == 1
