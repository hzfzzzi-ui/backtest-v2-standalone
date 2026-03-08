from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from backend.core.core.models import Signal
from backend.core.core.types import Side
from .base import Strategy


@dataclass(slots=True)
class BreakoutTrendStrategy(Strategy):
    breakout_window: int = 20
    enable_dual_breakout: bool = False
    breakout_window_short: int = 20
    breakout_window_long: int = 55
    breakout_entry_buffer_pct: float = 0.0
    # Entry quality controls
    # none | close_strength | volume_confirm | volatility_confirm
    entry_confirm_mode: str = "none"
    # none | t1_confirm | t2_confirm | pullback_confirm
    entry_delay_mode: str = "none"
    # Portfolio mode: equal_10 | equal_8 | equal_6 | profit_release
    portfolio_mode: str = "equal_10"
    order_size: int = 1000
    # Universe 过滤
    min_price: float = 0.0
    # 市场环境
    regime_ma: int = 60
    # V2 个股趋势过滤
    enable_v2_trend_filter: bool = True
    v2_trend_short_ma: int = 20
    v2_trend_long_ma: int = 60
    # ATR 退出
    enable_atr_stop: bool = True
    atr_stop_k: float = 2.0
    enable_atr_trail: bool = False
    atr_trail_k: float = 3.0
    # 止盈 / 固定止损
    enable_take_profit: bool = False
    take_profit_mode: str = "pct"
    take_profit_pct: float = 0.10
    take_profit_atr_k: float = 3.0
    enable_fixed_stop_loss: bool = False
    fixed_stop_loss_pct: float = 0.05
    # 时间退出
    max_hold_days: int = 0
    # 持仓约束 / 再入场约束
    min_hold_days: int = 0
    cooldown_days: int = 0
    min_hold_exempt_reasons: list[str] = field(default_factory=lambda: ["ATR_STOP_LOSS", "FIXED_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT"])
    # 趋势退出
    enable_ma20_exit: bool = False
    enable_low10_exit: bool = False
    # Regime 退出
    enable_risk_off_exit: bool = False
    # 动量排名选股
    momentum_top_pct: float = 0.0
    # 行业趋势门控
    enable_sector_gate: bool = False
    sector_rank_window: int = 60
    sector_top_pct: float = 0.30
    # Multi-alpha candidate expansion
    enable_pullback_candidates: bool = False
    pullback_variant_mode: str = "pb_reclaim_ma20"
    pullback_touch_lookback: int = 12
    pullback_reclaim_window: int = 3
    pullback_ma20_touch_band_pct: float = 0.01
    pullback_low_lookback: int = 10
    pullback_low_band_pct: float = 0.02
    pullback_box_window: int = 5
    pullback_box_range_pct_max: float = 0.08
    # Unified ranking
    enable_residual_ranking: bool = False
    residual_window: int = 60
    source_aware_residual_mode: str = "off"
    enable_sector_quality_ranking: bool = False
    sector_strength_window_short: int = 20
    sector_strength_window_long: int = 60
    volume_quality_window: int = 20
    residual_weight: float = 0.5
    sector_weight: float = 0.3
    quality_weight: float = 0.2

    def __post_init__(self) -> None:
        Strategy.__init__(self)

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, object]) -> list[Signal]:
        # Breakout 策略的信号生成由 BreakoutTrendProvider 矩阵引擎处理
        # 此方法仅作为 Strategy 接口的兼容实现
        return []
