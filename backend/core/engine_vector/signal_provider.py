"""信号提供者协议与共享数据类。

定义 SignalProvider Protocol 和引擎↔信号提供者之间的数据传输类型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Signal
from backend.core.core.types import Side


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

_STABLE_SIGNAL_DIAGNOSTIC_DEFAULTS: dict[str, Any] = {
    "composition_enabled": False,
    "composition_mode": "",
    "raw_alpha_signal_count": 0,
    "composed_buy_signal_count": 0,
    "composed_sell_signal_count": 0,
    "suppressed_raw_alpha_signal_count": 0,
    "conflict_resolution_count": 0,
    "source_only_exit_count": 0,
    "global_risk_override_count": 0,
    "bull_breakout_quality_veto_applied": False,
    "bull_breakout_quality_veto_block_count": 0,
    "bull_breakout_quality_veto_residual_block_count": 0,
    "bull_breakout_quality_veto_margin_block_count": 0,
}


@dataclass(frozen=True, slots=True)
class HoldingSourceSnapshot:
    """持仓来源归因快照。"""

    entry_alpha_id: str = ""
    entry_sleeve_id: str = ""
    entry_reason_code: str = ""
    entry_date: date | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta or {})))

    @classmethod
    def from_value(cls, value: Any) -> "HoldingSourceSnapshot":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                entry_alpha_id=str(value.get("entry_alpha_id", "") or ""),
                entry_sleeve_id=str(value.get("entry_sleeve_id", "") or ""),
                entry_reason_code=str(value.get("entry_reason_code", "") or ""),
                entry_date=value.get("entry_date"),
                meta=dict(value.get("meta") or {}),
            )
        raise TypeError(f"unsupported holding source snapshot: {type(value)!r}")

@dataclass(slots=True)
class ExitCounts:
    """各引擎级退出规则的触发计数。"""
    atr_stop: int = 0
    atr_trail: int = 0
    take_profit: int = 0
    fixed_stop_loss: int = 0
    ma20_exit: int = 0
    low10_exit: int = 0
    profit_decay_exit: int = 0


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
    holding_sources: Mapping[str, HoldingSourceSnapshot] = field(default_factory=dict)
    asset_context: Mapping[str, Any] = field(default_factory=dict)
    risk_on: bool = True
    market_state: str = ""

    def __post_init__(self) -> None:
        frozen_sources: dict[str, HoldingSourceSnapshot] = {}
        for symbol, source in dict(self.holding_sources or {}).items():
            frozen_sources[str(symbol).lower()] = HoldingSourceSnapshot.from_value(source)
        object.__setattr__(self, "holding_sources", MappingProxyType(frozen_sources))
        object.__setattr__(self, "asset_context", MappingProxyType(dict(self.asset_context or {})))


@dataclass(slots=True)
class DaySignals:
    """信号提供者的逐日输出。"""
    sell_signals: list[Signal]
    buy_signals: list[Signal]
    raw_alpha_signals: list[Signal] = field(default_factory=list)
    composed_sell_signals: list[Signal] = field(default_factory=list)
    composed_buy_signals: list[Signal] = field(default_factory=list)
    exit_syms: set[str] = field(default_factory=set)
    strength_map: dict[str, float] = field(default_factory=dict)
    mf_score_map: dict[str, float] = field(default_factory=dict)
    mf_gate_on_today: bool = False
    overlay_score_map: dict[str, float] = field(default_factory=dict)
    overlay_gate_on_today: bool = False
    overlay_mode: str = "off"
    overlay_observation_date: date | None = None
    overlay_score_source: str = ""
    strong_risk_on: bool = False
    exit_counts: ExitCounts = field(default_factory=ExitCounts)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provided = dict(self.diagnostics or {})
        diagnostics = dict(_STABLE_SIGNAL_DIAGNOSTIC_DEFAULTS)
        diagnostics.update(provided)
        if "raw_alpha_signal_count" not in provided:
            diagnostics["raw_alpha_signal_count"] = int(len(self.raw_alpha_signals))
        if "composed_buy_signal_count" not in provided:
            diagnostics["composed_buy_signal_count"] = int(len(self.composed_buy_signals))
        if "composed_sell_signal_count" not in provided:
            diagnostics["composed_sell_signal_count"] = int(len(self.composed_sell_signals))
        if "suppressed_raw_alpha_signal_count" not in provided:
            diagnostics["suppressed_raw_alpha_signal_count"] = max(
                int(len(self.raw_alpha_signals))
                - int(len(self.composed_buy_signals) + len(self.composed_sell_signals)),
                0,
            )
        if "composition_enabled" not in provided:
            diagnostics["composition_enabled"] = bool(
                self.raw_alpha_signals or self.composed_buy_signals or self.composed_sell_signals
            )
        object.__setattr__(self, "diagnostics", diagnostics)


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
    entry_bar_index: dict[str, int] | None = None,
    current_bar_index: int | None = None,
    entry_breakout_floor: dict[str, float] | None = None,
    exit_cfg: ExitConfig,
    get_atr: Callable[[str, date], float | None],
    risk_on: bool = True,
    enable_risk_off_exit: bool = True,
    risk_off_exit_mode: str = "risk_on_off",
    risk_off_exit_partial_pct: float = 1.0,
    risk_off_exit_partial_mode: str = "all_states",
    risk_off_exit_partial_only_if_profitable: bool = False,
    risk_off_partial_state: dict[str, bool] | None = None,
    market_state: str = "",
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
    trailing_activate_profit_pct = float(getattr(exit_cfg, "trailing_activate_profit_pct", 0.0) or 0.0)
    segmented_trend_exit_mode = str(getattr(exit_cfg, "segmented_trend_exit_mode", "off") or "off").strip().lower()
    segmented_mid_profit_pct = float(getattr(exit_cfg, "segmented_mid_profit_pct", 0.0) or 0.0)
    segmented_high_profit_pct = float(getattr(exit_cfg, "segmented_high_profit_pct", 0.0) or 0.0)
    segmented_high_trail_k = float(getattr(exit_cfg, "segmented_high_trail_k", getattr(exit_cfg, "atr_trail_k", 3.0)) or getattr(exit_cfg, "atr_trail_k", 3.0))
    enable_pre_profit_breakout_failure_exit = bool(getattr(exit_cfg, "enable_pre_profit_breakout_failure_exit", False))
    pre_profit_breakout_failure_max_bars = int(getattr(exit_cfg, "pre_profit_breakout_failure_max_bars", 0) or 0)
    pre_profit_breakout_failure_atr_buffer_k = float(getattr(exit_cfg, "pre_profit_breakout_failure_atr_buffer_k", 0.0) or 0.0)

    def _resolve_risk_off_exit_qty(held_qty: int) -> int:
        held = max(int(held_qty), 0)
        if held <= 0:
            return 0
        try:
            partial_pct = float(risk_off_exit_partial_pct)
        except Exception:
            partial_pct = 1.0
        if partial_pct <= 0.0 or partial_pct >= 1.0:
            return held
        lot_size = 100
        if held <= lot_size:
            return held
        planned = int(held * partial_pct)
        qty = max((planned // lot_size) * lot_size, lot_size)
        qty = min(qty, held)
        remain = held - qty
        if 0 < remain < lot_size:
            return held
        return max(qty, lot_size)

    partial_mode_norm = str(risk_off_exit_partial_mode or "all_states").strip().lower()
    partial_state = risk_off_partial_state if isinstance(risk_off_partial_state, dict) else {}

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
        pnl_pct = (cclose / avg_cost - 1.0) if (avg_cost > 0 and cclose > 0) else 0.0
        breakout_floor = float((entry_breakout_floor or {}).get(sym, 0.0) or 0.0)
        breakout_failure_floor = (
            float(breakout_floor - pre_profit_breakout_failure_atr_buffer_k * atr_v)
            if breakout_floor > 0.0 and atr_v is not None and pre_profit_breakout_failure_atr_buffer_k > 0.0
            else float(breakout_floor)
        )
        entry_idx = (entry_bar_index or {}).get(sym) if isinstance(entry_bar_index, dict) else None
        bars_since_entry = (
            int(current_bar_index) - int(entry_idx)
            if current_bar_index is not None and entry_idx is not None
            else None
        )
        effective_enable_atr_trail = bool(exit_cfg.enable_atr_trail)
        effective_atr_trail_k = float(exit_cfg.atr_trail_k)
        effective_trailing_activate_profit_pct = trailing_activate_profit_pct
        effective_enable_ma20_exit = bool(exit_cfg.enable_ma20_exit)
        effective_enable_low10_exit = bool(exit_cfg.enable_low10_exit)
        trend_exit_stage = "base"

        if segmented_trend_exit_mode in {"ma20", "low10", "chandelier"}:
            effective_enable_atr_trail = False
            effective_enable_ma20_exit = False
            effective_enable_low10_exit = False
            if segmented_trend_exit_mode == "chandelier":
                effective_trailing_activate_profit_pct = max(segmented_mid_profit_pct, 0.0)
                if pnl_pct >= segmented_high_profit_pct > 0.0:
                    effective_enable_atr_trail = bool(exit_cfg.enable_atr_trail)
                    effective_atr_trail_k = float(segmented_high_trail_k)
                    effective_trailing_activate_profit_pct = max(segmented_high_profit_pct, 0.0)
                    trend_exit_stage = "high_profit"
                elif pnl_pct >= segmented_mid_profit_pct > 0.0:
                    effective_enable_atr_trail = bool(exit_cfg.enable_atr_trail)
                    effective_atr_trail_k = float(exit_cfg.atr_trail_k)
                    effective_trailing_activate_profit_pct = max(segmented_mid_profit_pct, 0.0)
                    trend_exit_stage = "mid_profit"
                else:
                    trend_exit_stage = "pre_profit"
            else:
                effective_trailing_activate_profit_pct = max(segmented_high_profit_pct, 0.0)
                if pnl_pct >= segmented_high_profit_pct > 0.0:
                    effective_enable_atr_trail = bool(exit_cfg.enable_atr_trail)
                    effective_atr_trail_k = float(segmented_high_trail_k)
                    trend_exit_stage = "high_profit"
                    if segmented_trend_exit_mode == "ma20":
                        effective_enable_ma20_exit = True
                    else:
                        effective_enable_low10_exit = True
                elif pnl_pct >= segmented_mid_profit_pct > 0.0:
                    trend_exit_stage = "mid_profit"
                    if segmented_trend_exit_mode == "ma20":
                        effective_enable_ma20_exit = True
                    else:
                        effective_enable_low10_exit = True
                else:
                    trend_exit_stage = "pre_profit"

        reason = ""
        risk_off_mode = str(risk_off_exit_mode or "risk_on_off").strip().lower()
        market_state_norm = str(market_state or "").strip().upper()
        risk_off_triggered = False
        if enable_risk_off_exit:
            if risk_off_mode == "bear_only":
                risk_off_triggered = market_state_norm == "BEAR"
            elif risk_off_mode == "trans_down_freeze_bear_exit":
                risk_off_triggered = market_state_norm == "BEAR"
            elif risk_off_mode == "trans_down_topk_bear_exit":
                risk_off_triggered = market_state_norm == "BEAR"
            elif risk_off_mode == "trans_down_residual_floor_bear_exit":
                risk_off_triggered = market_state_norm == "BEAR"
            elif risk_off_mode == "trans_down_residual_profit_floor_bear_exit":
                risk_off_triggered = market_state_norm == "BEAR"
            elif risk_off_mode == "trans_down_residual_ma20_floor_bear_exit":
                risk_off_triggered = market_state_norm == "BEAR"
            elif risk_off_mode == "trans_down_or_bear":
                risk_off_triggered = market_state_norm in {"TRANS_DOWN", "BEAR"}
            else:
                risk_off_triggered = not risk_on
        if risk_off_triggered:
            reason = "RISK_OFF_EXIT"
        elif (
            enable_pre_profit_breakout_failure_exit
            and trailing_activate_profit_pct > 0.0
            and pnl_pct < trailing_activate_profit_pct
            and pre_profit_breakout_failure_max_bars > 0
            and bars_since_entry is not None
            and 0 <= int(bars_since_entry) <= pre_profit_breakout_failure_max_bars
            and breakout_floor > 0.0
            and cclose < breakout_failure_floor
        ):
            reason = "PRE_PROFIT_BREAKOUT_FAILURE_EXIT"
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
        elif (
            effective_enable_atr_trail
            and atr_v is not None
            and (effective_trailing_activate_profit_pct <= 0.0 or pnl_pct >= effective_trailing_activate_profit_pct)
            and cclose <= float(peak_state.get(sym, cclose) - effective_atr_trail_k * atr_v)
        ):
            reason = "ATR_TRAIL_EXIT"
            counts.atr_trail += 1
        elif check_ma20_exit is not None and effective_enable_ma20_exit and check_ma20_exit(sym):
            reason = "TREND_EXIT_MA20"
            counts.ma20_exit += 1
        elif check_low10_exit is not None and effective_enable_low10_exit and check_low10_exit(sym):
            reason = "TREND_EXIT_LOW10"
            counts.low10_exit += 1
        elif max_hold_days > 0 and sym in entry_day and (day - entry_day[sym]).days >= max_hold_days:
            reason = "TIME_EXIT"

        if reason:
            exit_qty = int(qty)
            meta = {
                "triggered_rule": reason,
                "atr_last": atr_v,
                "avg_cost": avg_cost,
                "pnl_pct": pnl_pct,
                "entry_breakout_floor": breakout_floor if breakout_floor > 0.0 else None,
                "effective_breakout_failure_floor": breakout_failure_floor if breakout_floor > 0.0 else None,
                "bars_since_entry": int(bars_since_entry) if bars_since_entry is not None else None,
                "pre_profit_breakout_failure_max_bars": int(pre_profit_breakout_failure_max_bars),
                "pre_profit_breakout_failure_atr_buffer_k": float(pre_profit_breakout_failure_atr_buffer_k),
                "trailing_activate_profit_pct": effective_trailing_activate_profit_pct,
                "segmented_trend_exit_mode": segmented_trend_exit_mode,
                "segmented_mid_profit_pct": segmented_mid_profit_pct,
                "segmented_high_profit_pct": segmented_high_profit_pct,
                "segmented_high_trail_k": segmented_high_trail_k,
                "effective_atr_trail_k": effective_atr_trail_k,
                "trend_exit_stage": trend_exit_stage,
            }
            if reason == "RISK_OFF_EXIT":
                allow_partial = True
                partial_state_seen = bool(partial_state.get(sym, False))
                if partial_mode_norm in {"trans_down_only", "trans_down"}:
                    allow_partial = market_state_norm == "TRANS_DOWN"
                elif partial_mode_norm == "first_trans_down_then_full":
                    allow_partial = market_state_norm == "TRANS_DOWN" and not partial_state_seen
                profit_gate_passed = pnl_pct > 0.0
                if allow_partial and bool(risk_off_exit_partial_only_if_profitable):
                    allow_partial = profit_gate_passed
                exit_qty = _resolve_risk_off_exit_qty(int(qty)) if allow_partial else int(qty)
                meta["risk_off_exit_partial_pct"] = float(risk_off_exit_partial_pct)
                meta["risk_off_exit_partial_mode"] = partial_mode_norm
                meta["risk_off_exit_partial_only_if_profitable"] = bool(risk_off_exit_partial_only_if_profitable)
                meta["risk_off_partial_state_seen"] = partial_state_seen
                meta["risk_off_partial_profit_gate_passed"] = bool(profit_gate_passed)
                meta["partial_exit"] = bool(exit_qty < int(qty))
                if partial_mode_norm == "first_trans_down_then_full":
                    meta["risk_off_partial_mark_on_fill"] = bool(exit_qty < int(qty))
            exit_syms.add(sym)
            exits.append(Signal(
                signal_date=day,
                symbol=sym,
                side=Side.SELL,
                qty=int(exit_qty),
                reason=reason,
                reason_code=reason,
                meta=meta,
            ))

    return exits, exit_syms, counts
