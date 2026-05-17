from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.core.config.models import StrategyConfig
from .base import Strategy
from .ma_atr_stop import MAAtrStopStrategy
from .ma_trend_filter import MATrendFilterStrategy
from .ema_cross import EMACrossStrategy
from .sma_cross import SMACrossStrategy
from .sma_cross_regime import SMACrossRegimeStrategy
from .sma_cross_regime_atr import SMACrossRegimeATRStrategy
from .multifactor_signal import MultifactorSignalStrategy
from .volume_breakout import VolumeBreakoutStrategy
from .momentum_roc import MomentumROCStrategy
from .relative_strength import RelativeStrengthStrategy
from .bollinger_breakout import BollingerBreakoutStrategy
from .rsi_reversal import RSIReversalStrategy
from .regime_router import RegimeDetector, RegimeRouter
from .breakout_trend import BreakoutTrendStrategy
from .composite_strategy import CompositeStrategy
from .multi_alpha_strategy import MultiAlphaStrategy


StrategySupportClass = Literal["product-supported", "research-only", "deprecated"]


@dataclass(frozen=True, slots=True)
class StrategySurface:
    name: str
    classification: StrategySupportClass
    ui_reachable: bool
    api_compile_supported: bool
    runtime_execution_supported: bool
    script_only_reachable: bool
    notes: str = ""


STRATEGY_SUPPORT_MATRIX: dict[str, StrategySurface] = {
    "bollinger_breakout": StrategySurface(
        name="bollinger_breakout",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Registry-only research strategy; not part of the main V2 workbench contract.",
    ),
    "breakout_trend": StrategySurface(
        name="breakout_trend",
        classification="product-supported",
        ui_reachable=True,
        api_compile_supported=True,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Only provider-protocol strategy integrated into the production runtime.",
    ),
    "composite": StrategySurface(
        name="composite",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Kept for research parity and script-driven experiments only.",
    ),
    "ema_cross": StrategySurface(
        name="ema_cross",
        classification="product-supported",
        ui_reachable=True,
        api_compile_supported=True,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Mainline 9-stage product strategy.",
    ),
    "ma_atr_stop": StrategySurface(
        name="ma_atr_stop",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Script-only strategy; not exposed in the main workbench.",
    ),
    "ma_trend_filter": StrategySurface(
        name="ma_trend_filter",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Research-only trend-filter variant.",
    ),
    "momentum_roc": StrategySurface(
        name="momentum_roc",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Research-only ranking strategy.",
    ),
    "multifactor_signal": StrategySurface(
        name="multifactor_signal",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Script and parity-harness surface; not a product feature.",
    ),
    "regime_router": StrategySurface(
        name="regime_router",
        classification="product-supported",
        ui_reachable=True,
        api_compile_supported=True,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Mainline product regime strategy compiled from the 9-stage workbench.",
    ),
    "relative_strength": StrategySurface(
        name="relative_strength",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Research-only rotational strategy.",
    ),
    "rsi_reversal": StrategySurface(
        name="rsi_reversal",
        classification="research-only",
        ui_reachable=True,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Supported as regime_router MR arm, but not as a product-supported primary strategy.",
    ),
    "sma_cross": StrategySurface(
        name="sma_cross",
        classification="product-supported",
        ui_reachable=True,
        api_compile_supported=True,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Mainline 9-stage product strategy.",
    ),
    "sma_cross_regime": StrategySurface(
        name="sma_cross_regime",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Older regime variant retained for research and parity checks.",
    ),
    "sma_cross_regime_atr": StrategySurface(
        name="sma_cross_regime_atr",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Research-only parity strategy used by provider comparison tools.",
    ),
    "volume_breakout": StrategySurface(
        name="volume_breakout",
        classification="research-only",
        ui_reachable=False,
        api_compile_supported=False,
        runtime_execution_supported=True,
        script_only_reachable=True,
        notes="Registry-only research strategy.",
    ),
}


def get_strategy_surface(name: str) -> StrategySurface:
    key = str(name or "").strip().lower()
    if key not in STRATEGY_SUPPORT_MATRIX:
        raise ValueError(f"unknown strategy surface: {name}")
    return STRATEGY_SUPPORT_MATRIX[key]


def list_strategy_surfaces(
    classification: StrategySupportClass | None = None,
) -> list[StrategySurface]:
    items = sorted(STRATEGY_SUPPORT_MATRIX.values(), key=lambda item: item.name)
    if classification is None:
        return items
    return [item for item in items if item.classification == classification]


def product_supported_strategy_names() -> tuple[str, ...]:
    return tuple(item.name for item in list_strategy_surfaces("product-supported"))


def build_strategy(cfg: StrategyConfig) -> Strategy:
    name = cfg.name.lower()
    params = dict(cfg.params or {})
    if name == "adaptive_regime":
        raise ValueError("strategy 'adaptive_regime' has been removed; use 'regime_router'")
    if name == "sma_cross":
        _default_exempt = ["ATR_STOP_LOSS", "FIXED_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT", "TREND_BREAK_EXIT"]
        return SMACrossStrategy(
            fast=int(params.get("fast", cfg.fast)),
            slow=int(params.get("slow", cfg.slow)),
            order_size=int(params.get("order_size", cfg.order_size)),
            min_price=float(params.get("min_price", 0.0)),
            regime_ma=int(params.get("regime_ma", 60)),
            enable_v2_trend_filter=bool(params.get("enable_v2_trend_filter", False)),
            v2_trend_short_ma=int(params.get("v2_trend_short_ma", 20)),
            v2_trend_long_ma=int(params.get("v2_trend_long_ma", 60)),
            enable_atr_stop=bool(params.get("enable_atr_stop", False)),
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
            min_hold_exempt_reasons=list(params.get("min_hold_exempt_reasons", _default_exempt)),
            enable_ma20_exit=bool(params.get("enable_ma20_exit", False)),
            enable_low10_exit=bool(params.get("enable_low10_exit", False)),
            momentum_top_pct=float(params.get("momentum_top_pct", 0.0)),
            enable_sector_gate=bool(params.get("enable_sector_gate", False)),
            sector_rank_window=int(params.get("sector_rank_window", 60)),
            sector_top_pct=float(params.get("sector_top_pct", 0.30)),
        )
    if name == "ema_cross":
        return EMACrossStrategy(
            fast=int(params.get("fast", cfg.fast)),
            slow=int(params.get("slow", cfg.slow)),
            order_size=int(params.get("order_size", cfg.order_size)),
            min_price=float(params.get("min_price", 0.0)),
            regime_ma=int(params.get("regime_ma", 60)),
            enable_v2_trend_filter=bool(params.get("enable_v2_trend_filter", False)),
            v2_trend_short_ma=int(params.get("v2_trend_short_ma", 20)),
            v2_trend_long_ma=int(params.get("v2_trend_long_ma", 60)),
            enable_atr_stop=bool(params.get("enable_atr_stop", False)),
            atr_stop_k=float(params.get("atr_stop_k", 2.0)),
            enable_atr_trail=bool(params.get("enable_atr_trail", False)),
            atr_trail_k=float(params.get("atr_trail_k", 3.0)),
            enable_take_profit=bool(params.get("enable_take_profit", False)),
            take_profit_mode=str(params.get("take_profit_mode", "pct")),
            take_profit_pct=float(params.get("take_profit_pct", 0.10)),
            take_profit_atr_k=float(params.get("take_profit_atr_k", 3.0)),
            enable_fixed_stop_loss=bool(params.get("enable_fixed_stop_loss", False)),
            fixed_stop_loss_pct=float(params.get("fixed_stop_loss_pct", 0.05)),
            enable_entry_above_slow_ma=bool(params.get("enable_entry_above_slow_ma", False)),
            enable_entry_slow_ma_slope=bool(params.get("enable_entry_slow_ma_slope", False)),
            entry_slope_lookback=int(params.get("entry_slope_lookback", 5)),
            max_hold_days=int(params.get("max_hold_days", 0)),
            min_hold_days=int(params.get("min_hold_days", 0)),
            cooldown_days=int(params.get("cooldown_days", 0)),
            min_hold_exempt_reasons=list(params.get("min_hold_exempt_reasons", ["ATR_STOP_LOSS", "FIXED_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT", "TREND_BREAK_EXIT"])),
            enable_ma20_exit=bool(params.get("enable_ma20_exit", False)),
            enable_low10_exit=bool(params.get("enable_low10_exit", False)),
            momentum_top_pct=float(params.get("momentum_top_pct", 0.0)),
            enable_sector_gate=bool(params.get("enable_sector_gate", False)),
            sector_rank_window=int(params.get("sector_rank_window", 60)),
            sector_top_pct=float(params.get("sector_top_pct", 0.30)),
        )
    if name == "ma_trend_filter":
        return MATrendFilterStrategy(
            fast=int(params.get("fast", cfg.fast)),
            slow=int(params.get("slow", cfg.slow)),
            order_size=int(params.get("order_size", cfg.order_size)),
            trend_ma=int(params.get("trend_ma", cfg.trend_ma)),
            use_benchmark_regime=bool(params.get("use_benchmark_regime", cfg.use_benchmark_regime)),
        )
    if name == "ma_atr_stop":
        return MAAtrStopStrategy(
            fast=int(params.get("fast", cfg.fast)),
            slow=int(params.get("slow", cfg.slow)),
            order_size=int(params.get("order_size", cfg.order_size)),
            atr_n=int(params.get("atr_n", cfg.atr_n)),
            atr_k=float(params.get("atr_k", cfg.atr_k)),
        )
    if name == "sma_cross_regime":
        return SMACrossRegimeStrategy(
            fast=int(params.get("fast", cfg.fast)),
            slow=int(params.get("slow", cfg.slow)),
            order_size=int(params.get("order_size", cfg.order_size)),
            regime_ma=int(params.get("regime_ma", cfg.trend_ma)),
            benchmark_symbol=str(params.get("benchmark_symbol", "000300.SH")),
            entry_buffer=float(params.get("entry_buffer", 0.0)),
            buffer_mode=str(params.get("buffer_mode", "slow_ma")),
            enable_trend_filter=bool(params.get("enable_trend_filter", False)),
            enable_trend_tier=bool(params.get("enable_trend_tier", True)),
            enable_trend_accel=bool(params.get("enable_trend_accel", True)),
            enable_trend_break_exit=bool(params.get("enable_trend_break_exit", True)),
            trend_break_confirm_days=int(params.get("trend_break_confirm_days", 3)),
            trend_break_confirm_gap_pct=float(params.get("trend_break_confirm_gap_pct", 0.0)),
            trend_break_use_benchmark_regime=bool(params.get("trend_break_use_benchmark_regime", False)),
            trend_tier_mode=str(params.get("trend_tier_mode", "MA120_GT_MA200")),
            weak_trend_order_scale=float(params.get("weak_trend_order_scale", 0.5)),
            strong_trend_order_scale=float(params.get("strong_trend_order_scale", 1.0)),
            trend_fast_ma=int(params.get("trend_fast_ma", 120)),
            trend_slow_ma=int(params.get("trend_slow_ma", 200)),
            enable_trend_slope_filter=bool(params.get("enable_trend_slope_filter", False)),
            slope_lookback=int(params.get("slope_lookback", 5)),
            enable_trend_continuity_filter=bool(params.get("enable_trend_continuity_filter", False)),
            continuity_n=int(params.get("continuity_n", 10)),
        )
    if name == "sma_cross_regime_atr":
        return SMACrossRegimeATRStrategy(
            fast=int(params.get("fast", cfg.fast)),
            slow=int(params.get("slow", cfg.slow)),
            order_size=int(params.get("order_size", cfg.order_size)),
            regime_ma=int(params.get("regime_ma", 120)),
            benchmark_symbol=str(params.get("benchmark_symbol", "000300.SH")),
            entry_buffer=float(params.get("entry_buffer", 0.01)),
            buffer_mode=str(params.get("buffer_mode", "slow_ma")),
            enable_trend_filter=bool(params.get("enable_trend_filter", False)),
            enable_trend_tier=bool(params.get("enable_trend_tier", True)),
            enable_trend_accel=bool(params.get("enable_trend_accel", True)),
            enable_trend_break_exit=bool(params.get("enable_trend_break_exit", True)),
            trend_break_confirm_days=int(params.get("trend_break_confirm_days", 3)),
            trend_break_confirm_gap_pct=float(params.get("trend_break_confirm_gap_pct", 0.0)),
            trend_break_use_benchmark_regime=bool(params.get("trend_break_use_benchmark_regime", False)),
            trend_tier_mode=str(params.get("trend_tier_mode", "MA120_GT_MA200")),
            weak_trend_order_scale=float(params.get("weak_trend_order_scale", 0.5)),
            strong_trend_order_scale=float(params.get("strong_trend_order_scale", 1.0)),
            trend_fast_ma=int(params.get("trend_fast_ma", 120)),
            trend_slow_ma=int(params.get("trend_slow_ma", 200)),
            enable_trend_slope_filter=bool(params.get("enable_trend_slope_filter", False)),
            slope_lookback=int(params.get("slope_lookback", 5)),
            enable_trend_continuity_filter=bool(params.get("enable_trend_continuity_filter", False)),
            continuity_n=int(params.get("continuity_n", 10)),
            atr_n=int(params.get("atr_n", 14)),
            atr_stop_k=float(params.get("atr_stop_k", 2.0)),
            atr_trail_k=float(params.get("atr_trail_k", 3.0)),
            enable_atr_stop=bool(params.get("enable_atr_stop", False)),
            enable_atr_trail=bool(params.get("enable_atr_trail", False)),
            debug_atr=bool(params.get("debug_atr", False)),
        )
    if name == "multifactor_signal":
        # 独立的多因子信号策略
        return MultifactorSignalStrategy(
            benchmark_symbol=str(params.get("benchmark_symbol", "000300.SH")),
            buy_threshold=float(params.get("buy_threshold", 50.0)),
            sell_threshold=float(params.get("sell_threshold", 30.0)),
            max_hold_days=int(params.get("max_hold_days", 0)),
            min_data_days=int(params.get("min_data_days", 60)),
            rebalance_on_score_change=bool(params.get("rebalance_on_score_change", True)),
        )
    if name == "volume_breakout":
        # 量能突破策略
        return VolumeBreakoutStrategy(
            vol_ma_period=int(params.get("vol_ma_period", 20)),
            vol_mult=float(params.get("vol_mult", 1.5)),
            min_data_days=int(params.get("min_data_days", 30)),
        )
    if name == "momentum_roc":
        # 20日动量策略
        return MomentumROCStrategy(
            roc_period=int(params.get("roc_period", 20)),
            roc_threshold=float(params.get("roc_threshold", 0.0)),
            enable_roc_exit=bool(params.get("enable_roc_exit", False)),
            min_data_days=int(params.get("min_data_days", 30)),
        )
    if name == "relative_strength":
        # 相对强度策略
        return RelativeStrengthStrategy(
            rs_period=int(params.get("rs_period", 60)),
            rs_threshold=float(params.get("rs_threshold", 0.7)),
            min_data_days=int(params.get("min_data_days", 70)),
        )
    if name == "bollinger_breakout":
        # 布林带突破策略
        return BollingerBreakoutStrategy(
            bb_period=int(params.get("bb_period", 20)),
            bb_std_mult=float(params.get("bb_std_mult", 2.0)),
            enable_bb_mid_exit=bool(params.get("enable_bb_mid_exit", False)),
            min_data_days=int(params.get("min_data_days", 30)),
        )
    if name == "rsi_reversal":
        return RSIReversalStrategy(
            rsi_period=int(params.get("rsi_period", 6)),
            rsi_buy_threshold=float(params.get("rsi_buy_threshold", 20.0)),
            rsi_sell_threshold=float(params.get("rsi_sell_threshold", 80.0)),
            mr_max_hold_days=int(params.get("mr_max_hold_days", 5)),
            mr_stop_loss_pct=float(params.get("mr_stop_loss_pct", 0.03)),
            order_size=int(params.get("order_size", cfg.order_size)),
        )
    if name == "breakout_trend":
        _default_exempt = ["ATR_STOP_LOSS", "FIXED_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT"]
        return BreakoutTrendStrategy(
            breakout_window=int(params.get("breakout_window", 20)),
            enable_dual_breakout=bool(params.get("enable_dual_breakout", False)),
            breakout_window_short=int(params.get("breakout_window_short", 20)),
            breakout_window_long=int(params.get("breakout_window_long", 55)),
            dual_breakout_mode=str(params.get("dual_breakout_mode", "or") or "or").strip().lower(),
            dual_breakout_gate_ma_window=int(params.get("dual_breakout_gate_ma_window", 120)),
            dual_breakout_gate_slope_lookback=int(params.get("dual_breakout_gate_slope_lookback", 10)),
            breakout_entry_buffer_pct=float(params.get("breakout_entry_buffer_pct", 0.0)),
            entry_confirm_mode=str(params.get("entry_confirm_mode", "none")),
            entry_delay_mode=str(params.get("entry_delay_mode", "none")),
            enable_entry_gap_guard=bool(params.get("enable_entry_gap_guard", False)),
            entry_gap_guard_pct=float(params.get("entry_gap_guard_pct", 0.04)),
            enable_entry_above_slow_ma=bool(params.get("enable_entry_above_slow_ma", False)),
            enable_entry_slow_ma_slope=bool(params.get("enable_entry_slow_ma_slope", False)),
            entry_slope_lookback=int(params.get("entry_slope_lookback", 5)),
            portfolio_mode=str(params.get("portfolio_mode", "equal_10")),
            order_size=int(params.get("order_size", cfg.order_size)),
            min_price=float(params.get("min_price", 0.0)),
            regime_ma=int(params.get("regime_ma", 60)),
            enable_v2_trend_filter=bool(params.get("enable_v2_trend_filter", True)),
            v2_trend_short_ma=int(params.get("v2_trend_short_ma", 20)),
            v2_trend_long_ma=int(params.get("v2_trend_long_ma", 60)),
            enable_atr_stop=bool(params.get("enable_atr_stop", True)),
            atr_stop_k=float(params.get("atr_stop_k", 2.0)),
            enable_atr_trail=bool(params.get("enable_atr_trail", False)),
            atr_trail_k=float(params.get("atr_trail_k", 3.0)),
            trailing_activate_profit_pct=float(params.get("trailing_activate_profit_pct", 0.0)),
            segmented_trend_exit_mode=str(params.get("segmented_trend_exit_mode", "off") or "off").strip().lower(),
            segmented_mid_profit_pct=float(params.get("segmented_mid_profit_pct", 0.0)),
            segmented_high_profit_pct=float(params.get("segmented_high_profit_pct", 0.0)),
            segmented_high_trail_k=float(params.get("segmented_high_trail_k", params.get("atr_trail_k", 3.0))),
            enable_pre_profit_breakout_failure_exit=bool(params.get("enable_pre_profit_breakout_failure_exit", False)),
            pre_profit_breakout_failure_max_bars=int(params.get("pre_profit_breakout_failure_max_bars", 0)),
            pre_profit_breakout_failure_atr_buffer_k=float(params.get("pre_profit_breakout_failure_atr_buffer_k", 0.0)),
            enable_profit_decay_exit=bool(params.get("enable_profit_decay_exit", False)),
            profit_decay_exit_profit_pct=float(params.get("profit_decay_exit_profit_pct", 0.15)),
            profit_decay_exit_min_hold_bars=int(params.get("profit_decay_exit_min_hold_bars", 10)),
            profit_decay_exit_residual_score_threshold=float(params.get("profit_decay_exit_residual_score_threshold", 0.35)),
            enable_peak_giveback_ma20_exit=bool(params.get("enable_peak_giveback_ma20_exit", False)),
            peak_giveback_ma20_min_peak_profit_pct=float(
                params.get("peak_giveback_ma20_min_peak_profit_pct", 0.20)
            ),
            peak_giveback_ma20_min_giveback_pct=float(params.get("peak_giveback_ma20_min_giveback_pct", 0.25)),
            peak_giveback_ma20_min_hold_bars=int(params.get("peak_giveback_ma20_min_hold_bars", 10)),
            peak_giveback_ma20_exit_pct=float(params.get("peak_giveback_ma20_exit_pct", 0.5)),
            enable_mfe_mae_confirmation_exit=bool(params.get("enable_mfe_mae_confirmation_exit", False)),
            mfe_mae_confirmation_lookahead_bars=int(params.get("mfe_mae_confirmation_lookahead_bars", 3)),
            mfe_mae_confirmation_min_mfe_pct=float(params.get("mfe_mae_confirmation_min_mfe_pct", 0.02)),
            mfe_mae_confirmation_max_mae_pct=float(params.get("mfe_mae_confirmation_max_mae_pct", -0.05)),
            mfe_mae_confirmation_exit_pct=float(params.get("mfe_mae_confirmation_exit_pct", 0.5)),
            mfe_mae_confirmation_scope=str(params.get("mfe_mae_confirmation_scope", "all") or "all").strip().lower(),
            mfe_mae_confirmation_action=str(params.get("mfe_mae_confirmation_action", "exit") or "exit").strip().lower(),
            mfe_mae_high_chase_min_core_flags=int(params.get("mfe_mae_high_chase_min_core_flags", 2)),
            mfe_mae_high_chase_ret5_pct=float(params.get("mfe_mae_high_chase_ret5_pct", 0.20)),
            mfe_mae_high_chase_ret10_pct=float(params.get("mfe_mae_high_chase_ret10_pct", 0.30)),
            mfe_mae_high_chase_ret20_pct=float(params.get("mfe_mae_high_chase_ret20_pct", 0.45)),
            mfe_mae_high_chase_ma20_extension_pct=float(params.get("mfe_mae_high_chase_ma20_extension_pct", 0.27)),
            mfe_mae_high_chase_ma60_extension_pct=float(params.get("mfe_mae_high_chase_ma60_extension_pct", 0.45)),
            mfe_mae_high_chase_atr_extension=float(params.get("mfe_mae_high_chase_atr_extension", 4.5)),
            mfe_mae_high_chase_breakout_margin_pct=float(params.get("mfe_mae_high_chase_breakout_margin_pct", 0.05)),
            mfe_mae_high_chase_open_gap_pct=float(params.get("mfe_mae_high_chase_open_gap_pct", 0.024)),
            mfe_mae_high_chase_fade_pct=float(params.get("mfe_mae_high_chase_fade_pct", 0.025)),
            mfe_mae_high_chase_breakout_quality_max=float(params.get("mfe_mae_high_chase_breakout_quality_max", 0.46)),
            mfe_mae_high_chase_volume_price_quality_max=float(params.get("mfe_mae_high_chase_volume_price_quality_max", 0.08)),
            mfe_mae_watch_review_bars=int(params.get("mfe_mae_watch_review_bars", 10)),
            mfe_mae_watch_review_min_mfe_pct=float(params.get("mfe_mae_watch_review_min_mfe_pct", 0.02)),
            mfe_mae_watch_review_max_current_return_pct=float(params.get("mfe_mae_watch_review_max_current_return_pct", 0.0)),
            mfe_mae_watch_review_max_mae_pct=float(params.get("mfe_mae_watch_review_max_mae_pct", -0.05)),
            mfe_mae_watch_deep_mae_immediate_pct=float(params.get("mfe_mae_watch_deep_mae_immediate_pct", -0.08)),
            enable_mfe_mae_restore_candidate=bool(params.get("enable_mfe_mae_restore_candidate", False)),
            mfe_mae_restore_candidate_scope=str(params.get("mfe_mae_restore_candidate_scope", "high_chase") or "high_chase").strip().lower(),
            mfe_mae_restore_candidate_max_bars=int(params.get("mfe_mae_restore_candidate_max_bars", 40)),
            mfe_mae_restore_candidate_target_basis=str(params.get("mfe_mae_restore_candidate_target_basis", "original_target") or "original_target").strip().lower(),
            mfe_mae_restore_candidate_clear_on_fill=bool(params.get("mfe_mae_restore_candidate_clear_on_fill", True)),
            enable_take_profit=bool(params.get("enable_take_profit", False)),
            take_profit_mode=str(params.get("take_profit_mode", "pct")),
            take_profit_pct=float(params.get("take_profit_pct", 0.10)),
            take_profit_atr_k=float(params.get("take_profit_atr_k", 3.0)),
            enable_fixed_stop_loss=bool(params.get("enable_fixed_stop_loss", False)),
            fixed_stop_loss_pct=float(params.get("fixed_stop_loss_pct", 0.05)),
            max_hold_days=int(params.get("max_hold_days", 0)),
            min_hold_days=int(params.get("min_hold_days", 0)),
            cooldown_days=int(params.get("cooldown_days", 0)),
            min_hold_exempt_reasons=list(params.get("min_hold_exempt_reasons", _default_exempt)),
            enable_ma20_exit=bool(params.get("enable_ma20_exit", False)),
            enable_low10_exit=bool(params.get("enable_low10_exit", False)),
            enable_risk_off_exit=bool(params.get("enable_risk_off_exit", False)),
            risk_off_exit_mode=str(params.get("risk_off_exit_mode", "risk_on_off") or "risk_on_off").strip().lower(),
            risk_off_exit_partial_pct=float(params.get("risk_off_exit_partial_pct", 1.0)),
            risk_off_exit_partial_mode=str(params.get("risk_off_exit_partial_mode", "all_states") or "all_states").strip().lower(),
            risk_off_exit_partial_only_if_profitable=bool(params.get("risk_off_exit_partial_only_if_profitable", False)),
            risk_off_exit_trans_down_max_positions=int(params.get("risk_off_exit_trans_down_max_positions", 0)),
            risk_off_exit_trans_down_min_residual_score=float(params.get("risk_off_exit_trans_down_min_residual_score", 0.0)),
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
            ranking_mode=str(params.get("ranking_mode", "none") or "none"),
            leadership_route_bucket_count=int(params.get("leadership_route_bucket_count", 3)),
              breakout_quality_gate_min_score=float(params.get("breakout_quality_gate_min_score", 0.55)),
              breakout_quality_margin_cap_pct=float(params.get("breakout_quality_margin_cap_pct", 0.08)),
              breakout_quality_fade_cap_pct=float(params.get("breakout_quality_fade_cap_pct", 0.035)),
              breakout_quality_open_gap_cap_pct=float(params.get("breakout_quality_open_gap_cap_pct", 0.04)),
              bull_breakout_quality_veto_enabled=bool(params.get("bull_breakout_quality_veto_enabled", False)),
              bull_breakout_quality_veto_min_residual_strength_score=float(
                  params.get("bull_breakout_quality_veto_min_residual_strength_score", 0.0)
              ),
              bull_breakout_quality_veto_min_breakout_margin_score=float(
                  params.get("bull_breakout_quality_veto_min_breakout_margin_score", 0.0)
              ),
              bad_breakout_quality_veto_enabled=bool(params.get("bad_breakout_quality_veto_enabled", False)),
              bad_breakout_quality_ret5_rank_min=float(
                  params.get("bad_breakout_quality_ret5_rank_min", 0.80)
              ),
              bad_breakout_quality_r2_60_rank_max=float(
                  params.get("bad_breakout_quality_r2_60_rank_max", 0.20)
              ),
              trend_quality_soft_score_enabled=bool(params.get("trend_quality_soft_score_enabled", False)),
              trend_quality_soft_score_weight=float(params.get("trend_quality_soft_score_weight", 0.30)),
              trend_quality_r2_60_weight=float(params.get("trend_quality_r2_60_weight", 0.45)),
              trend_quality_slope60_weight=float(params.get("trend_quality_slope60_weight", 0.25)),
              trend_quality_ret60_vol_adj_weight=float(params.get("trend_quality_ret60_vol_adj_weight", 0.15)),
              trend_quality_ret60_dd_adj_weight=float(params.get("trend_quality_ret60_dd_adj_weight", 0.15)),
              risk_archetype_soft_deprioritize_enabled=bool(
                  params.get("risk_archetype_soft_deprioritize_enabled", False)
              ),
              risk_archetype_soft_deprioritize_quantile=float(
                  params.get("risk_archetype_soft_deprioritize_quantile", 0.80)
              ),
              risk_archetype_hot_crowded_penalty=float(
                  params.get("risk_archetype_hot_crowded_penalty", 0.20)
              ),
              risk_archetype_high_volatility_penalty=float(
                  params.get("risk_archetype_high_volatility_penalty", 0.15)
              ),
              entry_risk_position_sizing_enabled=bool(
                  params.get("entry_risk_position_sizing_enabled", False)
              ),
              entry_risk_position_watch_scale=float(
                  params.get("entry_risk_position_watch_scale", 0.80)
              ),
              entry_risk_position_high_scale=float(
                  params.get("entry_risk_position_high_scale", 0.50)
              ),
              entry_risk_position_extreme_scale=float(
                  params.get("entry_risk_position_extreme_scale", 1.0 / 3.0)
              ),
              residual_window_regime_mode=str(params.get("residual_window_regime_mode", "off")),
              residual_window_fallback=int(params.get("residual_window_fallback", params.get("residual_window", 60))),
              residual_window_regime_fast_ma=int(params.get("residual_window_regime_fast_ma", 120)),
            residual_window_regime_slow_ma=int(params.get("residual_window_regime_slow_ma", 200)),
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
    if name == "regime_router":
        trend_name = str(params.get("trend_strategy", "sma_cross")).lower()
        trend_params = dict(params.get("trend_params", {}))
        trend_params.setdefault("fast", params.get("fast", cfg.fast))
        trend_params.setdefault("slow", params.get("slow", cfg.slow))
        trend_params.setdefault("order_size", params.get("order_size", cfg.order_size))
        trend_strategy = build_strategy(StrategyConfig(name=trend_name, params=trend_params))

        mr_name = str(params.get("mr_strategy", "rsi_reversal")).lower()
        mr_params = dict(params.get("mr_params", {}))
        mr_params.setdefault("order_size", params.get("order_size", cfg.order_size))
        mr_strategy = build_strategy(StrategyConfig(name=mr_name, params=mr_params))

        detector = RegimeDetector(
            regime_ma=int(params.get("regime_ma", 60)),
        )
        router = RegimeRouter(
            detector=detector,
            trend_strategy=trend_strategy,
            mr_strategy=mr_strategy,
        )
        # 可选: RegimeFilter 三层趋势过滤器配置
        rf_cfg = params.get("regime_filter")
        if isinstance(rf_cfg, dict):
            router.regime_filter_cfg = rf_cfg  # type: ignore[attr-defined]
        return router
    if name == "composite":
        multi_alpha_cfg = params.get("multi_alpha")
        if isinstance(multi_alpha_cfg, dict):
            return MultiAlphaStrategy(
                multi_alpha=dict(multi_alpha_cfg),
                portfolio_mode=str(params.get("portfolio_mode", "hard_sleeve_budget") or "hard_sleeve_budget"),
            )
        # 组合策略
        sub_strategies = []
        strategies_config = params.get("strategies", [])
        for sub_cfg in strategies_config:
            sub_strategy = build_strategy(
                StrategyConfig(
                    name=sub_cfg.get("name", ""),
                    params=sub_cfg.get("params", {}),
                )
            )
            sub_strategies.append(sub_strategy)

        return CompositeStrategy(
            strategies=sub_strategies,
            combine_mode=str(params.get("combine_mode", "AND")),
            vote_threshold=float(params.get("vote_threshold", 0.5)),
            debug=bool(params.get("debug", False)),
            log_interval_days=int(params.get("log_interval_days", 0)),
        )
    raise ValueError(f"unsupported strategy: {cfg.name}")
