from __future__ import annotations

import time
from datetime import date
from types import SimpleNamespace

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DaySignals, ExitCounts
from backend.core.stage_pipeline.adapters.daily_accounting import apply_daily_decision_diagnostics, prepare_daily_snapshot
from backend.core.stage_pipeline.adapters.result_bridge import build_portfolio_backtest_result


def _signal(
    symbol: str,
    *,
    side: Side,
    alpha_id: str,
    sleeve_id: str,
    compose_score: float = 0.0,
    raw_score: float = 0.0,
    exit_owner: str = "",
) -> Signal:
    meta = {
        "alpha_id": alpha_id,
        "alpha_source": alpha_id,
        "sleeve_id": sleeve_id,
        "raw_score": raw_score,
        "compose_score": compose_score,
    }
    if exit_owner:
        meta["exit_owner"] = exit_owner
    return Signal(
        signal_date=date(2026, 3, 2),
        symbol=symbol,
        side=side,
        qty=100,
        reason="SIG",
        reason_code="SIG",
        meta=meta,
    )


def test_multi_alpha_audit_summary_and_flagged_days_are_aggregated() -> None:
    trading_day = date(2026, 3, 2)
    runtime = SimpleNamespace(
        cash=1000.0,
        positions={"sh600001": 100, "sh600002": 100},
        close_idx={
            (trading_day, "sh600001"): 10.0,
            (trading_day, "sh600002"): 9.0,
        },
        peak_nav=1000.0,
        prev_nav=1000.0,
        _traded_value_today=0.0,
        daily_rows=[],
        route_id="multi_alpha_inline_runtime",
        composition_audit_rows=[],
        _compute_day_controls=lambda *_args: {
            "effective_max_positions": 5,
            "dd_state": "NORMAL",
            "market_state": "RANGE",
            "trade_mode": "LIGHT",
            "benchmark_regime_on": True,
            "risk_on_today": True,
        },
    )
    snapshot = prepare_daily_snapshot(runtime, day_index=0, day=trading_day)
    runtime._current_day = {"controls": snapshot.controls}

    raw_breakout = _signal("sh600101", side=Side.BUY, alpha_id="breakout_55", sleeve_id="trend", raw_score=0.61, compose_score=0.61)
    raw_rsi = _signal("sh600101", side=Side.BUY, alpha_id="rsi_reversal", sleeve_id="mr", raw_score=0.74, compose_score=0.74)
    composed_buy = _signal("sh600101", side=Side.BUY, alpha_id="rsi_reversal", sleeve_id="mr", compose_score=0.74)
    source_sell = _signal("sh600001", side=Side.SELL, alpha_id="breakout_55", sleeve_id="trend", exit_owner="source_only")
    override_sell = _signal("sh600002", side=Side.SELL, alpha_id="risk_control", sleeve_id="global", exit_owner="global_risk_override")

    day_signals = DaySignals(
        sell_signals=[source_sell, override_sell],
        buy_signals=[composed_buy],
        raw_alpha_signals=[raw_breakout, raw_rsi],
        composed_sell_signals=[source_sell, override_sell],
        composed_buy_signals=[composed_buy],
        exit_syms={"sh600001", "sh600002"},
        strength_map={"sh600101": 0.74},
        mf_score_map={"sh600101": 0.74},
        mf_gate_on_today=False,
        strong_risk_on=False,
        exit_counts=ExitCounts(),
        diagnostics={
            "composition_enabled": True,
            "regime_tag": "RANGE",
            "suppressed_raw_alpha_signal_count": 1,
            "conflict_resolution_count": 1,
        },
    )

    apply_daily_decision_diagnostics(
        runtime,
        day_signals=day_signals,
        debug_plan={
            "buy_candidates_count": 1,
            "buy_slots": 1,
            "selected_symbols": ["sh600101"],
            "same_symbol_policy": "prefer_higher_score",
            "sleeve_budget_mode": "hard_sleeve_budget",
            "sleeve_budget_reject_count": 2,
            "sleeve_slot_caps": {"mr": 2, "trend": 3},
            "sleeve_available_slots": {"mr": 2, "trend": 1},
            "sleeve_positions_after_sell": {"mr": 0, "trend": 1},
            "sleeve_candidate_counts": {"mr": 1, "trend": 1},
            "sleeve_selected_counts": {"mr": 1},
        },
    )

    runtime.trade_rows = []
    runtime.candidate_rows = []
    runtime.provider = SimpleNamespace(
        precompute_seconds=0.0,
        blocked_by_trend_count=0,
        total_buy_signals=0,
        diag_reason_counts={},
    )
    runtime.request = SimpleNamespace(max_positions=5, enable_strength_rank=False, strength_ma=120)
    runtime._simulation_t0 = time.perf_counter() - 1.0

    result = build_portfolio_backtest_result(runtime)
    audit = result.metrics["audit"]
    summary = audit["summary"]

    assert summary["raw_signal_counts_by_alpha"] == {"breakout_55": 1, "rsi_reversal": 1}
    assert summary["composed_signal_counts_by_alpha"] == {"breakout_55": 1, "risk_control": 1, "rsi_reversal": 1}
    assert summary["blocked_signal_counts_by_reason"] == {
        "DISABLED_BY_REGIME": 1,
        "SAME_SYMBOL_CONFLICT": 1,
        "SLEEVE_BUDGET_EXCEEDED": 2,
    }
    assert summary["conflict_resolution_counts"] == {"prefer_higher_score": 1}
    assert summary["source_only_exit_count"] == 1
    assert summary["global_risk_override_count"] == 1
    assert len(audit["flagged_days"]) == 1
    assert audit["flagged_days"][0]["date"] == "2026-03-02"
    assert audit["flagged_days"][0]["regime_tag"] == "RANGE"
    assert len(audit["flagged_days"][0]["raw_alpha_signals"]) == 2
    assert len(audit["flagged_days"][0]["composed_sell_signals"]) == 2
    assert result.metrics["source_only_exit_count"] == 1
    assert result.metrics["global_risk_override_count"] == 1

