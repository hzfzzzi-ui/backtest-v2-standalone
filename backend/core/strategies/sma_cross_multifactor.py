"""
SMA Cross + 多因子融合策略

在原有SMA Cross Regime ATR策略基础上，增加多因子信号评分，
根据综合评分决定买入优先级和订单金额。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.core.core.models import Position, Signal
from backend.core.core.types import Side
from .sma_cross_regime_atr import SMACrossRegimeATRStrategy
from .factors import compute_multifactor_score
from .signal_fusion import fuse_signal, rank_signals, get_fusion_config_template


@dataclass(slots=True)
class SMACrossMultifactorStrategy(SMACrossRegimeATRStrategy):
    """
    SMA Cross + 多因子融合策略

    继承SMACrossRegimeATR策略的所有功能，并添加：
    1. 多因子综合评分（成交量、动量、相对强度、布林带）
    2. 信号融合逻辑（根据评分决定买入优先级）
    3. 动态订单金额（根据信号强度调整订单大小）

    新增参数：
        enable_multifactor: 是否启用多因子评分
        fusion_mode: 融合模式（balanced/aggressive/conservative/custom）
        custom_fusion_config: 自定义融合配置
    """

    # 多因子相关参数
    enable_multifactor: bool = True
    fusion_mode: str = "balanced"  # balanced/aggressive/conservative/custom
    custom_fusion_config: dict | None = None

    def __post_init__(self) -> None:
        SMACrossRegimeATRStrategy.__post_init__(self)

        # DEBUG: 强制验证参数
        if not hasattr(self, 'enable_multifactor'):
            raise RuntimeError("enable_multifactor field is missing!")
        if not hasattr(self, 'fusion_mode'):
            raise RuntimeError("fusion_mode field is missing!")

        print(f"\n[MULTIFACTOR INIT] Strategy instance created:")
        print(f"  Instance ID: {id(self)}")
        print(f"  enable_multifactor: {self.enable_multifactor}")
        print(f"  fusion_mode: '{self.fusion_mode}'")
        print(f"  Type check: enable_multifactor is {type(self.enable_multifactor).__name__}, fusion_mode is {type(self.fusion_mode).__name__}")

        # 初始化融合配置
        if self.fusion_mode == "aggressive":
            from .signal_fusion import get_aggressive_config

            self.fusion_config = get_aggressive_config()
            print(f"  ✓ Using AGGRESSIVE config (min_threshold={self.fusion_config.get('min_score_threshold')})")
        elif self.fusion_mode == "conservative":
            from .signal_fusion import get_conservative_config

            self.fusion_config = get_conservative_config()
            print(f"  ✓ Using CONSERVATIVE config (min_threshold={self.fusion_config.get('min_score_threshold')})")
        elif self.fusion_mode == "custom" and self.custom_fusion_config:
            self.fusion_config = self.custom_fusion_config
            print(f"  ✓ Using CUSTOM config")
        else:  # balanced
            self.fusion_config = get_fusion_config_template()
            print(f"  ✓ Using BALANCED config (min_threshold={self.fusion_config.get('min_score_threshold')})")

        # 存储每日的多因子评分（用于RS排名）
        self.state.setdefault("daily_multifactor_scores", {})

    def generate_signals(self, day: date, history: pd.DataFrame, positions: dict[str, Position]) -> list[Signal]:
        """
        生成信号（重写父类方法）

        流程：
        1. 调用父类方法获取基础信号（SMA金叉/死叉）
        2. 对买入信号进行多因子评分
        3. 信号融合，决定是否允许买入和订单金额
        4. 返回增强后的信号列表
        """
        # DEBUG: 第一天打印信息
        if day.isoformat() == "2021-02-02":
            print(f"\n[MULTIFACTOR SIGNAL GEN] First day (2021-02-02):")
            print(f"  Instance ID: {id(self)}")
            print(f"  enable_multifactor: {self.enable_multifactor} (type: {type(self.enable_multifactor).__name__})")
            print(f"  fusion_mode: '{self.fusion_mode}'")
            if hasattr(self, 'fusion_config'):
                print(f"  fusion_config.min_score_threshold: {self.fusion_config.get('min_score_threshold')}")
                print(f"  fusion_config.enable_base_signal_filter: {self.fusion_config.get('enable_base_signal_filter')}")
                print(f"  fusion_config.enable_weak_signal: {self.fusion_config.get('enable_weak_signal')}")
            else:
                print(f"  fusion_config: NOT SET!")

        # 如果未启用多因子，直接返回父类信号
        if not self.enable_multifactor:
            if day.isoformat() == "2021-02-02":
                print(f"  ✗ SKIPPING multifactor (enable_multifactor={self.enable_multifactor})")
            return SMACrossRegimeATRStrategy.generate_signals(self, day, history, positions)

        if day.isoformat() == "2021-02-02":
            print(f"  ✓ Proceeding with multifactor logic")

        # 调用父类获取基础信号
        base_signals = SMACrossRegimeATRStrategy.generate_signals(self, day, history, positions)

        # 准备基准数据用于RS计算
        day_ts = pd.Timestamp(day)
        day_data = history[history["date"] <= day_ts]

        bench_code = f"BENCH:{self.benchmark_symbol}".lower()
        bench_df = day_data[day_data["symbol"].astype(str).str.lower() == bench_code].sort_values("date")

        # 第一遍：计算所有股票的多因子评分（用于RS排名）
        all_symbols_scores = {}
        all_symbols_rs = {}

        non_bench = day_data[~day_data["symbol"].astype(str).str.lower().str.startswith("bench:")]
        for symbol, sym_df in non_bench.groupby("symbol", sort=False):
            sym_df = sym_df.sort_values("date")

            if len(sym_df) < max(self.slow, 20):
                continue

            # 计算多因子评分
            score, details = compute_multifactor_score(
                sym_df=sym_df,
                benchmark_df=bench_df if len(bench_df) > 0 else None,
                all_symbols_rs=None,  # 第一遍先不用RS排名
                symbol=str(symbol),
                config=self.fusion_config,
            )

            all_symbols_scores[str(symbol)] = score

            # 提取RS值用于排名
            if "rs" in details and details["rs"].get("value") is not None:
                all_symbols_rs[str(symbol)] = details["rs"]["value"]

        # 存储今日评分
        self.state["daily_multifactor_scores"][day.isoformat()] = all_symbols_scores

        # 第二遍：增强买入信号
        enhanced_signals = []
        buy_signals = []

        for signal in base_signals:
            # 卖出信号直接保留
            if signal.side == Side.SELL:
                enhanced_signals.append(signal)
                continue

            # 处理买入信号
            if signal.side == Side.BUY:
                symbol = str(signal.symbol)

                # 获取股票历史数据
                sym_df = non_bench[non_bench["symbol"] == symbol].sort_values("date")

                if len(sym_df) < max(self.slow, 20):
                    # 数据不足，标记为BLOCKED
                    enhanced_signal = Signal(
                        signal_date=signal.signal_date,
                        symbol=signal.symbol,
                        side=signal.side,
                        qty=signal.qty,
                        action="BLOCKED",
                        reason="MULTIFACTOR_INSUFFICIENT_DATA",
                        reason_code="MULTIFACTOR_INSUFFICIENT_DATA",
                        meta={**signal.meta, "multifactor_enabled": True, "multifactor_insufficient_data": True},
                    )
                    enhanced_signals.append(enhanced_signal)
                    continue

                # 重新计算多因子评分（带RS排名）
                score, details = compute_multifactor_score(
                    sym_df=sym_df,
                    benchmark_df=bench_df if len(bench_df) > 0 else None,
                    all_symbols_rs=all_symbols_rs,
                    symbol=symbol,
                    config=self.fusion_config,
                )

                # 融合信号
                base_signal_triggered = signal.action != "BLOCKED"
                fused = fuse_signal(
                    symbol=symbol,
                    base_signal=base_signal_triggered,
                    multifactor_score=score,
                    multifactor_details=details,
                    config=self.fusion_config,
                )

                # 更新元数据
                enhanced_meta = {
                    **signal.meta,
                    "multifactor_enabled": True,
                    "multifactor_score": round(fused.score, 2),
                    "multifactor_strength": fused.strength.value,
                    "multifactor_details": fused.details,
                    "order_value_scale": round(fused.order_scale, 2),
                    "multifactor_buy_allowed": fused.buy_allowed,
                }

                # 根据融合结果决定是否允许买入
                if fused.buy_allowed:
                    # 允许买入，更新订单金额缩放
                    enhanced_signal = Signal(
                        signal_date=signal.signal_date,
                        symbol=signal.symbol,
                        side=signal.side,
                        qty=signal.qty,
                        reason=f"{signal.reason}_MULTIFACTOR_{fused.strength.value}",
                        reason_code=signal.reason_code,
                        meta=enhanced_meta,
                    )
                    buy_signals.append((fused.score, enhanced_signal))
                else:
                    # 不允许买入，标记为BLOCKED
                    blocked_reason = "MULTIFACTOR_LOW_SCORE" if fused.score < self.fusion_config.get(
                        "min_score_threshold", 30
                    ) else "MULTIFACTOR_BLOCKED"

                    enhanced_signal = Signal(
                        signal_date=signal.signal_date,
                        symbol=signal.symbol,
                        side=signal.side,
                        qty=signal.qty,
                        action="BLOCKED",
                        reason=blocked_reason,
                        reason_code=blocked_reason,
                        meta=enhanced_meta,
                    )
                    enhanced_signals.append(enhanced_signal)

        # 对买入信号按评分排序（高分优先）
        buy_signals.sort(key=lambda x: x[0], reverse=True)

        # 添加排序后的买入信号
        for _, signal in buy_signals:
            enhanced_signals.append(signal)

        return enhanced_signals


# ============================================================================
# 便捷工厂函数
# ============================================================================

def create_balanced_strategy(**kwargs) -> SMACrossMultifactorStrategy:
    """创建平衡模式的多因子策略"""
    return SMACrossMultifactorStrategy(fusion_mode="balanced", **kwargs)


def create_aggressive_strategy(**kwargs) -> SMACrossMultifactorStrategy:
    """创建激进模式的多因子策略"""
    return SMACrossMultifactorStrategy(fusion_mode="aggressive", **kwargs)


def create_conservative_strategy(**kwargs) -> SMACrossMultifactorStrategy:
    """创建保守模式的多因子策略"""
    return SMACrossMultifactorStrategy(fusion_mode="conservative", **kwargs)
