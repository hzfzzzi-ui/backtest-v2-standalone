from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters.candidate_boundary import build_candidate_boundary_result
from backend.core.stage_pipeline.adapters.candidate_plan import build_candidate_plan_result
from backend.core.stage_pipeline.adapters.fill_accounting import apply_open_fills
from backend.core.stage_pipeline.adapters.lineage import build_execution_lineage_audit, finalize_execution_lineage
from backend.core.stage_pipeline.adapters.order_planning import build_s7_order_stage_output


def _buy_signal() -> Signal:
    return Signal(
        signal_date=date(2026, 3, 2),
        symbol="SH600000",
        side=Side.BUY,
        qty=100,
        reason="ENTRY",
        reason_code="ENTRY",
        meta={
            "alpha_id": "breakout_55",
            "alpha_source": "breakout_55",
            "sleeve_id": "trend",
            "entry_alpha_id": "breakout_55",
            "entry_sleeve_id": "trend",
            "entry_reason_code": "ENTRY",
        },
    )


def _sell_signal() -> Signal:
    return Signal(
        signal_date=date(2026, 3, 2),
        symbol="SZ000001",
        side=Side.SELL,
        qty=100,
        reason="EXIT",
        reason_code="EXIT",
        meta={
            "alpha_id": "breakout_55",
            "alpha_source": "breakout_55",
            "sleeve_id": "trend",
            "entry_alpha_id": "breakout_55",
            "entry_sleeve_id": "trend",
            "entry_reason_code": "ENTRY",
        },
    )


def _prepare_candidate_contracts(runtime: SimpleNamespace) -> None:
    current_day = runtime._current_day
    candidate_boundary = build_candidate_boundary_result(
        runtime,
        day=current_day["day"],
        controls=current_day["controls"],
        day_signals=current_day["day_signals"],
    )
    candidate_plan = build_candidate_plan_result(
        runtime,
        day=current_day["day"],
        controls=current_day["controls"],
        day_signals=current_day["day_signals"],
        candidate_boundary=candidate_boundary,
        next_open=current_day["next_open"],
        nav=float(current_day["nav"]),
    )
    current_day["candidate_boundary"] = candidate_boundary
    current_day["candidate_plan"] = candidate_plan


def test_signal_order_fill_lineage_ids_propagate_end_to_end(monkeypatch) -> None:
    buy_signal = _buy_signal()

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        signal = kwargs["planned_items"][0]["signal"]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 0
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = ["sh600000"]
        return [
            SimpleNamespace(
                side=Side.BUY,
                symbol="SH600000",
                qty=100,
                reason_code="ENTRY",
                meta=dict(signal.meta or {}),
            )
        ]

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_execution_orders_from_candidate_plan",
        _fake_build_execution_orders_from_candidate_plan,
    )

    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[],
                buy_signals=[buy_signal],
                exit_syms=set(),
                strength_map={"sh600000": 1.0},
                mf_score_map={"sh600000": 1.0},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            ),
            "next_open": {"sh600000": 10.0},
            "next_trading_day": date(2026, 3, 3),
            "nav": 100000.0,
            "holding_symbols": tuple(),
        },
        request=SimpleNamespace(
            enable_multifactor_rank=False,
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
            strategy=SimpleNamespace(enable_entry_gap_guard=False, entry_gap_guard_pct=0.0, min_hold_days=0),
        ),
        provider=SimpleNamespace(_feats=None, _mx=None, _sym_to_col={}, entry_day={}, entry_day_overwrite=False, peak_state_on_buy={}),
        positions={},
        position_avg_cost={},
        holding_sources={},
        cash=100000.0,
        open_idx={(date(2026, 3, 3), "sh600000"): 10.0},
        close_idx={(date(2026, 3, 3), "sh600000"): 10.2},
        volume_idx={(date(2026, 3, 3), "sh600000"): 1000.0},
        amount_idx={(date(2026, 3, 3), "sh600000"): 10000.0},
        suspended_idx={(date(2026, 3, 3), "sh600000"): False},
        limit_up_idx={(date(2026, 3, 3), "sh600000"): 20.0},
        limit_down_idx={(date(2026, 3, 3), "sh600000"): 1.0},
        _slip_bps=0.0,
        _comm_rate=0.0,
        _comm_min=0.0,
        _stamp_rate=0.0,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=0,
        _tilt_bottom_n=0,
        _min_trade_price=5.0,
        _portfolio_mode="equal_10",
        _traded_value_today=0.0,
        trade_rows=[],
        candidate_rows=[],
        deferred_sell_orders=[],
        execution_lineage_records={},
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **_kwargs: None,
    )
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)
    order_payload = output.payload["next_day_orders"][0]
    order_meta = dict(order_payload["meta"] or {})

    assert str(order_meta.get("signal_id") or "").startswith("sig_")
    assert str(order_meta.get("order_id") or "").startswith("ord_")
    assert order_meta["scheduled_date"] == "2026-03-03"

    apply_open_fills(runtime, date(2026, 3, 3), output.payload["next_day_orders"])

    trade_row = runtime.trade_rows[0]
    assert trade_row["signal_id"] == order_meta["signal_id"]
    assert trade_row["order_id"] == order_meta["order_id"]
    assert str(trade_row["fill_id"]).startswith("fil_")

    ledger_rows = finalize_execution_lineage(runtime)
    assert ledger_rows[0]["terminal_status"] == "filled"
    assert ledger_rows[0]["fill_id"] == trade_row["fill_id"]
    assert build_execution_lineage_audit(ledger_rows)["status"] == "PASS"


def test_record_scheduled_orders_preserves_sell_buy_execution_order(monkeypatch) -> None:
    sell_signal = _sell_signal()
    buy_signal = _buy_signal()

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        sell = kwargs["sell_signals"][0]
        buy = kwargs["planned_items"][0]["signal"]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 0
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = ["sh600000"]
        return [
            SimpleNamespace(
                side=Side.SELL,
                symbol="SZ000001",
                qty=100,
                reason_code="EXIT",
                meta=dict(sell.meta or {}),
            ),
            SimpleNamespace(
                side=Side.BUY,
                symbol="SH600000",
                qty=100,
                reason_code="ENTRY",
                meta=dict(buy.meta or {}),
            ),
        ]

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_execution_orders_from_candidate_plan",
        _fake_build_execution_orders_from_candidate_plan,
    )

    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[sell_signal],
                buy_signals=[buy_signal],
                exit_syms={"sz000001"},
                strength_map={"sh600000": 1.0},
                mf_score_map={"sh600000": 1.0},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            ),
            "next_open": {"sh600000": 10.0, "sz000001": 20.0},
            "next_trading_day": date(2026, 3, 3),
            "nav": 100000.0,
            "holding_symbols": ("sz000001",),
        },
        request=SimpleNamespace(
            enable_multifactor_rank=False,
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
            strategy=SimpleNamespace(enable_entry_gap_guard=False, entry_gap_guard_pct=0.0, min_hold_days=0),
        ),
        provider=SimpleNamespace(
            _feats=None,
            _mx=None,
            _sym_to_col={},
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
            last_sell_day={},
            extra_clear_dicts=[],
        ),
        positions={"sz000001": 100},
        position_avg_cost={"sz000001": 18.0},
        holding_sources={
            "sz000001": {
                "entry_alpha_id": "breakout_55",
                "entry_sleeve_id": "trend",
                "entry_reason_code": "ENTRY",
                "entry_date": date(2026, 2, 20),
            }
        },
        cash=100.0,
        open_idx={
            (date(2026, 3, 3), "sh600000"): 10.0,
            (date(2026, 3, 3), "sz000001"): 20.0,
        },
        close_idx={
            (date(2026, 3, 3), "sh600000"): 10.2,
            (date(2026, 3, 3), "sz000001"): 20.1,
        },
        volume_idx={
            (date(2026, 3, 3), "sh600000"): 1000.0,
            (date(2026, 3, 3), "sz000001"): 1000.0,
        },
        amount_idx={
            (date(2026, 3, 3), "sh600000"): 10000.0,
            (date(2026, 3, 3), "sz000001"): 20000.0,
        },
        suspended_idx={
            (date(2026, 3, 3), "sh600000"): False,
            (date(2026, 3, 3), "sz000001"): False,
        },
        limit_up_idx={
            (date(2026, 3, 3), "sh600000"): 20.0,
            (date(2026, 3, 3), "sz000001"): 30.0,
        },
        limit_down_idx={
            (date(2026, 3, 3), "sh600000"): 1.0,
            (date(2026, 3, 3), "sz000001"): 1.0,
        },
        _slip_bps=0.0,
        _comm_rate=0.0,
        _comm_min=0.0,
        _stamp_rate=0.0,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=0,
        _tilt_bottom_n=0,
        _min_trade_price=5.0,
        _portfolio_mode="equal_10",
        _traded_value_today=0.0,
        trade_rows=[],
        candidate_rows=[],
        deferred_sell_orders=[],
        execution_lineage_records={},
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **_kwargs: None,
    )
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)

    assert [order["side"] for order in output.payload["next_day_orders"]] == [Side.SELL, Side.BUY]
    assert [order["symbol"] for order in output.payload["next_day_orders"]] == ["sz000001", "sh600000"]

    apply_open_fills(runtime, date(2026, 3, 3), output.payload["next_day_orders"])

    assert [trade["side"] for trade in runtime.trade_rows] == ["SELL", "BUY"]
    assert [trade["symbol"] for trade in runtime.trade_rows] == ["sz000001", "sh600000"]
    assert runtime.cash == 1100.0

    ledger_rows = finalize_execution_lineage(runtime)
    assert build_execution_lineage_audit(ledger_rows)["status"] == "PASS"


def test_execution_lineage_audit_tracks_planning_and_fill_cash_layers() -> None:
    rows = [
        {
            "signal_id": "sig_1",
            "signal_date": "2026-03-02",
            "order_id": "ord_1",
            "scheduled_date": "2026-03-03",
            "last_scheduled_date": "2026-03-03",
            "schedule_attempts": 1,
            "fill_id": "",
            "fill_date": "",
            "symbol": "sh600001",
            "side": "BUY",
            "qty": 100,
            "reason_code": "ENTRY",
            "signal_alpha_id": "breakout_55",
            "signal_sleeve_id": "trend",
            "entry_alpha_id": "breakout_55",
            "entry_sleeve_id": "trend",
            "terminal_status": "rejected",
            "terminal_reason": "INSUFFICIENT_CASH",
            "deferred_count": 0,
        }
    ]

    audit = build_execution_lineage_audit(
        rows,
        planning_reject_reason_counts={"SKIP_NO_CASH": 2},
        fill_reject_reason_counts={"INSUFFICIENT_CASH": 1},
    )

    assert audit["summary"]["planning_reject_reason_counts"] == {"SKIP_NO_CASH": 2}
    assert audit["summary"]["fill_reject_reason_counts"] == {"INSUFFICIENT_CASH": 1}
    assert audit["summary"]["planning_cash_skip_count"] == 2
    assert audit["summary"]["fill_insufficient_cash_count"] == 1
    assert audit["summary"]["terminal_reason_counts"]["INSUFFICIENT_CASH"] == 1
