"""
Centralized Reason Code Registry for Backtest Observability.

All reason codes follow the pattern: {LAYER}_{ACTION}_{DETAIL}
- RC_*: Strategy Layer
- OVL_*: Overlay Gate Layer
- RISK_*: Risk Layer
- EXE_*: Execution Layer
"""


class ReasonCodeRegistry:
    """Centralized reason code definitions across all layers."""

    # ==================== Strategy Layer (RC_*) ====================
    # Entry signals
    RC_SMA_CROSS_UP = "RC_SMA_CROSS_UP"                      # 均线金叉
    RC_SMA_CROSS_UP_TREND_OK = "RC_SMA_CROSS_UP_TREND_OK"    # 金叉且趋势确认
    RC_MOMENTUM_BREAKOUT = "RC_MOMENTUM_BREAKOUT"            # 动量突破
    RC_BOLLINGER_BREAKOUT = "RC_BOLLINGER_BREAKOUT"          # 布林带突破
    RC_VOLUME_BREAKOUT = "RC_VOLUME_BREAKOUT"                # 量能突破
    RC_RELATIVE_STRENGTH = "RC_RELATIVE_STRENGTH"            # 相对强度入场
    RC_MULTIFACTOR_STRONG = "RC_MULTIFACTOR_STRONG"          # 多因子强信号
    RC_MULTIFACTOR_MODERATE = "RC_MULTIFACTOR_MODERATE"      # 多因子中等信号
    RC_MULTIFACTOR_WEAK = "RC_MULTIFACTOR_WEAK"              # 多因子弱信号
    RC_COMPOSITE_AND_BUY = "RC_COMPOSITE_AND_BUY"            # 组合策略AND模式买入
    RC_COMPOSITE_OR_BUY = "RC_COMPOSITE_OR_BUY"              # 组合策略OR模式买入
    RC_COMPOSITE_VOTE_BUY = "RC_COMPOSITE_VOTE_BUY"          # 组合策略投票模式买入

    # Exit signals
    RC_SMA_CROSS_DOWN = "RC_SMA_CROSS_DOWN"                  # 均线死叉
    RC_RISK_OFF_EXIT = "RC_RISK_OFF_EXIT"                    # RISK_OFF模式退出
    RC_TREND_BREAK_EXIT = "RC_TREND_BREAK_EXIT"              # 趋势破坏退出
    RC_ATR_STOP = "RC_ATR_STOP"                              # ATR止损
    RC_ATR_STOP_LOSS = "RC_ATR_STOP_LOSS"                    # ATR止损触发
    RC_ATR_TRAIL_EXIT = "RC_ATR_TRAIL_EXIT"                  # ATR移动止损退出
    RC_MOMENTUM_EXIT = "RC_MOMENTUM_EXIT"                    # 动量退出
    RC_BOLLINGER_EXIT = "RC_BOLLINGER_EXIT"                  # 布林带退出
    RC_MULTIFACTOR_SCORE_LOW = "RC_MULTIFACTOR_SCORE_LOW"    # 多因子评分过低
    RC_MULTIFACTOR_MAX_HOLD = "RC_MULTIFACTOR_MAX_HOLD"      # 多因子最大持仓期
    RC_COMPOSITE_AND_SELL = "RC_COMPOSITE_AND_SELL"          # 组合策略AND模式卖出
    RC_COMPOSITE_OR_SELL = "RC_COMPOSITE_OR_SELL"            # 组合策略OR模式卖出
    RC_COMPOSITE_VOTE_SELL = "RC_COMPOSITE_VOTE_SELL"        # 组合策略投票模式卖出

    # Blocking reasons
    RC_BLOCK_SMA_CROSS_BLOCKED = "RC_BLOCK_SMA_CROSS_BLOCKED"        # 均线交叉被阻塞
    RC_BLOCK_TREND_FILTER = "RC_BLOCK_TREND_FILTER"                  # 趋势过滤器阻塞
    RC_BLOCK_ENTRY_BUFFER = "RC_BLOCK_ENTRY_BUFFER"                  # 入场缓冲期阻塞
    RC_BLOCK_INSUFFICIENT_DATA = "RC_BLOCK_INSUFFICIENT_DATA"        # 数据不足
    RC_BLOCK_RS_NEGATIVE = "RC_BLOCK_RS_NEGATIVE"                    # RS负值阻塞
    RC_BLOCK_VOLUME_LOW = "RC_BLOCK_VOLUME_LOW"                      # 量能不足
    RC_BLOCK_REGIME_BEAR = "RC_BLOCK_REGIME_BEAR"                    # 熊市regime

    # Legacy codes for backward compatibility
    RC_BREAKOUT_20D = "RC_BREAKOUT_20D"              # 20日突破
    RC_MA_CROSS_BULL = "RC_MA_CROSS_BULL"            # 金叉 (alias for RC_SMA_CROSS_UP)
    RC_MA_CROSS_BEAR = "RC_MA_CROSS_BEAR"            # 死叉 (alias for RC_SMA_CROSS_DOWN)
    RC_VOLUME_SURGE = "RC_VOLUME_SURGE"              # 量能激增
    RC_RS_POSITIVE = "RC_RS_POSITIVE"                # RS > 0
    RC_MULTIFACTOR_RANK = "RC_MULTIFACTOR_RANK"      # 多因子排名
    RC_MOMENTUM_STRONG = "RC_MOMENTUM_STRONG"        # 强动量信号
    RC_BLOCK_NO_BREAKOUT = "RC_BLOCK_NO_BREAKOUT"    # 无突破

    # ==================== Overlay Gate Layer (OVL_*) ====================
    # Overlay gate reasons
    OVL_BLOCK_ENTRY_RISK_OFF = "OVL_BLOCK_ENTRY_RISK_OFF"        # RISK_OFF阻塞
    OVL_BLOCK_PYRAMID_CHOP = "OVL_BLOCK_PYRAMID_CHOP"            # CHOP模式禁止加仓
    OVL_BLOCK_DD_COOLDOWN = "OVL_BLOCK_DD_COOLDOWN"              # 回撤冷却期
    OVL_BLOCK_DD_BAN_PYRAMID = "OVL_BLOCK_DD_BAN_PYRAMID"        # 回撤过高禁止加仓
    OVL_DD_DEGRADED = "OVL_DD_DEGRADED"                          # 回撤降级(tier1触发)
    OVL_DD_RECOVERED = "OVL_DD_RECOVERED"                        # 回撤恢复正常
    OVL_COOLDOWN_TRIGGERED = "OVL_COOLDOWN_TRIGGERED"            # 进入冷却期
    OVL_COOLDOWN_EXPIRED = "OVL_COOLDOWN_EXPIRED"                # 冷却期结束

    # ==================== Risk Layer (RISK_*) ====================
    # Position sizing reasons
    RISK_BLOCK_MAX_POSITIONS = "RISK_BLOCK_MAX_POSITIONS"        # 达到最大持仓数
    RISK_BLOCK_NO_CASH = "RISK_BLOCK_NO_CASH"                    # 资金不足
    RISK_BLOCK_R_TOO_SMALL = "RISK_BLOCK_R_TOO_SMALL"            # R值太小
    RISK_BLOCK_INVALID_PRICE = "RISK_BLOCK_INVALID_PRICE"        # 无效价格
    RISK_BLOCK_INVALID_STOP = "RISK_BLOCK_INVALID_STOP"          # 无效止损价
    RISK_APPROVE_ENTRY = "RISK_APPROVE_ENTRY"                    # 入场批准
    RISK_APPROVE_PYRAMID = "RISK_APPROVE_PYRAMID"                # 加仓批准

    # Stop reasons
    RISK_STOP_TRIGGERED = "RISK_STOP_TRIGGERED"                  # 止损触发
    RISK_TRAILING_STOP = "RISK_TRAILING_STOP"                    # 移动止损触发
    RISK_PROFIT_TARGET = "RISK_PROFIT_TARGET"                    # 止盈触发
    RISK_TIME_STOP = "RISK_TIME_STOP"                            # 时间止损

    # ==================== Execution Layer (EXE_*) ====================
    # Execution success/failure
    EXE_FILLED = "EXE_FILLED"                                    # 成交
    EXE_PARTIAL_FILL = "EXE_PARTIAL_FILL"                        # 部分成交
    EXE_REJECTED_NO_DATA = "EXE_REJECTED_NO_DATA"                # 缺OHLCV数据
    EXE_REJECTED_SUSPENDED = "EXE_REJECTED_SUSPENDED"            # 停牌
    EXE_REJECTED_LIMIT_UP = "EXE_REJECTED_LIMIT_UP"              # 涨停(无法买入)
    EXE_REJECTED_LIMIT_DOWN = "EXE_REJECTED_LIMIT_DOWN"          # 跌停(无法卖出)
    EXE_REJECTED_LOT_SIZE = "EXE_REJECTED_LOT_SIZE"              # 不符合手数要求
    EXE_REJECTED_NO_POSITION = "EXE_REJECTED_NO_POSITION"        # 无持仓无法卖出
    EXE_REJECTED_NO_SELLABLE = "EXE_REJECTED_NO_SELLABLE"        # 无可卖股数(T+1)
    EXE_REJECTED_NO_CASH = "EXE_REJECTED_NO_CASH"                # 资金不足
    EXE_REJECTED_LIQUIDITY = "EXE_REJECTED_LIQUIDITY"            # 流动性约束

    # Order skipping reasons
    EXE_SKIP_DUPLICATE = "EXE_SKIP_DUPLICATE"                    # 今日重复订单
    EXE_SKIP_ALREADY_HOLDING = "EXE_SKIP_ALREADY_HOLDING"        # 已持仓(无加仓)
    EXE_SKIP_QTY_ZERO = "EXE_SKIP_QTY_ZERO"                      # 仓位计算后数量为0
    EXE_SKIP_NO_NEXT_BAR = "EXE_SKIP_NO_NEXT_BAR"                # 提交日无bar数据

    @classmethod
    def get_category(cls, code: str) -> str:
        """Get category from reason code prefix."""
        if code.startswith("RC_"):
            return "STRATEGY"
        elif code.startswith("OVL_"):
            return "OVERLAY"
        elif code.startswith("RISK_"):
            return "RISK"
        elif code.startswith("EXE_"):
            return "EXECUTION"
        else:
            return "UNKNOWN"

    @classmethod
    def describe(cls, code: str) -> str:
        """Get human-readable description of reason code."""
        descriptions = {
            # Strategy
            cls.RC_BREAKOUT_20D: "20日高点突破且量能确认",
            cls.RC_MA_CROSS_BULL: "均线金叉",
            cls.RC_VOLUME_SURGE: "成交量激增",
            cls.RC_BLOCK_RS_NEGATIVE: "相对强度为负值，阻塞信号",

            # Overlay
            cls.OVL_BLOCK_ENTRY_RISK_OFF: "RISK_OFF模式，阻塞入场",
            cls.OVL_BLOCK_DD_COOLDOWN: "回撤冷却期，阻塞入场",
            cls.OVL_DD_DEGRADED: "回撤达到tier1阈值，降级",

            # Risk
            cls.RISK_BLOCK_MAX_POSITIONS: "已达最大持仓数",
            cls.RISK_APPROVE_ENTRY: "风控审批通过，允许入场",
            cls.RISK_STOP_TRIGGERED: "止损价触发",

            # Execution
            cls.EXE_FILLED: "订单成功成交",
            cls.EXE_REJECTED_LIMIT_UP: "涨停无法买入",
            cls.EXE_SKIP_DUPLICATE: "今日已有相同订单",
        }
        return descriptions.get(code, f"Unknown code: {code}")
