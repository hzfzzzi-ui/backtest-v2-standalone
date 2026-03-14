from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.multi_alpha_signal_provider import MultiAlphaSignalProvider
from backend.core.engine_vector.signal_provider import DayContext, DaySignals


def _ctx() -> DayContext:
    return DayContext(
        positions={},
        position_avg_cost={},
        cash=100000.0,
        nav=100000.0,
        base_order_value=10000.0,
        max_positions=5,
        close_idx={},
        open_idx={},
        next_day=date(2026, 3, 3),
        holding_sources={},
        risk_on=True,
    )


def _breakout_buy(symbol: str, score: float) -> Signal:
    return Signal(
        signal_date=date(2026, 3, 2),
        symbol=symbol,
        side=Side.BUY,
        qty=100,
        reason="BREAKOUT_HIGH",
        reason_code="BREAKOUT_HIGH",
        meta={"final_score": score, "close": 10.0, "slow_ma": 9.5},
    )


class _FakeBreakoutProvider:
    def __init__(self, score: float, symbol: str = "sh600000") -> None:
        self._signal = _breakout_buy(symbol, score)

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        return DaySignals(
            sell_signals=[],
            buy_signals=[self._signal],
        )


def _provider_for_test(*, breakout_score: float) -> MultiAlphaSignalProvider:
    provider = MultiAlphaSignalProvider()
    provider._compose_mode = "REGIME_ROUTE"
    provider._same_symbol_policy = "PREFER_HIGHER_SCORE"
    provider._regime_matrix = {
        "TREND_UP": ["breakout_55"],
        "RANGE": ["breakout_55", "rsi_reversal"],
        "WEAK_DOWN": ["rsi_reversal"],
    }
    provider._module_specs = {
        "breakout_55": SimpleNamespace(
            name="breakout_55",
            alpha_id="breakout_55",
            family="trend",
            sleeve_id="trend",
            params={},
        ),
        "rsi_reversal": SimpleNamespace(
            name="rsi_reversal",
            alpha_id="rsi_reversal",
            family="mean_revert",
            sleeve_id="mr",
            params={"rsi_buy_threshold": 20.0, "rsi_sell_threshold": 80.0, "order_size": 100},
        ),
    }
    provider._breakout_provider = _FakeBreakoutProvider(score=breakout_score)
    provider._rsi_rows_by_day = {
        date(2026, 3, 2): pd.DataFrame(
            [{"symbol": "sh600000", "close": 10.0, "rsi": 25.0, "rsi_prev": 5.0}]
        )
    }
    return provider


def test_multi_alpha_provider_regime_route_suppresses_disabled_module() -> None:
    provider = _provider_for_test(breakout_score=0.42)
    provider._risk_on_map = {date(2026, 3, 2): True}
    provider._strong_risk_on_map = {date(2026, 3, 2): True}

    day_signals = provider.day_signals(date(2026, 3, 2), 0, _ctx())

    assert len(day_signals.raw_alpha_signals) == 2
    assert len(day_signals.buy_signals) == 1
    assert day_signals.buy_signals[0].meta["alpha_id"] == "breakout_55"
    assert day_signals.diagnostics["regime_tag"] == "TREND_UP"
    assert day_signals.diagnostics["suppressed_raw_alpha_signal_count"] == 1


def test_multi_alpha_provider_prefers_higher_score_for_same_symbol_conflict() -> None:
    provider = _provider_for_test(breakout_score=0.40)
    provider._risk_on_map = {date(2026, 3, 2): True}
    provider._strong_risk_on_map = {date(2026, 3, 2): False}

    day_signals = provider.day_signals(date(2026, 3, 2), 0, _ctx())

    assert len(day_signals.raw_alpha_signals) == 2
    assert len(day_signals.buy_signals) == 1
    assert day_signals.buy_signals[0].meta["alpha_id"] == "rsi_reversal"
    assert day_signals.buy_signals[0].meta["conflict_resolution"] == "prefer_higher_score"
    assert day_signals.diagnostics["conflict_resolution_count"] == 1


def test_multi_alpha_provider_source_only_sell_does_not_kill_other_alpha_holding() -> None:
    provider = _provider_for_test(breakout_score=0.40)
    provider._risk_on_map = {date(2026, 3, 2): True}
    provider._strong_risk_on_map = {date(2026, 3, 2): False}
    provider._rsi_rows_by_day = {
        date(2026, 3, 2): pd.DataFrame(
            [{"symbol": "sh600000", "close": 10.0, "rsi": 70.0, "rsi_prev": 85.0}]
        )
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
        holding_sources={"sh600000": {"entry_alpha_id": "breakout_55"}},
        risk_on=True,
    )

    day_signals = provider.day_signals(date(2026, 3, 2), 0, ctx)

    assert day_signals.sell_signals == []


def test_multi_alpha_provider_source_only_sell_triggers_for_matching_alpha() -> None:
    provider = _provider_for_test(breakout_score=0.40)
    provider._risk_on_map = {date(2026, 3, 2): True}
    provider._strong_risk_on_map = {date(2026, 3, 2): False}
    provider.entry_day["sh600000"] = date(2026, 2, 24)
    provider._rsi_rows_by_day = {
        date(2026, 3, 2): pd.DataFrame(
            [{"symbol": "sh600000", "close": 10.0, "rsi": 70.0, "rsi_prev": 85.0}]
        )
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
        holding_sources={"sh600000": {"entry_alpha_id": "rsi_reversal"}},
        risk_on=True,
    )

    day_signals = provider.day_signals(date(2026, 3, 2), 0, ctx)

    assert len(day_signals.sell_signals) == 1
    assert day_signals.sell_signals[0].meta["alpha_id"] == "rsi_reversal"
    assert day_signals.sell_signals[0].meta["exit_owner"] == "source_only"
    assert day_signals.sell_signals[0].reason_code == "MR_RSI_OVERBOUGHT_SELL"
