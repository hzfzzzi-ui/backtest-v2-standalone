"""Vectorized regime router signal provider façade."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from backend.core.config.models import ExitConfig
from backend.core.core.models import Signal
from backend.core.core.types import Side
from backend.core.engine_vector.market_filter_gate import resolve_mf_gate_on_today
from backend.core.engine_vector.regime_router_day_routes import (
    run_regime_router_exits_only_route,
    run_regime_router_light_route,
    run_regime_router_mr_route,
    run_regime_router_perstock_route,
    run_regime_router_trend_route,
)
from backend.core.engine_vector.regime_router_precompute import (
    precompute_regime_router_provider,
)
from backend.core.engine_vector.signal_provider import (
    DayContext,
    DaySignals,
    ExitCounts,
    evaluate_engine_exits,
)


class RegimeRouterSignalProvider:
    """Façade provider for the regime router route."""

    def __init__(self) -> None:
        self.extra_clear_dicts: list[dict] = []
        self.last_sell_day: dict[str, date] | None = None
        self.entry_day: dict[str, date] = {}
        self.entry_day_overwrite: bool = False
        self.peak_state_on_buy: dict[str, float] | None = None

        self._config: Any = None
        self._runtime_state: Any = None
        self._mx: Any = None
        self._feats: Any = None
        self._sma_buy_ok: np.ndarray = np.array([])
        self._sma_sell_ok: np.ndarray = np.array([])
        self._rsi_buy: np.ndarray = np.array([])
        self._rsi_overbought: np.ndarray = np.array([])
        self._sma_cand_idx: list[np.ndarray] = []
        self._rsi_cand_idx: list[np.ndarray] = []
        self._bench_close: np.ndarray = np.array([])
        self._regime_on: np.ndarray = np.array([])
        self._use_regime_filter: bool = False
        self._regime_filter: Any = None
        self._risk_on_exits: np.ndarray = np.array([])
        self._strong_risk_on: np.ndarray = np.array([])
        self._sym_to_col: dict[str, int] = {}

        self._use_market_filter: bool = False
        self._market_state: np.ndarray = np.array([])
        self._trade_mode: np.ndarray = np.array([])
        self._ema_light_buy_ok: np.ndarray = np.array([])
        self._ema_light_sell_ok: np.ndarray = np.array([])
        self._ema_light_cand_idx: list[np.ndarray] = []
        self._regime_engine_name: str = "ma200_legacy"
        self._formal_regime_features: Any = None
        self._required_feature_blocks_ready: np.ndarray = np.array([], dtype=bool)
        self._regime_confidence_arr: np.ndarray = np.array([], dtype=float)
        self._regime_duration_bars_arr: np.ndarray = np.array([], dtype=np.int32)
        self._regime_transition_reason_arr: np.ndarray = np.array([], dtype=object)
        self._feature_availability_arr: np.ndarray = np.array([], dtype=object)
        self._fallback_active_arr: np.ndarray = np.array([], dtype=bool)

        self._atr_lookup: dict[str, dict[date, float]] = {}
        self._need_atr: bool = False

        self._ec: ExitConfig = ExitConfig()
        self._atr_stop_k: float = 2.0
        self._peak_close_state: dict[str, float] = {}

        self._fast: int = 5
        self._slow: int = 20
        self._trend_order_size: int = 1000
        self._mr_rsi_period: int = 6
        self._mr_rsi_buy_threshold: float = 20.0
        self._mr_rsi_sell_threshold: float = 80.0
        self._mr_max_hold_days: int = 5
        self._mr_stop_loss_pct: float = 0.03
        self._mr_order_size: int = 1000
        self._ma_type: str = "SMA"

        self._mr_symbols: set[str] = set()
        self._mr_entry_day: dict[str, date] = {}
        self._mr_entry_price: dict[str, float] = {}

        self._enable_multifactor_rank: bool = False
        self._mf_rank_gate_mode: str = "ALWAYS_ON"

        self.total_buy_signals: int = 0
        self.blocked_by_trend_count: int = 0
        self.regime_trend_days: int = 0
        self.regime_mr_days: int = 0
        self.mr_rsi_oversold_buy_count: int = 0
        self.mr_rsi_overbought_sell_count: int = 0
        self.mr_stop_loss_count: int = 0
        self.mr_time_exit_count: int = 0
        self.atr_stop_exit_count: int = 0
        self.atr_trail_exit_count: int = 0
        self.atr_trail_update_count: int = 0
        self.take_profit_exit_count: int = 0
        self.fixed_stop_loss_exit_count: int = 0
        self.precompute_seconds: float = 0.0
        self.diag_reason_counts: dict[str, int] = {}

        self.market_state_bull_days: int = 0
        self.market_state_bear_days: int = 0
        self.market_state_trans_down_days: int = 0
        self.market_state_trans_up_days: int = 0
        self.trade_mode_main_days: int = 0
        self.trade_mode_light_days: int = 0
        self.trade_mode_notrade_days: int = 0

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
        precompute_regime_router_provider(
            self,
            history=history,
            benchmark=benchmark,
            raw_history=raw_history,
            trading_days=trading_days,
            strategy=strategy,
            **kwargs,
        )

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        i = day_idx
        positions = ctx.positions
        position_avg_cost = ctx.position_avg_cost
        close_idx = ctx.close_idx

        if self._use_market_filter:
            if self._use_regime_filter:
                regime_row = self._regime_on[i]
                regime_on_global = bool(np.any(regime_row))
            else:
                regime_on_global = bool(self._regime_on[i])
        elif self._use_regime_filter:
            regime_row = self._regime_on[i]
            regime_on_global = bool(np.any(regime_row))
            trend_count = int(np.sum(regime_row))
            mr_count = int(len(regime_row)) - trend_count
            if trend_count >= mr_count:
                self.regime_trend_days += 1
            else:
                self.regime_mr_days += 1
        else:
            regime_on_global = bool(self._regime_on[i])
            if regime_on_global:
                self.regime_trend_days += 1
            else:
                self.regime_mr_days += 1

        positions_before_sell = int(sum(1 for qty in positions.values() if int(qty) > 0))
        exit_rule_sells, exit_rule_syms, ecounts, _fragility_diagnostics = evaluate_engine_exits(
            positions=positions,
            day=day,
            close_idx=close_idx,
            position_avg_cost=position_avg_cost,
            peak_state=self._peak_close_state,
            entry_day=self.entry_day,
            exit_cfg=self._ec,
            get_atr=lambda sym, trading_day: (self._atr_lookup.get(sym) or {}).get(trading_day)
            if self._need_atr
            else None,
            risk_on=bool(self._risk_on_exits[i]),
            max_hold_days=0,
            atr_stop_k=self._atr_stop_k,
        )
        self.atr_stop_exit_count += ecounts.atr_stop
        self.atr_trail_exit_count += ecounts.atr_trail
        self.take_profit_exit_count += ecounts.take_profit
        self.fixed_stop_loss_exit_count += ecounts.fixed_stop_loss

        sell_sigs: list[Signal] = list(exit_rule_sells)
        buy_sigs: list[Signal] = []

        market_state_name = ""
        trade_mode_name = ""
        market_state_names = ("BULL", "TRANS_DOWN", "TRANS_UP", "BEAR")
        trade_mode_names = ("TREND_MAIN", "TREND_LIGHT", "NO_TRADE")

        if self._use_market_filter:
            market_state_value = int(self._market_state[i])
            trade_mode_value = int(self._trade_mode[i])
            market_state_name = (
                market_state_names[market_state_value]
                if market_state_value < len(market_state_names)
                else "BULL"
            )
            trade_mode_name = (
                trade_mode_names[trade_mode_value]
                if trade_mode_value < len(trade_mode_names)
                else "NO_TRADE"
            )

            if market_state_value == 0:
                self.market_state_bull_days += 1
            elif market_state_value == 1:
                self.market_state_trans_down_days += 1
            elif market_state_value == 2:
                self.market_state_trans_up_days += 1
            else:
                self.market_state_bear_days += 1

            if trade_mode_value == 0:
                self.trade_mode_main_days += 1
                self._day_signals_trend(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
            elif trade_mode_value == 1:
                self.trade_mode_light_days += 1
                self._day_signals_light(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
            else:
                self.trade_mode_notrade_days += 1
                self._day_signals_exits_only(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)

            if trade_mode_value == 2:
                self.regime_mr_days += 1
            else:
                self.regime_trend_days += 1
        elif self._use_regime_filter:
            self._day_signals_perstock(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
        elif regime_on_global:
            self._day_signals_trend(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)
        else:
            self._day_signals_mr(i, day, positions, close_idx, exit_rule_syms, sell_sigs, buy_sigs)

        pending_buy_syms = {sig.symbol for sig in buy_sigs if sig.side == Side.BUY}
        to_remove = [
            sym
            for sym in self._mr_symbols
            if sym not in pending_buy_syms and (sym not in positions or int(positions.get(sym, 0)) <= 0)
        ]
        for sym in to_remove:
            self._mr_symbols.discard(sym)
            self._mr_entry_day.pop(sym, None)
            self._mr_entry_price.pop(sym, None)

        strong_risk_on_today = bool(self._strong_risk_on[i])
        mf_gate_on_today = resolve_mf_gate_on_today(
            enable_multifactor_rank=self._enable_multifactor_rank,
            mf_rank_gate_mode=self._mf_rank_gate_mode,
            risk_on_today=True,
            strong_risk_on_today=strong_risk_on_today,
        )

        if self._use_market_filter and market_state_name:
            for sig in buy_sigs:
                sig.meta["market_state"] = market_state_name
                sig.meta["trade_mode"] = trade_mode_name
            for sig in sell_sigs:
                if "market_state" not in sig.meta:
                    sig.meta["market_state"] = market_state_name
                    sig.meta["trade_mode"] = trade_mode_name

        diagnostics: dict[str, Any] = {
            "positions_before_sell": positions_before_sell,
            "raw_buy_signal_count": len(buy_sigs),
            "buy_candidate_count": len(buy_sigs),
            "after_held_filter_count": len(buy_sigs),
            "market_state": market_state_name,
            "trade_mode": trade_mode_name,
        }
        if i < len(self._regime_confidence_arr):
            diagnostics["regime_engine"] = str(self._regime_engine_name or "ma200_legacy")
            diagnostics["regime_confidence"] = float(self._regime_confidence_arr[i])
            diagnostics["regime_duration_bars"] = int(self._regime_duration_bars_arr[i]) if i < len(self._regime_duration_bars_arr) else 0
            diagnostics["regime_transition_reason"] = str(self._regime_transition_reason_arr[i] or "")
            diagnostics["feature_availability"] = self._feature_availability_arr[i] if i < len(self._feature_availability_arr) else {}
            diagnostics["fallback_active"] = bool(self._fallback_active_arr[i]) if i < len(self._fallback_active_arr) else False

        if self._use_market_filter and market_state_name:
            for sig in buy_sigs:
                sig.meta["market_state"] = market_state_name
                sig.meta["trade_mode"] = trade_mode_name
                sig.meta["regime_engine"] = str(self._regime_engine_name or "ma200_legacy")
                if i < len(self._regime_confidence_arr):
                    sig.meta["regime_confidence"] = float(self._regime_confidence_arr[i])
                    sig.meta["regime_duration_bars"] = int(self._regime_duration_bars_arr[i])
                    sig.meta["regime_transition_reason"] = str(self._regime_transition_reason_arr[i] or "")
            for sig in sell_sigs:
                if "market_state" not in sig.meta:
                    sig.meta["market_state"] = market_state_name
                    sig.meta["trade_mode"] = trade_mode_name
                sig.meta["regime_engine"] = str(self._regime_engine_name or "ma200_legacy")
                if i < len(self._regime_confidence_arr):
                    sig.meta["regime_confidence"] = float(self._regime_confidence_arr[i])
                    sig.meta["regime_duration_bars"] = int(self._regime_duration_bars_arr[i])
                    sig.meta["regime_transition_reason"] = str(self._regime_transition_reason_arr[i] or "")

        return DaySignals(
            sell_signals=sell_sigs,
            buy_signals=buy_sigs,
            exit_syms=exit_rule_syms,
            strength_map={},
            mf_score_map={},
            mf_gate_on_today=mf_gate_on_today,
            strong_risk_on=strong_risk_on_today,
            exit_counts=ecounts,
            diagnostics=diagnostics,
        )

    def _day_signals_trend(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        run_regime_router_trend_route(
            self,
            i,
            day,
            positions,
            close_idx,
            exit_rule_syms,
            sell_sigs,
            buy_sigs,
        )

    def _day_signals_mr(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        run_regime_router_mr_route(
            self,
            i,
            day,
            positions,
            close_idx,
            exit_rule_syms,
            sell_sigs,
            buy_sigs,
        )

    def _day_signals_light(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        run_regime_router_light_route(
            self,
            i,
            day,
            positions,
            close_idx,
            exit_rule_syms,
            sell_sigs,
            buy_sigs,
        )

    def _day_signals_exits_only(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        run_regime_router_exits_only_route(
            self,
            i,
            day,
            positions,
            close_idx,
            exit_rule_syms,
            sell_sigs,
            buy_sigs,
        )

    def _day_signals_perstock(
        self,
        i: int,
        day: date,
        positions: dict[str, int],
        close_idx: dict[tuple[date, str], float],
        exit_rule_syms: set[str],
        sell_sigs: list[Signal],
        buy_sigs: list[Signal],
    ) -> None:
        run_regime_router_perstock_route(
            self,
            i,
            day,
            positions,
            close_idx,
            exit_rule_syms,
            sell_sigs,
            buy_sigs,
        )
