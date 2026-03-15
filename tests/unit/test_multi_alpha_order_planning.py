from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters.fill_accounting import apply_open_fills
from backend.core.portfolio.portfolio_builder import build_rebalance_orders
from backend.core.stage_pipeline.adapters.order_planning import build_s7_order_stage_output


def _signal(symbol: str, *, sleeve_id: str, alpha_id: str, compose_score: float) -> Signal:
    return Signal(
        signal_date=date(2026, 3, 2),
        symbol=symbol,
        side=Side.BUY,
        qty=100,
        reason="ENTRY",
        reason_code="ENTRY",
        meta={
            "alpha_id": alpha_id,
            "alpha_source": alpha_id,
            "sleeve_id": sleeve_id,
            "compose_score": compose_score,
            "entry_alpha_id": alpha_id,
            "entry_sleeve_id": sleeve_id,
            "entry_reason_code": "ENTRY",
        },
    )


def _request_stub(*, fast_mode: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        enable_multifactor_rank=False,
        mf_rank_gate_mode="ALWAYS_ON",
        fast_mode=fast_mode,
        lot_size=100,
        enable_strength_rank=False,
        strength_ma=120,
        strength_top_k_mode="FILL_TO_MAX",
        mf_topk=10,
        mf_concentrate_topn=3,
        mf_concentrate_scale=1.5,
        momentum_top_pct=0.0,
    )


def test_resolve_mf_gate_on_today_supports_market_state_modes() -> None:
    assert (
        resolve_mf_gate_on_today(
            enable_multifactor_rank=True,
            mf_rank_gate_mode="BULL_ONLY",
            risk_on_today=False,
            strong_risk_on_today=False,
            market_state_today="BULL",
        )
        is True
    )
    assert (
        resolve_mf_gate_on_today(
            enable_multifactor_rank=True,
            mf_rank_gate_mode="BULL_ONLY",
            risk_on_today=True,
            strong_risk_on_today=True,
            market_state_today="TRANS_UP",
        )
        is False
    )
    assert (
        resolve_mf_gate_on_today(
            enable_multifactor_rank=True,
            mf_rank_gate_mode="TRANS_UP_OR_BULL",
            risk_on_today=False,
            strong_risk_on_today=False,
            market_state_today="TRANS_UP",
        )
        is True
    )
    assert (
        resolve_mf_gate_on_today(
            enable_multifactor_rank=True,
            mf_rank_gate_mode="TRANS_UP_OR_BULL",
            risk_on_today=True,
            strong_risk_on_today=False,
            market_state_today="BEAR",
        )
        is False
    )


def test_order_planning_hard_sleeve_budget_prefilters_composed_signals(monkeypatch) -> None:
    buy_signals = [
        _signal("sh600101", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.91),
        _signal("sh600102", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.81),
        _signal("sh600103", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.71),
        _signal("sh600201", sleeve_id="mr", alpha_id="rsi_reversal", compose_score=0.88),
        _signal("sh600202", sleeve_id="mr", alpha_id="rsi_reversal", compose_score=0.78),
        _signal("sh600203", sleeve_id="mr", alpha_id="rsi_reversal", compose_score=0.68),
    ]
    captured: dict[str, object] = {}

    def _fake_build_rebalance_orders(**kwargs):
        captured["buy_symbols"] = [str(sig.symbol).lower() for sig in kwargs["buy_signals"]]
        captured["buy_sleeves"] = [str((sig.meta or {}).get("sleeve_id", "")) for sig in kwargs["buy_signals"]]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        return []

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_rebalance_orders",
        _fake_build_rebalance_orders,
    )

    diag_calls: list[dict[str, object]] = []
    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[],
                buy_signals=buy_signals,
                raw_alpha_signals=buy_signals,
                composed_buy_signals=buy_signals,
                exit_syms=set(),
                strength_map={str(sig.symbol).lower(): float((sig.meta or {}).get("compose_score", 0.0)) for sig in buy_signals},
                mf_score_map={str(sig.symbol).lower(): float((sig.meta or {}).get("compose_score", 0.0)) for sig in buy_signals},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={"composition_enabled": True},
            ),
            "next_open": {str(sig.symbol).lower(): 10.0 for sig in buy_signals},
            "nav": 100000.0,
            "holding_symbols": ("sh600001", "sh600002"),
        },
        request=_request_stub(),
        provider=SimpleNamespace(
            _feats=None,
            _mx=None,
            _sym_to_col={},
            _same_symbol_policy="PREFER_HIGHER_SCORE",
            _multi_alpha={
                "signal_composition": {
                    "modules": [
                        {"name": "breakout_55", "weight": 0.6},
                        {"name": "rsi_reversal", "weight": 0.4},
                    ]
                }
            },
            _module_specs={
                "breakout_55": SimpleNamespace(sleeve_id="trend"),
                "rsi_reversal": SimpleNamespace(sleeve_id="mr"),
            },
        ),
        positions={"sh600001": 100, "sh600002": 100},
        holding_sources={
            "sh600001": {"entry_sleeve_id": "trend"},
            "sh600002": {"entry_sleeve_id": "trend"},
        },
        cash=100000.0,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=3,
        _tilt_bottom_n=2,
        _min_trade_price=5.0,
        _portfolio_mode="hard_sleeve_budget",
        candidate_rows=[],
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **kwargs: diag_calls.append(kwargs),
    )

    output = build_s7_order_stage_output(runtime)

    assert output.summary_fragment["portfolio_mode"] == "hard_sleeve_budget"
    assert captured["buy_symbols"] == ["sh600101", "sh600201", "sh600202"]
    assert captured["buy_sleeves"] == ["trend", "mr", "mr"]
    assert output.reason_counts["SLEEVE_BUDGET_EXCEEDED"] == 3
    assert {row["symbol"] for row in runtime.candidate_rows} == {"sh600102", "sh600103", "sh600203"}
    assert all(row["reject_reason"] == "SLEEVE_BUDGET_EXCEEDED" for row in runtime.candidate_rows)
    assert diag_calls[0]["debug_plan"]["sleeve_slot_caps"] == {"mr": 2, "trend": 3}
    assert diag_calls[0]["debug_plan"]["sleeve_available_slots"] == {"mr": 2, "trend": 1}


def test_order_planning_passthrough_for_non_multi_alpha_portfolio_mode(monkeypatch) -> None:
    buy_signals = [
        _signal("sh600301", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.55),
        _signal("sh600302", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.45),
    ]
    captured: dict[str, object] = {}

    def _fake_build_rebalance_orders(**kwargs):
        captured["buy_symbols"] = [str(sig.symbol).lower() for sig in kwargs["buy_signals"]]
        kwargs["debug_plan"]["reject_reason_counts"] = {"NO_CASH": 1}
        return []

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_rebalance_orders",
        _fake_build_rebalance_orders,
    )

    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[],
                buy_signals=buy_signals,
                exit_syms=set(),
                strength_map={},
                mf_score_map={},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            ),
            "next_open": {"sh600301": 10.0, "sh600302": 10.0},
            "nav": 100000.0,
            "holding_symbols": (),
        },
        request=_request_stub(),
        provider=SimpleNamespace(_feats=None, _mx=None, _sym_to_col={}),
        positions={},
        holding_sources={},
        cash=100000.0,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=3,
        _tilt_bottom_n=2,
        _min_trade_price=5.0,
        _portfolio_mode="equal_10",
        candidate_rows=[],
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **_kwargs: None,
    )

    output = build_s7_order_stage_output(runtime)

    assert captured["buy_symbols"] == ["sh600301", "sh600302"]
    assert output.reason_counts == {"NO_CASH": 1}
    assert runtime.candidate_rows == []


def test_order_planning_accumulates_reject_reason_counts_in_fast_mode(monkeypatch) -> None:
    buy_signals = [_signal("sh600303", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.55)]

    def _fake_build_rebalance_orders(**kwargs):
        kwargs["debug_plan"]["reject_reason_counts"] = {"SKIP_NO_CASH": 2, "SKIP_QTY_ZERO": 1}
        return []

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_rebalance_orders",
        _fake_build_rebalance_orders,
    )

    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[],
                buy_signals=buy_signals,
                exit_syms=set(),
                strength_map={},
                mf_score_map={},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            ),
            "next_open": {"sh600303": 10.0},
            "nav": 100000.0,
            "holding_symbols": (),
        },
        request=_request_stub(fast_mode=True),
        provider=SimpleNamespace(_feats=None, _mx=None, _sym_to_col={}),
        positions={},
        holding_sources={},
        cash=100000.0,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=3,
        _tilt_bottom_n=2,
        _min_trade_price=5.0,
        _portfolio_mode="equal_10",
        candidate_rows=[],
        order_reject_reason_counts={},
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **_kwargs: None,
    )

    output = build_s7_order_stage_output(runtime)

    assert output.reason_counts == {"SKIP_NO_CASH": 2, "SKIP_QTY_ZERO": 1}
    assert runtime.order_reject_reason_counts == {"SKIP_NO_CASH": 2, "SKIP_QTY_ZERO": 1}
    assert runtime.candidate_rows == []


def test_t_plus_one_order_only_persists_source_after_next_day_fill(monkeypatch) -> None:
    buy_signal = _signal("sh600401", sleeve_id="mr", alpha_id="rsi_reversal", compose_score=0.83)

    def _fake_build_rebalance_orders(**kwargs):
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        return [
            SimpleNamespace(
                side=Side.BUY,
                symbol="sh600401",
                qty=100,
                reason_code="MR_RSI_OVERSOLD_BUY",
                meta={
                    "entry_alpha_id": "rsi_reversal",
                    "entry_sleeve_id": "mr",
                    "entry_reason_code": "MR_RSI_OVERSOLD_BUY",
                },
            )
        ]

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_rebalance_orders",
        _fake_build_rebalance_orders,
    )

    next_day = date(2026, 3, 3)
    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[],
                buy_signals=[buy_signal],
                raw_alpha_signals=[buy_signal],
                composed_buy_signals=[buy_signal],
                exit_syms=set(),
                strength_map={"sh600401": 0.83},
                mf_score_map={"sh600401": 0.83},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={"composition_enabled": True},
            ),
            "next_open": {"sh600401": 12.0},
            "nav": 100000.0,
            "holding_symbols": (),
        },
        request=_request_stub(),
        provider=SimpleNamespace(
            _feats=None,
            _mx=None,
            _sym_to_col={},
            entry_day={},
            entry_day_overwrite=False,
            peak_state_on_buy={},
        ),
        positions={},
        position_avg_cost={},
        holding_sources={},
        cash=5000.0,
        open_idx={(next_day, "sh600401"): 12.0},
        close_idx={(next_day, "sh600401"): 12.1},
        _slip_bps=0.0,
        _comm_rate=0.0005,
        _comm_min=1.0,
        _stamp_rate=0.001,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=3,
        _tilt_bottom_n=2,
        _min_trade_price=5.0,
        _portfolio_mode="hard_sleeve_budget",
        _traded_value_today=0.0,
        trade_rows=[],
        candidate_rows=[],
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **_kwargs: None,
    )

    output = build_s7_order_stage_output(runtime)

    assert runtime.holding_sources == {}
    apply_open_fills(runtime, next_day, output.payload["next_day_orders"])
    assert runtime.holding_sources["sh600401"]["entry_alpha_id"] == "rsi_reversal"


def test_build_rebalance_orders_applies_mf_rank_tilt_scales() -> None:
    buy_signals = [
        _signal("sh600501", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.95),
        _signal("sh600502", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.85),
        _signal("sh600503", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.75),
        _signal("sh600504", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.65),
        _signal("sh600505", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.55),
    ]
    orders = build_rebalance_orders(
        positions={},
        cash_available=150000.0,
        nav_close=100000.0,
        max_positions=5,
        lot_size=100,
        sell_signals=[],
        buy_signals=buy_signals,
        next_open={str(sig.symbol).lower(): 10.0 for sig in buy_signals},
        enable_multifactor_rank=True,
        mf_topk=5,
        mf_concentrate_topn=0,
        mf_concentrate_scale=1.0,
        mf_gate_on_today=True,
        mf_score_map={
            "sh600501": 0.95,
            "sh600502": 0.85,
            "sh600503": 0.75,
            "sh600504": 0.65,
            "sh600505": 0.55,
        },
        weight_mode="mf_rank_tilt",
        min_positions=5,
        tilt_strength=0.15,
        tilt_top_n=2,
        tilt_bottom_n=1,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert [order.symbol for order in buy_orders] == [
        "sh600501",
        "sh600502",
        "sh600503",
        "sh600504",
        "sh600505",
    ]
    assert [round(float(order.order_value_scale), 2) for order in buy_orders] == [1.15, 1.15, 1.0, 1.0, 0.85]


def test_build_rebalance_orders_applies_score_weighted_scales() -> None:
    buy_signals = [
        _signal("sh600511", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.91),
        _signal("sh600512", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.81),
        _signal("sh600513", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.71),
    ]
    buy_signals[0].meta["final_score"] = 1.0
    buy_signals[1].meta["final_score"] = 0.5
    buy_signals[2].meta["final_score"] = 0.0

    orders = build_rebalance_orders(
        positions={},
        cash_available=120000.0,
        nav_close=90000.0,
        max_positions=3,
        lot_size=100,
        sell_signals=[],
        buy_signals=buy_signals,
        next_open={str(sig.symbol).lower(): 10.0 for sig in buy_signals},
        weight_mode="score_weighted",
        min_positions=3,
        score_weight_min_scale=0.75,
        score_weight_max_scale=1.25,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert [order.symbol for order in buy_orders] == ["sh600511", "sh600512", "sh600513"]
    assert [round(float(order.order_value_scale), 2) for order in buy_orders] == [1.25, 1.0, 0.75]
    assert [int(order.qty) for order in buy_orders] == [3700, 3000, 2200]


def test_build_rebalance_orders_skips_buy_when_entry_gap_exceeds_threshold() -> None:
    buy_signal = _signal("sh600601", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.82)
    candidate_audit: list[dict] = []
    debug_plan: dict[str, object] = {}

    orders = build_rebalance_orders(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=5,
        lot_size=100,
        sell_signals=[],
        buy_signals=[buy_signal],
        next_open={"sh600601": 10.5},
        decision_close_map={"sh600601": 10.0},
        enable_entry_gap_guard=True,
        entry_gap_guard_pct=0.04,
        decision_date=date(2026, 3, 2),
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
    )

    assert orders == []
    assert candidate_audit[0]["symbol"] == "sh600601"
    assert candidate_audit[0]["reject_reason"] == "SKIP_ENTRY_GAP_GUARD"
    assert debug_plan["reject_reason_counts"] == {"SKIP_ENTRY_GAP_GUARD": 1}


def test_build_rebalance_orders_cash_aware_candidate_planner_prefers_feasible_subset() -> None:
    buy_signals = [
        _signal("sh600701", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.95),
        _signal("sh600702", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.85),
        _signal("sh600703", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.75),
    ]
    candidate_audit: list[dict] = []
    debug_plan: dict[str, object] = {}

    orders = build_rebalance_orders(
        positions={},
        cash_available=56000.0,
        nav_close=90000.0,
        max_positions=3,
        lot_size=100,
        sell_signals=[],
        buy_signals=buy_signals,
        next_open={
            "sh600701": 290.0,
            "sh600702": 140.0,
            "sh600703": 140.0,
        },
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        min_positions=3,
        candidate_plan_mode="cash_aware",
        cash_aware_search_top_n=3,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert [order.symbol for order in buy_orders] == ["sh600702", "sh600703"]
    reject_rows = {str(row["symbol"]).lower(): str(row["reject_reason"]) for row in candidate_audit if not bool(row.get("selected"))}
    assert reject_rows["sh600701"] == "NOT_SELECTED_CASH_AWARE"
    assert debug_plan["candidate_plan_mode"] == "cash_aware"
    assert debug_plan["cash_aware_selected_symbols"] == ["sh600702", "sh600703"]


def test_build_rebalance_orders_rotation_replace_swaps_weakest_held_when_full() -> None:
    buy_signal = _signal("sh600803", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.97)
    candidate_audit: list[dict] = []
    debug_plan: dict[str, object] = {}

    orders = build_rebalance_orders(
        positions={"sh600801": 100, "sh600802": 100},
        cash_available=1000.0,
        nav_close=3000.0,
        max_positions=2,
        lot_size=100,
        sell_signals=[],
        buy_signals=[buy_signal],
        next_open={"sh600801": 10.0, "sh600802": 10.0, "sh600803": 10.0},
        enable_multifactor_rank=True,
        mf_gate_on_today=True,
        mf_topk=10,
        mf_score_map={
            "sh600801": 0.40,
            "sh600802": 0.60,
            "sh600803": 0.92,
        },
        strength_map={
            "sh600801": 0.40,
            "sh600802": 0.60,
            "sh600803": 0.92,
        },
        decision_date=date(2026, 3, 2),
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        strong_risk_on_today=True,
        rotation_replace_enabled=True,
        rotation_replace_only_strong_risk_on=True,
        rotation_replace_max_swaps_per_day=1,
        rotation_replace_candidate_top_n=3,
        rotation_replace_min_score_gap=0.15,
        holding_entry_dates={
            "sh600801": date(2026, 2, 20),
            "sh600802": date(2026, 2, 20),
        },
        min_positions=2,
        rotation_min_hold_days=5,
    )

    assert [(order.side, order.symbol, order.reason_code) for order in orders] == [
        (Side.SELL, "sh600801", "ROTATION_REPLACE"),
        (Side.BUY, "sh600803", "ENTRY"),
    ]
    assert float((orders[0].meta or {}).get("rotation_score_gap") or 0.0) == 0.52
    assert float((orders[1].meta or {}).get("rotation_candidate_score") or 0.0) == 0.92
    assert debug_plan["rotation_replace_count"] == 1
    assert debug_plan["rotation_replace_pairs"][0]["held_symbol"] == "sh600801"
    assert debug_plan["rotation_replace_pairs"][0]["candidate_symbol"] == "sh600803"


def test_build_rebalance_orders_industry_second_stage_tiebreak_only_reorders_equal_strength_candidates() -> None:
    sig_a = Signal(
        signal_date=date(2026, 3, 2),
        symbol="sh600901",
        side=Side.BUY,
        qty=100,
        reason="ENTRY",
        reason_code="ENTRY",
        meta={
            "residual_refine_mode": "industry_second_stage_tiebreak",
            "industry_second_stage_active": True,
            "industry_second_stage_score": 0.95,
        },
    )
    sig_b = Signal(
        signal_date=date(2026, 3, 2),
        symbol="sh600902",
        side=Side.BUY,
        qty=100,
        reason="ENTRY",
        reason_code="ENTRY",
        meta={
            "residual_refine_mode": "industry_second_stage_tiebreak",
            "industry_second_stage_active": True,
            "industry_second_stage_score": 0.55,
        },
    )

    orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_b, sig_a],
        next_open={"sh600901": 10.0, "sh600902": 10.0},
        enable_strength_rank=True,
        strength_map={"sh600901": 0.80, "sh600902": 0.80},
        min_positions=1,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert len(buy_orders) == 1
    assert buy_orders[0].symbol == "sh600901"
