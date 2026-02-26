"""
信号融合模块

提供多因子信号的融合逻辑，根据综合评分决定信号强度和买入优先级。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignalStrength(str, Enum):
    """信号强度等级"""

    STRONG = "STRONG"  # 强信号 (评分 >= 70)
    MODERATE = "MODERATE"  # 中等信号 (50 <= 评分 < 70)
    WEAK = "WEAK"  # 弱信号 (30 <= 评分 < 50)
    VERY_WEAK = "VERY_WEAK"  # 极弱信号 (评分 < 30)


@dataclass(frozen=True)
class FusedSignal:
    """
    融合后的信号

    Attributes:
        symbol: 股票代码
        score: 综合评分 (0-100)
        strength: 信号强度等级
        details: 详细的因子分数
        buy_allowed: 是否允许买入
        order_scale: 订单金额缩放系数 (0.5-2.0)
    """

    symbol: str
    score: float
    strength: SignalStrength
    details: dict
    buy_allowed: bool
    order_scale: float


def classify_signal_strength(score: float) -> SignalStrength:
    """
    根据评分分类信号强度

    Args:
        score: 综合评分 (0-100)

    Returns:
        SignalStrength: 信号强度等级
    """
    if score >= 70:
        return SignalStrength.STRONG
    elif score >= 50:
        return SignalStrength.MODERATE
    elif score >= 30:
        return SignalStrength.WEAK
    else:
        return SignalStrength.VERY_WEAK


def compute_order_scale(
    score: float,
    strength: SignalStrength,
    config: dict | None = None,
) -> float:
    """
    根据信号强度计算订单金额缩放系数

    Args:
        score: 综合评分
        strength: 信号强度
        config: 配置参数

    Returns:
        float: 订单金额缩放系数 (0.5-2.0)
    """
    if config is None:
        config = {}

    # 默认缩放系数
    strong_scale = config.get("strong_signal_scale", 2.0)
    moderate_scale = config.get("moderate_signal_scale", 1.5)
    weak_scale = config.get("weak_signal_scale", 1.0)
    very_weak_scale = config.get("very_weak_signal_scale", 0.5)

    if strength == SignalStrength.STRONG:
        # 强信号：线性插值 1.5-2.0
        return moderate_scale + (strong_scale - moderate_scale) * ((score - 70) / 30)
    elif strength == SignalStrength.MODERATE:
        # 中等信号：线性插值 1.0-1.5
        return weak_scale + (moderate_scale - weak_scale) * ((score - 50) / 20)
    elif strength == SignalStrength.WEAK:
        # 弱信号：线性插值 0.5-1.0
        return very_weak_scale + (weak_scale - very_weak_scale) * ((score - 30) / 20)
    else:
        # 极弱信号：固定0.5
        return very_weak_scale


def fuse_signal(
    symbol: str,
    base_signal: bool,  # 基础信号（如SMA金叉）
    multifactor_score: float,  # 多因子评分
    multifactor_details: dict,  # 多因子详情
    config: dict | None = None,
) -> FusedSignal:
    """
    融合基础信号和多因子评分

    Args:
        symbol: 股票代码
        base_signal: 基础信号（True表示触发）
        multifactor_score: 多因子综合评分
        multifactor_details: 多因子详细信息
        config: 配置参数

    Returns:
        FusedSignal: 融合后的信号
    """
    if config is None:
        config = {}

    # 配置参数
    min_score_threshold = config.get("min_score_threshold", 30.0)  # 最低评分阈值
    enable_base_signal_filter = config.get("enable_base_signal_filter", True)  # 是否要求基础信号
    enable_weak_signal = config.get("enable_weak_signal", True)  # 是否允许弱信号

    # 分类信号强度
    strength = classify_signal_strength(multifactor_score)

    # 计算订单缩放系数
    order_scale = compute_order_scale(multifactor_score, strength, config)

    # 判断是否允许买入
    buy_allowed = True

    # 检查1：基础信号过滤
    if enable_base_signal_filter and not base_signal:
        buy_allowed = False

    # 检查2：最低评分阈值
    if multifactor_score < min_score_threshold:
        buy_allowed = False

    # 检查3：弱信号开关
    if not enable_weak_signal and strength in (SignalStrength.WEAK, SignalStrength.VERY_WEAK):
        buy_allowed = False

    return FusedSignal(
        symbol=symbol,
        score=multifactor_score,
        strength=strength,
        details=multifactor_details,
        buy_allowed=buy_allowed,
        order_scale=order_scale,
    )


def rank_signals(
    signals: list[FusedSignal],
    max_buy: int | None = None,
) -> list[FusedSignal]:
    """
    对信号进行排序，优先选择高分信号

    Args:
        signals: 融合信号列表
        max_buy: 最大买入数量（None表示不限制）

    Returns:
        list[FusedSignal]: 排序后的信号列表
    """
    # 过滤掉不允许买入的信号
    buyable_signals = [s for s in signals if s.buy_allowed]

    # 按评分从高到低排序
    sorted_signals = sorted(buyable_signals, key=lambda x: x.score, reverse=True)

    # 如果有数量限制，截取
    if max_buy is not None:
        sorted_signals = sorted_signals[:max_buy]

    return sorted_signals


def get_fusion_config_template() -> dict:
    """
    获取融合配置模板

    Returns:
        dict: 默认配置
    """
    return {
        # 因子开关
        "enable_volume_factor": True,
        "enable_momentum_factor": True,
        "enable_rs_factor": True,
        "enable_bollinger_factor": True,
        # 因子权重（每个因子独立计分，1.0表示全部计入）
        "volume_weight": 1.0,
        "momentum_weight": 1.0,
        "rs_weight": 1.0,
        "bollinger_weight": 1.0,
        # 融合参数
        "enable_base_signal_filter": True,  # 是否要求SMA金叉
        "min_score_threshold": 30.0,  # 最低评分阈值
        "enable_weak_signal": True,  # 是否允许弱信号
        # 订单缩放系数
        "strong_signal_scale": 2.0,  # 强信号（>=70分）
        "moderate_signal_scale": 1.5,  # 中等信号（50-70分）
        "weak_signal_scale": 1.0,  # 弱信号（30-50分）
        "very_weak_signal_scale": 0.5,  # 极弱信号（<30分）
    }


# ============================================================================
# 融合策略示例
# ============================================================================

def get_aggressive_config() -> dict:
    """激进配置：降低门槛，允许弱信号"""
    config = get_fusion_config_template()
    config.update(
        {
            "enable_base_signal_filter": False,  # 不要求SMA金叉
            "min_score_threshold": 20.0,  # 降低阈值
            "enable_weak_signal": True,
            "strong_signal_scale": 2.5,
            "moderate_signal_scale": 1.8,
            "weak_signal_scale": 1.2,
            "very_weak_signal_scale": 0.8,
        }
    )
    return config


def get_conservative_config() -> dict:
    """保守配置：提高门槛，只要强信号"""
    config = get_fusion_config_template()
    config.update(
        {
            "enable_base_signal_filter": True,  # 必须有SMA金叉
            "min_score_threshold": 50.0,  # 提高阈值
            "enable_weak_signal": False,  # 不允许弱信号
            "strong_signal_scale": 1.5,
            "moderate_signal_scale": 1.2,
            "weak_signal_scale": 0.8,
            "very_weak_signal_scale": 0.5,
        }
    )
    return config


def get_balanced_config() -> dict:
    """平衡配置：适中的门槛和缩放"""
    return get_fusion_config_template()
