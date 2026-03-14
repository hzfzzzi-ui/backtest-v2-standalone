from __future__ import annotations

from datetime import date

import pandas as pd

from backend.core.config.models import StrategyConfig
from backend.core.engine_vector.signal_provider import DayContext
from backend.core.stage_pipeline.adapters.route_runtime import build_signal_provider
from backend.core.strategies.multi_alpha_strategy import MultiAlphaStrategy
from backend.core.strategies.registry import build_strategy


def _multi_alpha_payload() -> dict[str, object]:
    return {
        "signal_generation": {
            "modules": [
                {"name": "breakout_55", "alpha_id": "breakout_55"},
                {"name": "rsi_reversal", "alpha_id": "rsi_rev_6_20_80"},
            ]
        },
        "signal_composition": {
            "enabled": True,
            "compose_mode": "REGIME_ROUTE",
        },
    }


def test_build_strategy_uses_multi_alpha_strategy_for_composite_payload() -> None:
    strategy = build_strategy(
        StrategyConfig(
            name="composite",
            params={"multi_alpha": _multi_alpha_payload(), "portfolio_mode": "hard_sleeve_budget"},
        )
    )

    assert isinstance(strategy, MultiAlphaStrategy)
    assert strategy.portfolio_mode == "hard_sleeve_budget"
    assert strategy.multi_alpha["signal_composition"]["compose_mode"] == "REGIME_ROUTE"


def test_build_signal_provider_routes_multi_alpha_to_dedicated_provider() -> None:
    strategy = MultiAlphaStrategy(multi_alpha=_multi_alpha_payload())

    route_id, provider = build_signal_provider(strategy)

    assert route_id == "multi_alpha_inline_runtime"
    assert provider.__class__.__name__ == "MultiAlphaSignalProvider"

    provider.precompute(
        history=pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-03-02"),
                    "symbol": "sh600000",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.9,
                    "close": 10.1,
                    "volume": 1000000.0,
                    "amount": 10100000.0,
                }
            ]
        ),
        benchmark=pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-03-02"),
                    "close": 100.0,
                }
            ]
        ),
        raw_history=None,
        trading_days=[date(2026, 3, 2)],
        strategy=strategy,
    )
    day_signals = provider.day_signals(
        date(2026, 3, 2),
        0,
        DayContext(
            positions={},
            position_avg_cost={},
            cash=100000.0,
            nav=100000.0,
            base_order_value=10000.0,
            max_positions=5,
            close_idx={},
            open_idx={},
            next_day=date(2026, 3, 3),
            holding_sources={"sh600000": {"entry_alpha_id": "breakout_55"}},
        ),
    )

    assert day_signals.buy_signals == []
    assert day_signals.sell_signals == []
    assert day_signals.diagnostics["composition_enabled"] is True
    assert day_signals.diagnostics["composition_mode"] == "REGIME_ROUTE"
    assert day_signals.diagnostics["holding_source_count"] == 1
