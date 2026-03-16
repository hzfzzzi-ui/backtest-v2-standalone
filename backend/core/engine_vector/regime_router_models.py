"""Shared config/runtime owners for the regime router provider."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

import numpy as np

from backend.core.config.models import ExitConfig


def _empty_bool_array() -> np.ndarray:
    return np.array([], dtype=bool)


def _empty_float_array() -> np.ndarray:
    return np.array([], dtype=float)


@dataclass(slots=True)
class RegimeRouterConfig:
    fast: int = 5
    slow: int = 20
    trend_order_size: int = 1000
    mr_rsi_period: int = 6
    mr_rsi_buy_threshold: float = 20.0
    mr_rsi_sell_threshold: float = 80.0
    mr_max_hold_days: int = 5
    mr_stop_loss_pct: float = 0.03
    mr_order_size: int = 1000
    ma_type: str = "SMA"
    regime_ma: int = 60
    atr_stop_k: float = 2.0
    enable_multifactor_rank: bool = False
    mf_rank_gate_mode: str = "ALWAYS_ON"
    min_price: float = 0.0
    min_list_days: int = 0
    min_avg_turnover_20d: float = 0.0


@dataclass(slots=True)
class RegimeRouterRuntimeState:
    mx: Any = None
    feats: Any = None
    bench_close: np.ndarray = field(default_factory=_empty_float_array)
    regime_on: np.ndarray = field(default_factory=_empty_bool_array)
    risk_on_exits: np.ndarray = field(default_factory=_empty_bool_array)
    strong_risk_on: np.ndarray = field(default_factory=_empty_bool_array)
    sym_to_col: dict[str, int] = field(default_factory=dict)


def build_regime_router_config(
    strategy: Any,
    *,
    kwargs: dict[str, Any],
) -> RegimeRouterConfig:
    detector = getattr(strategy, "detector", None)
    trend_strat = getattr(strategy, "trend_strategy", None)
    mr_strat = getattr(strategy, "mr_strategy", None)
    universe_filters = dict(getattr(strategy, "state", {}).get("universe_filters") or {})

    return RegimeRouterConfig(
        fast=int(getattr(trend_strat, "fast", 5)),
        slow=int(getattr(trend_strat, "slow", 20)),
        trend_order_size=int(getattr(trend_strat, "order_size", 1000)),
        mr_rsi_period=int(getattr(mr_strat, "rsi_period", 6)),
        mr_rsi_buy_threshold=float(getattr(mr_strat, "rsi_buy_threshold", 20.0)),
        mr_rsi_sell_threshold=float(getattr(mr_strat, "rsi_sell_threshold", 80.0)),
        mr_max_hold_days=int(getattr(mr_strat, "mr_max_hold_days", 5)),
        mr_stop_loss_pct=float(getattr(mr_strat, "mr_stop_loss_pct", 0.03)),
        mr_order_size=int(getattr(mr_strat, "order_size", 1000)),
        ma_type=str(getattr(trend_strat, "ma_type", "SMA")).upper(),
        regime_ma=int(getattr(detector, "regime_ma", 60)) if detector else 60,
        atr_stop_k=float(kwargs.get("atr_stop_k", 2.0)),
        enable_multifactor_rank=bool(kwargs.get("enable_multifactor_rank", False)),
        mf_rank_gate_mode=str(kwargs.get("mf_rank_gate_mode") or "ALWAYS_ON"),
        min_price=float(
            universe_filters.get(
                "min_price",
                getattr(strategy, "min_price", 0.0) or getattr(trend_strat, "min_price", 0.0),
            )
            or 0.0
        ),
        min_list_days=int(universe_filters.get("min_list_days", 0) or 0),
        min_avg_turnover_20d=float(universe_filters.get("min_avg_turnover_20d", 0.0) or 0.0),
    )


def apply_regime_router_config(
    provider: Any,
    config: RegimeRouterConfig,
    *,
    exit_cfg: ExitConfig,
) -> None:
    provider._config = config
    provider._ec = exit_cfg
    provider._fast = int(config.fast)
    provider._slow = int(config.slow)
    provider._trend_order_size = int(config.trend_order_size)
    provider._mr_rsi_period = int(config.mr_rsi_period)
    provider._mr_rsi_buy_threshold = float(config.mr_rsi_buy_threshold)
    provider._mr_rsi_sell_threshold = float(config.mr_rsi_sell_threshold)
    provider._mr_max_hold_days = int(config.mr_max_hold_days)
    provider._mr_stop_loss_pct = float(config.mr_stop_loss_pct)
    provider._mr_order_size = int(config.mr_order_size)
    provider._ma_type = str(config.ma_type)
    provider._enable_multifactor_rank = bool(config.enable_multifactor_rank)
    provider._mf_rank_gate_mode = str(config.mf_rank_gate_mode)
    provider._atr_stop_k = float(config.atr_stop_k)


def capture_regime_router_runtime_state(provider: Any) -> RegimeRouterRuntimeState:
    state = RegimeRouterRuntimeState(
        mx=provider._mx,
        feats=provider._feats,
        bench_close=provider._bench_close,
        regime_on=provider._regime_on,
        risk_on_exits=provider._risk_on_exits,
        strong_risk_on=provider._strong_risk_on,
        sym_to_col=dict(provider._sym_to_col),
    )
    provider._runtime_state = state
    return state
