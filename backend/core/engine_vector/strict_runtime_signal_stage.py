"""Signal/candidate stage for the default vector runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from backend.core.engine_vector.candidate_index import build_daily_candidate_index
from backend.core.engine_vector.signal_matrix import build_signal_matrices
from backend.core.portfolio.price_index import build_backtest_price_indices


@dataclass(slots=True)
class DefaultRuntimeSignalStage:
    sig_m: dict[str, Any]
    cand_idx: Any
    open_idx: dict[tuple[date, str], float]
    close_idx: dict[tuple[date, str], float]
    sym_to_col: dict[str, int]


def build_default_runtime_signal_state(
    *,
    strategy: Any,
    history: pd.DataFrame,
    raw_history: pd.DataFrame | None,
    trading_days: list[date],
    sector_data: Any,
    industry_map: Any,
    inputs: Any,
    benchmark_state: Any,
) -> DefaultRuntimeSignalStage:
    params = inputs.params
    mx = inputs.mx
    feats = inputs.feats

    sig_m = build_signal_matrices(
        close=mx.close,
        fast_ma=feats.fast_ma,
        slow_ma=feats.slow_ma,
        trend_fast_ma=feats.trend_fast_ma,
        trend_slow_ma=feats.trend_slow_ma,
        tradable=mx.tradable,
        entry_buffer=params["entry_buffer"],
        enable_trend_filter=params["enable_trend_filter"],
        enable_trend_tier=params["enable_trend_tier"],
        enable_trend_slope_filter=params["enable_trend_slope_filter"],
        slope_lookback=params["slope_lookback"],
        enable_trend_continuity_filter=params["enable_trend_continuity_filter"],
        continuity_n=params["continuity_n"],
        risk_on=benchmark_state.risk_on,
        sma20=feats.sma20 if params["enable_v2_trend_filter"] else None,
        sma60=feats.sma60 if params["enable_v2_trend_filter"] else None,
    )
    if params["enable_sector_gate"] and sector_data and industry_map:
        from backend.core.engine_vector.features import compute_sector_eligible

        _sector_eligible = compute_sector_eligible(
            sector_data=sector_data,
            industry_map=industry_map,
            symbols=mx.symbols,
            dates=mx.dates,
            window=params["sector_rank_window"],
            top_pct=params["sector_top_pct"],
        )
        sig_m["buy_base"] = sig_m["buy_base"] & _sector_eligible

    cand_idx = build_daily_candidate_index(sig_m["buy_base"])
    _raw = raw_history if raw_history is not None else history
    _raw_hist = _raw.copy()
    _raw_hist["date"] = pd.to_datetime(_raw_hist["date"])
    _raw_hist["symbol"] = _raw_hist["symbol"].astype(str).str.lower()
    day_list = list(trading_days)
    open_idx, close_idx = build_backtest_price_indices(
        history=_raw_hist,
        trading_days=day_list,
    )
    del _raw_hist
    sym_to_col = {s: i for i, s in enumerate(mx.symbols)}
    return DefaultRuntimeSignalStage(
        sig_m=sig_m,
        cand_idx=cand_idx,
        open_idx=open_idx,
        close_idx=close_idx,
        sym_to_col=sym_to_col,
    )
