from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.models import ExitConfig
from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from backend.core.engine_vector.breakout_signal_provider import BreakoutTrendProvider
from backend.core.engine_vector.signal_provider import DayContext, DaySignals, ExitCounts
from backend.core.strategies.breakout_trend import BreakoutTrendStrategy
from backend.core.strategies.multi_alpha_strategy import MultiAlphaStrategy


@dataclass(frozen=True, slots=True)
class _ModuleSpec:
    name: str
    alpha_id: str
    family: str
    sleeve_id: str
    params: dict[str, Any]


def _normalized_symbol(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalized_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _safe_score(value: Any, *, fallback: float = 0.5) -> float:
    try:
        score = float(value)
    except Exception:
        return float(fallback)
    if np.isnan(score):
        return float(fallback)
    return float(score)


class MultiAlphaSignalProvider:
    """First-phase multi-alpha provider for regime-routed breakout + RSI."""

    def __init__(self) -> None:
        self.last_sell_day: dict[str, date] = {}
        self.entry_day: dict[str, date] = {}
        self.entry_day_overwrite: bool = True
        self._breakout_peak_state: dict[str, float] = {}
        self.peak_state_on_buy: dict[str, float] | None = self._breakout_peak_state
        self.extra_clear_dicts: list[dict] = [self._breakout_peak_state]

        self._strategy: MultiAlphaStrategy | None = None
        self._multi_alpha: dict[str, Any] = {}
        self._module_specs: dict[str, _ModuleSpec] = {}
        self._compose_mode: str = ""
        self._same_symbol_policy: str = ""
        self._regime_matrix: dict[str, list[str]] = {}
        self._history: pd.DataFrame = pd.DataFrame()
        self._history_by_day: dict[date, pd.DataFrame] = {}
        self._breakout_provider: BreakoutTrendProvider | None = None
        self._rsi_rows_by_day: dict[date, pd.DataFrame] = {}
        self._risk_on_map: dict[date, bool] = {}
        self._strong_risk_on_map: dict[date, bool] = {}
        self._market_state: np.ndarray = np.array([], dtype=np.int8)
        self._trade_mode: np.ndarray = np.array([], dtype=np.int8)
        self.precompute_seconds: float = 0.0

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
        if not isinstance(strategy, MultiAlphaStrategy):
            raise TypeError(f"multi-alpha runtime expects MultiAlphaStrategy, got {type(strategy)!r}")
        self._strategy = strategy
        self._multi_alpha = dict(strategy.multi_alpha or {})
        self._module_specs = self._build_module_specs()
        self._compose_mode = str(
            (self._multi_alpha.get("signal_composition") or {}).get("compose_mode", "") or ""
        ).strip().upper()
        self._same_symbol_policy = str(
            (self._multi_alpha.get("signal_composition") or {}).get("same_symbol_policy", "") or ""
        ).strip().upper()
        self._regime_matrix = {
            str(key or "").strip().upper(): [_normalized_name(name) for name in list(value or ())]
            for key, value in dict((self._multi_alpha.get("signal_composition") or {}).get("regime_matrix") or {}).items()
        }

        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"]).dt.normalize()
        hist["symbol"] = hist["symbol"].astype(str).str.lower()
        self._history = hist.sort_values(["date", "symbol"]).reset_index(drop=True)
        self._history_by_day = {
            pd.Timestamp(day_key).date(): group.copy()
            for day_key, group in self._history.groupby(self._history["date"].dt.date, sort=False)
        }

        day_list = list(trading_days)
        self._build_regime_maps(benchmark=benchmark, trading_days=day_list)

        breakout_spec = self._module_specs.get("breakout_55")
        if breakout_spec is not None:
            breakout_strategy = self._build_breakout_strategy(breakout_spec)
            breakout_provider = BreakoutTrendProvider()
            breakout_provider.precompute(
                history=history,
                benchmark=benchmark,
                raw_history=raw_history,
                trading_days=day_list,
                strategy=breakout_strategy,
                exit_cfg=kwargs.get("exit_cfg") or ExitConfig(),
                st_history=kwargs.get("st_history"),
                strength_ma=int(kwargs.get("strength_ma", 120) or 120),
                base_order_value=float(kwargs.get("base_order_value", 0.0) or 0.0),
                sector_data=kwargs.get("sector_data"),
                industry_map=kwargs.get("industry_map"),
                industry_history=kwargs.get("industry_history"),
                history_lookback_days=kwargs.get("history_lookback_days"),
                enable_multifactor_rank=bool(kwargs.get("enable_multifactor_rank", False)),
                mf_rank_gate_mode=str(kwargs.get("mf_rank_gate_mode") or "ALWAYS_ON"),
                market_filter_cfg=kwargs.get("market_filter_cfg"),
                benchmark_regime_cfg=kwargs.get("benchmark_regime_cfg"),
                sizing_cfg=kwargs.get("sizing_cfg"),
                risk_budget_cfg=kwargs.get("risk_budget_cfg"),
                regime_filter_cfg=getattr(breakout_strategy, "regime_filter_cfg", None),
            )
            breakout_provider.last_sell_day = self.last_sell_day
            breakout_provider.entry_day = self.entry_day
            breakout_provider._peak_close_state = self._breakout_peak_state
            breakout_provider.peak_state_on_buy = self._breakout_peak_state
            breakout_provider.extra_clear_dicts = [self._breakout_peak_state]
            self._breakout_provider = breakout_provider

        rsi_spec = self._module_specs.get("rsi_reversal")
        if rsi_spec is not None:
            self._rsi_rows_by_day = self._build_rsi_rows_by_day(self._history, rsi_spec)

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals:
        regime_tag = self._resolve_regime_tag(day)
        enabled_modules = set(self._enabled_modules_for_regime(regime_tag))
        raw_alpha_signals: list[Signal] = []
        composed_buy_signals: list[Signal] = []
        composed_sell_signals: list[Signal] = []
        strength_map: dict[str, float] = {}
        mf_score_map: dict[str, float] = {}
        diagnostics: dict[str, Any] = {
            "composition_enabled": True,
            "composition_mode": self._compose_mode,
            "regime_tag": regime_tag,
            "enabled_modules": sorted(enabled_modules),
            "holding_source_count": int(len(ctx.holding_sources)),
        }
        conflict_resolution_count = 0
        suppressed_by_regime = 0
        aggregated_exit_counts = ExitCounts()

        breakout_spec = self._module_specs.get("breakout_55")
        if breakout_spec is not None and self._breakout_provider is not None:
            breakout_ctx = self._filtered_ctx_for_alpha(ctx, alpha_id=breakout_spec.alpha_id)
            breakout_day = self._breakout_provider.day_signals(day, day_idx, breakout_ctx)
            self._accumulate_exit_counts(aggregated_exit_counts, breakout_day.exit_counts)
            for sig in breakout_day.sell_signals:
                raw_sig = self._tag_signal(
                    sig,
                    alpha_id=breakout_spec.alpha_id,
                    alpha_family=breakout_spec.family,
                    sleeve_id=breakout_spec.sleeve_id,
                    raw_score=0.0,
                )
                raw_alpha_signals.append(raw_sig)
                composed_sell_signals.append(
                    self._tag_signal(
                        raw_sig,
                        alpha_id=breakout_spec.alpha_id,
                        alpha_family=breakout_spec.family,
                        sleeve_id=breakout_spec.sleeve_id,
                        compose_score=0.0,
                        regime_tag=regime_tag,
                        enabled_by_policy=True,
                        exit_owner="source_only",
                    )
                )
            for sig in breakout_day.buy_signals:
                raw_score = _safe_score((sig.meta or {}).get("final_score"))
                raw_sig = self._tag_signal(
                    sig,
                    alpha_id=breakout_spec.alpha_id,
                    alpha_family=breakout_spec.family,
                    sleeve_id=breakout_spec.sleeve_id,
                    raw_score=raw_score,
                )
                raw_alpha_signals.append(raw_sig)
                if "breakout_55" not in enabled_modules:
                    suppressed_by_regime += 1
                    continue
                composed = self._tag_signal(
                    raw_sig,
                    alpha_id=breakout_spec.alpha_id,
                    alpha_family=breakout_spec.family,
                    sleeve_id=breakout_spec.sleeve_id,
                    compose_score=raw_score,
                    regime_tag=regime_tag,
                    enabled_by_policy=True,
                )
                composed_buy_signals.append(composed)
                strength_map[_normalized_symbol(composed.symbol)] = float(raw_score)
                mf_score_map[_normalized_symbol(composed.symbol)] = float(raw_score)

        rsi_spec = self._module_specs.get("rsi_reversal")
        if rsi_spec is not None:
            for raw_sig in self._build_rsi_raw_signals(day, ctx, rsi_spec):
                raw_alpha_signals.append(raw_sig)
                if raw_sig.side == Side.SELL:
                    composed_sell_signals.append(
                        self._tag_signal(
                            raw_sig,
                            alpha_id=rsi_spec.alpha_id,
                            alpha_family=rsi_spec.family,
                            sleeve_id=rsi_spec.sleeve_id,
                            compose_score=0.0,
                            regime_tag=regime_tag,
                            enabled_by_policy=True,
                            exit_owner="source_only",
                        )
                    )
                    continue
                if "rsi_reversal" not in enabled_modules:
                    suppressed_by_regime += 1
                    continue
                compose_score = _safe_score((raw_sig.meta or {}).get("raw_score"))
                composed = self._tag_signal(
                    raw_sig,
                    alpha_id=rsi_spec.alpha_id,
                    alpha_family=rsi_spec.family,
                    sleeve_id=rsi_spec.sleeve_id,
                    compose_score=compose_score,
                    regime_tag=regime_tag,
                    enabled_by_policy=True,
                )
                composed_buy_signals.append(composed)
                strength_map[_normalized_symbol(composed.symbol)] = float(compose_score)
                mf_score_map[_normalized_symbol(composed.symbol)] = float(compose_score)

        composed_buy_signals, conflict_resolution_count = self._apply_same_symbol_policy(
            composed_buy_signals,
            same_symbol_policy=self._same_symbol_policy,
        )
        strength_map = {
            _normalized_symbol(sig.symbol): _safe_score((sig.meta or {}).get("compose_score"))
            for sig in composed_buy_signals
        }
        mf_score_map = dict(strength_map)
        diagnostics["suppressed_raw_alpha_signal_count"] = int(suppressed_by_regime)
        diagnostics["conflict_resolution_count"] = int(conflict_resolution_count)
        diagnostics["raw_buy_signal_count"] = int(sum(1 for sig in raw_alpha_signals if sig.side == Side.BUY))
        diagnostics["buy_candidate_count"] = int(len(composed_buy_signals))
        diagnostics["after_held_filter_count"] = int(len(composed_buy_signals))
        diagnostics["source_only_exit_count"] = int(
            sum(1 for sig in composed_sell_signals if str((sig.meta or {}).get("exit_owner", "") or "") == "source_only")
        )
        diagnostics["global_risk_override_count"] = int(
            sum(1 for sig in composed_sell_signals if str((sig.meta or {}).get("exit_owner", "") or "") == "global_risk_override")
        )

        return DaySignals(
            sell_signals=self._dedupe_sell_signals(composed_sell_signals),
            buy_signals=composed_buy_signals,
            raw_alpha_signals=raw_alpha_signals,
            composed_sell_signals=composed_sell_signals,
            composed_buy_signals=composed_buy_signals,
            exit_syms={_normalized_symbol(sig.symbol) for sig in composed_sell_signals},
            strength_map=strength_map,
            mf_score_map=mf_score_map,
            mf_gate_on_today=False,
            strong_risk_on=bool(self._strong_risk_on_map.get(day, False)),
            exit_counts=aggregated_exit_counts,
            diagnostics=diagnostics,
        )

    def _build_module_specs(self) -> dict[str, _ModuleSpec]:
        specs: dict[str, _ModuleSpec] = {}
        modules = list((self._multi_alpha.get("signal_generation") or {}).get("modules") or ())
        for module in modules:
            name = _normalized_name(module.get("name"))
            if not name:
                continue
            family = str(module.get("family", "") or "").strip().lower()
            if not family:
                family = "trend" if name == "breakout_55" else "mean_revert"
            sleeve_id = "trend" if family == "trend" else "mr"
            specs[name] = _ModuleSpec(
                name=name,
                alpha_id=str(module.get("alpha_id", name) or name),
                family=family,
                sleeve_id=sleeve_id,
                params=dict(module.get("params") or {}),
            )
        return specs

    def _build_breakout_strategy(self, spec: _ModuleSpec) -> BreakoutTrendStrategy:
        params = dict(spec.params or {})
        return BreakoutTrendStrategy(
            breakout_window=int(params.get("breakout_window", 55)),
            enable_dual_breakout=bool(params.get("enable_dual_breakout", False)),
            breakout_window_short=int(params.get("breakout_window_short", 20)),
            breakout_window_long=int(params.get("breakout_window_long", 55)),
            breakout_entry_buffer_pct=float(params.get("breakout_entry_buffer_pct", 0.0)),
            entry_confirm_mode=str(params.get("entry_confirm_mode", "none")),
            entry_delay_mode=str(params.get("entry_delay_mode", "none")),
            portfolio_mode=str(params.get("portfolio_mode", "equal_10")),
            order_size=int(params.get("order_size", 1000)),
            min_price=float(params.get("min_price", 0.0)),
            regime_ma=int(params.get("regime_ma", 60)),
            enable_v2_trend_filter=bool(params.get("enable_v2_trend_filter", True)),
            v2_trend_short_ma=int(params.get("v2_trend_short_ma", 20)),
            v2_trend_long_ma=int(params.get("v2_trend_long_ma", 60)),
            enable_atr_stop=bool(params.get("enable_atr_stop", True)),
            atr_stop_k=float(params.get("atr_stop_k", 2.0)),
            enable_atr_trail=bool(params.get("enable_atr_trail", False)),
            atr_trail_k=float(params.get("atr_trail_k", 3.0)),
            enable_take_profit=bool(params.get("enable_take_profit", False)),
            take_profit_mode=str(params.get("take_profit_mode", "pct")),
            take_profit_pct=float(params.get("take_profit_pct", 0.10)),
            take_profit_atr_k=float(params.get("take_profit_atr_k", 3.0)),
            enable_fixed_stop_loss=bool(params.get("enable_fixed_stop_loss", False)),
            fixed_stop_loss_pct=float(params.get("fixed_stop_loss_pct", 0.05)),
            max_hold_days=int(params.get("max_hold_days", 0)),
            min_hold_days=int(params.get("min_hold_days", 0)),
            cooldown_days=int(params.get("cooldown_days", 0)),
            enable_ma20_exit=bool(params.get("enable_ma20_exit", False)),
            enable_low10_exit=bool(params.get("enable_low10_exit", False)),
            enable_risk_off_exit=bool(params.get("enable_risk_off_exit", False)),
            momentum_top_pct=float(params.get("momentum_top_pct", 0.0)),
            enable_sector_gate=bool(params.get("enable_sector_gate", False)),
            sector_rank_window=int(params.get("sector_rank_window", 60)),
            sector_top_pct=float(params.get("sector_top_pct", 0.30)),
            enable_pullback_candidates=bool(params.get("enable_pullback_candidates", False)),
            pullback_variant_mode=str(params.get("pullback_variant_mode", "pb_reclaim_ma20")),
            pullback_touch_lookback=int(params.get("pullback_touch_lookback", 12)),
            pullback_reclaim_window=int(params.get("pullback_reclaim_window", 3)),
            pullback_ma20_touch_band_pct=float(params.get("pullback_ma20_touch_band_pct", 0.01)),
            pullback_low_lookback=int(params.get("pullback_low_lookback", 10)),
            pullback_low_band_pct=float(params.get("pullback_low_band_pct", 0.02)),
            pullback_box_window=int(params.get("pullback_box_window", 5)),
            pullback_box_range_pct_max=float(params.get("pullback_box_range_pct_max", 0.08)),
            enable_residual_ranking=bool(params.get("enable_residual_ranking", False)),
            residual_window=int(params.get("residual_window", 60)),
            residual_benchmark_weight=float(params.get("residual_benchmark_weight", 0.5)),
            residual_industry_weight=float(params.get("residual_industry_weight", 0.5)),
            industry_relative_mode=str(params.get("industry_relative_mode", "sector_proxy") or "sector_proxy"),
            industry_relative_regime_mode=str(
                params.get("industry_relative_regime_mode", "off") or "off"
            ),
            residual_weight_regime_mode=str(params.get("residual_weight_regime_mode", "off")),
            residual_benchmark_weight_fallback=float(
                params.get("residual_benchmark_weight_fallback", params.get("residual_benchmark_weight", 0.5))
            ),
            residual_industry_weight_fallback=float(
                params.get("residual_industry_weight_fallback", params.get("residual_industry_weight", 0.5))
            ),
            source_aware_residual_mode=str(params.get("source_aware_residual_mode", "off")),
            residual_refine_mode=str(params.get("residual_refine_mode", "off")),
            residual_refine_weight=float(params.get("residual_refine_weight", 0.0)),
            industry_second_stage_min_industry_score=float(
                params.get("industry_second_stage_min_industry_score", 0.85)
            ),
            enable_sector_quality_ranking=bool(params.get("enable_sector_quality_ranking", False)),
            sector_strength_window_short=int(params.get("sector_strength_window_short", 20)),
            sector_strength_window_long=int(params.get("sector_strength_window_long", 60)),
            volume_quality_window=int(params.get("volume_quality_window", 20)),
            residual_weight=float(params.get("residual_weight", 0.5)),
            sector_weight=float(params.get("sector_weight", 0.3)),
            quality_weight=float(params.get("quality_weight", 0.2)),
        )

    def _build_regime_maps(self, *, benchmark: pd.DataFrame, trading_days: list[date]) -> None:
        day_count = len(trading_days)
        self._market_state = np.zeros(day_count, dtype=np.int8)
        self._trade_mode = np.zeros(day_count, dtype=np.int8)
        self._risk_on_map = {day: True for day in trading_days}
        self._strong_risk_on_map = {day: False for day in trading_days}
        if benchmark.empty or not trading_days:
            return

        bench = benchmark.copy()
        bench["date"] = pd.to_datetime(bench["date"]).dt.normalize()
        bench = bench.sort_values("date")
        close = pd.Series(pd.to_numeric(bench["close"], errors="coerce").to_numpy(dtype=float), index=bench["date"])
        day_index = pd.DatetimeIndex(pd.to_datetime([pd.Timestamp(day).normalize() for day in trading_days]))
        close = close.reindex(day_index)
        ma60 = close.rolling(60, min_periods=60).mean()
        ma120 = close.rolling(120, min_periods=120).mean()
        ma200 = close.rolling(200, min_periods=200).mean()
        risk_on = (close > ma60).fillna(True).to_numpy(dtype=bool)
        strong = (ma120 > ma200).fillna(False).to_numpy(dtype=bool)
        market_state = np.full(day_count, 1, dtype=np.int8)
        market_state[strong] = 0
        market_state[~risk_on & strong] = 2
        market_state[~risk_on & ~strong] = 3
        trade_mode = np.where(market_state == 0, 0, np.where(market_state == 3, 2, 1)).astype(np.int8)
        self._market_state = market_state
        self._trade_mode = trade_mode
        self._risk_on_map = {day: bool(risk_on[idx]) for idx, day in enumerate(trading_days)}
        self._strong_risk_on_map = {day: bool(strong[idx]) for idx, day in enumerate(trading_days)}

    def _build_rsi_rows_by_day(self, history: pd.DataFrame, spec: _ModuleSpec) -> dict[date, pd.DataFrame]:
        params = dict(spec.params or {})
        period = max(2, int(params.get("rsi_period", 6)))
        hist = history.copy()
        hist = hist[~hist["symbol"].astype(str).str.lower().str.startswith("bench:")]
        hist["close"] = pd.to_numeric(hist["close"], errors="coerce")
        hist = hist.dropna(subset=["close"]).sort_values(["symbol", "date"]).reset_index(drop=True)
        delta = hist.groupby("symbol", sort=False)["close"].diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)
        hist["avg_gain"] = gain.groupby(hist["symbol"], sort=False).transform(
            lambda series: series.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        )
        hist["avg_loss"] = loss.groupby(hist["symbol"], sort=False).transform(
            lambda series: series.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        )
        rs = hist["avg_gain"] / hist["avg_loss"].replace(0.0, np.nan)
        hist["rsi"] = 100.0 - 100.0 / (1.0 + rs)
        hist["rsi_prev"] = hist.groupby("symbol", sort=False)["rsi"].shift(1)
        rows_by_day: dict[date, pd.DataFrame] = {}
        for day_key, group in hist.groupby(hist["date"].dt.date, sort=False):
            rows_by_day[pd.Timestamp(day_key).date()] = group[["symbol", "close", "rsi", "rsi_prev"]].copy()
        return rows_by_day

    def _resolve_regime_tag(self, day: date) -> str:
        strong = bool(self._strong_risk_on_map.get(day, False))
        risk_on = bool(self._risk_on_map.get(day, True))
        if strong:
            return "TREND_UP"
        if risk_on:
            return "RANGE"
        return "WEAK_DOWN"

    def _enabled_modules_for_regime(self, regime_tag: str) -> list[str]:
        configured = list(self._regime_matrix.get(regime_tag, ()))
        if configured:
            return configured
        return list(self._module_specs.keys())

    def _filtered_ctx_for_alpha(self, ctx: DayContext, *, alpha_id: str) -> DayContext:
        positions = {
            symbol: int(qty)
            for symbol, qty in ctx.positions.items()
            if int(qty) > 0 and self._holding_source_alpha(ctx, symbol) == alpha_id
        }
        position_avg_cost = {
            symbol: float(ctx.position_avg_cost.get(symbol, 0.0))
            for symbol in positions
        }
        holding_sources = {
            symbol: ctx.holding_sources.get(symbol)
            for symbol in positions
            if ctx.holding_sources.get(symbol) is not None
        }
        return DayContext(
            positions=positions,
            position_avg_cost=position_avg_cost,
            cash=ctx.cash,
            nav=ctx.nav,
            base_order_value=ctx.base_order_value,
            max_positions=ctx.max_positions,
            close_idx=ctx.close_idx,
            open_idx=ctx.open_idx,
            next_day=ctx.next_day,
            holding_sources=holding_sources,
            risk_on=ctx.risk_on,
            market_state=ctx.market_state,
        )

    def _holding_source_alpha(self, ctx: DayContext, symbol: str) -> str:
        snapshot = ctx.holding_sources.get(_normalized_symbol(symbol))
        if snapshot is None:
            return ""
        return str(snapshot.entry_alpha_id or "")

    def _build_rsi_raw_signals(self, day: date, ctx: DayContext, spec: _ModuleSpec) -> list[Signal]:
        params = dict(spec.params or {})
        buy_threshold = float(params.get("rsi_buy_threshold", 20.0))
        sell_threshold = float(params.get("rsi_sell_threshold", 80.0))
        max_hold_days = int(params.get("mr_max_hold_days", params.get("max_hold_days", 5)))
        stop_loss_pct = float(params.get("mr_stop_loss_pct", params.get("stop_loss_pct", 0.03)))
        order_size = int(params.get("order_size", 1000))
        rows = self._rsi_rows_by_day.get(day)
        if rows is None or rows.empty:
            return []
        out: list[Signal] = []
        position_map = {
            _normalized_symbol(symbol): Position(
                symbol=_normalized_symbol(symbol),
                total_qty=int(qty),
                sellable_qty=int(qty),
                avg_cost=float(ctx.position_avg_cost.get(_normalized_symbol(symbol), 0.0)),
            )
            for symbol, qty in ctx.positions.items()
            if int(qty) > 0
        }
        for row in rows.itertuples(index=False):
            symbol = _normalized_symbol(row.symbol)
            rsi_now = float(row.rsi) if not pd.isna(row.rsi) else np.nan
            rsi_prev = float(row.rsi_prev) if not pd.isna(row.rsi_prev) else np.nan
            close_today = float(row.close) if not pd.isna(row.close) else 0.0
            if np.isnan(rsi_now) or np.isnan(rsi_prev) or close_today <= 0:
                continue

            has_pos = symbol in position_map and position_map[symbol].total_qty > 0
            meta = {
                "close": round(close_today, 6),
                "rsi_value": round(rsi_now, 2),
                "rsi_prev": round(rsi_prev, 2),
            }
            if has_pos and self._holding_source_alpha(ctx, symbol) == spec.alpha_id:
                sell_reason = ""
                if rsi_prev >= sell_threshold and rsi_now < sell_threshold:
                    sell_reason = "MR_RSI_OVERBOUGHT_SELL"
                else:
                    avg_cost = float(ctx.position_avg_cost.get(symbol, 0.0) or 0.0)
                    if avg_cost > 0 and close_today <= avg_cost * (1.0 - stop_loss_pct):
                        sell_reason = "MR_STOP_LOSS"
                    elif max_hold_days > 0 and symbol in self.entry_day:
                        if (day - self.entry_day[symbol]).days >= max_hold_days:
                            sell_reason = "MR_TIME_EXIT"
                if sell_reason:
                    out.append(
                        Signal(
                            signal_date=day,
                            symbol=symbol,
                            side=Side.SELL,
                            qty=int(position_map[symbol].sellable_qty),
                            reason=sell_reason,
                            reason_code=sell_reason,
                            meta={
                                **meta,
                                "triggered_rule": sell_reason,
                                "held_days": (day - self.entry_day.get(symbol, day)).days,
                            },
                        )
                    )
                continue

            if has_pos:
                continue
            if not (rsi_prev <= buy_threshold and rsi_now > buy_threshold):
                continue
            raw_score = max(0.0, min(1.0, (buy_threshold - rsi_prev) / max(buy_threshold, 1.0)))
            out.append(
                Signal(
                    signal_date=day,
                    symbol=symbol,
                    side=Side.BUY,
                    qty=order_size,
                    reason="MR_RSI_OVERSOLD_BUY",
                    reason_code="MR_RSI_OVERSOLD_BUY",
                    meta={
                        **meta,
                        "triggered_rule": "MR_RSI_OVERSOLD_BUY",
                        "raw_score": float(raw_score),
                    },
                )
            )
        return out

    def _tag_signal(
        self,
        signal: Signal,
        *,
        alpha_id: str,
        alpha_family: str,
        sleeve_id: str,
        raw_score: float | None = None,
        compose_score: float | None = None,
        regime_tag: str = "",
        enabled_by_policy: bool | None = None,
        conflict_resolution: str = "",
        exit_owner: str = "",
    ) -> Signal:
        meta = dict(signal.meta or {})
        meta["alpha_id"] = alpha_id
        meta["alpha_family"] = alpha_family
        meta["alpha_source"] = alpha_id
        meta["sleeve_id"] = sleeve_id
        meta["entry_alpha_id"] = alpha_id
        meta["entry_sleeve_id"] = sleeve_id
        meta["entry_reason_code"] = str(signal.reason_code or signal.reason or "")
        if raw_score is not None:
            meta["raw_score"] = float(raw_score)
        if compose_score is not None:
            meta["compose_score"] = float(compose_score)
        if regime_tag:
            meta["regime_tag"] = regime_tag
        if enabled_by_policy is not None:
            meta["enabled_by_policy"] = bool(enabled_by_policy)
        if conflict_resolution:
            meta["conflict_resolution"] = conflict_resolution
        if exit_owner:
            meta["exit_owner"] = str(exit_owner)
        return Signal(
            signal_date=signal.signal_date,
            symbol=_normalized_symbol(signal.symbol),
            side=signal.side,
            qty=int(signal.qty),
            action=str(signal.action or ""),
            reason=str(signal.reason or ""),
            reason_code=str(signal.reason_code or ""),
            meta=meta,
        )

    def _apply_same_symbol_policy(
        self,
        buy_signals: list[Signal],
        *,
        same_symbol_policy: str,
    ) -> tuple[list[Signal], int]:
        if same_symbol_policy != "PREFER_HIGHER_SCORE":
            return buy_signals, 0
        grouped: dict[str, list[Signal]] = {}
        for sig in buy_signals:
            grouped.setdefault(_normalized_symbol(sig.symbol), []).append(sig)
        resolved: list[Signal] = []
        conflict_count = 0
        for symbol in sorted(grouped):
            group = grouped[symbol]
            if len(group) == 1:
                resolved.append(group[0])
                continue
            conflict_count += 1
            winner = sorted(
                group,
                key=lambda sig: (
                    -_safe_score((sig.meta or {}).get("compose_score")),
                    str((sig.meta or {}).get("alpha_id", "")),
                    str(sig.reason_code or ""),
                ),
            )[0]
            resolved.append(
                self._tag_signal(
                    winner,
                    alpha_id=str((winner.meta or {}).get("alpha_id", "") or ""),
                    alpha_family=str((winner.meta or {}).get("alpha_family", "") or ""),
                    sleeve_id=str((winner.meta or {}).get("sleeve_id", "") or ""),
                    raw_score=_safe_score((winner.meta or {}).get("raw_score"), fallback=0.0),
                    compose_score=_safe_score((winner.meta or {}).get("compose_score"), fallback=0.0),
                    regime_tag=str((winner.meta or {}).get("regime_tag", "") or ""),
                    enabled_by_policy=bool((winner.meta or {}).get("enabled_by_policy", True)),
                    conflict_resolution="prefer_higher_score",
                    exit_owner=str((winner.meta or {}).get("exit_owner", "") or ""),
                )
            )
        return resolved, conflict_count

    def _dedupe_sell_signals(self, sell_signals: list[Signal]) -> list[Signal]:
        best_by_symbol: dict[str, Signal] = {}
        for sig in sell_signals:
            symbol = _normalized_symbol(sig.symbol)
            current = best_by_symbol.get(symbol)
            if current is None:
                best_by_symbol[symbol] = sig
                continue
            current_key = (
                0 if str((current.meta or {}).get("exit_owner", "") or "") == "global_risk_override" else 1,
                str((current.meta or {}).get("alpha_id", "")),
                str(current.reason_code or ""),
            )
            new_key = (
                0 if str((sig.meta or {}).get("exit_owner", "") or "") == "global_risk_override" else 1,
                str((sig.meta or {}).get("alpha_id", "")),
                str(sig.reason_code or ""),
            )
            if new_key < current_key:
                best_by_symbol[symbol] = sig
        return [best_by_symbol[symbol] for symbol in sorted(best_by_symbol)]

    def _accumulate_exit_counts(self, dst: ExitCounts, src: ExitCounts) -> None:
        dst.atr_stop += int(src.atr_stop)
        dst.atr_trail += int(src.atr_trail)
        dst.take_profit += int(src.take_profit)
        dst.fixed_stop_loss += int(src.fixed_stop_loss)
        dst.ma20_exit += int(src.ma20_exit)
        dst.low10_exit += int(src.low10_exit)
        dst.profit_decay_exit += int(src.profit_decay_exit)
