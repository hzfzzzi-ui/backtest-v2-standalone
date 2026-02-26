from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.core.portfolio.portfolio_builder import build_rebalance_orders
from backend.core.strategies.sma_cross_regime_atr import SMACrossRegimeATRStrategy


def _mk_rows(symbol: str, closes: list[float], start: date) -> list[dict]:
    out: list[dict] = []
    for i, c in enumerate(closes):
        d = start + timedelta(days=i)
        out.append(
            {
                "date": pd.Timestamp(d),
                "symbol": symbol,
                "open": float(c),
                "high": float(c) * 1.01,
                "low": float(c) * 0.99,
                "close": float(c),
            }
        )
    return out


def test_minimal_selection_flow_topk_and_reject_reasons() -> None:
    # Day-6 both symbols cross up; portfolio has only 1 slot.
    start = date(2026, 1, 1)
    day = start + timedelta(days=5)
    history = pd.DataFrame(
        _mk_rows("BENCH:000300.SH", [100, 101, 102, 103, 104, 105], start)
        + _mk_rows("AAA", [10, 10, 10, 10, 10, 20], start)
        + _mk_rows("BBB", [10, 10, 10, 10, 10, 18], start)
    )

    strategy = SMACrossRegimeATRStrategy(
        fast=3,
        slow=5,
        regime_ma=3,
        entry_buffer=0.0,
        enable_trend_filter=False,
    )

    signals = strategy.generate_signals(day, history, positions={})
    buy_signals = [s for s in signals if str(s.side.value).upper() == "BUY"]
    sell_signals = [s for s in signals if str(s.side.value).upper() == "SELL"]
    assert len(buy_signals) == 2
    assert len(sell_signals) == 0

    candidate_audit: list[dict] = []
    debug_plan: dict = {}
    orders = build_rebalance_orders(
        positions={},
        cash_available=100000.0,
        nav_close=100000.0,
        max_positions=1,
        lot_size=100,
        sell_signals=sell_signals,
        buy_signals=buy_signals,
        next_open={"aaa": 20.1, "bbb": 18.1},
        enable_multifactor_rank=True,
        mf_gate_on_today=True,
        mf_topk=1,
        mf_score_map={"aaa": 0.9, "bbb": 0.1},
        decision_date=day,
        candidate_audit=candidate_audit,
        debug_plan=debug_plan,
    )

    # Only top-1 by MF score should be bought.
    assert len(orders) == 1
    assert orders[0].symbol == "aaa"
    assert str(orders[0].side.value).upper() == "BUY"

    by_symbol = {str(x.get("symbol")).lower(): x for x in candidate_audit}
    assert by_symbol["aaa"]["selected"] is True
    assert by_symbol["bbb"]["selected"] is False
    assert by_symbol["bbb"]["reject_reason"] == "NOT_IN_TOPK"

    assert debug_plan.get("mf_rank_triggered") is True
    assert int(debug_plan.get("buy_slots") or 0) == 1
    assert int(debug_plan.get("buy_candidates_count") or 0) == 2
    assert "aaa" in list(debug_plan.get("selected_symbols") or [])
