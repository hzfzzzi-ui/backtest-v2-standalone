from __future__ import annotations

import json
import time
from datetime import date
from types import SimpleNamespace

from pytest import MonkeyPatch

from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters.daily_accounting import apply_daily_decision_diagnostics, prepare_daily_snapshot
from backend.core.stage_pipeline.adapters.fill_accounting import apply_open_fills
from backend.core.stage_pipeline.adapters.result_bridge import build_portfolio_backtest_result


def test_apply_open_fills_sell_clears_position_and_updates_provider_state() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600000"): 10.0},
        close_idx={(trading_day, "sh600000"): 10.1},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600000": 100},
        position_avg_cost={"sh600000": 9.5},
        holding_sources={
            "sh600000": {
                "entry_alpha_id": "breakout_55",
                "entry_sleeve_id": "trend",
                "entry_reason_code": "BREAKOUT_HIGH",
                "entry_date": trading_day,
            }
        },
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={"sh600000": True},
            extra_clear_dicts=[{"sh600000": {"cached": True}}, {"sh600000": True}],
            entry_day={"sh600000": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600000",
        qty=100,
        reason_code="EXIT",
        meta={"triggered_rule": "RULE_X", "break_streak": 2},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {}
    assert runtime.position_avg_cost == {}
    assert runtime.holding_sources == {}
    assert round(runtime.cash, 3) == 1997.001
    assert round(runtime._traded_value_today, 3) == 999.0
    assert runtime.provider.last_sell_day["sh600000"] == trading_day
    assert runtime.provider.extra_clear_dicts[0] == {}
    assert runtime.provider.extra_clear_dicts[1] == {}
    assert runtime.provider.entry_day == {}
    assert runtime.trade_rows[0]["side"] == "SELL"
    assert runtime.trade_rows[0]["reason_code"] == "EXIT"
    assert runtime.trade_rows[0]["triggered_rule"] == "RULE_X"
    assert runtime.trade_rows[0]["exit_owner"] == ""
    assert runtime.trade_rows[0]["entry_alpha_id"] == "breakout_55"


def test_apply_open_fills_buy_updates_avg_cost_and_buy_side_effects() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600001"): 10.0},
        close_idx={(trading_day, "sh600001"): 10.2},
        hfq_close_idx={(trading_day, "sh600001"): 102.0},
        adj_factor_idx={(trading_day, "sh600001"): 10.0},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=2000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        position_entry_adj={},
        holding_sources={},
        provider=SimpleNamespace(
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600001",
        qty=100,
        reason_code="ENTRY",
        meta={"triggered_rule": "RULE_Y", "break_streak": 1},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {"sh600001": 100}
    assert round(runtime.position_avg_cost["sh600001"], 2) == 10.01
    assert runtime.position_entry_adj["sh600001"] == 10.0
    assert round(runtime.cash, 2) == 998.0
    assert round(runtime._traded_value_today, 2) == 1001.0
    assert runtime.provider.entry_day["sh600001"] == trading_day
    assert runtime.provider.peak_state_on_buy["sh600001"] == 10.2
    assert runtime.holding_sources["sh600001"]["entry_alpha_id"] == ""
    assert runtime.trade_rows[0]["side"] == "BUY"
    assert runtime.trade_rows[0]["reason_code"] == "ENTRY"
    assert runtime.trade_rows[0]["triggered_rule"] == "RULE_Y"


def test_prepare_daily_snapshot_uses_hfq_valuation_when_entry_adj_present() -> None:
    trading_day = date(2015, 4, 1)
    runtime = SimpleNamespace(
        cash=0.0,
        positions={"sz000540": 17000},
        position_entry_adj={"sz000540": 19.863},
        close_idx={(trading_day, "sz000540"): 14.13},
        hfq_close_idx={(trading_day, "sz000540"): 705.70872},
        peak_nav=0.0,
        prev_nav=608260.0,
        _traded_value_today=0.0,
        daily_rows=[],
        _compute_day_controls=lambda *_args, **_kwargs: {
            "effective_max_positions": 10,
            "dd_state": "NORMAL",
            "regime_engine": "weekly_five_state",
            "market_state_5": "LIGHT_TREND",
            "market_state_score": 3,
            "market_state_raw": "LIGHT_TREND",
            "market_state_smoothed": "LIGHT_TREND",
            "risk_budget_multiplier": 0.4,
            "weekly_observation_flag": False,
            "market_state": "TRANS_UP",
            "trade_mode": "TREND_LIGHT",
            "benchmark_regime_on": True,
            "feature_availability": {},
            "risk_on_today": True,
        },
        _last_accounting_snapshot=None,
    )

    snapshot = prepare_daily_snapshot(runtime, day_index=0, day=trading_day)

    assert round(snapshot.market_value, 2) == 603989.74
    assert round(snapshot.nav, 2) == 603989.74


def test_apply_open_fills_buy_persists_entry_source_fields() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600002"): 12.0},
        close_idx={(trading_day, "sh600002"): 12.1},
        _slip_bps=0.0,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=5000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        holding_sources={},
        provider=SimpleNamespace(
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600002",
        qty=100,
        reason_code="ENTRY",
        meta={
            "entry_alpha_id": "rsi_reversal",
            "entry_sleeve_id": "mr",
            "entry_reason_code": "MR_RSI_OVERSOLD_BUY",
        },
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.holding_sources["sh600002"]["entry_alpha_id"] == "rsi_reversal"
    assert runtime.holding_sources["sh600002"]["entry_sleeve_id"] == "mr"
    assert runtime.trade_rows[0]["entry_alpha_id"] == "rsi_reversal"
    assert runtime.trade_rows[0]["entry_reason_code"] == "MR_RSI_OVERSOLD_BUY"


def test_apply_open_fills_buy_persists_entry_breakout_state_for_provider_exits() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600002"): 12.0},
        close_idx={(trading_day, "sh600002"): 12.1},
        _slip_bps=0.0,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=5000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        holding_sources={},
        provider=SimpleNamespace(
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
            entry_bar_index={},
            entry_breakout_floor_raw={},
        ),
        request=SimpleNamespace(
            data_bundle=SimpleNamespace(
                trading_days=[date(2026, 3, 1), trading_day, date(2026, 3, 3)],
            )
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600002",
        qty=100,
        reason_code="ENTRY",
        meta={
            "entry_breakout_floor_raw": 11.8,
        },
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.provider.entry_day["sh600002"] == trading_day
    assert runtime.provider.entry_bar_index["sh600002"] == 1
    assert runtime.provider.entry_breakout_floor_raw["sh600002"] == 11.8


def test_apply_open_fills_sell_preserves_global_risk_override_marker() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600003"): 8.0},
        close_idx={(trading_day, "sh600003"): 8.1},
        _slip_bps=0.0,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600003": 100},
        position_avg_cost={"sh600003": 7.5},
        holding_sources={
            "sh600003": {
                "entry_alpha_id": "breakout_55",
                "entry_sleeve_id": "trend",
                "entry_reason_code": "BREAKOUT_HIGH",
                "entry_date": trading_day,
            }
        },
        provider=SimpleNamespace(
            last_sell_day={},
            extra_clear_dicts=[],
            entry_day={"sh600003": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600003",
        qty=100,
        reason_code="RISK_OFF_EXIT",
        meta={"exit_owner": "global_risk_override"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.trade_rows[0]["exit_owner"] == "global_risk_override"
    assert runtime.trade_rows[0]["entry_alpha_id"] == "breakout_55"


def test_apply_open_fills_partial_sell_keeps_residual_position() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600013"): 8.0},
        close_idx={(trading_day, "sh600013"): 8.1},
        _slip_bps=0.0,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600013": 1000},
        position_avg_cost={"sh600013": 7.5},
        holding_sources={
            "sh600013": {
                "entry_alpha_id": "breakout_55",
                "entry_sleeve_id": "trend",
                "entry_reason_code": "BREAKOUT_HIGH",
                "entry_date": trading_day,
            }
        },
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[],
            entry_day={"sh600013": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600013",
        qty=500,
        reason_code="RISK_OFF_EXIT",
        meta={"partial_exit": True, "risk_off_exit_partial_pct": 0.5},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions["sh600013"] == 500
    assert runtime.position_avg_cost["sh600013"] == 7.5
    assert runtime.holding_sources["sh600013"]["entry_alpha_id"] == "breakout_55"
    assert runtime.provider.last_sell_day == {}
    assert runtime.provider._risk_off_partial_state == {}
    assert runtime.provider.entry_day["sh600013"] == trading_day
    assert runtime.trade_rows[0]["qty"] == 500


def test_apply_open_fills_partial_sell_marks_state_after_actual_fill() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600014"): 8.0},
        close_idx={(trading_day, "sh600014"): 8.1},
        _slip_bps=0.0,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600014": 1000},
        position_avg_cost={"sh600014": 7.5},
        holding_sources={},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[],
            entry_day={"sh600014": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600014",
        qty=500,
        reason_code="RISK_OFF_EXIT",
        meta={
            "partial_exit": True,
            "risk_off_exit_partial_pct": 0.5,
            "risk_off_partial_mark_on_fill": True,
        },
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions["sh600014"] == 500
    assert runtime.provider._risk_off_partial_state["sh600014"] is True


def test_apply_open_fills_buy_from_flat_clears_stale_partial_state() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600015"): 10.0},
        close_idx={(trading_day, "sh600015"): 10.2},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=2000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        holding_sources={},
        provider=SimpleNamespace(
            _risk_off_partial_state={"sh600015": True},
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600015",
        qty=100,
        reason_code="ENTRY",
        meta={},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions["sh600015"] == 100
    assert runtime.provider._risk_off_partial_state == {}


def test_apply_open_fills_skips_sell_on_suspended_zero_liquidity_bar() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600004"): 8.0},
        close_idx={(trading_day, "sh600004"): 8.1},
        volume_idx={(trading_day, "sh600004"): 0.0},
        amount_idx={(trading_day, "sh600004"): 0.0},
        suspended_idx={(trading_day, "sh600004"): True},
        _slip_bps=0.0,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600004": 100},
        position_avg_cost={"sh600004": 7.5},
        holding_sources={"sh600004": {"entry_reason_code": "BREAKOUT_HIGH"}},
        deferred_sell_orders=[],
        provider=SimpleNamespace(
            last_sell_day={},
            extra_clear_dicts=[],
            entry_day={"sh600004": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600004",
        qty=100,
        reason_code="ATR_TRAIL_EXIT",
        meta={"triggered_rule": "ATR_TRAIL_EXIT"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.cash == 1000.0
    assert runtime._traded_value_today == 0.0
    assert runtime.positions == {"sh600004": 100}
    assert runtime.trade_rows == []
    assert runtime.provider.last_sell_day == {}
    assert runtime.deferred_sell_orders == [
        {
            "side": Side.SELL,
            "symbol": "sh600004",
            "qty": 100,
            "reason_code": "ATR_TRAIL_EXIT",
            "meta": {
                "triggered_rule": "ATR_TRAIL_EXIT",
                "entry_reason_code": "BREAKOUT_HIGH",
                "deferred_execution": True,
                "deferred_from_date": "2026-03-02",
                "last_deferred_date": "2026-03-02",
            },
        }
    ]


def test_apply_open_fills_skips_buy_on_zero_turnover_bar() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600005"): 10.0},
        close_idx={(trading_day, "sh600005"): 10.2},
        volume_idx={(trading_day, "sh600005"): 1200.0},
        amount_idx={(trading_day, "sh600005"): 0.0},
        suspended_idx={(trading_day, "sh600005"): False},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=2000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        holding_sources={},
        provider=SimpleNamespace(
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600005",
        qty=100,
        reason_code="ENTRY",
        meta={"triggered_rule": "RULE_Y"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.cash == 2000.0
    assert runtime.positions == {}
    assert runtime.trade_rows == []


def test_apply_open_fills_skips_sell_on_limit_down_bar() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600006"): 9.0},
        close_idx={(trading_day, "sh600006"): 9.1},
        volume_idx={(trading_day, "sh600006"): 50000.0},
        amount_idx={(trading_day, "sh600006"): 450000.0},
        suspended_idx={(trading_day, "sh600006"): False},
        limit_down_idx={(trading_day, "sh600006"): 9.0},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600006": 100},
        position_avg_cost={"sh600006": 7.0},
        holding_sources={"sh600006": {"entry_reason_code": "BREAKOUT_HIGH"}},
        deferred_sell_orders=[],
        provider=SimpleNamespace(
            last_sell_day={},
            extra_clear_dicts=[],
            entry_day={"sh600006": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600006",
        qty=100,
        reason_code="ATR_TRAIL_EXIT",
        meta={"triggered_rule": "ATR_TRAIL_EXIT"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.cash == 1000.0
    assert runtime.positions == {"sh600006": 100}
    assert runtime.trade_rows == []
    assert runtime.deferred_sell_orders[0]["symbol"] == "sh600006"
    assert runtime.deferred_sell_orders[0]["qty"] == 100


def test_apply_open_fills_skips_buy_on_tick_rounded_limit_up_bar() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sz002261"): 26.98},
        close_idx={(trading_day, "sz002261"): 25.27},
        volume_idx={(trading_day, "sz002261"): 50000.0},
        amount_idx={(trading_day, "sz002261"): 450000.0},
        suspended_idx={(trading_day, "sz002261"): False},
        limit_up_idx={(trading_day, "sz002261"): 26.983},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=200000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        holding_sources={},
        provider=SimpleNamespace(
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SZ002261",
        qty=100,
        reason_code="BREAKOUT_HIGH",
        meta={"triggered_rule": "BREAKOUT_HIGH"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.cash == 200000.0
    assert runtime.positions == {}
    assert runtime.trade_rows == []


def test_apply_open_fills_skips_sell_on_tick_rounded_limit_down_bar() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sz002797"): 6.24},
        close_idx={(trading_day, "sz002797"): 6.71},
        volume_idx={(trading_day, "sz002797"): 50000.0},
        amount_idx={(trading_day, "sz002797"): 450000.0},
        suspended_idx={(trading_day, "sz002797"): False},
        limit_down_idx={(trading_day, "sz002797"): 6.237},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sz002797": 100},
        position_avg_cost={"sz002797": 7.0},
        holding_sources={"sz002797": {"entry_reason_code": "BREAKOUT_HIGH"}},
        deferred_sell_orders=[],
        provider=SimpleNamespace(
            last_sell_day={},
            extra_clear_dicts=[],
            entry_day={"sz002797": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SZ002797",
        qty=100,
        reason_code="ATR_STOP_LOSS",
        meta={"triggered_rule": "ATR_STOP_LOSS"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.cash == 1000.0
    assert runtime.positions == {"sz002797": 100}
    assert runtime.trade_rows == []
    assert runtime.deferred_sell_orders[0]["symbol"] == "sz002797"
    assert runtime.deferred_sell_orders[0]["qty"] == 100


def test_prepare_daily_snapshot_updates_nav_trackers_and_daily_row() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        cash=1000.0,
        positions={"sh600000": 100},
        close_idx={(trading_day, "sh600000"): 10.0},
        peak_nav=900.0,
        prev_nav=950.0,
        _traded_value_today=95.0,
        daily_rows=[],
        route_id="strict_inline_runtime",
        _compute_day_controls=lambda *_args: {
            "effective_max_positions": 5,
            "dd_state": "NORMAL",
            "market_state": "",
            "trade_mode": "",
            "benchmark_regime_on": True,
            "risk_on_today": True,
            "regime_engine": "ma200_legacy",
            "market_state_5": "LIGHT",
            "base_state_5": "TRANS_UP",
            "effective_state_5": "LIGHT",
            "coarse_state": "RISK_ON",
            "effective_coarse_state": "NEUTRAL",
            "reason_codes": ["MANUAL_OVERRIDE_ACTIVE", "BASE_STATE::TRANS_UP"],
            "block_scores": {"trend_block": {"support": 0.7, "stress": 0.1, "net": 0.6}},
            "subscores": {"technical": 0.7, "sentiment": 0.3, "macro_global": None},
            "manual_override": {"active": True, "reason": "manual_cut", "scope": "runtime", "actor": "pm"},
            "state_stability_metrics": {"pending_transition": False, "cooldown_active": False},
            "defense_bias": 0.35,
            "feature_availability": {"trend_block": True},
            "regime_transition_reason": "MANUAL_REVIEW",
        },
    )

    snapshot = prepare_daily_snapshot(runtime, day_index=0, day=trading_day)

    assert snapshot.nav == 2000.0
    assert snapshot.market_value == 1000.0
    assert snapshot.controls["effective_max_positions"] == 5
    assert runtime.prev_nav == 2000.0
    assert runtime.peak_nav == 2000.0
    assert runtime.daily_rows[0]["date"] == "2026-03-02"
    assert runtime.daily_rows[0]["positions_count"] == 1
    assert round(runtime.daily_rows[0]["turnover_pct"], 2) == 0.10
    assert runtime.daily_rows[0]["regime_engine"] == "ma200_legacy"
    assert runtime.daily_rows[0]["regime_transition_reason"] == "MANUAL_REVIEW"
    assert runtime.daily_rows[0]["feature_availability_json"] == '{"trend_block": true}'
    assert runtime.daily_rows[0]["base_state_5"] == "TRANS_UP"
    assert runtime.daily_rows[0]["effective_state_5"] == "LIGHT"
    assert runtime.daily_rows[0]["coarse_state"] == "RISK_ON"
    assert runtime.daily_rows[0]["effective_coarse_state"] == "NEUTRAL"
    assert json.loads(runtime.daily_rows[0]["reason_codes_json"]) == ["MANUAL_OVERRIDE_ACTIVE", "BASE_STATE::TRANS_UP"]
    assert json.loads(runtime.daily_rows[0]["block_scores_json"]) == {"trend_block": {"support": 0.7, "stress": 0.1, "net": 0.6}}
    assert json.loads(runtime.daily_rows[0]["subscores_json"]) == {"technical": 0.7, "sentiment": 0.3, "macro_global": None}
    assert json.loads(runtime.daily_rows[0]["manual_override_json"]) == {"active": True, "reason": "manual_cut", "scope": "runtime", "actor": "pm"}
    assert json.loads(runtime.daily_rows[0]["state_stability_metrics_json"]) == {"pending_transition": False, "cooldown_active": False}
    assert runtime.daily_rows[0]["defense_bias"] == 0.35
    governor_budget = json.loads(runtime.daily_rows[0]["governor_budget_json"])
    assert governor_budget["effective_max_positions"] == 5
    assert governor_budget["sleeve_budgets"]["cn_stock_trend_alpha_core"]["slot_cap"] == 5
    assert governor_budget["regime_source_state"] == "TRANS_UP"
    assert governor_budget["regime_effective_state"] == "LIGHT"
    assert governor_budget["manual_override"]["active"] is True
    assert governor_budget["defense_bias"] == 0.35


def test_apply_daily_decision_diagnostics_populates_multifactor_sorting_fields() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2026-03-02",
                "positions_count": 0,
                "positions_count_end_of_day": 0,
                "candidates_count": 0,
                "selected_count": 0,
                "buy_slots_before_buy": 0,
                "buy_slots_after_sell": 0,
                "buy_candidate_count": 0,
                "after_held_filter_count": 0,
                "positions_before_sell": 0,
                "sells_executed_count": 0,
                "positions_after_sell": 0,
                "buy_slots_calculated": 0,
                "raw_buy_signal_count": 0,
                "raw_alpha_signal_count": 0,
                "composed_buy_signal_count": 0,
                "composed_sell_signal_count": 0,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 0,
                "candidates_after_held_filter_count": 0,
                "sorting_triggered": False,
                "mf_rank_triggered": 0,
                "mf_rank_applied": 0,
                "mf_candidates_when_triggered": 0,
                "mf_topk_reject_count": 0,
                "mf_concentrated_selected_count": 0,
                "mf_gate_on": 0,
                "strong_risk_on": 0,
                "mf_rank_suppressed_by_strong_gate": 0,
                "same_symbol_conflict_count": 0,
                "sleeve_budget_reject_count": 0,
                "source_only_exit_count": 0,
                "global_risk_override_count": 0,
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
    )
    buy_signal = SimpleNamespace(symbol="SH600001", meta={"alpha_id": "breakout_55", "compose_score": 0.91})
    day_signals = DaySignals(
        sell_signals=[],
        buy_signals=[buy_signal],
        raw_alpha_signals=[buy_signal],
        composed_buy_signals=[buy_signal],
        composed_sell_signals=[],
        exit_syms=set(),
        strength_map={},
        mf_score_map={"sh600001": 0.91},
        mf_gate_on_today=False,
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={
            "raw_buy_signal_count": 1,
            "raw_alpha_signal_count": 1,
            "composed_buy_signal_count": 1,
            "composed_sell_signal_count": 0,
            "buy_candidate_count": 3,
            "after_held_filter_count": 2,
            "composition_enabled": False,
            "enable_multifactor_rank": True,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 3,
            "buy_slots": 1,
            "selected_symbols": ["sh600001"],
            "selected_count": 1,
            "after_slot_filter_count": 1,
            "after_cash_lot_count": 1,
            "mf_rank_triggered": True,
            "mf_rank_applied": True,
            "mf_candidates_when_triggered": 3,
            "mf_topk_reject_count": 2,
            "mf_concentrated_selected_count": 1,
            "mf_gate_on": False,
        },
    )

    daily_row = runtime.daily_rows[-1]
    assert daily_row["buy_candidate_count"] == 3
    assert daily_row["after_held_filter_count"] == 2
    assert daily_row["after_slot_filter_count"] == 1
    assert daily_row["after_cash_lot_count"] == 1
    assert daily_row["sorting_triggered"] is True
    assert daily_row["mf_rank_triggered"] == 1
    assert daily_row["mf_rank_applied"] == 1
    assert daily_row["mf_candidates_when_triggered"] == 3
    assert daily_row["mf_topk_reject_count"] == 2
    assert daily_row["mf_concentrated_selected_count"] == 1
    assert daily_row["mf_gate_on"] == 0
    assert daily_row["strong_risk_on"] == 0
    assert daily_row["mf_rank_suppressed_by_strong_gate"] == 1
    diagnostics_input = json.loads(daily_row["diagnostics_input_json"])
    assert diagnostics_input["route_id"] == "strict_inline_runtime"
    assert diagnostics_input["raw_buy_candidate_count"] == 3
    assert diagnostics_input["raw_after_held_filter_count"] == 2
    assert diagnostics_input["raw_after_slot_filter_count"] == 1
    assert diagnostics_input["raw_after_cash_lot_count"] == 1
    governor_budget = json.loads(daily_row["governor_budget_json"])
    assert governor_budget["sleeve_budget_mode"] == "governed_single_sleeve"
    assert governor_budget["budget_diagnostics"]["deployment_gap"] == 1
    assert "BUY_SLOT_UNUSED" in governor_budget["budget_reason_codes"]


def test_apply_daily_decision_diagnostics_preserves_unavailable_stage_counts() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2026-03-02",
                "positions_count": 0,
                "positions_count_end_of_day": 0,
                "candidates_count": 0,
                "selected_count": 0,
                "buy_slots_before_buy": 0,
                "buy_slots_after_sell": 0,
                "buy_candidate_count": 0,
                "after_held_filter_count": 0,
                "positions_before_sell": 0,
                "sells_executed_count": 0,
                "positions_after_sell": 0,
                "buy_slots_calculated": 0,
                "raw_buy_signal_count": 0,
                "raw_alpha_signal_count": 0,
                "composed_buy_signal_count": 0,
                "composed_sell_signal_count": 0,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 0,
                "candidates_after_held_filter_count": 0,
                "sorting_triggered": False,
                "mf_rank_triggered": 0,
                "mf_rank_applied": 0,
                "mf_candidates_when_triggered": 0,
                "mf_topk_reject_count": 0,
                "mf_concentrated_selected_count": 0,
                "mf_gate_on": 0,
                "strong_risk_on": 0,
                "mf_rank_suppressed_by_strong_gate": 0,
                "same_symbol_conflict_count": 0,
                "sleeve_budget_reject_count": 0,
                "source_only_exit_count": 0,
                "global_risk_override_count": 0,
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
    )
    buy_signal = SimpleNamespace(symbol="SH600001", meta={})
    day_signals = DaySignals(
        sell_signals=[],
        buy_signals=[buy_signal],
        raw_alpha_signals=[],
        composed_buy_signals=[],
        composed_sell_signals=[],
        exit_syms=set(),
        strength_map={},
        mf_score_map={},
        mf_gate_on_today=False,
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={
            "raw_buy_signal_count": 1,
            "composition_enabled": False,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 1,
            "buy_slots": 1,
            "selected_symbols": [],
        },
    )

    daily_row = runtime.daily_rows[-1]
    assert daily_row["buy_candidate_count"] == 0
    assert daily_row["after_held_filter_count"] == 0
    assert daily_row["after_slot_filter_count"] == 0
    assert daily_row["after_cash_lot_count"] == 0
    assert daily_row["candidates_after_held_filter_count"] == 0
    diagnostics_input = json.loads(daily_row["diagnostics_input_json"])
    assert diagnostics_input["raw_after_slot_filter_count"] is None
    assert diagnostics_input["raw_after_cash_lot_count"] is None


def test_apply_daily_decision_diagnostics_keeps_breakout_counts_raw_for_artifact_builder() -> None:
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2026-03-02",
                "positions_count": 0,
                "positions_count_end_of_day": 0,
                "candidates_count": 0,
                "selected_count": 0,
                "buy_slots_before_buy": 0,
                "buy_slots_after_sell": 0,
                "buy_candidate_count": 0,
                "after_held_filter_count": 0,
                "positions_before_sell": 0,
                "sells_executed_count": 0,
                "positions_after_sell": 0,
                "buy_slots_calculated": 0,
                "raw_buy_signal_count": 0,
                "raw_alpha_signal_count": 0,
                "composed_buy_signal_count": 0,
                "composed_sell_signal_count": 0,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 0,
                "candidates_after_held_filter_count": 0,
                "sorting_triggered": False,
                "mf_rank_triggered": 0,
                "mf_rank_applied": 0,
                "mf_candidates_when_triggered": 0,
                "mf_topk_reject_count": 0,
                "mf_concentrated_selected_count": 0,
                "mf_gate_on": 0,
                "strong_risk_on": 0,
                "mf_rank_suppressed_by_strong_gate": 0,
                "same_symbol_conflict_count": 0,
                "sleeve_budget_reject_count": 0,
                "source_only_exit_count": 0,
                "global_risk_override_count": 0,
                "benchmark_regime_on": True,
            }
        ],
        route_id="provider_breakout_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
    )
    buy_signal = SimpleNamespace(symbol="SH600001", meta={})
    day_signals = DaySignals(
        sell_signals=[],
        buy_signals=[buy_signal],
        raw_alpha_signals=[],
        composed_buy_signals=[],
        composed_sell_signals=[],
        exit_syms=set(),
        strength_map={},
        mf_score_map={},
        mf_gate_on_today=False,
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={
            "raw_buy_signal_count": 5,
            "buy_candidate_count": 5,
            "after_held_filter_count": 3,
            "composition_enabled": False,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 0,
            "buy_slots": 2,
            "selected_symbols": ["sh600001"],
            "selected_count": 1,
        },
    )

    daily_row = runtime.daily_rows[-1]
    assert daily_row["buy_candidate_count"] == 5
    assert daily_row["after_held_filter_count"] == 3
    assert daily_row["after_slot_filter_count"] == 0
    assert daily_row["after_cash_lot_count"] == 1
    diagnostics_input = json.loads(daily_row["diagnostics_input_json"])
    assert diagnostics_input["route_id"] == "provider_breakout_runtime"
    assert diagnostics_input["benchmark_regime_on"] is True
    assert diagnostics_input["raw_buy_candidate_count"] == 5
    assert diagnostics_input["raw_after_held_filter_count"] == 3
    assert diagnostics_input["raw_after_slot_filter_count"] is None
    governor_budget = json.loads(daily_row["governor_budget_json"])
    assert governor_budget["budget_diagnostics"]["deployment_gap"] == 1
    assert "NO_SELECTED_ORDERS" not in governor_budget["budget_reason_codes"]


def test_apply_daily_decision_diagnostics_resolves_cn_etf_governor_truth_from_asset_context() -> None:
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2026-03-02",
                "drawdown": 0.0,
                "positions_count": 0,
                "positions_count_end_of_day": 0,
                "candidates_count": 0,
                "selected_count": 0,
                "buy_slots_before_buy": 0,
                "buy_slots_after_sell": 0,
                "buy_candidate_count": 0,
                "after_held_filter_count": 0,
                "positions_before_sell": 0,
                "sells_executed_count": 0,
                "positions_after_sell": 0,
                "buy_slots_calculated": 0,
                "raw_buy_signal_count": 0,
                "raw_alpha_signal_count": 0,
                "composed_buy_signal_count": 0,
                "composed_sell_signal_count": 0,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 0,
                "candidates_after_held_filter_count": 0,
                "sorting_triggered": False,
                "mf_rank_triggered": 0,
                "mf_rank_applied": 0,
                "mf_candidates_when_triggered": 0,
                "mf_topk_reject_count": 0,
                "mf_concentrated_selected_count": 0,
                "mf_gate_on": 0,
                "strong_risk_on": 0,
                "mf_rank_suppressed_by_strong_gate": 0,
                "same_symbol_conflict_count": 0,
                "sleeve_budget_reject_count": 0,
                "source_only_exit_count": 0,
                "global_risk_override_count": 0,
                "effective_max_positions": 2,
                "breadth_max_positions": 2,
                "dd_state": "NORMAL",
                "regime_transition_reason": "",
                "market_state_5": "BULL",
                "base_state_5": "BULL",
                "effective_state_5": "BULL",
                "coarse_state": "RISK_ON",
                "effective_coarse_state": "RISK_ON",
                "risk_budget_multiplier": 1.0,
                "reason_codes_json": "[]",
                "manual_override_json": "{}",
                "defense_bias": 0.0,
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "asset_scope": "cn_a_equity",
                        "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core",
                        "budget_consumer_system_role": "stock_alpha_sleeve",
                        "budget_semantics": "consume_governor_sleeve_budget",
                        "total_risk_budget": 1.0,
                        "budget_reason_codes": [],
                    }
                ),
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
        request=SimpleNamespace(
            max_positions=2,
            asset_context={"asset_scope": "cn_etf"},
        ),
    )
    buy_signal = SimpleNamespace(symbol="SH510050", meta={"sleeve_id": "cn_etf_beta"})
    day_signals = DaySignals(
        sell_signals=[],
        buy_signals=[buy_signal],
        raw_alpha_signals=[],
        composed_buy_signals=[],
        composed_sell_signals=[],
        exit_syms=set(),
        strength_map={},
        mf_score_map={},
        mf_gate_on_today=False,
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={
            "raw_buy_signal_count": 1,
            "composition_enabled": False,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 1,
            "buy_slots": 1,
            "selected_symbols": ["sh510050"],
            "selected_count": 1,
        },
    )

    governor_budget = json.loads(runtime.daily_rows[-1]["governor_budget_json"])
    assert governor_budget["asset_scope"] == "cn_etf"
    assert governor_budget["budget_consumer_sleeve_id"] == "cn_etf_beta"
    assert governor_budget["budget_consumer_system_role"] == "market_beta_sleeve"
    assert governor_budget["target_exposure"] == 1.0
    assert governor_budget["target_exposure_source"] == "slot_cap_default"
    assert governor_budget["min_deployable_exposure"] == 0.5
    assert governor_budget["min_deployable_exposure_source"] == "derived_from_target"
    assert governor_budget["fallback_allowed"] is False
    assert governor_budget["actual_exposure"] == 0.0
    assert governor_budget["actual_risk_exposure"] == 0.0
    assert governor_budget["actual_fallback_exposure"] == 0.0
    assert governor_budget["deployability_gap"] == 1.0


def test_apply_daily_decision_diagnostics_populates_moneyflow_overlay_fields() -> None:
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2026-03-02",
                "positions_count": 0,
                "positions_count_end_of_day": 0,
                "candidates_count": 0,
                "selected_count": 0,
                "buy_slots_before_buy": 0,
                "buy_slots_after_sell": 0,
                "buy_candidate_count": 0,
                "after_held_filter_count": 0,
                "positions_before_sell": 0,
                "sells_executed_count": 0,
                "positions_after_sell": 0,
                "buy_slots_calculated": 0,
                "raw_buy_signal_count": 0,
                "raw_alpha_signal_count": 0,
                "composed_buy_signal_count": 0,
                "composed_sell_signal_count": 0,
                "after_slot_filter_count": 0,
                "after_cash_lot_count": 0,
                "candidates_after_held_filter_count": 0,
                "sorting_triggered": False,
                "mf_rank_triggered": 0,
                "mf_rank_applied": 0,
                "mf_candidates_when_triggered": 0,
                "mf_topk_reject_count": 0,
                "mf_concentrated_selected_count": 0,
                "mf_gate_on": 0,
                "moneyflow_overlay_enabled": 0,
                "moneyflow_overlay_mode": "off",
                "moneyflow_overlay_gate_on": 0,
                "moneyflow_overlay_observation_date": "",
                "moneyflow_overlay_score_source": "",
                "strong_risk_on": 0,
                "mf_rank_suppressed_by_strong_gate": 0,
                "same_symbol_conflict_count": 0,
                "sleeve_budget_reject_count": 0,
                "source_only_exit_count": 0,
                "global_risk_override_count": 0,
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
    )
    buy_signal = SimpleNamespace(symbol="SH600001", meta={})
    day_signals = DaySignals(
        sell_signals=[],
        buy_signals=[buy_signal],
        exit_syms=set(),
        strength_map={},
        mf_score_map={"sh600001": 0.91},
        mf_gate_on_today=False,
        overlay_score_map={"sh600001": 0.73},
        overlay_gate_on_today=True,
        overlay_mode="tiebreak",
        overlay_observation_date=date(2026, 2, 28),
        overlay_score_source="LEGACY_PIT_NO_GROWTH_BOARDS_T10_DECAY",
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={
            "raw_buy_signal_count": 1,
            "moneyflow_overlay_enabled": True,
            "moneyflow_overlay_gate_on": True,
            "moneyflow_overlay_mode": "tiebreak",
            "moneyflow_overlay_observation_date": "2026-02-28",
            "moneyflow_overlay_score_source": "LEGACY_PIT_NO_GROWTH_BOARDS_T10_DECAY",
            "composition_enabled": False,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 1,
            "buy_slots": 1,
            "selected_symbols": ["sh600001"],
            "selected_count": 1,
            "moneyflow_overlay_enabled": True,
            "moneyflow_overlay_mode": "tiebreak",
            "moneyflow_overlay_gate_on": True,
            "moneyflow_overlay_observation_date": "2026-02-28",
            "moneyflow_overlay_score_source": "LEGACY_PIT_NO_GROWTH_BOARDS_T10_DECAY",
        },
    )

    daily_row = runtime.daily_rows[-1]
    assert daily_row["moneyflow_overlay_enabled"] == 1
    assert daily_row["moneyflow_overlay_mode"] == "tiebreak"
    assert daily_row["moneyflow_overlay_gate_on"] == 1
    assert daily_row["moneyflow_overlay_observation_date"] == "2026-02-28"
    assert daily_row["moneyflow_overlay_score_source"] == "LEGACY_PIT_NO_GROWTH_BOARDS_T10_DECAY"


def test_build_portfolio_backtest_result_preserves_metrics_shape() -> None:
    captured: dict[str, object] = {}

    def _fake_compute_metrics(*args, **kwargs):
        captured["daily_df"] = args[0]
        captured["trades_df"] = args[1]
        captured["kwargs"] = kwargs
        return {"audit": {}, "baseline": "ok"}

    monkeypatch = MonkeyPatch()
    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.result_bridge._compute_metrics",
        _fake_compute_metrics,
    )
    try:
        runtime = SimpleNamespace(
            daily_rows=[{
                "date": "2026-03-02",
                "nav": 1.0,
                "drawdown": 0.0,
                "market_state": "BULL",
                "regime_confidence": 0.40,
                "regime_transition_reason": "CONFIDENCE_FLOOR_HOLD",
                "feature_availability_json": json.dumps(
                    {
                        "required_blocks_ready": False,
                        "fallback_active": True,
                    }
                ),
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "total_risk_budget": 0.4,
                        "total_exposure_cap": 0.5,
                        "drawdown_state": "REDUCED",
                        "recovery_state": "DRAWDOWN_RECOVERY_PENDING",
                        "cooldown_state": "INACTIVE",
                        "defense_floor": 0.0,
                        "sleeve_budget_reject_count": 2,
                        "budget_reason_codes": [
                            "DRAWDOWN_REDUCED",
                            "TOTAL_RISK_BUDGET_REDUCED",
                            "SLEEVE_BUDGET_REJECTS",
                        ],
                        "budget_diagnostics": {
                            "buy_slots": 2,
                            "selected_count": 1,
                            "deployment_gap": 1,
                        },
                    }
                ),
            }],
            trade_rows=[{"date": "2026-03-02", "symbol": "sh600000", "side": "BUY"}],
            candidate_rows=[{"date": "2026-03-02", "symbol": "sh600000"}],
            request=SimpleNamespace(
                max_positions=5,
                enable_strength_rank=False,
                strength_ma=120,
                regime_engine_cfg=SimpleNamespace(
                    persistence=SimpleNamespace(confidence_floor=0.55)
                ),
            ),
            provider=SimpleNamespace(
                precompute_seconds=1.25,
                blocked_by_trend_count=3,
                total_buy_signals=7,
                diag_reason_counts={"ATR_STOP_LOSS": 2, "TREND_EXIT_MA20": 1},
            ),
            route_id="provider_breakout_runtime",
            _simulation_t0=time.perf_counter() - 2.0,
            market_filter_bull_days=11,
            market_filter_bear_days=2,
            market_state_trans_down_days=3,
            market_state_trans_up_days=4,
            trade_mode_main_days=5,
            trade_mode_light_days=6,
            trade_mode_notrade_days=7,
        )

        result = build_portfolio_backtest_result(runtime)
    finally:
        monkeypatch.undo()

    assert list(captured["daily_df"]["date"]) == ["2026-03-02"]
    assert list(captured["trades_df"]["symbol"]) == ["sh600000"]
    assert result.metrics["baseline"] == "ok"
    assert result.metrics["notes"] == "stage_pipeline_bridge=true"
    assert result.metrics["precompute_seconds"] == 1.25
    assert result.metrics["blocked_by_trend_count"] == 3
    assert result.metrics["exit_atr_stop_count"] == 2
    assert result.metrics["exit_ma20_count"] == 1
    assert result.metrics["trade_mode_notrade_days"] == 7
    assert result.metrics["regime_confidence_mean"] == 0.4
    assert result.metrics["regime_low_confidence_days"] == 1
    assert result.metrics["regime_switch_count"] == 0
    assert result.metrics["regime_transition_reason_counts"] == {"CONFIDENCE_FLOOR_HOLD": 1}
    assert result.metrics["regime_feature_unavailable_days"] == 1
    assert result.metrics["risk_budget_active_days"] == 1
    assert result.metrics["audit"]["governor_budget"]["summary"]["budget_reason_counts"]["DRAWDOWN_REDUCED"] == 1
    assert result.metrics["audit"]["governor_budget"]["summary"]["sleeve_budget_reject_days"] == 1


def test_build_portfolio_backtest_result_keeps_cn_etf_governor_latest_truth() -> None:
    def _fake_compute_metrics(*args, **kwargs):
        return {"audit": {}, "baseline": "ok"}

    monkeypatch = MonkeyPatch()
    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.result_bridge._compute_metrics",
        _fake_compute_metrics,
    )
    try:
        runtime = SimpleNamespace(
            daily_rows=[{
                "date": "2026-03-20",
                "nav": 1.0,
                "drawdown": 0.0,
                "market_state": "BULL",
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "asset_scope": "cn_a_equity",
                        "budget_consumer_sleeve_id": "cn_stock_trend_alpha_core",
                        "budget_consumer_system_role": "stock_alpha_sleeve",
                        "budget_semantics": "consume_governor_sleeve_budget",
                        "total_risk_budget": 0.7,
                        "budget_reason_codes": [],
                    }
                ),
            }],
            trade_rows=[],
            candidate_rows=[],
            request=SimpleNamespace(
                max_positions=4,
                enable_strength_rank=False,
                strength_ma=120,
                asset_context={"asset_scope": "cn_etf"},
            ),
            provider=SimpleNamespace(
                precompute_seconds=0.0,
                blocked_by_trend_count=0,
                total_buy_signals=0,
                diag_reason_counts={},
            ),
            route_id="provider_breakout_runtime",
            _simulation_t0=time.perf_counter() - 1.0,
            market_filter_bull_days=0,
            market_filter_bear_days=0,
            market_state_trans_down_days=0,
            market_state_trans_up_days=0,
            trade_mode_main_days=0,
            trade_mode_light_days=0,
            trade_mode_notrade_days=0,
        )

        result = build_portfolio_backtest_result(runtime)
    finally:
        monkeypatch.undo()

    latest = result.metrics["audit"]["governor_budget"]["latest"]
    assert latest["asset_scope"] == "cn_etf"
    assert latest["budget_consumer_sleeve_id"] == "cn_etf_beta"
    assert latest["budget_consumer_system_role"] == "market_beta_sleeve"
    assert latest["risk_budget_multiplier"] == 0.7
    assert latest["local_budget_controls"] == []
    assert list(latest["sleeve_budgets"].keys()) == ["cn_etf_beta"]
