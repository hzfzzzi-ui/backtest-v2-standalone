# ma200-market-state Specification

## Purpose
基于基准指数 MA200 位置与斜率的四态市场分类，及对应的交易模式映射。

## Requirements

### Requirement: MA200 四态市场分类

系统 SHALL 在 `RegimeRouterSignalProvider.precompute()` 中基于基准指数计算四种市场状态：
- **BULL**: benchmark close > MA200 且 MA200 slope >= 0
- **TRANS_DOWN**: benchmark close > MA200 且 MA200 slope < 0
- **TRANS_UP**: benchmark close < MA200 且 MA200 slope >= 0
- **BEAR**: benchmark close < MA200 且 MA200 slope < 0

MA200 slope 定义为 `MA200[t] - MA200[t - slope_window]`，slope_window 默认 20 个交易日。

市场状态 SHALL 存储为 `_market_state[T]` 数组（int8），在 precompute 阶段一次性计算。

#### Scenario: BULL 状态判定
- **WHEN** 基准指数收盘价 > MA200 且 MA200 slope >= 0
- **THEN** 当日 market_state = BULL

#### Scenario: BEAR 状态判定
- **WHEN** 基准指数收盘价 < MA200 且 MA200 slope < 0
- **THEN** 当日 market_state = BEAR

#### Scenario: TRANS_DOWN 状态判定
- **WHEN** 基准指数收盘价 > MA200 且 MA200 slope < 0
- **THEN** 当日 market_state = TRANS_DOWN

#### Scenario: TRANS_UP 状态判定
- **WHEN** 基准指数收盘价 < MA200 且 MA200 slope >= 0
- **THEN** 当日 market_state = TRANS_UP

#### Scenario: MA200 数据不足
- **WHEN** 交易天数 < 200 + slope_window，MA200 或 slope 无法计算
- **THEN** 当日 market_state SHALL 默认为 BULL（允许交易）

### Requirement: 交易模式映射

系统 SHALL 根据 market_state 和过渡态入场条件计算每日 trade_mode：
- **TREND_MAIN**: market_state == BULL
- **TREND_LIGHT**: market_state in (TRANS_DOWN, TRANS_UP) 且当日 entry_signal == True
- **NO_TRADE**: market_state == BEAR，或 market_state in (TRANS_DOWN, TRANS_UP) 且 entry_signal == False

trade_mode SHALL 存储为 `_trade_mode[T]` 数组（int8），在 precompute 阶段计算。

#### Scenario: BULL 映射到 TREND_MAIN
- **WHEN** market_state == BULL
- **THEN** trade_mode = TREND_MAIN

#### Scenario: BEAR 映射到 NO_TRADE
- **WHEN** market_state == BEAR
- **THEN** trade_mode = NO_TRADE

#### Scenario: 过渡态有入场信号
- **WHEN** market_state in (TRANS_DOWN, TRANS_UP) 且当日 entry_signal == True
- **THEN** trade_mode = TREND_LIGHT

#### Scenario: 过渡态无入场信号
- **WHEN** market_state in (TRANS_DOWN, TRANS_UP) 且当日 entry_signal == False
- **THEN** trade_mode = NO_TRADE

### Requirement: 过渡态入场条件

系统 SHALL 对两种过渡态分别定义入场确认条件（均基于基准指数）：

**条件 A（TRANS_DOWN）**: benchmark MA20 > MA60 且 benchmark close > MA20 且 close > max(close, 20d)

**条件 B（TRANS_UP）**: benchmark close > highest(high, 60d) 且 benchmark close > MA60 且 benchmark MA20 > MA60

所有 MA 和 breakout 指标 SHALL 在 precompute 阶段基于 benchmark 数据矩阵化计算。

#### Scenario: TRANS_DOWN 入场确认
- **WHEN** market_state == TRANS_DOWN 且 benchmark MA20 > MA60 且 close > MA20 且 close > 20日最高收盘价
- **THEN** entry_signal = True，trade_mode = TREND_LIGHT

#### Scenario: TRANS_DOWN 无确认
- **WHEN** market_state == TRANS_DOWN 但上述三个条件任一不满足
- **THEN** entry_signal = False，trade_mode = NO_TRADE

#### Scenario: TRANS_UP 入场确认
- **WHEN** market_state == TRANS_UP 且 close > 60日最高价 且 close > MA60 且 MA20 > MA60
- **THEN** entry_signal = True，trade_mode = TREND_LIGHT

#### Scenario: TRANS_UP 无确认
- **WHEN** market_state == TRANS_UP 但上述三个条件任一不满足
- **THEN** entry_signal = False，trade_mode = NO_TRADE

### Requirement: TREND_LIGHT 使用 EMA5/20 策略

当 trade_mode == TREND_LIGHT 时，系统 SHALL 使用 EMA(5)/EMA(20) 交叉作为买卖信号（替代主趋势的 SMA cross）：
- 买入: EMA5 > EMA20（level check，与主趋势 SMA 逻辑一致）
- 卖出: EMA5 < EMA20
- signal_mode meta 字段 SHALL 为 "TREND_LIGHT"

EMA5/20 信号矩阵 SHALL 在 precompute 阶段与 SMA 信号矩阵并行计算。

#### Scenario: TREND_LIGHT 买入信号
- **WHEN** trade_mode == TREND_LIGHT 且某股票 EMA5 > EMA20 且无持仓
- **THEN** 产生 BUY 信号，reason_code = "EMA_LIGHT_CROSS_UP"，meta.signal_mode = "TREND_LIGHT"

#### Scenario: TREND_LIGHT 卖出信号
- **WHEN** 持有 TREND_LIGHT 持仓且该股票 EMA5 < EMA20
- **THEN** 产生 SELL 信号，reason_code = "EMA_LIGHT_CROSS_DOWN"

#### Scenario: NO_TRADE 模式行为
- **WHEN** trade_mode == NO_TRADE
- **THEN** 系统 SHALL 不产生任何买入信号，仅处理已有持仓的退出规则（ATR stop、time exit 等）

### Requirement: MarketFilterConfig 配置

系统 SHALL 提供 `MarketFilterConfig` dataclass：
- `enabled: bool = False` — 总开关
- `slope_window: int = 20` — MA200 斜率计算回看窗口
- `bull_multiplier: float = 1.5` — BULL 态 risk_budget trend_multiplier
- `light_multiplier: float = 0.6` — TREND_LIGHT 态 multiplier
- `ema_light_fast: int = 5` — 轻趋势 EMA 快线周期
- `ema_light_slow: int = 20` — 轻趋势 EMA 慢线周期

配置 SHALL 在 `BacktestConfig` 中作为 `market_filter: MarketFilterConfig` 字段存在。

#### Scenario: 默认关闭
- **WHEN** market_filter.enabled == False
- **THEN** 系统 SHALL 使用现有 regime_on (MA60) 二值路由逻辑，行为不变

#### Scenario: 配置透传
- **WHEN** 用户在前端设置 market_filter 参数
- **THEN** 参数 SHALL 经 API → loader → engine → signal_provider 完整透传

### Requirement: daily_row 市场状态字段

系统 SHALL 在每日行数据中写入市场状态信息：
- `market_state`: 字符串，"BULL" / "TRANS_DOWN" / "TRANS_UP" / "BEAR"
- `trade_mode`: 字符串，"TREND_MAIN" / "TREND_LIGHT" / "NO_TRADE"

#### Scenario: daily_row 包含市场状态
- **WHEN** market_filter 启用且回测运行
- **THEN** 每行 daily_row SHALL 包含 `market_state` 和 `trade_mode` 字段

### Requirement: 市场状态分布计数器

系统 SHALL 在 metrics 中输出市场状态分布统计：
- `market_state_bull_days`: BULL 天数
- `market_state_bear_days`: BEAR 天数
- `market_state_trans_down_days`: TRANS_DOWN 天数
- `market_state_trans_up_days`: TRANS_UP 天数
- `trade_mode_main_days`: TREND_MAIN 天数
- `trade_mode_light_days`: TREND_LIGHT 天数
- `trade_mode_notrade_days`: NO_TRADE 天数

#### Scenario: 计数器输出
- **WHEN** 回测完成
- **THEN** metrics dict SHALL 包含上述 7 个计数器字段
