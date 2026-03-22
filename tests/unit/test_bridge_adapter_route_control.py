from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters import bridge_adapter
from backend.core.stage_pipeline.adapters.route_runtime import initialize_route_controls
from backend.core.stage_pipeline.adapters.day_controls import compute_day_controls
from backend.core.stage_pipeline.adapters.signal_postprocess import postprocess_day_signals
from backend.core.stage_pipeline.adapters.stage_applicability import is_stage_disabled, stage_is_applicable
from backend.core.stage_pipeline.context import DayContext


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
        _breadth_enabled=True,
        _breadth_score_arr=np.array([0.40], dtype=float),
        _breadth_maxpos_arr=np.array([6], dtype=np.int32),
        provider=SimpleNamespace(_risk_on=np.array([True], dtype=bool)),
    )

    controls = compute_day_controls(runtime, 0, trading_day, -0.05)

    assert controls["effective_max_positions"] == 6
    assert controls["dd_state"] == "NORMAL"
    assert controls["market_state"] == "BULL"
    assert controls["trade_mode"] == "TREND_MAIN"
    assert controls["benchmark_regime_on"] is True
    assert controls["risk_on_today"] is True
    assert controls["breadth_score"] == 0.40
    assert controls["breadth_max_positions"] == 6
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


def test_initialize_route_controls_formal_engine_uses_light_multiplier_fallbacks() -> None:
    trading_day = date(2026, 3, 2)
    controls = initialize_route_controls(
        route_id="provider_breakout_runtime",
        data_bundle=SimpleNamespace(
            benchmark=pd.DataFrame(),
            trading_days=[trading_day],
        ),
        market_filter_cfg=SimpleNamespace(
            enabled=True,
            bull_multiplier=1.5,
            light_multiplier=0.6,
            trans_down_multiplier=None,
            trans_up_multiplier=None,
            bear_multiplier=None,
        ),
        benchmark_regime_cfg=None,
        breadth_cfg=None,
        provider=SimpleNamespace(
            _regime_engine_name="market_regime_framework",
            _market_state=np.array([1], dtype=np.int8),
            _trade_mode=np.array([1], dtype=np.int8),
        ),
    )

    assert controls.mf_enabled is True
    assert float(controls.mf_mult_arr[0]) == 0.6


def test_initialize_route_controls_weekly_engine_uses_provider_risk_budget_multiplier() -> None:
    trading_day = date(2026, 3, 2)
    controls = initialize_route_controls(
        route_id="provider_breakout_runtime",
        data_bundle=SimpleNamespace(
            benchmark=pd.DataFrame(),
            trading_days=[trading_day],
        ),
        market_filter_cfg=SimpleNamespace(enabled=True, bull_multiplier=1.8, light_multiplier=0.6),
        benchmark_regime_cfg=None,
        breadth_cfg=None,
        provider=SimpleNamespace(
            _regime_engine_name="weekly_five_state",
            _market_state=np.array([4], dtype=np.int8),
            _trade_mode=np.array([0], dtype=np.int8),
            _risk_budget_multiplier_arr=np.array([0.4], dtype=float),
        ),
    )

    assert controls.mf_enabled is True
    assert float(controls.mf_mult_arr[0]) == 0.4


def test_initialize_route_controls_legacy_overlay_uses_provider_veto_arrays() -> None:
    trading_day = date(2026, 3, 2)
    controls = initialize_route_controls(
        route_id="provider_breakout_runtime",
        data_bundle=SimpleNamespace(
            benchmark=pd.DataFrame(),
            trading_days=[trading_day],
        ),
        market_filter_cfg=SimpleNamespace(enabled=True, bull_multiplier=1.5, light_multiplier=0.6),
        benchmark_regime_cfg=None,
        breadth_cfg=None,
        provider=SimpleNamespace(
            _regime_engine_name="ma200_legacy",
            _legacy_turn_weak_overlay_active=True,
            _market_state=np.array([0], dtype=np.int8),
            _trade_mode=np.array([2], dtype=np.int8),
            _risk_budget_multiplier_arr=np.array([0.0], dtype=float),
        ),
    )

    assert controls.mf_enabled is True
    assert int(controls.mf_trade_mode_arr[0]) == 2
    assert float(controls.mf_mult_arr[0]) == 0.0


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


def test_postprocess_day_signals_freezes_entries_in_trans_down_for_m1_mode() -> None:
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
        _mf_state_arr=np.array([1], dtype=np.int8),
        provider=SimpleNamespace(_risk_off_exit_mode="trans_down_freeze_bear_exit"),
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
        controls={"benchmark_regime_on": True, "market_state": "TRANS_DOWN"},
    )

    assert gated.buy_signals == []


def test_postprocess_day_signals_freezes_entries_in_trans_up_when_flag_enabled() -> None:
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
        _mf_state_arr=np.array([2], dtype=np.int8),
        _market_filter_cfg=SimpleNamespace(freeze_trans_up_entries=True),
        provider=SimpleNamespace(_risk_off_exit_mode=""),
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
        controls={"benchmark_regime_on": True, "market_state": "TRANS_UP", "trade_mode": "TREND_LIGHT"},
    )

    assert gated.buy_signals == []


def test_postprocess_day_signals_trims_to_topk_holdings_in_trans_down_for_m2_mode() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
        _mf_state_arr=np.array([1], dtype=np.int8),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[trading_day])),
        positions={"sh600000": 100, "sz000001": 100, "sh600519": 100},
        close_idx={
            (trading_day, "sh600000"): 11.0,
            (trading_day, "sz000001"): 10.0,
            (trading_day, "sh600519"): 9.0,
        },
        position_avg_cost={"sh600000": 10.0, "sz000001": 10.0, "sh600519": 10.0},
        provider=SimpleNamespace(
            _risk_off_exit_mode="trans_down_topk_bear_exit",
            _risk_off_exit_trans_down_max_positions=2,
        ),
    )
    signals = DaySignals(
        sell_signals=[],
        buy_signals=[SimpleNamespace(symbol="SH600001"), SimpleNamespace(symbol="SZ000002")],
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
        controls={"benchmark_regime_on": True, "market_state": "TRANS_DOWN"},
    )

    assert gated.buy_signals == []
    assert len(gated.sell_signals) == 1
    assert gated.sell_signals[0].symbol == "sh600519"
    assert gated.sell_signals[0].qty == 100
    assert gated.sell_signals[0].reason_code == "TRANS_DOWN_TOPK_TRIM"
    assert gated.sell_signals[0].meta["trans_down_max_positions"] == 2


def test_compute_day_controls_weekly_five_state_uses_string_state_counters() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        request=SimpleNamespace(
            max_positions=10,
            data_bundle=SimpleNamespace(trading_days=[trading_day]),
        ),
        route_id="provider_breakout_runtime",
        _portfolio_mode="equal_10",
        positions={},
        close_idx={},
        position_avg_cost={},
        _dd_enabled=False,
        _dd_reduce_pct=0.12,
        _dd_reduce_scale=0.4,
        _mf_enabled=True,
        _mf_state_arr=np.array([0], dtype=np.int8),
        _mf_mult_arr=np.array([0.15], dtype=float),
        _MARKET_STATE_NAMES=("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR"),
        _TRADE_MODE_NAMES=("TREND_MAIN", "TREND_LIGHT", "NO_TRADE"),
        market_filter_bull_days=0,
        market_filter_bear_days=0,
        market_state_trans_down_days=0,
        market_state_trans_up_days=0,
        trade_mode_main_days=0,
        trade_mode_light_days=0,
        trade_mode_notrade_days=0,
        _br_enabled=False,
        _breadth_enabled=False,
        provider=SimpleNamespace(
            _market_state_name_arr=np.array(["TURN_WEAK"], dtype=object),
            _trade_mode_name_arr=np.array(["TREND_MAIN"], dtype=object),
            _market_state_raw_name_arr=np.array(["TURN_WEAK"], dtype=object),
            _market_state_smoothed_name_arr=np.array(["TURN_WEAK"], dtype=object),
            _market_state_score_arr=np.array([2.0], dtype=float),
            _risk_budget_multiplier_arr=np.array([0.15], dtype=float),
            _weekly_observation_flag_arr=np.array([True], dtype=bool),
            _risk_on=np.array([True], dtype=bool),
        ),
    )

    controls = compute_day_controls(runtime, 0, trading_day, 0.0)

    assert controls["market_state"] == "TURN_WEAK"
    assert controls["market_state_5"] == "TURN_WEAK"
    assert controls["trade_mode"] == "TREND_MAIN"
    assert controls["risk_budget_multiplier"] == 0.15
    assert controls["weekly_observation_flag"] is True
    assert runtime.market_state_trans_down_days == 1
    assert runtime.trade_mode_main_days == 1


def test_postprocess_day_signals_blocks_weekly_five_state_no_trade_by_trade_mode() -> None:
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
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
        controls={"benchmark_regime_on": True, "market_state": "DEFENSIVE", "trade_mode": "NO_TRADE"},
    )

    assert gated.buy_signals == []


def test_postprocess_day_signals_trims_below_residual_floor_in_trans_down() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
        _mf_state_arr=np.array([1], dtype=np.int8),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[trading_day])),
        positions={"sh600000": 100, "sz000001": 100, "sh600519": 100},
        close_idx={
            (trading_day, "sh600000"): 11.0,
            (trading_day, "sz000001"): 10.0,
            (trading_day, "sh600519"): 9.0,
        },
        position_avg_cost={"sh600000": 10.0, "sz000001": 10.0, "sh600519": 10.0},
        provider=SimpleNamespace(
            _risk_off_exit_mode="trans_down_residual_floor_bear_exit",
            _risk_off_exit_trans_down_min_residual_score=0.85,
            _risk_off_exit_trans_down_max_positions=0,
            _residual_strength_score=np.array([[0.91, 0.84, 0.73]], dtype=float),
            _sym_to_col={"sh600000": 0, "sz000001": 1, "sh600519": 2},
        ),
    )
    signals = DaySignals(
        sell_signals=[],
        buy_signals=[SimpleNamespace(symbol="SH600001"), SimpleNamespace(symbol="SZ000002")],
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
        controls={"benchmark_regime_on": True, "market_state": "TRANS_DOWN"},
    )

    assert gated.buy_signals == []
    assert len(gated.sell_signals) == 2
    assert {signal.symbol for signal in gated.sell_signals} == {"sz000001", "sh600519"}
    assert all(signal.reason_code == "TRANS_DOWN_RESIDUAL_TRIM" for signal in gated.sell_signals)
    assert all(signal.meta["trans_down_min_residual_score"] == 0.85 for signal in gated.sell_signals)


def test_postprocess_day_signals_trims_if_residual_or_profit_condition_fails_in_trans_down() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
        _mf_state_arr=np.array([1], dtype=np.int8),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[trading_day])),
        positions={"sh600000": 100, "sz000001": 100, "sh600519": 100},
        close_idx={
            (trading_day, "sh600000"): 11.0,
            (trading_day, "sz000001"): 10.0,
            (trading_day, "sh600519"): 9.0,
        },
        position_avg_cost={"sh600000": 10.0, "sz000001": 9.0, "sh600519": 10.0},
        provider=SimpleNamespace(
            _risk_off_exit_mode="trans_down_residual_profit_floor_bear_exit",
            _risk_off_exit_trans_down_min_residual_score=0.85,
            _risk_off_exit_trans_down_max_positions=0,
            _residual_strength_score=np.array([[0.91, 0.84, 0.93]], dtype=float),
            _sym_to_col={"sh600000": 0, "sz000001": 1, "sh600519": 2},
        ),
    )
    signals = DaySignals(
        sell_signals=[],
        buy_signals=[SimpleNamespace(symbol="SH600001"), SimpleNamespace(symbol="SZ000002")],
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
        controls={"benchmark_regime_on": True, "market_state": "TRANS_DOWN"},
    )

    assert gated.buy_signals == []
    assert len(gated.sell_signals) == 2
    assert {signal.symbol for signal in gated.sell_signals} == {"sz000001", "sh600519"}
    assert all(signal.reason_code == "TRANS_DOWN_RESIDUAL_PROFIT_TRIM" for signal in gated.sell_signals)
    by_symbol = {signal.symbol: signal for signal in gated.sell_signals}
    assert by_symbol["sz000001"].meta["quality_passed"] is False
    assert by_symbol["sz000001"].meta["profit_passed"] is True
    assert by_symbol["sh600519"].meta["quality_passed"] is True
    assert by_symbol["sh600519"].meta["profit_passed"] is False


def test_postprocess_day_signals_trims_if_residual_or_ma20_condition_fails_in_trans_down() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        route_id="provider_breakout_runtime",
        _br_enabled=False,
        _mf_enabled=True,
        _mf_state_arr=np.array([1], dtype=np.int8),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[trading_day])),
        positions={"sh600000": 100, "sz000001": 100, "sh600519": 100},
        close_idx={
            (trading_day, "sh600000"): 11.0,
            (trading_day, "sz000001"): 10.0,
            (trading_day, "sh600519"): 9.0,
        },
        position_avg_cost={"sh600000": 10.0, "sz000001": 9.0, "sh600519": 10.0},
        provider=SimpleNamespace(
            _risk_off_exit_mode="trans_down_residual_ma20_floor_bear_exit",
            _risk_off_exit_trans_down_min_residual_score=0.85,
            _risk_off_exit_trans_down_max_positions=0,
            _residual_strength_score=np.array([[0.91, 0.84, 0.93]], dtype=float),
            _sym_to_col={"sh600000": 0, "sz000001": 1, "sh600519": 2},
            _mx=SimpleNamespace(close=np.array([[11.0, 10.0, 9.0]], dtype=float)),
            _feats=SimpleNamespace(sma20=np.array([[10.5, 9.5, 9.5]], dtype=float)),
        ),
    )
    signals = DaySignals(
        sell_signals=[],
        buy_signals=[SimpleNamespace(symbol="SH600001"), SimpleNamespace(symbol="SZ000002")],
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
        controls={"benchmark_regime_on": True, "market_state": "TRANS_DOWN"},
    )

    assert gated.buy_signals == []
    assert len(gated.sell_signals) == 2
    assert {signal.symbol for signal in gated.sell_signals} == {"sz000001", "sh600519"}
    assert all(signal.reason_code == "TRANS_DOWN_RESIDUAL_MA20_TRIM" for signal in gated.sell_signals)
    by_symbol = {signal.symbol: signal for signal in gated.sell_signals}
    assert by_symbol["sz000001"].meta["quality_passed"] is False
    assert by_symbol["sz000001"].meta["ma20_passed"] is True
    assert by_symbol["sh600519"].meta["quality_passed"] is True
    assert by_symbol["sh600519"].meta["ma20_passed"] is False


def test_ensure_day_passes_market_state_into_provider_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeProvider:
        def day_signals(self, trading_day, day_index, ctx):
            captured["trading_day"] = trading_day
            captured["day_index"] = day_index
            captured["risk_on"] = ctx.risk_on
            captured["market_state"] = ctx.market_state
            return DaySignals(
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

    monkeypatch.setattr(
        bridge_adapter,
        "prepare_daily_snapshot",
        lambda runtime, *, day_index, day: SimpleNamespace(
            nav=1_000_000.0,
            market_value=0.0,
            controls={
                "effective_max_positions": 8,
                "risk_on_today": False,
                "market_state": "BEAR",
                "benchmark_regime_on": False,
            },
        ),
    )

    runtime = SimpleNamespace(
        _prepared_day_index=-1,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        cash=1_000_000.0,
        holding_sources={},
        close_idx={},
        open_idx={},
        provider=_FakeProvider(),
        _current_day=None,
        _apply_open_fills=lambda trading_day, fills_today: None,
        _provider_base_order_value=lambda nav, max_positions: nav / max_positions,
        _postprocess_day_signals=lambda day_index, day_signals, controls: day_signals,
    )
    day_context = DayContext.from_trading_days([date(2026, 3, 2), date(2026, 3, 3)], 0)

    bridge_adapter.StagePipelineBridgeRuntime.ensure_day(runtime, day_context, fills_today=[])

    assert captured["trading_day"] == date(2026, 3, 2)
    assert captured["day_index"] == 0
    assert captured["risk_on"] is False
    assert captured["market_state"] == "BEAR"
