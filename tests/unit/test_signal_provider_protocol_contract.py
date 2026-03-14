from __future__ import annotations

from datetime import date

import pytest

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.signal_provider import DayContext, DaySignals


def _signal(symbol: str, side: Side, *, reason_code: str) -> Signal:
    return Signal(
        signal_date=date(2026, 3, 2),
        symbol=symbol,
        side=side,
        qty=100,
        reason=reason_code,
        reason_code=reason_code,
        meta={},
    )


def test_day_signals_keeps_stable_multi_alpha_diagnostics() -> None:
    raw_buy = _signal("sh600000", Side.BUY, reason_code="RAW_BREAKOUT")
    composed_buy = _signal("sh600000", Side.BUY, reason_code="COMPOSED_BREAKOUT")

    day_signals = DaySignals(
        sell_signals=[],
        buy_signals=[composed_buy],
        raw_alpha_signals=[raw_buy],
        composed_buy_signals=[composed_buy],
        diagnostics={
            "composition_enabled": True,
            "composition_mode": "REGIME_ROUTE",
        },
    )

    assert day_signals.diagnostics["composition_enabled"] is True
    assert day_signals.diagnostics["composition_mode"] == "REGIME_ROUTE"
    assert day_signals.diagnostics["raw_alpha_signal_count"] == 1
    assert day_signals.diagnostics["composed_buy_signal_count"] == 1
    assert day_signals.diagnostics["composed_sell_signal_count"] == 0
    assert day_signals.diagnostics["suppressed_raw_alpha_signal_count"] == 0
    assert "conflict_resolution_count" in day_signals.diagnostics


def test_day_context_exposes_read_only_holding_sources_snapshot() -> None:
    original_sources = {
        "sh600000": {
            "entry_alpha_id": "breakout_55",
            "entry_sleeve_id": "trend",
            "entry_reason_code": "BREAKOUT_HIGH",
            "entry_date": date(2026, 3, 1),
            "meta": {"compose_score": 0.91},
        }
    }
    ctx = DayContext(
        positions={"sh600000": 100},
        position_avg_cost={"sh600000": 10.0},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=5,
        close_idx={},
        open_idx={},
        next_day=date(2026, 3, 3),
        holding_sources=original_sources,
    )

    original_sources["sh600000"]["entry_alpha_id"] = "mutated"
    original_sources["sh600000"]["meta"]["compose_score"] = 0.0

    snapshot = ctx.holding_sources["sh600000"]
    assert snapshot.entry_alpha_id == "breakout_55"
    assert snapshot.entry_sleeve_id == "trend"
    assert snapshot.meta["compose_score"] == 0.91

    with pytest.raises(TypeError):
        ctx.holding_sources["sh600001"] = snapshot  # type: ignore[index]
    with pytest.raises(TypeError):
        snapshot.meta["compose_score"] = 0.5  # type: ignore[index]
