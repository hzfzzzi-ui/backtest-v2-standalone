from __future__ import annotations

from datetime import date
from typing import Any

from backend.core.engine_vector.breakout_signal_provider import BreakoutTrendProvider
from backend.core.engine_vector.etf_beta.execution_paths import build_etf_day_signals
from backend.core.engine_vector.etf_beta.provider_config import _rebalance_flags
from backend.core.engine_vector.etf_beta.provider_state import reset_etf_beta_provider_state
from backend.core.engine_vector.etf_beta.selection import precompute_etf_beta
from backend.core.engine_vector.signal_provider import DayContext, DaySignals


class CNETFBetaSignalProvider(BreakoutTrendProvider):
    def __init__(self) -> None:
        super().__init__()
        reset_etf_beta_provider_state(self)

    def precompute(
        self,
        *,
        history: Any,
        benchmark: Any,
        raw_history: Any,
        trading_days: list[date],
        strategy: Any,
        **kwargs: Any,
    ) -> None:
        super().precompute(
            history=history,
            benchmark=benchmark,
            raw_history=raw_history,
            trading_days=trading_days,
            strategy=strategy,
            **kwargs,
        )
        precompute_etf_beta(self, benchmark=benchmark, kwargs=kwargs)

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        return build_etf_day_signals(self, day, day_idx, ctx)


__all__ = ["CNETFBetaSignalProvider", "_rebalance_flags"]
