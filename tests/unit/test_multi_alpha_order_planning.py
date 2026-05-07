from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters.fill_accounting import apply_open_fills
from backend.core.stage_pipeline.adapters.bridge_adapter import apply_s7_order_stage_side_effects
from backend.core.stage_pipeline.adapters.candidate_boundary import build_candidate_boundary_result
from backend.core.stage_pipeline.adapters.candidate_plan import build_candidate_plan_result
from backend.core.portfolio.candidate_plan import _allow_existing_holding_top_up, build_candidate_plan
from backend.core.portfolio.execution_orders import build_execution_orders_from_candidate_plan
from backend.core.portfolio.portfolio_runtime import build_rebalance_orders
from backend.core.stage_pipeline.adapters.order_planning import _build_action_intent_payloads, build_s7_order_stage_output


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


def _prepare_candidate_contracts(runtime: SimpleNamespace) -> tuple[dict[str, object], dict[str, object]]:
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
    return candidate_boundary, candidate_plan


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


def test_order_planning_requires_upstream_candidate_contracts() -> None:
    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[],
                buy_signals=[],
                exit_syms=set(),
                strength_map={},
                mf_score_map={},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            ),
            "next_open": {},
            "nav": 100000.0,
            "holding_symbols": tuple(),
        },
        request=_request_stub(),
        positions={},
        cash=100000.0,
    )

    with pytest.raises(RuntimeError, match="candidate_boundary must be prepared before order_planning"):
        build_s7_order_stage_output(runtime)


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

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        captured["buy_symbols"] = [str(item.get("symbol", "")).lower() for item in kwargs["planned_items"]]
        captured["buy_sleeves"] = [
            str((getattr(item.get("signal"), "meta", {}) or {}).get("sleeve_id", ""))
            for item in kwargs["planned_items"]
        ]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 0
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = []
        return []

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_execution_orders_from_candidate_plan",
        _fake_build_execution_orders_from_candidate_plan,
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
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)

    assert output.summary_fragment["portfolio_mode"] == "hard_sleeve_budget"
    assert captured["buy_symbols"] == ["sh600101", "sh600201", "sh600202"]
    assert captured["buy_sleeves"] == ["trend", "mr", "mr"]
    assert output.payload["candidate_boundary"]["reject_reason_counts"] == {"SLEEVE_BUDGET_EXCEEDED": 3}
    assert output.payload["candidate_boundary"]["contract_version"] == "candidate_boundary_v1"
    assert output.payload["candidate_boundary"]["notes"]["execution_boundary_role"] == "internal_only"
    assert output.payload["candidate_plan"]["contract_version"] == "candidate_plan_v1"
    assert output.payload["candidate_plan"]["plan_mode"] == "ranked"
    assert output.payload["candidate_plan"]["notes"]["execution_boundary_role"] == "internal_only"
    assert [item["symbol"] for item in output.payload["candidate_plan"]["planned_candidates"]] == [
        "sh600101",
        "sh600201",
        "sh600202",
    ]
    assert output.payload["candidate_boundary"]["boundary_mode"] == "hard_sleeve_budget"
    assert [item["symbol"] for item in output.payload["candidate_boundary"]["selected_candidates"]] == [
        "sh600101",
        "sh600201",
        "sh600202",
    ]
    assert [item["owner_system"] for item in output.payload["subsystem_budgets"]] == ["mr", "trend"]
    assert [item["owner_system"] for item in output.payload["action_intents"]] == ["mr", "trend"]
    assert output.payload["formal_execution_boundary"]["target_book"]["contract_version"] == "target_book_v1"
    assert output.payload["formal_execution_boundary"]["execution_audit"]["contract_version"] == "execution_audit_v1"
    assert "candidate_plan" not in output.payload["formal_execution_boundary"]
    assert output.reason_counts == {}
    assert runtime.candidate_rows == []
    assert diag_calls == []

    apply_s7_order_stage_side_effects(runtime, output)

    assert {row["symbol"] for row in runtime.candidate_rows} == {"sh600102", "sh600103", "sh600203"}
    assert all(row["reject_reason"] == "SLEEVE_BUDGET_EXCEEDED" for row in runtime.candidate_rows)
    assert all(row["decision_layer"] == "candidate_boundary" for row in runtime.candidate_rows)
    assert diag_calls[0]["debug_plan"]["sleeve_slot_caps"] == {"mr": 2, "trend": 3}
    assert diag_calls[0]["debug_plan"]["sleeve_available_slots"] == {"mr": 2, "trend": 1}
    assert diag_calls[0]["debug_plan"]["system_sleeve_id"] == "cn_stock_trend_alpha_core"
    assert diag_calls[0]["debug_plan"]["system_budget_owner"] == "global_portfolio_governor"
    assert diag_calls[0]["debug_plan"]["system_budget_semantics"] == "consume_governor_sleeve_budget"
    assert diag_calls[0]["debug_plan"]["system_sleeve_raw_ids"] == ["mr", "trend"]
    assert diag_calls[0]["debug_plan"]["system_sleeve_phase1_excluded_capabilities"] == [
        "value_bluechip_satellite",
        "cn_etf_beta",
        "insurance_overlay",
    ]


def test_candidate_plan_allows_etf_standalone_deploy_top_up_for_existing_holding() -> None:
    buy_signal = Signal(
        signal_date=date(2026, 3, 2),
        symbol="sh510300",
        side=Side.BUY,
        qty=1,
        reason="ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_ACTIVE",
        reason_code="ETF_BETA_TRANS_UP_INTER_REBALANCE_DEPLOY_ACTIVE",
        meta={
            "alpha_id": "cn_etf_beta",
            "alpha_source": "cn_etf_beta_selector",
            "sleeve_id": "cn_etf_beta",
            "owner_system": "cn_etf_beta",
            "strategy_role": "governed_broad_based_standalone_mainline",
            "execution_path": "trans_up_inter_rebalance_deploy",
            "target_weight_basis": "delta_deploy_gap",
            "target_weight": 0.35,
            "final_target_weight": 0.9,
            "compose_score": 1.0,
            "close": 5.0,
            "slow_ma": 4.0,
        },
    )

    result = build_candidate_plan(
        positions={"sh510300": 100000},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[buy_signal],
        next_open={"sh510300": 5.0},
        decision_date=date(2026, 3, 2),
        base_order_value=100000.0,
        weight_mode="equal",
        candidate_plan_mode="ranked",
    )

    planned_symbols = [str(item.get("symbol", "")).lower() for item in result["planned_items"]]
    assert planned_symbols == ["sh510300"]
    assert result["reject_reason_counts"].get("ALREADY_HELD", 0) == 0
    assert result["debug_plan"]["buy_candidates_count"] == 1


def test_order_planning_hard_sleeve_budget_uses_market_state_weight_override(monkeypatch) -> None:
    buy_signals = [
        _signal("sh600111", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.91),
        _signal("sh600112", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.81),
        _signal("sh600211", sleeve_id="mr", alpha_id="moneyflow_monthly", compose_score=0.88),
        _signal("sh600212", sleeve_id="mr", alpha_id="moneyflow_monthly", compose_score=0.78),
        _signal("sh600213", sleeve_id="mr", alpha_id="moneyflow_monthly", compose_score=0.68),
    ]
    captured: dict[str, object] = {}

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        captured["buy_symbols"] = [str(item.get("symbol", "")).lower() for item in kwargs["planned_items"]]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 0
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = []
        return []

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_execution_orders_from_candidate_plan",
        _fake_build_execution_orders_from_candidate_plan,
    )

    diag_calls: list[dict[str, object]] = []
    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 5, "risk_on_today": False},
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
                diagnostics={"composition_enabled": True, "market_state": "BEAR"},
            ),
            "next_open": {str(sig.symbol).lower(): 10.0 for sig in buy_signals},
            "nav": 100000.0,
            "holding_symbols": (),
        },
        request=_request_stub(),
        provider=SimpleNamespace(
            _feats=None,
            _mx=None,
            _sym_to_col={},
            _same_symbol_policy="PREFER_HIGHER_SCORE",
            _market_state_name_map={date(2026, 3, 2): "BEAR"},
            _multi_alpha={
                "signal_composition": {
                    "modules": [
                        {"name": "breakout_55", "weight": 0.5},
                        {"name": "moneyflow_monthly", "weight": 0.5},
                    ],
                    "market_state_weight_overrides": {
                        "BEAR": {"trend": 0.2, "mr": 0.8}
                    },
                }
            },
            _module_specs={
                "breakout_55": SimpleNamespace(sleeve_id="trend"),
                "moneyflow_monthly": SimpleNamespace(sleeve_id="mr"),
            },
        ),
        positions={},
        holding_sources={},
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
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)

    assert output.summary_fragment["portfolio_mode"] == "hard_sleeve_budget"
    assert captured["buy_symbols"] == ["sh600111", "sh600211", "sh600212", "sh600213"]
    assert output.reason_counts == {}
    assert diag_calls == []

    apply_s7_order_stage_side_effects(runtime, output)

    assert diag_calls[0]["debug_plan"]["market_state_weight_override_key"] == "BEAR"
    assert diag_calls[0]["debug_plan"]["sleeve_weights_effective"] == {"mr": 0.8, "trend": 0.2}
    assert diag_calls[0]["debug_plan"]["sleeve_slot_caps"] == {"mr": 4, "trend": 1}
    assert diag_calls[0]["debug_plan"]["system_sleeve_id"] == "cn_stock_trend_alpha_core"


def test_order_planning_passthrough_for_non_multi_alpha_portfolio_mode(monkeypatch) -> None:
    buy_signals = [
        _signal("sh600301", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.55),
        _signal("sh600302", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.45),
    ]
    captured: dict[str, object] = {}

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        captured["buy_symbols"] = [str(item.get("symbol", "")).lower() for item in kwargs["planned_items"]]
        kwargs["debug_plan"]["reject_reason_counts"] = {"NO_CASH": 1}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {"NO_CASH": 1}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 1
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = []
        return []

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
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)

    assert captured["buy_symbols"] == ["sh600301", "sh600302"]
    assert output.reason_counts == {"NO_CASH": 1}
    assert runtime.candidate_rows == []
    assert output.payload["candidate_boundary"]["contract_version"] == "candidate_boundary_v1"
    assert output.payload["candidate_boundary"]["boundary_mode"] == "equal_10"


def test_order_planning_accumulates_reject_reason_counts_in_fast_mode(monkeypatch) -> None:
    buy_signals = [_signal("sh600303", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.55)]

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        kwargs["candidate_audit"].extend(
            [
                {
                    "date": "2026-03-02",
                    "symbol": "sh600303",
                    "selected": False,
                    "reject_reason": "SKIP_NO_CASH",
                    "cash_blocked_flag": True,
                    "cash_available": 5000.0,
                    "estimated_qty": 100,
                    "estimated_amount": 10000.0,
                    "estimated_price": 100.0,
                },
                {
                    "date": "2026-03-02",
                    "symbol": "sh600304",
                    "selected": False,
                    "reject_reason": "SKIP_QTY_ZERO",
                    "cash_blocked_flag": False,
                },
            ]
        )
        kwargs["debug_plan"]["reject_reason_counts"] = {"SKIP_NO_CASH": 2, "SKIP_QTY_ZERO": 1}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {"SKIP_NO_CASH": 2, "SKIP_QTY_ZERO": 1}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 3
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = []
        return []

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
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)

    assert output.reason_counts == {"SKIP_NO_CASH": 2, "SKIP_QTY_ZERO": 1}
    assert runtime.order_reject_reason_counts == {}
    assert runtime.candidate_rows == []

    apply_s7_order_stage_side_effects(runtime, output)

    assert runtime.order_reject_reason_counts == {"SKIP_NO_CASH": 2, "SKIP_QTY_ZERO": 1}
    assert runtime.candidate_rows == [
        {
            "date": "2026-03-02",
            "symbol": "sh600303",
            "selected": False,
            "reject_reason": "SKIP_NO_CASH",
            "cash_blocked_flag": True,
            "cash_available": 5000.0,
            "estimated_qty": 100,
            "estimated_amount": 10000.0,
            "estimated_price": 100.0,
        }
    ]


def test_order_planning_forwards_base_order_value_to_execution_kernel(monkeypatch) -> None:
    buy_signals = [_signal("sh600305", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.91)]
    captured: dict[str, object] = {}

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        captured["base_order_value"] = kwargs["base_order_value"]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 0
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = []
        return []

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
                buy_signals=buy_signals,
                exit_syms=set(),
                strength_map={},
                mf_score_map={},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            ),
            "next_open": {"sh600305": 50.0},
            "nav": 100000.0,
            "holding_symbols": (),
        },
        request=SimpleNamespace(**vars(_request_stub()), base_order_value=15000.0),
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
    _prepare_candidate_contracts(runtime)

    build_s7_order_stage_output(runtime)

    assert captured["base_order_value"] == pytest.approx(15000.0)


def test_order_planning_does_not_use_provider_derived_base_order_value(monkeypatch) -> None:
    buy_signals = [_signal("sh600306", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.88)]
    captured: dict[str, object] = {}

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        captured["base_order_value"] = kwargs["base_order_value"]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 0
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = []
        return []

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_execution_orders_from_candidate_plan",
        _fake_build_execution_orders_from_candidate_plan,
    )

    def _provider_base_order_value(*_args, **_kwargs):
        raise AssertionError("order_planning should not call provider-derived base_order_value")

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
            "next_open": {"sh600306": 50.0},
            "nav": 100000.0,
            "holding_symbols": (),
        },
        request=SimpleNamespace(**vars(_request_stub()), base_order_value=0.0),
        provider=SimpleNamespace(_feats=None, _mx=None, _sym_to_col={}),
        positions={},
        holding_sources={},
        cash=100000.0,
        _weight_mode="equal",
        _min_positions_cfg=10,
        _tilt_strength=0.0,
        _tilt_top_n=3,
        _tilt_bottom_n=2,
        _min_trade_price=5.0,
        _portfolio_mode="equal_10",
        candidate_rows=[],
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **_kwargs: None,
        _provider_base_order_value=_provider_base_order_value,
    )
    _prepare_candidate_contracts(runtime)

    build_s7_order_stage_output(runtime)

    assert captured["base_order_value"] == pytest.approx(0.0)


def test_t_plus_one_order_only_persists_source_after_next_day_fill(monkeypatch) -> None:
    buy_signal = _signal("sh600401", sleeve_id="mr", alpha_id="rsi_reversal", compose_score=0.83)

    def _fake_build_execution_orders_from_candidate_plan(**kwargs):
        planned_item = kwargs["planned_items"][0]
        kwargs["debug_plan"]["reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_reason_counts"] = {}
        kwargs["debug_plan"]["execution_kernel_reject_count"] = 0
        kwargs["debug_plan"]["execution_kernel_selected_symbols"] = ["sh600401"]
        return [
            SimpleNamespace(
                side=Side.BUY,
                symbol="sh600401",
                qty=100,
                reason_code="MR_RSI_OVERSOLD_BUY",
                meta=dict(getattr(planned_item.get("signal"), "meta", {}) or {}),
            )
        ]

    monkeypatch.setattr(
        "backend.core.stage_pipeline.adapters.order_planning.build_execution_orders_from_candidate_plan",
        _fake_build_execution_orders_from_candidate_plan,
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
            "next_trading_day": next_day,
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
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)

    assert runtime.holding_sources == {}
    target_book = output.payload["target_book"]
    assert target_book["contract_version"] == "target_book_v1"
    assert target_book["decision_date"] == "2026-03-02"
    assert target_book["execution_date"] == "2026-03-03"
    assert target_book["targets"] == [
        {
            "symbol": "sh600401",
            "target_weight": pytest.approx(0.012),
            "owner_system": "mr",
            "reason_codes": ["MR_RSI_OVERSOLD_BUY"],
            "priority": 1,
        }
    ]
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


def test_build_rebalance_orders_records_cash_blocked_candidate_details() -> None:
    buy_signal = _signal("sh600611", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.82)
    candidate_audit: list[dict] = []
    debug_plan: dict[str, object] = {}

    orders = build_rebalance_orders(
        positions={},
        cash_available=5000.0,
        nav_close=100000.0,
        max_positions=5,
        lot_size=100,
        sell_signals=[],
        buy_signals=[buy_signal],
        next_open={"sh600611": 100.0},
        decision_date=date(2026, 3, 2),
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        base_order_value=10000.0,
    )

    assert orders == []
    cash_blocked_row = next(row for row in candidate_audit if row["symbol"] == "sh600611")
    assert cash_blocked_row["reject_reason"] == "SKIP_NO_CASH"
    assert cash_blocked_row["cash_blocked_flag"] is True
    assert cash_blocked_row["cash_blocked_reason"] == "SKIP_NO_CASH"
    assert cash_blocked_row["cash_available"] == 5000.0
    assert cash_blocked_row["estimated_qty"] == 100
    assert cash_blocked_row["estimated_amount"] == 10000.0
    assert cash_blocked_row["estimated_price"] == 100.0
    assert debug_plan["reject_reason_counts"] == {"SKIP_NO_CASH": 1}


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


def test_build_rebalance_orders_moneyflow_overlay_tiebreak_reorders_equal_baseline_scores() -> None:
    sig_a = _signal("sh601001", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.50)
    sig_b = _signal("sh601002", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.50)

    orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b],
        next_open={"sh601001": 10.0, "sh601002": 10.0},
        enable_multifactor_rank=True,
        mf_topk=1,
        mf_gate_on_today=True,
        mf_score_map={"sh601001": 0.60, "sh601002": 0.60},
        overlay_mode="tiebreak",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601001": 0.20, "sh601002": 0.90},
        decision_date=date(2026, 3, 2),
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert len(buy_orders) == 1
    assert buy_orders[0].symbol == "sh601002"


def test_build_rebalance_orders_moneyflow_overlay_bull_only_tiebreak_only_reorders_inside_bull() -> None:
    sig_a = _signal("sh601031", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.50)
    sig_b = _signal("sh601032", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.50)

    bull_debug_plan: dict[str, object] = {}
    bull_orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b],
        next_open={"sh601031": 10.0, "sh601032": 10.0},
        enable_multifactor_rank=True,
        mf_topk=1,
        mf_gate_on_today=True,
        mf_score_map={"sh601031": 0.60, "sh601032": 0.60},
        overlay_mode="bull_only_tiebreak",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601031": 0.20, "sh601032": 0.90},
        market_state_today="BULL",
        debug_plan=bull_debug_plan,
        decision_date=date(2026, 3, 2),
    )
    bull_buy_orders = [order for order in bull_orders if order.side == Side.BUY]
    assert len(bull_buy_orders) == 1
    assert bull_buy_orders[0].symbol == "sh601032"
    assert bull_debug_plan["moneyflow_overlay_mode"] == "bull_only_tiebreak"
    assert bull_debug_plan["moneyflow_overlay_gate_on"] is True
    assert bull_debug_plan["moneyflow_overlay_bull_only"] is True
    assert bull_debug_plan["moneyflow_overlay_bull_gate_on"] is True
    assert bull_debug_plan["moneyflow_overlay_bull_suppressed"] is False

    non_bull_debug_plan: dict[str, object] = {}
    non_bull_orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b],
        next_open={"sh601031": 10.0, "sh601032": 10.0},
        enable_multifactor_rank=True,
        mf_topk=1,
        mf_gate_on_today=True,
        mf_score_map={"sh601031": 0.60, "sh601032": 0.60},
        overlay_mode="bull_only_tiebreak",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601031": 0.20, "sh601032": 0.90},
        market_state_today="TRANS_UP",
        debug_plan=non_bull_debug_plan,
        decision_date=date(2026, 3, 2),
    )
    non_bull_buy_orders = [order for order in non_bull_orders if order.side == Side.BUY]
    assert len(non_bull_buy_orders) == 1
    assert non_bull_buy_orders[0].symbol == "sh601031"
    assert non_bull_debug_plan["moneyflow_overlay_gate_on"] is False
    assert non_bull_debug_plan["moneyflow_overlay_bull_only"] is True
    assert non_bull_debug_plan["moneyflow_overlay_bull_gate_on"] is False
    assert non_bull_debug_plan["moneyflow_overlay_bull_suppressed"] is True


def test_build_rebalance_orders_moneyflow_overlay_soft_weight_uses_overlay_score_without_reordering() -> None:
    sig_a = _signal("sh601011", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.90)
    sig_b = _signal("sh601012", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.80)
    sig_c = _signal("sh601013", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.70)

    orders = build_rebalance_orders(
        positions={},
        cash_available=120000.0,
        nav_close=90000.0,
        max_positions=3,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b, sig_c],
        next_open={"sh601011": 10.0, "sh601012": 10.0, "sh601013": 10.0},
        enable_multifactor_rank=True,
        mf_topk=3,
        mf_gate_on_today=True,
        mf_concentrate_topn=0,
        mf_concentrate_scale=1.0,
        mf_score_map={"sh601011": 0.90, "sh601012": 0.80, "sh601013": 0.70},
        overlay_mode="soft_weight",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601011": 0.0, "sh601012": 0.5, "sh601013": 1.0},
        weight_mode="score_weighted",
        score_weight_min_scale=0.9,
        score_weight_max_scale=1.1,
        min_positions=3,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert [order.symbol for order in buy_orders] == ["sh601011", "sh601012", "sh601013"]
    assert [round(float(order.order_value_scale), 2) for order in buy_orders] == [0.9, 1.0, 1.1]


def test_build_rebalance_orders_moneyflow_overlay_band_rerank_reorders_inside_candidate_band() -> None:
    sig_a = _signal("sh601041", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.90)
    sig_b = _signal("sh601042", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.80)
    sig_c = _signal("sh601043", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.70)
    sig_d = _signal("sh601044", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.60)
    candidate_audit: list[dict[str, object]] = []
    debug_plan: dict[str, object] = {}

    orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=2,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b, sig_c, sig_d],
        next_open={"sh601041": 10.0, "sh601042": 10.0, "sh601043": 10.0, "sh601044": 10.0},
        enable_multifactor_rank=True,
        mf_topk=2,
        mf_gate_on_today=True,
        mf_score_map={"sh601041": 0.90, "sh601042": 0.80, "sh601043": 0.70, "sh601044": 0.60},
        overlay_mode="band_rerank",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601041": 0.10, "sh601042": 0.20, "sh601043": 0.95, "sh601044": 0.99},
        overlay_band_limit=3,
        decision_date=date(2026, 3, 2),
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        min_positions=0,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert [order.symbol for order in buy_orders] == ["sh601043", "sh601042"]
    by_symbol = {str(row.get("symbol")).lower(): row for row in candidate_audit}
    assert by_symbol["sh601043"]["mf_rank"] == 3
    assert by_symbol["sh601043"]["final_score_rank"] == 1
    assert by_symbol["sh601044"]["final_score_rank"] == 4
    assert debug_plan["moneyflow_overlay_mode"] == "band_rerank"
    assert debug_plan["moneyflow_overlay_band_limit"] == 3
    assert debug_plan["moneyflow_overlay_rerank_count"] > 0


def test_build_rebalance_orders_moneyflow_overlay_bull_only_band_rerank_only_reorders_inside_bull() -> None:
    sig_a = _signal("sh601051", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.90)
    sig_b = _signal("sh601052", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.80)
    sig_c = _signal("sh601053", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.70)

    bull_debug_plan: dict[str, object] = {}
    bull_orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b, sig_c],
        next_open={"sh601051": 10.0, "sh601052": 10.0, "sh601053": 10.0},
        enable_multifactor_rank=True,
        mf_topk=1,
        mf_gate_on_today=True,
        mf_score_map={"sh601051": 0.90, "sh601052": 0.80, "sh601053": 0.70},
        overlay_mode="bull_only_band_rerank",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601051": 0.10, "sh601052": 0.20, "sh601053": 0.95},
        overlay_band_limit=3,
        market_state_today="BULL",
        debug_plan=bull_debug_plan,
        decision_date=date(2026, 3, 2),
    )
    bull_buy_orders = [order for order in bull_orders if order.side == Side.BUY]
    assert len(bull_buy_orders) == 1
    assert bull_buy_orders[0].symbol == "sh601053"
    assert bull_debug_plan["moneyflow_overlay_mode"] == "bull_only_band_rerank"
    assert bull_debug_plan["moneyflow_overlay_state_gate_mode"] == "bull_only"
    assert bull_debug_plan["moneyflow_overlay_gate_on"] is True
    assert bull_debug_plan["moneyflow_overlay_bull_only"] is True
    assert bull_debug_plan["moneyflow_overlay_bull_gate_on"] is True
    assert bull_debug_plan["moneyflow_overlay_rerank_count"] > 0

    non_bull_debug_plan: dict[str, object] = {}
    non_bull_candidate_audit: list[dict[str, object]] = []
    for sig in (sig_a, sig_b, sig_c):
        sig.meta["moneyflow_overlay_gate_on"] = True
        sig.meta["moneyflow_overlay_mode"] = "bull_only_band_rerank"
    non_bull_orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b, sig_c],
        next_open={"sh601051": 10.0, "sh601052": 10.0, "sh601053": 10.0},
        enable_multifactor_rank=True,
        mf_topk=1,
        mf_gate_on_today=True,
        mf_score_map={"sh601051": 0.90, "sh601052": 0.80, "sh601053": 0.70},
        overlay_mode="bull_only_band_rerank",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601051": 0.10, "sh601052": 0.20, "sh601053": 0.95},
        overlay_band_limit=3,
        market_state_today="TRANS_UP",
        debug_plan=non_bull_debug_plan,
        candidate_audit=non_bull_candidate_audit,
        decision_date=date(2026, 3, 2),
    )
    non_bull_buy_orders = [order for order in non_bull_orders if order.side == Side.BUY]
    assert len(non_bull_buy_orders) == 1
    assert non_bull_buy_orders[0].symbol == "sh601051"
    assert non_bull_buy_orders[0].meta["moneyflow_overlay_gate_on"] is False
    assert non_bull_buy_orders[0].meta["moneyflow_overlay_mode"] == "bull_only_band_rerank"
    assert {row["overlay_gate_on"] for row in non_bull_candidate_audit} == {False}
    assert non_bull_debug_plan["moneyflow_overlay_gate_on"] is False
    assert non_bull_debug_plan["moneyflow_overlay_state_gate_mode"] == "bull_only"
    assert non_bull_debug_plan["moneyflow_overlay_state_gate_on"] is False
    assert non_bull_debug_plan["moneyflow_overlay_bull_only"] is True


def test_build_rebalance_orders_moneyflow_overlay_bull_trans_up_band_rerank_reorders_inside_trans_up() -> None:
    sig_a = _signal("sh601061", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.90)
    sig_b = _signal("sh601062", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.80)
    sig_c = _signal("sh601063", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.70)

    debug_plan: dict[str, object] = {}
    orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b, sig_c],
        next_open={"sh601061": 10.0, "sh601062": 10.0, "sh601063": 10.0},
        enable_multifactor_rank=True,
        mf_topk=1,
        mf_gate_on_today=True,
        mf_score_map={"sh601061": 0.90, "sh601062": 0.80, "sh601063": 0.70},
        overlay_mode="bull_trans_up_band_rerank",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601061": 0.10, "sh601062": 0.20, "sh601063": 0.95},
        overlay_band_limit=3,
        market_state_today="TRANS_UP",
        debug_plan=debug_plan,
        decision_date=date(2026, 3, 2),
    )
    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert len(buy_orders) == 1
    assert buy_orders[0].symbol == "sh601063"
    assert debug_plan["moneyflow_overlay_mode"] == "bull_trans_up_band_rerank"
    assert debug_plan["moneyflow_overlay_state_gate_mode"] == "bull_trans_up"
    assert debug_plan["moneyflow_overlay_state_gate_on"] is True
    assert debug_plan["moneyflow_overlay_bull_trans_up"] is True
    assert debug_plan["moneyflow_overlay_bull_trans_up_gate_on"] is True


def test_stage_candidate_plan_uses_market_state_5_for_moneyflow_overlay_state_gate() -> None:
    sig_a = _signal("sh601071", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.90)
    sig_b = _signal("sh601072", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.80)
    sig_c = _signal("sh601073", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.70)
    runtime = SimpleNamespace(
        request=SimpleNamespace(
            enable_multifactor_rank=True,
            mf_rank_gate_mode="ALWAYS_ON",
            lot_size=100,
            enable_strength_rank=False,
            strength_ma=120,
            mf_topk=1,
            mf_concentrate_topn=3,
            mf_concentrate_scale=1.5,
            momentum_top_pct=0.0,
            base_order_value=0.0,
            strategy=SimpleNamespace(enable_entry_gap_guard=False, entry_gap_guard_pct=0.0, min_hold_days=0),
        ),
        positions={},
        cash=20_000.0,
        close_idx={},
        holding_sources={},
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=0,
        _tilt_bottom_n=0,
        _candidate_plan_atr_close_map={},
        _min_trade_price=0.0,
        _sizing_cfg=SimpleNamespace(
            score_weight_min_scale=0.75,
            score_weight_max_scale=1.25,
            candidate_plan_mode="ranked",
            cash_aware_search_top_n=12,
            rotation_replace_enabled=False,
            rotation_replace_only_strong_risk_on=True,
            rotation_replace_max_swaps_per_day=1,
            rotation_replace_candidate_top_n=3,
            rotation_replace_min_score_gap=0.15,
        ),
    )
    day_signals = DaySignals(
        sell_signals=[],
        buy_signals=[sig_a, sig_b, sig_c],
        mf_score_map={"sh601071": 0.90, "sh601072": 0.80, "sh601073": 0.70},
        overlay_mode="bull_only_band_rerank",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601071": 0.10, "sh601072": 0.20, "sh601073": 0.95},
        overlay_band_limit=3,
    )
    common_kwargs = {
        "runtime": runtime,
        "day": date(2026, 3, 2),
        "day_signals": day_signals,
        "candidate_boundary": {"buy_signals": [sig_a, sig_b, sig_c]},
        "next_open": {"sh601071": 10.0, "sh601072": 10.0, "sh601073": 10.0},
        "nav": 20_000.0,
    }

    bull_plan = build_candidate_plan_result(
        controls={"effective_max_positions": 1, "risk_on_today": True, "market_state": "", "market_state_5": "BULL"},
        **common_kwargs,
    )
    trans_up_plan = build_candidate_plan_result(
        controls={"effective_max_positions": 1, "risk_on_today": True, "market_state": "", "market_state_5": "TRANS_UP"},
        **common_kwargs,
    )

    assert bull_plan["debug_plan"]["moneyflow_overlay_gate_on"] is True
    assert [item["symbol"] for item in bull_plan["planned_items"]][:1] == ["sh601073"]
    assert trans_up_plan["debug_plan"]["moneyflow_overlay_gate_on"] is False
    assert [item["symbol"] for item in trans_up_plan["planned_items"]][:1] == ["sh601071"]


def test_build_rebalance_orders_moneyflow_overlay_veto_bottom50_rejects_low_overlay_bucket() -> None:
    sig_a = _signal("sh601021", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.90)
    sig_b = _signal("sh601022", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.80)
    candidate_audit: list[dict[str, object]] = []
    debug_plan: dict[str, object] = {}

    orders = build_rebalance_orders(
        positions={},
        cash_available=20_000.0,
        nav_close=20_000.0,
        max_positions=2,
        lot_size=100,
        sell_signals=[],
        buy_signals=[sig_a, sig_b],
        next_open={"sh601021": 10.0, "sh601022": 10.0},
        enable_multifactor_rank=True,
        mf_topk=2,
        mf_gate_on_today=True,
        mf_score_map={"sh601021": 0.90, "sh601022": 0.80},
        overlay_mode="veto_bottom50",
        overlay_gate_on_today=True,
        overlay_score_map={"sh601021": 0.90, "sh601022": 0.10},
        decision_date=date(2026, 3, 2),
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        min_positions=0,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert [order.symbol for order in buy_orders] == ["sh601021"]
    by_symbol = {str(row.get("symbol")).lower(): row for row in candidate_audit}
    assert by_symbol["sh601022"]["reject_reason"] == "MONEYFLOW_OVERLAY_VETO"
    assert debug_plan["moneyflow_overlay_mode"] == "veto_bottom50"
    assert debug_plan["moneyflow_overlay_gate_on"] is True
    assert debug_plan["moneyflow_overlay_veto_count"] == 1
    assert debug_plan["moneyflow_overlay_veto_bottom_pct"] == 0.5


def test_build_rebalance_orders_respects_signal_meta_order_value_scale() -> None:
    buy_signal = _signal("sh601101", sleeve_id="etf", alpha_id="cn_etf_beta", compose_score=0.9)
    buy_signal.meta["order_value_scale"] = 0.4

    orders = build_rebalance_orders(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        buy_signals=[buy_signal],
        next_open={"sh601101": 10.0},
        min_positions=1,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert len(buy_orders) == 1
    assert round(float(buy_orders[0].order_value_scale), 2) == 0.4
    assert int(buy_orders[0].qty) == 4000


def test_build_rebalance_orders_rejects_out_of_range_target_weight_contract() -> None:
    buy_signal = _signal("sh510300", sleeve_id="cn_etf_beta", alpha_id="cn_etf_beta", compose_score=0.9)
    buy_signal.meta["target_weight"] = 1.8

    with pytest.raises(ValueError, match="target_weight must be <= 1.0"):
        build_rebalance_orders(
            positions={},
            cash_available=100000.0,
            nav_close=100000.0,
            max_positions=1,
            lot_size=100,
            sell_signals=[],
            buy_signals=[buy_signal],
            next_open={"sh510300": 10.0},
            min_positions=1,
        )


def test_allow_existing_holding_top_up_accepts_trans_up_confirmed_scale_up_contract() -> None:
    assert _allow_existing_holding_top_up(
        {
            "trans_up_recovery_confirmed_scale_up_active": True,
            "sleeve_id": "trend",
            "alpha_id": "breakout_55",
        }
    ) is True


def test_build_rebalance_orders_ignores_legacy_etf_private_target_fields_without_target_weight() -> None:
    buy_signal = _signal("sh510300", sleeve_id="cn_etf_beta", alpha_id="cn_etf_beta", compose_score=0.9)
    buy_signal.meta.update(
        {
            "target_exposure": 0.6,
            "requested_budget": 0.6,
            "applied_budget": 0.6,
            "target_exposure_per_symbol": 0.6,
        }
    )

    orders = build_rebalance_orders(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=5,
        lot_size=100,
        sell_signals=[],
        buy_signals=[buy_signal],
        next_open={"sh510300": 10.0},
        min_positions=0,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert len(buy_orders) == 1
    assert int(buy_orders[0].qty) == 2000


def test_build_execution_orders_from_candidate_plan_recomputes_formal_sizing() -> None:
    buy_signal = _signal("sh600001", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.9)
    planned_items = [
        {
            "symbol": "sh600001",
            "signal": buy_signal,
            "price": 10.0,
            "candidate_qty": 1000,
            "candidate_cost": 10000.0,
            "target_amount_scaled": 10000.0,
            "order_value_scale": 1.0,
            "selected": False,
            "selected_rank": None,
            "reject_reason": "",
            "pre_reject_reason": "",
        }
    ]

    orders = build_execution_orders_from_candidate_plan(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=2,
        lot_size=100,
        sell_signals=[],
        planned_items=planned_items,
        next_open={"sh600001": 10.0},
        min_positions=0,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert len(buy_orders) == 1
    assert int(buy_orders[0].qty) == 5000
    assert float((buy_orders[0].meta or {}).get("target_weight")) == pytest.approx(0.5)


def test_build_action_intent_payloads_nets_same_symbol_dual_side_to_single_delta() -> None:
    buy_signal = _signal("sh510300", sleeve_id="cn_etf_beta", alpha_id="cn_etf_beta", compose_score=0.9)
    buy_signal.meta["owner_system"] = "cn_etf_beta"
    sell_signal = Signal(
        signal_date=date(2026, 3, 2),
        symbol="sh510300",
        side=Side.SELL,
        qty=100,
        reason="EXIT",
        reason_code="EXIT",
        meta={
            "alpha_id": "cn_etf_beta",
            "sleeve_id": "cn_etf_beta",
            "owner_system": "cn_etf_beta",
        },
    )
    payloads = _build_action_intent_payloads(
        day=date(2026, 3, 2),
        planned_items=[
            {
                "symbol": "sh510300",
                "signal": buy_signal,
                "price": 10.0,
                "target_amount_scaled": 3000.0,
            }
        ],
        sell_signals=[sell_signal],
        positions={"sh510300": 200},
        nav_close=100000.0,
        subsystem_budgets=[{"owner_system": "cn_etf_beta", "budget_value": 0.5}],
        default_owner_system="cn_etf_beta",
    )

    assert len(payloads) == 1
    assert payloads[0]["owner_system"] == "cn_etf_beta"
    assert len(payloads[0]["actions"]) == 1
    assert payloads[0]["actions"][0]["symbol"] == "sh510300"
    assert payloads[0]["actions"][0]["side"] == "BUY"
    assert payloads[0]["actions"][0]["suggested_size_value"] == pytest.approx(0.02)
    assert payloads[0]["actions"][0]["notes"]["netted_from_dual_side"] is True


def test_build_execution_orders_from_candidate_plan_clips_buy_to_affordable_lot_under_fill_cost() -> None:
    buy_signal = _signal("sh600001", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.9)
    buy_signal.meta["target_weight"] = 1.0
    planned_items = [
        {
            "symbol": "sh600001",
            "signal": buy_signal,
            "price": 10.0,
            "candidate_qty": 10000,
            "candidate_cost": 100000.0,
            "target_amount_scaled": 100000.0,
            "order_value_scale": 1.0,
            "selected": False,
            "selected_rank": None,
            "reject_reason": "",
            "pre_reject_reason": "",
        }
    ]

    orders = build_execution_orders_from_candidate_plan(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        planned_items=planned_items,
        next_open={"sh600001": 10.0},
        slip_bps=0.01,
        comm_rate=0.001,
        comm_min=5.0,
        min_positions=0,
    )

    buy_orders = [order for order in orders if order.side == Side.BUY]
    assert len(buy_orders) == 1
    assert int(buy_orders[0].qty) == 9800
    assert float((buy_orders[0].meta or {}).get("target_weight")) == pytest.approx(0.98)
    assert float((buy_orders[0].meta or {}).get("order_net_cost")) <= 100000.0


def test_build_execution_orders_from_candidate_plan_rejects_buy_when_affordable_qty_below_lot() -> None:
    buy_signal = _signal("sh600001", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.9)
    buy_signal.meta["target_weight"] = 0.2
    planned_items = [
        {
            "symbol": "sh600001",
            "signal": buy_signal,
            "price": 10.0,
            "candidate_qty": 2000,
            "candidate_cost": 20000.0,
            "target_amount_scaled": 20000.0,
            "order_value_scale": 1.0,
            "selected": False,
            "selected_rank": None,
            "reject_reason": "",
            "pre_reject_reason": "",
        }
    ]
    debug_plan: dict[str, object] = {}
    candidate_audit: list[dict[str, object]] = []

    orders = build_execution_orders_from_candidate_plan(
        positions={},
        cash_available=900.0,
        nav_close=100000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        planned_items=planned_items,
        next_open={"sh600001": 10.0},
        slip_bps=0.01,
        comm_rate=0.001,
        comm_min=5.0,
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        min_positions=0,
    )

    assert orders == []
    assert debug_plan["reject_reason_counts"] == {"SKIP_NO_CASH": 1}
    assert candidate_audit[0]["reject_reason"] == "SKIP_NO_CASH"


def test_build_execution_orders_from_candidate_plan_rejects_explicit_zero_target_weight_contract() -> None:
    buy_signal = _signal("sh511010", sleeve_id="cn_etf_beta", alpha_id="cn_etf_beta", compose_score=0.9)
    buy_signal.meta["target_weight"] = 0.0
    buy_signal.meta["final_target_weight"] = 0.0
    planned_items = [
        {
            "symbol": "sh511010",
            "signal": buy_signal,
            "price": 3.0,
            "candidate_qty": 3300,
            "candidate_cost": 9900.0,
            "target_amount_scaled": 9900.0,
            "order_value_scale": 1.0,
            "selected": False,
            "selected_rank": None,
            "reject_reason": "",
            "pre_reject_reason": "",
        }
    ]
    debug_plan: dict[str, object] = {}
    candidate_audit: list[dict[str, object]] = []

    orders = build_execution_orders_from_candidate_plan(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=2,
        lot_size=100,
        sell_signals=[],
        planned_items=planned_items,
        next_open={"sh511010": 3.0},
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        min_positions=0,
    )

    assert orders == []
    assert debug_plan["reject_reason_counts"] == {"SKIP_QTY_ZERO": 1}
    assert candidate_audit[0]["reject_reason"] == "SKIP_QTY_ZERO"


def test_a_share_buy_affordability_smoke_fills_after_planning_clip() -> None:
    buy_signal = _signal("sh600001", sleeve_id="trend", alpha_id="breakout_55", compose_score=0.9)
    buy_signal.meta["target_weight"] = 1.0
    planned_items = [
        {
            "symbol": "sh600001",
            "signal": buy_signal,
            "price": 10.0,
            "candidate_qty": 10000,
            "candidate_cost": 100000.0,
            "target_amount_scaled": 100000.0,
            "order_value_scale": 1.0,
            "selected": False,
            "selected_rank": None,
            "reject_reason": "",
            "pre_reject_reason": "",
        }
    ]

    orders = build_execution_orders_from_candidate_plan(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[],
        planned_items=planned_items,
        next_open={"sh600001": 10.0},
        slip_bps=0.01,
        comm_rate=0.001,
        comm_min=5.0,
        min_positions=0,
    )

    runtime = SimpleNamespace(
        open_idx={(date(2026, 3, 3), "sh600001"): 10.0},
        close_idx={(date(2026, 3, 3), "sh600001"): 10.2},
        volume_idx={(date(2026, 3, 3), "sh600001"): 1000.0},
        amount_idx={(date(2026, 3, 3), "sh600001"): 10000.0},
        suspended_idx={(date(2026, 3, 3), "sh600001"): False},
        limit_up_idx={(date(2026, 3, 3), "sh600001"): 20.0},
        limit_down_idx={(date(2026, 3, 3), "sh600001"): 1.0},
        _slip_bps=0.01,
        _comm_rate=0.001,
        _comm_min=5.0,
        _stamp_rate=0.0,
        _min_trade_price=5.0,
        cash=100000.0,
        _traded_value_today=0.0,
        positions={},
        position_avg_cost={},
        position_entry_adj={},
        holding_sources={},
        provider=SimpleNamespace(entry_day={}, entry_day_overwrite=False, peak_state_on_buy={}),
        trade_rows=[],
        order_reject_reason_counts={},
        fill_reject_reason_counts={},
    )

    apply_open_fills(runtime, date(2026, 3, 3), orders)

    assert runtime.positions["sh600001"] == 9800
    assert runtime.trade_rows[0]["side"] == "BUY"
    assert runtime.fill_reject_reason_counts == {}


def test_build_execution_orders_from_candidate_plan_rejects_source_only_sell_owner_mismatch() -> None:
    sell_signal = Signal(
        signal_date=date(2026, 3, 2),
        symbol="sh600001",
        side=Side.SELL,
        qty=100,
        reason="EXIT",
        reason_code="EXIT",
        meta={
            "alpha_id": "moneyflow_monthly",
            "sleeve_id": "mr",
            "owner_system": "mr",
            "exit_owner": "source_only",
        },
    )
    candidate_audit: list[dict[str, object]] = []
    debug_plan: dict[str, object] = {}

    orders = build_execution_orders_from_candidate_plan(
        positions={"sh600001": 100},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=[sell_signal],
        planned_items=[],
        next_open={"sh600001": 10.0},
        decision_date=date(2026, 3, 2),
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
        holding_sources={"sh600001": {"entry_sleeve_id": "trend", "entry_alpha_id": "breakout_55"}},
        min_positions=0,
    )

    assert orders == []
    assert debug_plan["reject_reason_counts"] == {"SOURCE_ONLY_OWNER_MISMATCH": 1}
    assert candidate_audit[0]["symbol"] == "sh600001"
    assert candidate_audit[0]["reject_reason"] == "SOURCE_ONLY_OWNER_MISMATCH"


def test_build_s7_order_stage_output_records_source_only_rejection_in_execution_audit() -> None:
    sell_signal = Signal(
        signal_date=date(2026, 3, 2),
        symbol="sh600001",
        side=Side.SELL,
        qty=100,
        reason="EXIT",
        reason_code="EXIT",
        meta={
            "alpha_id": "moneyflow_monthly",
            "sleeve_id": "mr",
            "owner_system": "mr",
            "exit_owner": "source_only",
        },
    )
    runtime = SimpleNamespace(
        _current_day={
            "day": date(2026, 3, 2),
            "controls": {"effective_max_positions": 1, "risk_on_today": True},
            "day_signals": DaySignals(
                sell_signals=[sell_signal],
                buy_signals=[],
                exit_syms={"sh600001"},
                strength_map={},
                mf_score_map={},
                mf_gate_on_today=False,
                strong_risk_on=False,
                exit_counts=ExitCounts(),
                diagnostics={},
            ),
            "next_open": {"sh600001": 10.0},
            "nav": 100000.0,
            "holding_symbols": ("sh600001",),
        },
        request=_request_stub(),
        provider=SimpleNamespace(_feats=None, _mx=None, _sym_to_col={}),
        positions={"sh600001": 100},
        holding_sources={"sh600001": {"entry_sleeve_id": "trend", "entry_alpha_id": "breakout_55"}},
        cash=100000.0,
        _weight_mode="equal",
        _min_positions_cfg=0,
        _tilt_strength=0.0,
        _tilt_top_n=0,
        _tilt_bottom_n=0,
        _min_trade_price=5.0,
        _portfolio_mode="equal_10",
        candidate_rows=[],
        _prepared_day_index=0,
        _apply_daily_decision_diagnostics=lambda **_kwargs: None,
        deferred_sell_orders=[],
        close_idx={},
        order_reject_reason_counts={},
        _sizing_cfg=None,
    )
    _prepare_candidate_contracts(runtime)

    output = build_s7_order_stage_output(runtime)
    records = list(output.payload["formal_execution_boundary"]["execution_audit"]["records"])

    assert output.reason_counts == {"SOURCE_ONLY_OWNER_MISMATCH": 1}
    assert records[0]["side"] == "SELL"
    assert records[0]["outcome"] == "rejected"
    assert records[0]["reason_codes"] == ["SOURCE_ONLY_SELL_MISMATCH"]
