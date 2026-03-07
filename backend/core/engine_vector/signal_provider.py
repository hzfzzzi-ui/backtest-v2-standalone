"""信号提供者协议与共享数据类。

定义 SignalProvider Protocol 和引擎↔信号提供者之间的数据传输类型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Protocol, runtime_checkable

import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Signal
from backend.core.core.types import Side


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ExitCounts:
    """各引擎级退出规则的触发计数。"""
    atr_stop: int = 0
    atr_trail: int = 0
    take_profit: int = 0
    fixed_stop_loss: int = 0
    ma20_exit: int = 0
    low10_exit: int = 0


@dataclass(slots=True)
class DayContext:
    """引擎状态的只读快照，传递给信号提供者。

    注意：positions / position_avg_cost 是引用（非拷贝），provider 不得修改。
    """
    positions: dict[str, int]
    position_avg_cost: dict[str, float]
    cash: float
    nav: float
    base_order_value: float
    max_positions: int
    close_idx: dict[tuple[date, str], float]
    open_idx: dict[tuple[date, str], float]
    next_day: date | None
    risk_on: bool = True


@dataclass(slots=True)
class DaySignals:
    """信号提供者的逐日输出。"""
    sell_signals: list[Signal]
    buy_signals: list[Signal]
    exit_syms: set[str]
    strength_map: dict[str, float]
    mf_score_map: dict[str, float]
    mf_gate_on_today: bool
    strong_risk_on: bool
    exit_counts: ExitCounts
    diagnostics: dict[str, Any]


# ---------------------------------------------------------------------------
# SignalProvider 协议
# ---------------------------------------------------------------------------

@runtime_checkable
class SignalProvider(Protocol):
    """信号提供者协议 — 引擎通过此接口获取逐日交易信号。"""

    # -- fill hooks：引擎在 _process_pending_fills 中使用 --
    extra_clear_dicts: list[dict]
    last_sell_day: dict[str, date] | None
    entry_day: dict[str, date]
    entry_day_overwrite: bool
    peak_state_on_buy: dict[str, float] | None

    def precompute(
        self,
        *,
        history: pd.DataFrame,
        benchmark: pd.DataFrame,
        raw_history: pd.DataFrame | None,
        trading_days: list[date],
        strategy: Any,
        **kwargs: Any,
    ) -> None:
        """日循环前的一次性预计算。"""
        ...

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        """生成当日卖出/买入信号。"""
        ...


# ---------------------------------------------------------------------------
# 共享退出规则评估
# ---------------------------------------------------------------------------

def evaluate_engine_exits(
    *,
    positions: dict[str, int],
    day: date,
    close_idx: dict[tuple[date, str], float],
    position_avg_cost: dict[str, float],
    peak_state: dict[str, float],
    entry_day: dict[str, date],
    exit_cfg: ExitConfig,
    get_atr: Callable[[str, date], float | None],
    risk_on: bool = True,
    enable_risk_off_exit: bool = True,
    max_hold_days: int = 0,
    atr_stop_k: float = 2.0,
    check_ma20_exit: Callable[[str], bool] | None = None,
    check_low10_exit: Callable[[str], bool] | None = None,
) -> tuple[list[Signal], set[str], ExitCounts]:
    """评估所有持仓的引擎级退出规则。

    按优先级：RISK_OFF > ATR_STOP > FIXED_STOP > TAKE_PROFIT > ATR_TRAIL > MA20_EXIT > LOW10_EXIT > TIME_EXIT。
    原地更新 peak_state。
    返回 (exit_signals, exit_syms_set, exit_counts)。
    """
    exits: list[Signal] = []
    exit_syms: set[str] = set()
    counts = ExitCounts()

    for sym, qty in list(positions.items()):
        if int(qty) <= 0:
            continue
        cclose = float(close_idx.get((day, sym), 0.0) or 0.0)
        if cclose <= 0:
            continue

        # peak update
        old_peak = float(peak_state.get(sym, cclose))
        new_peak = max(old_peak, cclose)
        peak_state[sym] = new_peak

        avg_cost = float(position_avg_cost.get(sym, 0.0))
        atr_v = get_atr(sym, day)

        reason = ""
        if enable_risk_off_exit and not risk_on:
            reason = "RISK_OFF_EXIT"
        elif exit_cfg.enable_atr_stop and atr_v is not None and cclose <= float(avg_cost - atr_stop_k * atr_v):
            reason = "ATR_STOP_LOSS"
            counts.atr_stop += 1
        elif exit_cfg.enable_fixed_stop_loss and avg_cost > 0 and cclose <= avg_cost * (1.0 - exit_cfg.fixed_stop_loss_pct):
            reason = "FIXED_STOP_LOSS"
            counts.fixed_stop_loss += 1
        elif exit_cfg.enable_take_profit and avg_cost > 0 and (
            (exit_cfg.take_profit_mode == "pct" and cclose >= avg_cost * (1.0 + exit_cfg.take_profit_pct))
            or (exit_cfg.take_profit_mode == "atr" and atr_v is not None and cclose >= avg_cost + exit_cfg.take_profit_atr_k * atr_v)
        ):
            reason = "TAKE_PROFIT"
            counts.take_profit += 1
        elif exit_cfg.enable_atr_trail and atr_v is not None and cclose <= float(peak_state.get(sym, cclose) - exit_cfg.atr_trail_k * atr_v):
            reason = "ATR_TRAIL_EXIT"
            counts.atr_trail += 1
        elif check_ma20_exit is not None and exit_cfg.enable_ma20_exit and check_ma20_exit(sym):
            reason = "TREND_EXIT_MA20"
            counts.ma20_exit += 1
        elif check_low10_exit is not None and exit_cfg.enable_low10_exit and check_low10_exit(sym):
            reason = "TREND_EXIT_LOW10"
            counts.low10_exit += 1
        elif max_hold_days > 0 and sym in entry_day and (day - entry_day[sym]).days >= max_hold_days:
            reason = "TIME_EXIT"

        if reason:
            exit_syms.add(sym)
            exits.append(Signal(
                signal_date=day,
                symbol=sym,
                side=Side.SELL,
                qty=int(qty),
                reason=reason,
                reason_code=reason,
                meta={"triggered_rule": reason, "atr_last": atr_v, "avg_cost": avg_cost},
            ))

    return exits, exit_syms, counts
