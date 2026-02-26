"""
多因子计算模块

提供多种技术指标和因子计算函数，用于增强信号生成的准确性。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================================
# 1. 成交量因子 (Volume Factors)
# ============================================================================

def compute_volume_breakout(
    volume: pd.Series,
    lookback: int = 20,
    threshold: float = 1.5,
) -> bool:
    """
    成交量突破检测

    当当前成交量 > N日平均成交量 × 阈值时，认为成交量突破

    Args:
        volume: 成交量序列
        lookback: 回看天数
        threshold: 突破阈值倍数（默认1.5倍）

    Returns:
        bool: 是否发生成交量突破
    """
    if len(volume) < lookback + 1:
        return False

    vol_ma = float(volume.rolling(lookback).mean().iloc[-1])
    current_vol = float(volume.iloc[-1])

    if pd.isna(vol_ma) or vol_ma == 0:
        return False

    return current_vol > (vol_ma * threshold)


def compute_volume_trend(
    volume: pd.Series,
    short_window: int = 5,
    long_window: int = 20,
) -> tuple[bool, float]:
    """
    成交量趋势分析

    通过短期和长期成交量均线的关系判断成交量趋势

    Args:
        volume: 成交量序列
        short_window: 短期窗口
        long_window: 长期窗口

    Returns:
        (bool, float): (成交量上升趋势, 成交量比率)
    """
    if len(volume) < long_window + 1:
        return False, 0.0

    vol_short = float(volume.rolling(short_window).mean().iloc[-1])
    vol_long = float(volume.rolling(long_window).mean().iloc[-1])

    if pd.isna(vol_short) or pd.isna(vol_long) or vol_long == 0:
        return False, 0.0

    ratio = vol_short / vol_long
    return ratio > 1.0, ratio


# ============================================================================
# 2. 动量因子 (Momentum Factors)
# ============================================================================

def compute_roc(
    close: pd.Series,
    period: int = 20,
) -> float | None:
    """
    变动率指标 (Rate of Change)

    计算N日价格变化百分比

    Args:
        close: 收盘价序列
        period: 周期

    Returns:
        float | None: ROC值（百分比）
    """
    if len(close) < period + 1:
        return None

    current = float(close.iloc[-1])
    past = float(close.iloc[-(period + 1)])

    if pd.isna(current) or pd.isna(past) or past == 0:
        return None

    return ((current - past) / past) * 100


def compute_momentum(
    close: pd.Series,
    period: int = 10,
) -> float | None:
    """
    动量指标 (Momentum)

    计算N日价格动量

    Args:
        close: 收盘价序列
        period: 周期

    Returns:
        float | None: 动量值
    """
    if len(close) < period + 1:
        return None

    current = float(close.iloc[-1])
    past = float(close.iloc[-(period + 1)])

    if pd.isna(current) or pd.isna(past):
        return None

    return current - past


def compute_momentum_score(
    close: pd.Series,
    roc_period: int = 20,
    mom_period: int = 10,
) -> tuple[float, dict]:
    """
    综合动量评分

    结合ROC和Momentum计算综合评分

    Args:
        close: 收盘价序列
        roc_period: ROC周期
        mom_period: Momentum周期

    Returns:
        (float, dict): (综合评分 0-100, 详细信息)
    """
    roc = compute_roc(close, roc_period)
    mom = compute_momentum(close, mom_period)

    if roc is None or mom is None:
        return 0.0, {"roc": None, "momentum": None}

    # 归一化评分
    # ROC > 0 且越大越好，最高50分
    roc_score = min(max(roc, 0), 50)

    # Momentum > 0 且越大越好，最高50分
    # 假设动量在0-10范围内，超过10记为50分
    mom_score = min(max(mom / 10 * 50, 0), 50)

    total_score = roc_score + mom_score

    return total_score, {
        "roc": round(roc, 2),
        "roc_score": round(roc_score, 2),
        "momentum": round(mom, 2),
        "momentum_score": round(mom_score, 2),
        "total_score": round(total_score, 2),
    }


# ============================================================================
# 3. 相对强度因子 (Relative Strength)
# ============================================================================

def compute_rs(
    close: pd.Series,
    benchmark_close: pd.Series,
    period: int = 20,
) -> float | None:
    """
    相对强度指标 (Relative Strength)

    计算股票相对于基准的强度

    Args:
        close: 股票收盘价序列
        benchmark_close: 基准收盘价序列
        period: 周期

    Returns:
        float | None: RS值（百分比）
    """
    if len(close) < period + 1 or len(benchmark_close) < period + 1:
        return None

    stock_ret = (close.iloc[-1] / close.iloc[-(period + 1)] - 1) * 100
    bench_ret = (benchmark_close.iloc[-1] / benchmark_close.iloc[-(period + 1)] - 1) * 100

    if pd.isna(stock_ret) or pd.isna(bench_ret):
        return None

    return float(stock_ret - bench_ret)


def compute_rs_rank(
    symbol: str,
    all_symbols_rs: dict[str, float],
) -> tuple[float, int, int]:
    """
    RS排名

    计算股票在所有股票中的RS排名百分位

    Args:
        symbol: 股票代码
        all_symbols_rs: 所有股票的RS值字典 {symbol: rs_value}

    Returns:
        (float, int, int): (百分位 0-100, 排名, 总数)
    """
    if symbol not in all_symbols_rs:
        return 0.0, 0, 0

    # 过滤None值
    valid_rs = {k: v for k, v in all_symbols_rs.items() if v is not None}
    if not valid_rs:
        return 0.0, 0, 0

    # 排序（从高到低）
    sorted_symbols = sorted(valid_rs.items(), key=lambda x: x[1], reverse=True)

    # 找到当前股票的排名
    rank = next((i + 1 for i, (s, _) in enumerate(sorted_symbols) if s == symbol), 0)
    total = len(sorted_symbols)

    if total == 0:
        return 0.0, 0, 0

    # 百分位（排名越前，百分位越高）
    percentile = ((total - rank + 1) / total) * 100

    return percentile, rank, total


# ============================================================================
# 4. 布林带因子 (Bollinger Bands)
# ============================================================================

def compute_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[float | None, float | None, float | None, float | None]:
    """
    布林带指标

    Args:
        close: 收盘价序列
        period: 周期
        num_std: 标准差倍数

    Returns:
        (upper, middle, lower, bandwidth): 上轨、中轨、下轨、带宽
    """
    if len(close) < period:
        return None, None, None, None

    middle = float(close.rolling(period).mean().iloc[-1])
    std = float(close.rolling(period).std().iloc[-1])

    if pd.isna(middle) or pd.isna(std):
        return None, None, None, None

    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    bandwidth = (upper - lower) / middle if middle != 0 else 0

    return upper, middle, lower, bandwidth


def compute_bollinger_breakout(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[bool, dict]:
    """
    布林带突破检测

    Args:
        close: 收盘价序列
        period: 周期
        num_std: 标准差倍数

    Returns:
        (bool, dict): (是否突破上轨, 详细信息)
    """
    upper, middle, lower, bandwidth = compute_bollinger_bands(close, period, num_std)

    if upper is None:
        return False, {}

    current_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else current_close

    # 突破上轨：当前收盘价 > 上轨 且 前一收盘价 <= 上轨
    breakout = current_close > upper and prev_close <= upper

    # 计算相对位置（0-100）
    position = 0.0
    if upper is not None and lower is not None and upper != lower:
        position = ((current_close - lower) / (upper - lower)) * 100

    return breakout, {
        "upper": round(upper, 4) if upper else None,
        "middle": round(middle, 4) if middle else None,
        "lower": round(lower, 4) if lower else None,
        "bandwidth": round(bandwidth, 4) if bandwidth else None,
        "position_pct": round(position, 2),
        "breakout": breakout,
    }


# ============================================================================
# 5. 资金流向因子 (Money Flow)
# ============================================================================

def compute_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 14,
) -> float | None:
    """
    资金流量指标 (Money Flow Index)

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        volume: 成交量序列
        period: 周期

    Returns:
        float | None: MFI值 (0-100)
    """
    if len(close) < period + 1:
        return None

    # 典型价格
    typical_price = (high + low + close) / 3

    # 资金流量
    money_flow = typical_price * volume

    # 价格变化
    price_change = typical_price.diff()

    # 正资金流 和 负资金流
    positive_flow = pd.Series([mf if pc > 0 else 0 for mf, pc in zip(money_flow, price_change)])
    negative_flow = pd.Series([mf if pc < 0 else 0 for mf, pc in zip(money_flow, price_change)])

    # N日累计
    positive_sum = float(positive_flow.rolling(period).sum().iloc[-1])
    negative_sum = float(negative_flow.rolling(period).sum().iloc[-1])

    if pd.isna(positive_sum) or pd.isna(negative_sum):
        return None

    if negative_sum == 0:
        return 100.0

    money_ratio = positive_sum / negative_sum
    mfi = 100 - (100 / (1 + money_ratio))

    return float(mfi)


# ============================================================================
# 6. 趋势强度因子 (Trend Strength)
# ============================================================================

def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> float | None:
    """
    平均趋向指标 (Average Directional Index)

    衡量趋势的强度（不考虑方向）

    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: 周期

    Returns:
        float | None: ADX值 (0-100)
    """
    if len(close) < period + 1:
        return None

    # TR (True Range)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    # +DM and -DM
    high_diff = high.diff()
    low_diff = -low.diff()

    plus_dm = pd.Series([hd if hd > ld and hd > 0 else 0 for hd, ld in zip(high_diff, low_diff)])
    minus_dm = pd.Series([ld if ld > hd and ld > 0 else 0 for ld, hd in zip(low_diff, high_diff)])

    # Smoothed TR, +DM, -DM
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

    # DX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)

    # ADX
    adx = dx.rolling(period).mean()

    adx_value = float(adx.iloc[-1])

    if pd.isna(adx_value):
        return None

    return adx_value


# ============================================================================
# 7. 综合因子评分函数
# ============================================================================

def compute_multifactor_score(
    sym_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
    all_symbols_rs: dict[str, float] | None = None,
    symbol: str = "",
    config: dict | None = None,
) -> tuple[float, dict]:
    """
    综合多因子评分

    Args:
        sym_df: 股票历史数据
        benchmark_df: 基准指数历史数据
        all_symbols_rs: 所有股票的RS值
        symbol: 股票代码
        config: 配置参数

    Returns:
        (float, dict): (综合评分 0-100, 详细信息)
    """
    if config is None:
        config = {}

    # 默认配置
    enable_volume = config.get("enable_volume_factor", True)
    enable_momentum = config.get("enable_momentum_factor", True)
    enable_rs = config.get("enable_rs_factor", True)
    enable_bollinger = config.get("enable_bollinger_factor", True)

    volume_weight = config.get("volume_weight", 0.25)
    momentum_weight = config.get("momentum_weight", 0.25)
    rs_weight = config.get("rs_weight", 0.25)
    bollinger_weight = config.get("bollinger_weight", 0.25)

    total_score = 0.0
    details = {}

    # 1. 成交量因子 (0-25分)
    if enable_volume and "volume" in sym_df.columns:
        vol_breakout = compute_volume_breakout(sym_df["volume"])
        vol_trend, vol_ratio = compute_volume_trend(sym_df["volume"])

        vol_score = 0.0
        if vol_breakout:
            vol_score += 15
        if vol_trend:
            vol_score += min((vol_ratio - 1.0) * 10, 10)

        total_score += vol_score * volume_weight
        details["volume"] = {
            "breakout": vol_breakout,
            "trend": vol_trend,
            "ratio": round(vol_ratio, 2),
            "score": round(vol_score * volume_weight, 2),
        }

    # 2. 动量因子 (0-25分)
    if enable_momentum and "close" in sym_df.columns:
        mom_score, mom_details = compute_momentum_score(sym_df["close"])
        total_score += (mom_score / 100) * 25 * momentum_weight
        details["momentum"] = mom_details

    # 3. 相对强度因子 (0-25分)
    if enable_rs and benchmark_df is not None and "close" in sym_df.columns and "close" in benchmark_df.columns:
        rs_value = compute_rs(sym_df["close"], benchmark_df["close"])

        if rs_value is not None:
            # RS > 0 表示跑赢指数，最高25分
            rs_score = min(max(rs_value / 10 * 25, 0), 25)

            # 如果有RS排名信息，加权
            rs_percentile = 0.0
            if all_symbols_rs and symbol:
                rs_percentile, rank, total = compute_rs_rank(symbol, all_symbols_rs)
                # 排名在前30%加分
                if rs_percentile >= 70:
                    rs_score = 25
                elif rs_percentile >= 50:
                    rs_score = max(rs_score, 15)

            total_score += rs_score * rs_weight
            details["rs"] = {
                "value": round(rs_value, 2),
                "percentile": round(rs_percentile, 2),
                "score": round(rs_score * rs_weight, 2),
            }

    # 4. 布林带因子 (0-25分)
    if enable_bollinger and "close" in sym_df.columns:
        bb_breakout, bb_details = compute_bollinger_breakout(sym_df["close"])

        bb_score = 0.0
        if bb_breakout:
            bb_score = 25
        elif bb_details.get("position_pct", 0) > 50:
            # 在上半部分，给部分分数
            bb_score = (bb_details.get("position_pct", 0) - 50) / 50 * 15

        total_score += bb_score * bollinger_weight
        details["bollinger"] = {
            **bb_details,
            "score": round(bb_score * bollinger_weight, 2),
        }

    return round(total_score, 2), details
