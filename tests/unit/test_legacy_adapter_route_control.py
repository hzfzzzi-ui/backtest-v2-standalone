from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np

from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters.day_controls import compute_day_controls
from backend.core.stage_pipeline.adapters.signal_postprocess import postprocess_day_signals
from backend.core.stage_pipeline.adapters.stage_applicability import is_stage_disabled, stage_is_applicable


def test_stage_applicability_respects_disabled_and_route_specific_rules() -> None:
    runtime = SimpleNamespace(
        request=SimpleNamespace(
            disabled_stages=("s6",),
            strategy=SimpleNamespace(enable_sector_gate=True),
        ),
        route_id="provider_breakout_runtime",
        _market_filter_cfg=None,
        _benchmark_regime_cfg=None,
        _dd_enabled=True,
    )

    assert is_stage_disabled(runtime.request.disabled_stages, "S6") is True
    assert stage_is_applicable(runtime, "S6") is False
    assert stage_is_applicable(runtime, "S2") is True
    assert stage_is_applicable(runtime, "S3") is True
    assert stage_is_applicable(runtime, "S8") is True


def test_stage_applicability_uses_filter_configs_for_s2() -> None:
    runtime = SimpleNamespace(
        request=SimpleNamespace(
            disabled_stages=(),
            strategy=SimpleNamespace(enable_sector_gate=False),
        ),
        route_id="strict_inline_runtime",
        _market_filter_cfg=SimpleNamespace(enabled=True),
        _benchmark_regime_cfg=None,
        _dd_enabled=False,
    )

    assert stage_is_applicable(runtime, "S2") is True
    assert stage_is_applicable(runtime, "S3") is False
    assert stage_is_applicable(runtime, "S8") is False


def test_compute_day_controls_breakout_route_preserves_market_state_and_counters() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        request=SimpleNamespace(
            max_positions=10,
            data_bundle=SimpleNamespace(trading_days=[trading_day]),
        ),
        route_id="provider_breakout_runtime",
        _portfolio_mode="equal_8",
        positions={},
        close_idx={},
        position_avg_cost={},
        _dd_enabled=True,
        _dd_reduce_pct=0.12,
        _dd_reduce_scale=0.4,
        _mf_enabled=True,
        _mf_state_arr=np.array([0], dtype=np.int8),
        _mf_mult_arr=np.array([1.0], dtype=float),
        _MARKET_STATE_NAMES=("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR"),
        _TRADE_MODE_NAMES=("TREND_MAIN", "TREND_LIGHT", "NO_TRADE"),
        market_filter_bull_days=0,
        market_filter_bear_days=0,
        market_state_trans_down_days=0,
        market_state_trans_up_days=0,
        trade_mode_main_days=0,
        trade_mode_light_days=0,
        trade_mode_notrade_days=0,
        _br_enabled=True,
        _br_gate_arr=np.array([True], dtype=bool),
        provider=SimpleNamespace(_risk_on=np.array([True], dtype=bool)),
    )

    controls = compute_day_controls(runtime, 0, trading_day, -0.05)

    assert controls["effective_max_positions"] == 8
    assert controls["dd_state"] == "NORMAL"
    assert controls["market_state"] == "BULL"
    assert controls["trade_mode"] == "TREND_MAIN"
    assert controls["benchmark_regime_on"] is True
    assert controls["risk_on_today"] is True
    assert runtime.market_filter_bull_days == 1
    assert runtime.trade_mode_main_days == 1


def test_compute_day_controls_non_breakout_route_uses_provider_diagnostics() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        request=SimpleNamespace(max_positions=10),
        route_id="strict_inline_runtime",
        _dd_enabled=True,
        _dd_reduce_pct=0.12,
        _dd_reduce_scale=0.4,
        _MARKET_STATE_NAMES=("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR"),
        _TRADE_MODE_NAMES=("TREND_MAIN", "TREND_LIGHT", "NO_TRADE"),
        provider=SimpleNamespace(
            _risk_on_map={trading_day: False},
            _market_state=np.array([1], dtype=np.int8),
            _trade_mode=np.array([2], dtype=np.int8),
        ),
    )

    controls = compute_day_controls(runtime, 0, trading_day, -0.2)

    assert controls["effective_max_positions"] == 4
    assert controls["dd_state"] == "REDUCED"
    assert controls["risk_on_today"] is False
    assert controls["market_state"] == "TRANS_DOWN"
    assert controls["trade_mode"] == "NO_TRADE"
    assert controls["benchmark_regime_on"] is True


def test_postprocess_day_signals_respects_breakout_gates() -> None:
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=True,
        _mf_enabled=False,
        _mf_state_arr=np.array([0], dtype=np.int8),
    )
    signals = DaySignals(
        sell_signals=[],
        buy_signals=[SimpleNamespace(symbol="SH600000")],
        exit_syms=set(),
        strength_map={},
        mf_score_map={},
        mf_gate_on_today=False,
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={},
    )

    gated = postprocess_day_signals(
        runtime,
        day_index=0,
        day_signals=signals,
        controls={"benchmark_regime_on": False},
    )

    assert gated.buy_signals == []


def test_postprocess_day_signals_respects_market_filter_state_gate() -> None:
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
        _mf_state_arr=np.array([3], dtype=np.int8),
    )
    signals = DaySignals(
        sell_signals=[],
        buy_signals=[SimpleNamespace(symbol="SH600000"), SimpleNamespace(symbol="SZ000001")],
        exit_syms=set(),
        strength_map={},
        mf_score_map={},
        mf_gate_on_today=False,
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={},
    )

    gated = postprocess_day_signals(
        runtime,
        day_index=0,
        day_signals=signals,
        controls={"benchmark_regime_on": True},
    )

    assert gated.buy_signals == []
