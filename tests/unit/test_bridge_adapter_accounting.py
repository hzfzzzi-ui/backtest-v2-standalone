from __future__ import annotations

import json
import time
from datetime import date
from types import SimpleNamespace

import pytest
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


def test_apply_open_fills_rejects_new_buy_when_live_positions_already_hit_pending_cap() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600001"): 10.0},
        close_idx={(trading_day, "sh600001"): 10.2},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=2000.0,
        _traded_value_today=0.0,
        positions={"sh600000": 100},
        position_avg_cost={"sh600000": 9.5},
        position_entry_adj={"sh600000": 1.0},
        holding_sources={"sh600000": {"entry_reason_code": "BREAKOUT_HIGH", "entry_date": trading_day}},
        provider=SimpleNamespace(
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        _current_day={"controls": {"effective_max_positions": 1}},
        trade_rows=[],
        fill_reject_reason_counts={},
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600001",
        qty=100,
        reason_code="ENTRY",
        meta={"triggered_rule": "RULE_Y"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {"sh600000": 100}
    assert runtime.trade_rows == []
    assert runtime.fill_reject_reason_counts == {"POSITION_CAP_REACHED": 1}
    assert runtime._last_fill_reject_reason_counts_today == {"POSITION_CAP_REACHED": 1}
    assert runtime._last_accounting_snapshot.counters["FILL::POSITION_CAP_REACHED"] == 1


def test_apply_open_fills_allows_sell_then_buy_to_reuse_slot_at_pending_cap() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600000"): 10.0, (trading_day, "sh600001"): 10.0},
        close_idx={(trading_day, "sh600000"): 10.1, (trading_day, "sh600001"): 10.2},
        _slip_bps=0.0,
        _comm_rate=0.0,
        _comm_min=0.0,
        _stamp_rate=0.0,
        _min_trade_price=5.0,
        cash=0.0,
        _traded_value_today=0.0,
        positions={"sh600000": 100},
        position_avg_cost={"sh600000": 9.5},
        position_entry_adj={"sh600000": 1.0},
        holding_sources={"sh600000": {"entry_reason_code": "BREAKOUT_HIGH", "entry_date": trading_day}},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[{}],
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        _current_day={"controls": {"effective_max_positions": 1}},
        trade_rows=[],
        fill_reject_reason_counts={},
    )
    orders = [
        SimpleNamespace(side=Side.SELL, symbol="SH600000", qty=100, reason_code="EXIT", meta={}),
        SimpleNamespace(side=Side.BUY, symbol="SH600001", qty=100, reason_code="ENTRY", meta={}),
    ]

    apply_open_fills(runtime, trading_day, orders)

    assert runtime.positions == {"sh600001": 100}
    assert [trade["side"] for trade in runtime.trade_rows] == ["SELL", "BUY"]
    assert runtime.fill_reject_reason_counts == {}


def test_apply_open_fills_buy_cost_only_keeps_open_fill_price_and_books_slippage_as_cash() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600001"): 10.0},
        close_idx={(trading_day, "sh600001"): 10.2},
        hfq_close_idx={(trading_day, "sh600001"): 102.0},
        adj_factor_idx={(trading_day, "sh600001"): 10.0},
        _slip_bps=0.001,
        _slippage_mode="cost_only",
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
        meta={},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.trade_rows[0]["fill_price"] == 10.0
    assert runtime.trade_rows[0]["value"] == 1000.0
    assert runtime.trade_rows[0]["slippage"] == 1.0
    assert runtime.trade_rows[0]["slippage_mode"] == "cost_only"
    assert runtime.trade_rows[0]["net_amount"] == 1002.0


def test_apply_open_fills_sell_cost_only_keeps_open_fill_price_and_books_slippage_as_cash() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600000"): 10.0},
        close_idx={(trading_day, "sh600000"): 10.1},
        _slip_bps=0.001,
        _slippage_mode="cost_only",
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=1000.0,
        _traded_value_today=0.0,
        positions={"sh600000": 100},
        position_avg_cost={"sh600000": 9.5},
        holding_sources={"sh600000": {"entry_reason_code": "BREAKOUT_HIGH", "entry_date": trading_day}},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={"sh600000": True},
            extra_clear_dicts=[{}],
            entry_day={"sh600000": trading_day},
        ),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH600000",
        qty=100,
        reason_code="EXIT",
        meta={},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.trade_rows[0]["fill_price"] == 10.0
    assert runtime.trade_rows[0]["value"] == 1000.0
    assert runtime.trade_rows[0]["slippage"] == 1.0
    assert runtime.trade_rows[0]["slippage_mode"] == "cost_only"
    assert runtime.trade_rows[0]["net_amount"] == 997.0


def test_apply_open_fills_adjusts_position_qty_for_etf_share_fold_before_sell() -> None:
    previous_day = date(2015, 4, 17)
    trading_day = date(2015, 4, 20)
    previous_close = 7.7984 * 0.28032483
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh510500"): 7.7984},
        close_idx={
            (previous_day, "sh510500"): previous_close,
            (trading_day, "sh510500"): 7.8210,
        },
        adj_factor_idx={(trading_day, "sh510500"): 0.28032483},
        _slip_bps=0.0,
        _comm_rate=0.0003,
        _comm_min=5.0,
        _stamp_rate=0.001,
        _min_trade_price=0.0,
        cash=46.94608,
        _traded_value_today=0.0,
        positions={"sh510500": 571200},
        position_avg_cost={"sh510500": 2.2194},
        position_entry_adj={"sh510500": 1.0},
        holding_sources={"sh510500": {"entry_reason_code": "ETF_ENTRY", "entry_date": date(2015, 4, 8)}},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[{}],
            entry_day={"sh510500": date(2015, 4, 8)},
        ),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[previous_day, trading_day])),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH510500",
        qty=571200,
        reason_code="EXIT",
        meta={},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {}
    assert runtime.trade_rows[0]["qty"] == 160122
    assert round(runtime.trade_rows[0]["value"], 2) == 1248695.40
    assert runtime.trade_rows[0]["reason_code"] == "EXIT"
    adjustment = runtime._last_accounting_snapshot.daily_marks["corporate_action_adjustments"][0]
    assert adjustment["symbol"] == "sh510500"
    assert adjustment["date"] == "2015-04-20"
    assert adjustment["prev_qty"] == 571200
    assert adjustment["adjusted_qty"] == 160122
    assert adjustment["prev_entry_adj"] == pytest.approx(1.0)
    assert adjustment["current_adj"] == pytest.approx(0.28032483)
    assert adjustment["prev_avg_cost"] == pytest.approx(2.2194)
    assert adjustment["adjusted_avg_cost"] == pytest.approx(7.91724372043675)


def test_apply_open_fills_keeps_qty_when_adj_change_looks_like_small_cash_distribution() -> None:
    previous_day = date(2020, 9, 17)
    trading_day = date(2020, 9, 18)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh511010"): 120.66},
        close_idx={
            (previous_day, "sh511010"): 120.71,
            (trading_day, "sh511010"): 120.714,
        },
        adj_factor_idx={(trading_day, "sh511010"): 1.0},
        _slip_bps=0.0,
        _comm_rate=0.0003,
        _comm_min=5.0,
        _stamp_rate=0.0,
        _min_trade_price=0.0,
        cash=0.0,
        _traded_value_today=0.0,
        positions={"sh511010": 11000},
        position_avg_cost={"sh511010": 120.0},
        position_entry_adj={"sh511010": 1.012},
        holding_sources={"sh511010": {"entry_reason_code": "ETF_ENTRY", "entry_date": date(2020, 9, 1)}},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[{}],
            entry_day={"sh511010": date(2020, 9, 1)},
        ),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[previous_day, trading_day])),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH511010",
        qty=11000,
        reason_code="EXIT",
        meta={},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {}
    assert runtime.trade_rows[0]["qty"] == 11000
    assert runtime._last_accounting_snapshot.daily_marks["corporate_action_adjustments"] == []


def test_apply_open_fills_pay_date_dividend_creates_receivable_then_settles_cash() -> None:
    pre_day = date(2020, 9, 17)
    ex_day = date(2020, 9, 18)
    pay_day = date(2020, 9, 21)
    event_id = "sh511010|2020-09-18|2020-09-21|0.03"
    runtime = SimpleNamespace(
        open_idx={(ex_day, "sh511010"): 120.66, (pay_day, "sh511010"): 120.70},
        close_idx={
            (pre_day, "sh511010"): 120.71,
            (ex_day, "sh511010"): 120.714,
            (pay_day, "sh511010"): 120.73,
        },
        hfq_close_idx={(ex_day, "sh511010"): 122.16, (pay_day, "sh511010"): 122.18},
        adj_factor_idx={
            (pre_day, "sh511010"): 1.0,
            (ex_day, "sh511010"): 1.012,
            (pay_day, "sh511010"): 1.012,
        },
        dividend_events_ex_idx={
            ex_day: (
                {
                    "event_id": event_id,
                    "symbol": "sh511010",
                    "ex_date": ex_day,
                    "cash_pay_date": pay_day,
                    "div_cash": 0.03,
                },
            )
        },
        dividend_events_pay_idx={
            pay_day: (
                {
                    "event_id": event_id,
                    "symbol": "sh511010",
                    "ex_date": ex_day,
                    "cash_pay_date": pay_day,
                    "div_cash": 0.03,
                },
            )
        },
        _dividend_cash_timing_mode="pay_date",
        _slip_bps=0.0,
        _comm_rate=0.0003,
        _comm_min=5.0,
        _stamp_rate=0.0,
        _min_trade_price=0.0,
        cash=0.0,
        dividend_receivable=0.0,
        _traded_value_today=0.0,
        positions={"sh511010": 11000},
        position_avg_cost={"sh511010": 120.0},
        position_entry_adj={"sh511010": 1.0},
        pending_dividend_receivables={},
        processed_dividend_ex_event_ids=set(),
        processed_dividend_cash_event_ids=set(),
        dividend_event_rows=[],
        holding_sources={"sh511010": {"entry_reason_code": "ETF_ENTRY", "entry_date": date(2020, 9, 1)}},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[{}],
            entry_day={"sh511010": date(2020, 9, 1)},
        ),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[pre_day, ex_day, pay_day])),
        trade_rows=[],
    )

    apply_open_fills(runtime, ex_day, [])

    assert runtime.cash == pytest.approx(0.0)
    assert runtime.dividend_receivable == pytest.approx(330.0)
    assert runtime.position_entry_adj["sh511010"] == pytest.approx(1.012)
    assert runtime._last_accounting_snapshot.dividend_receivable == pytest.approx(330.0)
    assert runtime._last_accounting_snapshot.daily_marks["dividend_receivable_create_today"] == pytest.approx(330.0)
    assert runtime._last_accounting_snapshot.daily_marks["dividend_cash_credit_today"] == pytest.approx(0.0)

    apply_open_fills(runtime, pay_day, [])

    assert runtime.cash == pytest.approx(330.0)
    assert runtime.dividend_receivable == pytest.approx(0.0)
    assert runtime._last_accounting_snapshot.dividend_receivable == pytest.approx(0.0)
    assert runtime._last_accounting_snapshot.daily_marks["dividend_receivable_settle_today"] == pytest.approx(330.0)
    assert runtime._last_accounting_snapshot.daily_marks["dividend_cash_credit_today"] == pytest.approx(330.0)
    runtime.daily_rows = []
    runtime.candidate_rows = []
    runtime.accounting_audit_rows = []
    runtime.composition_audit_rows = []
    runtime.execution_lineage_records = {}
    runtime.order_reject_reason_counts = {}
    runtime.fill_reject_reason_counts = {}
    runtime.route_id = "strict_inline_runtime"
    runtime.market_filter_bull_days = 0
    runtime.market_filter_bear_days = 0
    runtime.market_state_trans_down_days = 0
    runtime.market_state_trans_up_days = 0
    runtime.trade_mode_main_days = 0
    runtime.trade_mode_light_days = 0
    runtime.trade_mode_notrade_days = 0
    runtime._simulation_t0 = time.perf_counter()
    runtime.request.initial_cash = 0.0
    runtime.request.max_positions = 10
    runtime.request.enable_strength_rank = False
    runtime.request.strength_ma = 55
    runtime.provider.blocked_by_trend_count = 0
    runtime.provider.total_buy_signals = 0
    runtime.provider.precompute_seconds = 0.0
    runtime.provider.diag_reason_counts = {}
    result = build_portfolio_backtest_result(runtime)
    assert result.cash_events is not None
    assert list(result.cash_events["cash_event_type"]) == [
        "DIVIDEND_RECEIVABLE",
        "DIVIDEND_CASH",
        "DIVIDEND_RECEIVABLE",
    ]
    assert list(result.cash_events["action"].fillna("")) == ["create", "", "settle"]


def test_apply_open_fills_ex_date_dividend_credits_cash_without_receivable() -> None:
    pre_day = date(2020, 9, 17)
    ex_day = date(2020, 9, 18)
    runtime = SimpleNamespace(
        open_idx={(ex_day, "sh511010"): 120.66},
        close_idx={
            (pre_day, "sh511010"): 120.71,
            (ex_day, "sh511010"): 120.714,
        },
        hfq_close_idx={(ex_day, "sh511010"): 122.16},
        adj_factor_idx={
            (pre_day, "sh511010"): 1.0,
            (ex_day, "sh511010"): 1.012,
        },
        dividend_events_ex_idx={
            ex_day: (
                {
                    "event_id": "sh511010|2020-09-18|2020-09-18|0.03",
                    "symbol": "sh511010",
                    "ex_date": ex_day,
                    "cash_pay_date": ex_day,
                    "div_cash": 0.03,
                },
            )
        },
        dividend_events_pay_idx={},
        _dividend_cash_timing_mode="ex_date",
        _slip_bps=0.0,
        _comm_rate=0.0003,
        _comm_min=5.0,
        _stamp_rate=0.0,
        _min_trade_price=0.0,
        cash=0.0,
        dividend_receivable=0.0,
        _traded_value_today=0.0,
        positions={"sh511010": 11000},
        position_avg_cost={"sh511010": 120.0},
        position_entry_adj={"sh511010": 1.0},
        pending_dividend_receivables={},
        processed_dividend_ex_event_ids=set(),
        processed_dividend_cash_event_ids=set(),
        dividend_event_rows=[],
        holding_sources={"sh511010": {"entry_reason_code": "ETF_ENTRY", "entry_date": date(2020, 9, 1)}},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[{}],
            entry_day={"sh511010": date(2020, 9, 1)},
        ),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[pre_day, ex_day])),
        trade_rows=[],
    )

    apply_open_fills(runtime, ex_day, [])

    assert runtime.cash == pytest.approx(330.0)
    assert runtime.dividend_receivable == pytest.approx(0.0)
    assert runtime.position_entry_adj["sh511010"] == pytest.approx(1.012)
    assert runtime._last_accounting_snapshot.daily_marks["dividend_cash_credit_today"] == pytest.approx(330.0)
    assert runtime._last_accounting_snapshot.daily_marks["dividend_receivable_create_today"] == pytest.approx(0.0)


def test_apply_open_fills_ignores_large_adj_jump_when_price_gap_does_not_match_share_transform() -> None:
    previous_day = date(2020, 9, 17)
    trading_day = date(2020, 9, 18)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh510500"): 7.0},
        close_idx={
            (previous_day, "sh510500"): 7.009,
            (trading_day, "sh510500"): 7.136,
        },
        adj_factor_idx={(trading_day, "sh510500"): 1.0},
        _slip_bps=0.0,
        _comm_rate=0.0003,
        _comm_min=5.0,
        _stamp_rate=0.001,
        _min_trade_price=0.0,
        cash=0.0,
        _traded_value_today=0.0,
        positions={"sh510500": 411264},
        position_avg_cost={"sh510500": 2.2194},
        position_entry_adj={"sh510500": 0.28},
        holding_sources={"sh510500": {"entry_reason_code": "ETF_ENTRY", "entry_date": date(2020, 8, 1)}},
        provider=SimpleNamespace(
            last_sell_day={},
            _risk_off_partial_state={},
            extra_clear_dicts=[{}],
            entry_day={"sh510500": date(2020, 8, 1)},
        ),
        request=SimpleNamespace(data_bundle=SimpleNamespace(trading_days=[previous_day, trading_day])),
        trade_rows=[],
    )
    order = SimpleNamespace(
        side=Side.SELL,
        symbol="SH510500",
        qty=411264,
        reason_code="EXIT",
        meta={},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {}
    assert runtime.trade_rows[0]["qty"] == 411264
    assert runtime._last_accounting_snapshot.daily_marks["corporate_action_adjustments"] == []


def test_apply_open_fills_buy_reject_tracks_fill_cash_reason_counts() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        open_idx={(trading_day, "sh600001"): 10.0},
        close_idx={(trading_day, "sh600001"): 10.2},
        _slip_bps=0.001,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _min_trade_price=5.0,
        cash=500.0,
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
        order_reject_reason_counts={},
        fill_reject_reason_counts={},
    )
    order = SimpleNamespace(
        side=Side.BUY,
        symbol="SH600001",
        qty=100,
        reason_code="ENTRY",
        meta={"triggered_rule": "RULE_Y"},
    )

    apply_open_fills(runtime, trading_day, [order])

    assert runtime.positions == {}
    assert runtime.trade_rows == []
    assert runtime.fill_reject_reason_counts == {"INSUFFICIENT_CASH": 1}
    assert runtime._last_fill_reject_reason_counts_today == {"INSUFFICIENT_CASH": 1}
    assert runtime._last_accounting_snapshot.counters["FILL::INSUFFICIENT_CASH"] == 1


def test_apply_daily_decision_diagnostics_separates_planning_and_fill_cash_counts() -> None:
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
                "governor_budget_json": "{}",
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
        request=SimpleNamespace(max_positions=2),
        _last_fill_reject_reason_counts_today={"INSUFFICIENT_CASH": 1},
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
        diagnostics={"raw_buy_signal_count": 1, "composition_enabled": False},
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 1,
            "buy_slots": 1,
            "selected_symbols": [],
            "selected_count": 0,
            "execution_kernel_reject_reason_counts": {"SKIP_NO_CASH": 2},
        },
    )

    daily_row = runtime.daily_rows[-1]
    assert daily_row["planning_cash_skip_count"] == 2
    assert daily_row["fill_cash_reject_count"] == 1
    assert json.loads(daily_row["planning_reject_reason_counts_json"]) == {"SKIP_NO_CASH": 2}
    assert json.loads(daily_row["fill_reject_reason_counts_json"]) == {"INSUFFICIENT_CASH": 1}


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


def test_prepare_daily_snapshot_adds_dividend_receivable_into_nav() -> None:
    trading_day = date(2020, 9, 18)
    runtime = SimpleNamespace(
        cash=1000.0,
        dividend_receivable=330.0,
        positions={"sh511010": 11000},
        position_entry_adj={"sh511010": 1.012},
        close_idx={(trading_day, "sh511010"): 120.714},
        hfq_close_idx={(trading_day, "sh511010"): 122.162168},
        peak_nav=0.0,
        prev_nav=1000.0,
        _traded_value_today=0.0,
        daily_rows=[],
        _compute_day_controls=lambda *_args, **_kwargs: {
            "effective_max_positions": 10,
            "dd_state": "NORMAL",
            "regime_engine": "weekly_five_state",
            "market_state_5": "BULL",
            "market_state_score": 5,
            "market_state_raw": "BULL",
            "market_state_smoothed": "BULL",
            "risk_budget_multiplier": 1.0,
            "weekly_observation_flag": False,
            "market_state": "BULL",
            "trade_mode": "TREND_MAIN",
            "benchmark_regime_on": True,
            "feature_availability": {},
            "risk_on_today": True,
        },
        _last_accounting_snapshot=None,
    )

    snapshot = prepare_daily_snapshot(runtime, day_index=0, day=trading_day)

    assert round(snapshot.market_value, 2) == 1327849.65
    assert round(snapshot.nav, 2) == 1329179.65
    assert snapshot.accounting_snapshot.dividend_receivable == pytest.approx(330.0)


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
    assert governor_budget["regime_effective_state"] == "TRANS_UP"
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
    assert "target_exposure_source" not in governor_budget
    assert "min_deployable_exposure" not in governor_budget
    assert "fallback_allowed" not in governor_budget
    diagnostics = json.loads(runtime.daily_rows[-1]["diagnostics_input_json"])
    formal_view = diagnostics["diagnostics"]["etf_beta_formal_view"]
    assert formal_view["target_exposure_source"] == "governor_total_exposure_cap"
    assert formal_view["min_deployable_exposure"] == pytest.approx(0.0)
    assert formal_view["min_deployable_exposure_source"] == "phase1_allocation_engine"
    assert formal_view["fallback_allowed"] is False


def test_apply_daily_decision_diagnostics_overrides_cn_etf_phase1_budget_fields_from_governor_truth() -> None:
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
                "market_state_5": "TRANS_DOWN",
                "base_state_5": "TRANS_DOWN",
                "effective_state_5": "TRANS_DOWN",
                "coarse_state": "RISK_OFF",
                "effective_coarse_state": "RISK_OFF",
                "risk_budget_multiplier": 0.8,
                "reason_codes_json": "[]",
                "manual_override_json": "{}",
                "defense_bias": 0.0,
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "asset_scope": "cn_etf",
                        "budget_consumer_sleeve_id": "cn_etf_beta",
                        "budget_consumer_system_role": "market_beta_sleeve",
                        "budget_semantics": "consume_governor_sleeve_budget",
                        "regime_effective_state": "TRANS_DOWN",
                        "total_risk_budget": 0.5,
                        "total_exposure_cap": 0.5,
                        "budget_reason_codes": [],
                        "sleeve_budgets": {
                            "cn_etf_beta": {
                                "slot_cap": 2,
                                "target_exposure": 0.4,
                                "target_exposure_source": "budget_snapshot",
                                "target_selected_count": 2,
                            }
                        },
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
            governed_a_share={
                "etf_beta": {
                    "enabled": True,
                    "strategy_role": "phase1_allocation_engine",
                    "source_entry_type": "cn_etf_phase1_allocation_entry",
                    "research_rule_family": "phase1_allocation_engine_v1",
                    "governor_boundary_mode": "consume_governor_sleeve_budget",
                    "local_policy_mode": "phase1_bucket_allocation",
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "exposure_policy_family": "phase1_governed_allocation_v1",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                    "max_selected_symbols": 3,
                }
            },
        ),
    )
    buy_signal = SimpleNamespace(symbol="SH510300", meta={"sleeve_id": "cn_etf_beta"})
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
            "etf_beta_rebalance_day": True,
            "etf_beta_eligible_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH", "511010.SH"],
            "etf_beta_selected_symbols": ["510300.SH", "510500.SH"],
            "etf_beta_deployable_slot_cap": 2,
            "etf_beta_target_selected_count": 2,
            "etf_beta_target_selected_count_source": "state_slot_cap_fallback",
            "etf_beta_requested_budget": 0.0,
            "etf_beta_applied_budget": 0.0,
            "etf_beta_target_exposure": 0.0,
            "etf_beta_target_exposure_source": "governor_sleeve_budget",
            "etf_beta_min_deployable_exposure": 0.0,
            "etf_beta_min_deployable_exposure_source": "phase1_allocation_engine",
            "etf_beta_targets": {},
            "etf_beta_cash_weight": 0.0,
            "etf_beta_defense_weight": 0.0,
            "etf_beta_equity_core_bucket": 0.0,
            "etf_beta_defense_tilt_bucket": 0.0,
            "etf_beta_cash_buffer_bucket": 0.0,
            "etf_beta_allocation_reason_codes": [],
            "etf_beta_target_actual_exposure": 0.0,
            "etf_beta_target_deployability_gap": 0.0,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 2,
            "buy_slots": 2,
            "selected_symbols": ["sh510300", "sh510500"],
            "selected_count": 2,
        },
    )

    diagnostics_input = json.loads(runtime.daily_rows[-1]["diagnostics_input_json"])
    diagnostics = diagnostics_input["diagnostics"]
    formal_view = diagnostics["etf_beta_formal_view"]
    research_view = diagnostics["etf_beta_research_view"]

    assert formal_view["target_exposure"] == pytest.approx(0.4)
    assert formal_view["target_exposure_source"] == "governor_sleeve_budget"
    assert formal_view["min_deployable_exposure"] == pytest.approx(0.0)
    assert formal_view["min_deployable_exposure_source"] == "phase1_allocation_engine"
    assert formal_view["targets"]["511010.SH"] == pytest.approx(0.22)
    assert "510500.SH" not in formal_view["targets"]
    assert "512100.SH" not in formal_view["targets"]
    assert sum(float(value) for value in formal_view["targets"].values()) == pytest.approx(0.4)
    assert formal_view["target_selected_count"] == 2
    assert formal_view["target_selected_count_source"] == "input"
    assert formal_view["boundary_policy_mode"] == "formal_phase1_document_aligned_v1"
    assert formal_view["governor_hard_blocked"] is False
    assert formal_view["local_boundary_state"] == "REDUCED_ALLOCATION"
    assert "PHASE1_DOCUMENT_REDUCED_ALLOCATION" in formal_view["local_boundary_reason_codes"]
    assert "PHASE1_ALLOCATION_ENGINE::THREE_BUCKET" in formal_view["reason_codes"]
    assert research_view["requested_budget"] == pytest.approx(0.4)
    assert research_view["applied_budget"] == pytest.approx(0.4)
    assert research_view["defense_weight"] == pytest.approx(0.22)
    assert research_view["equity_core_bucket"] == pytest.approx(0.45)
    assert research_view["defense_tilt_bucket"] == pytest.approx(0.10)
    assert research_view["cash_buffer_bucket"] == pytest.approx(0.45)
    assert research_view["cash_weight"] == pytest.approx(0.0)
    assert research_view["strategic_floor_cap"] == pytest.approx(0.18)
    assert research_view["tactical_overlay_cap"] == pytest.approx(0.0)
    assert research_view["deployability_gap"] == pytest.approx(0.4)


def test_apply_daily_decision_diagnostics_prefers_notional_total_exposure_cap_over_risk_multiplier() -> None:
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
                "risk_budget_multiplier": 1.8,
                "reason_codes_json": "[]",
                "manual_override_json": "{}",
                "defense_bias": 0.0,
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "asset_scope": "cn_etf",
                        "budget_consumer_sleeve_id": "cn_etf_beta",
                        "budget_consumer_system_role": "market_beta_sleeve",
                        "budget_semantics": "consume_governor_sleeve_budget",
                        "regime_effective_state": "BULL",
                        "total_risk_budget": 1.8,
                        "total_exposure_cap": 0.2,
                        "budget_reason_codes": [],
                        "sleeve_budgets": {
                            "cn_etf_beta": {
                                "slot_cap": 2,
                                "target_selected_count": 2,
                            }
                        },
                    }
                ),
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
        request=SimpleNamespace(
            max_positions=10,
            asset_context={"asset_scope": "cn_etf"},
            governed_a_share={
                "etf_beta": {
                    "enabled": True,
                    "strategy_role": "phase1_allocation_engine",
                    "source_entry_type": "cn_etf_phase1_allocation_entry",
                    "research_rule_family": "phase1_allocation_engine_v1",
                    "governor_boundary_mode": "consume_governor_sleeve_budget",
                    "local_policy_mode": "phase1_bucket_allocation",
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "exposure_policy_family": "phase1_governed_allocation_v1",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                    "max_selected_symbols": 3,
                }
            },
        ),
    )
    buy_signal = SimpleNamespace(symbol="SH510300", meta={"sleeve_id": "cn_etf_beta"})
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
            "etf_beta_target_selected_count": 2,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 2,
            "buy_slots": 2,
            "selected_symbols": ["sh510300", "sh510500"],
            "selected_count": 2,
        },
    )

    diagnostics_input = json.loads(runtime.daily_rows[-1]["diagnostics_input_json"])
    diagnostics = diagnostics_input["diagnostics"]
    governor_budget = json.loads(runtime.daily_rows[-1]["governor_budget_json"])
    formal_view = diagnostics["etf_beta_formal_view"]
    research_view = diagnostics["etf_beta_research_view"]

    assert formal_view["target_exposure"] == pytest.approx(0.2)
    assert research_view["requested_budget"] == pytest.approx(0.2)
    assert research_view["applied_budget"] == pytest.approx(0.2)
    assert runtime.daily_rows[-1]["etf_target_exposure"] == pytest.approx(0.2)
    assert governor_budget["target_exposure"] == pytest.approx(0.2)


def test_apply_daily_decision_diagnostics_projects_trans_up_redeploy_fields() -> None:
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2026-03-20",
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
                "effective_max_positions": 1,
                "breadth_max_positions": 1,
                "dd_state": "NORMAL",
                "regime_transition_reason": "",
                "market_state_5": "TRANS_UP",
                "base_state_5": "TRANS_UP",
                "effective_state_5": "TRANS_UP",
                "coarse_state": "RISK_ON",
                "effective_coarse_state": "RISK_ON",
                "risk_budget_multiplier": 0.75,
                "reason_codes_json": "[]",
                "manual_override_json": "{}",
                "defense_bias": 0.0,
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "asset_scope": "cn_etf",
                        "budget_consumer_sleeve_id": "cn_etf_beta",
                        "budget_consumer_system_role": "market_beta_sleeve",
                        "budget_semantics": "consume_governor_sleeve_budget",
                        "regime_effective_state": "TRANS_UP",
                        "total_risk_budget": 0.75,
                        "total_exposure_cap": 0.1,
                        "budget_reason_codes": [],
                        "sleeve_budgets": {
                            "cn_etf_beta": {
                                "slot_cap": 1,
                                "target_selected_count": 1,
                                "target_exposure": 0.1,
                            }
                        },
                    }
                ),
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 1}},
        positions={},
        composition_audit_rows=[],
        request=SimpleNamespace(
            max_positions=10,
            asset_context={"asset_scope": "cn_etf"},
            governed_a_share={
                "etf_beta": {
                    "enabled": True,
                    "strategy_role": "strategic_beta_stabilizer",
                    "source_entry_type": "cn_etf_phase1_allocation_entry",
                    "research_rule_family": "phase1_allocation_engine_v1",
                    "governor_boundary_mode": "consume_governor_sleeve_budget",
                    "local_policy_mode": "phase1_bucket_allocation",
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "exposure_policy_family": "phase1_governed_allocation_v1",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                    "max_selected_symbols": 3,
                }
            },
        ),
    )
    buy_signal = SimpleNamespace(symbol="SH510300", meta={"sleeve_id": "cn_etf_beta"})
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
            "etf_beta_target_selected_count": 1,
            "etf_beta_execution_path": "trans_up_state_change_redeploy",
            "etf_beta_trans_up_contract_mode": "single_seat_core_recovery",
            "etf_beta_trans_up_single_seat_core_recovery": True,
            "etf_beta_trans_up_redeploy_active": True,
            "etf_beta_trans_up_redeploy_reason_code": "ETF_BETA_TRANS_UP_REDEPLOY_ACTIVE",
            "etf_beta_trans_up_redeploy_reject_reason": None,
            "etf_beta_trans_up_redeploy_floor_gap": 0.0527,
            "etf_beta_trans_up_redeploy_edge_from_state": "RISK_OFF",
            "etf_beta_pace_policy_gap": 0.0473,
            "etf_beta_pace_policy_reason_code": "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY",
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 1,
            "buy_slots": 1,
            "selected_symbols": ["sh510300"],
            "selected_count": 1,
        },
    )

    diagnostics_input = json.loads(runtime.daily_rows[-1]["diagnostics_input_json"])
    diagnostics = diagnostics_input["diagnostics"]
    research_view = diagnostics["etf_beta_research_view"]

    assert "etf_execution_path" not in runtime.daily_rows[-1]
    assert research_view["execution_path"] == "trans_up_state_change_redeploy"
    assert research_view["trans_up_contract_mode"] == "single_seat_core_recovery"
    assert research_view["trans_up_single_seat_core_recovery"] is True
    assert research_view["trans_up_redeploy_active"] is True
    assert research_view["trans_up_redeploy_reason_code"] == "ETF_BETA_TRANS_UP_REDEPLOY_ACTIVE"
    assert research_view["trans_up_redeploy_reject_reason"] is None
    assert research_view["trans_up_redeploy_floor_gap"] == pytest.approx(0.0527)
    assert research_view["trans_up_redeploy_edge_from_state"] == "RISK_OFF"
    assert research_view["pace_policy_gap"] == pytest.approx(0.0473)
    assert research_view["pace_policy_reason_code"] == "ETF_BETA_DEPLOYMENT_PACE_FLOOR_ONLY"
    assert research_view["rebalance_timing_gap"] == pytest.approx(0.0)
    assert research_view["execution_residual_gap"] == pytest.approx(0.0527)
    assert research_view["gap_primary_owner"] == "pace_policy"


def test_apply_daily_decision_diagnostics_preserves_standalone_provider_target_contract() -> None:
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2014-07-14",
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
                "market_state_5": "TRANS_UP",
                "base_state_5": "TRANS_UP",
                "effective_state_5": "TRANS_UP",
                "coarse_state": "RISK_ON",
                "effective_coarse_state": "RISK_ON",
                "risk_budget_multiplier": 1.0,
                "reason_codes_json": "[]",
                "manual_override_json": "{}",
                "defense_bias": 0.0,
                "governor_budget_json": json.dumps(
                    {
                        "contract_version": "cn_a_governor_budget@1",
                        "asset_scope": "cn_etf",
                        "budget_consumer_sleeve_id": "cn_etf_beta",
                        "budget_consumer_system_role": "market_beta_sleeve",
                        "budget_semantics": "consume_governor_state_and_budget",
                        "regime_effective_state": "TRANS_UP",
                        "total_risk_budget": 1.0,
                        "total_exposure_cap": 0.9,
                        "budget_reason_codes": [],
                        "sleeve_budgets": {
                            "cn_etf_beta": {
                                "slot_cap": 2,
                                "target_selected_count": 2,
                                "target_exposure": 0.9,
                                "allow_new_risk": True,
                            }
                        },
                    }
                ),
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
        request=SimpleNamespace(
            max_positions=10,
            asset_context={"asset_scope": "cn_etf"},
            governed_a_share={
                "etf_beta": {
                    "enabled": True,
                    "strategy_role": "governed_broad_based_standalone_mainline",
                    "source_entry_type": "cn_etf_broad_based_standalone_mainline_entry",
                    "research_rule_family": "broad_based_rotation_template_a",
                    "governor_boundary_mode": "consume_governor_state_and_budget",
                    "local_policy_mode": "broad_based_rotation_mainline",
                    "exposure_policy_family": "broad_based_standalone_mainline_v1",
                    "policy_scope": "broad_based_only",
                    "broad_based_only": True,
                    "core_accumulator_symbols": ["510300.SH"],
                    "tactical_satellite_symbols": ["510500.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                    "symbol_role_map": {
                        "510300.SH": "core_accumulator",
                        "510500.SH": "tactical_satellite",
                        "511010.SH": "limited_defense",
                    },
                    "target_exposure_by_state_5": {"TRANS_UP": 0.9},
                    "target_selected_count_by_state_5": {"TRANS_UP": 2},
                }
            },
        ),
    )
    buy_signal = SimpleNamespace(symbol="SH510500", meta={"sleeve_id": "cn_etf_beta"})
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
            "etf_beta_target_selected_count": 2,
            "etf_beta_execution_path": "trans_up_inter_rebalance_deploy",
            "etf_beta_formal_view": {
                "target_exposure": 0.9,
                "target_exposure_source": "state_map::TRANS_UP",
                "min_deployable_exposure": 0.0,
                "min_deployable_exposure_source": "phase1_allocation_engine",
                "target_selected_count": 2,
                "target_selected_count_source": "state_map::TRANS_UP",
                "fallback_allowed": False,
                "fallback_allowed_source": "state_map::TRANS_UP",
                "targets": {"510500.SH": 0.9},
                "selected_symbols": ["510500.SH"],
            },
            "etf_beta_research_view": {
                "execution_path": "trans_up_inter_rebalance_deploy",
                "deployability_gap": 0.9,
            },
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 1,
            "buy_slots": 2,
            "selected_symbols": ["sh510500"],
            "selected_count": 1,
        },
    )

    diagnostics_input = json.loads(runtime.daily_rows[-1]["diagnostics_input_json"])
    diagnostics = diagnostics_input["diagnostics"]
    formal_view = diagnostics["etf_beta_formal_view"]
    research_view = diagnostics["etf_beta_research_view"]

    assert formal_view["targets"] == {"510500.SH": pytest.approx(0.9)}
    assert formal_view["target_exposure"] == pytest.approx(0.9)
    assert research_view["execution_path"] == "trans_up_inter_rebalance_deploy"
    assert research_view["deployability_gap"] == pytest.approx(0.9)


def test_apply_daily_decision_diagnostics_persists_bull_partial_overlay_pace_fields() -> None:
    runtime = SimpleNamespace(
        daily_rows=[
            {
                "date": "2026-03-20",
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
                        "asset_scope": "cn_etf",
                        "budget_consumer_sleeve_id": "cn_etf_beta",
                        "budget_consumer_system_role": "market_beta_sleeve",
                        "budget_semantics": "consume_governor_sleeve_budget",
                        "regime_effective_state": "BULL",
                        "total_risk_budget": 1.0,
                        "total_exposure_cap": 0.2,
                        "budget_reason_codes": [],
                        "sleeve_budgets": {
                            "cn_etf_beta": {
                                "slot_cap": 2,
                                "target_selected_count": 2,
                                "target_exposure": 0.2,
                            }
                        },
                    }
                ),
            }
        ],
        route_id="strict_inline_runtime",
        _current_day={"controls": {"effective_max_positions": 2}},
        positions={},
        composition_audit_rows=[],
        request=SimpleNamespace(
            max_positions=10,
            asset_context={"asset_scope": "cn_etf"},
            governed_a_share={
                "etf_beta": {
                    "enabled": True,
                    "strategy_role": "strategic_beta_stabilizer",
                    "source_entry_type": "cn_etf_phase1_allocation_entry",
                    "research_rule_family": "phase1_allocation_engine_v1",
                    "governor_boundary_mode": "consume_governor_sleeve_budget",
                    "local_policy_mode": "phase1_bucket_allocation",
                    "boundary_policy_mode": "formal_phase1_document_aligned_v1",
                    "exposure_policy_family": "phase1_governed_allocation_v1",
                    "core_beta_symbols": ["510300.SH", "510500.SH", "510050.SH", "512100.SH"],
                    "limited_defense_candidates": ["511010.SH"],
                    "max_selected_symbols": 3,
                    "bull_partial_overlay_pace_ratio": 0.5,
                }
            },
        ),
    )
    buy_signal = SimpleNamespace(symbol="SH510300", meta={"sleeve_id": "cn_etf_beta"})
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
            "etf_beta_target_selected_count": 2,
            "etf_beta_execution_path": "monthly_rebalance",
            "etf_beta_bull_partial_overlay_pace_ratio": 0.5,
            "etf_beta_bull_pace_mode": "partial_overlay_v1",
            "etf_beta_pace_policy_gap": 0.056,
            "etf_beta_pace_policy_reason_code": "ETF_BETA_DEPLOYMENT_PACE_BULL_PARTIAL_OVERLAY",
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 2,
            "buy_slots": 2,
            "selected_symbols": ["sh510300", "sh510500"],
            "selected_count": 2,
        },
    )

    diagnostics_input = json.loads(runtime.daily_rows[-1]["diagnostics_input_json"])
    diagnostics = diagnostics_input["diagnostics"]
    research_view = diagnostics["etf_beta_research_view"]

    assert "etf_bull_partial_overlay_pace_ratio" not in runtime.daily_rows[-1]
    assert research_view["bull_partial_overlay_pace_ratio"] == pytest.approx(0.5)
    assert research_view["bull_pace_mode"] == "partial_overlay_v1"
    assert research_view["pace_policy_gap"] == pytest.approx(0.056)
    assert research_view["pace_policy_reason_code"] == "ETF_BETA_DEPLOYMENT_PACE_BULL_PARTIAL_OVERLAY"


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

