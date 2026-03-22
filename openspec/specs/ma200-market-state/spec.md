# ma200-market-state Specification

## Purpose
基于基准指数 MA200 位置与斜率的四态市场分类，及对应的交易模式映射。
## Requirements
### Requirement: MA200 四态市场分类

系统 SHALL 在 `RegimeRouterSignalProvider.precompute()` 和 legacy 运行时路径中，基于基准指数计算四种市场状态：
- **BULL**: benchmark close > MA(long_ma_window) 且长均线 slope >= 0
- **TRANS_DOWN**: benchmark close > MA(long_ma_window) 且长均线 slope < 0
- **TRANS_UP**: benchmark close < MA(long_ma_window) 且长均线 slope >= 0
- **BEAR**: benchmark close < MA(long_ma_window) 且长均线 slope < 0

长均线窗口 SHALL 由 `MarketFilterConfig.long_ma_window` 驱动，默认值为 `200`。

长均线 slope 定义为 `MA(long_ma_window)[t] - MA(long_ma_window)[t - slope_window]`，其中 `slope_window` 默认 20 个交易日。

市场状态 SHALL 存储为 `_market_state[T]` 数组（int8），在 precompute 阶段一次性计算。

系统 SHALL 在 `RegimeRouterSignalProvider.precompute()` 和 legacy 运行时路径中，基于基准指数计算四种市场状态：
- **BULL**: benchmark close > MA(long_ma_window) 且长均线 slope >= 0
- **TRANS_DOWN**: benchmark close > MA(long_ma_window) 且长均线 slope < 0
- **TRANS_UP**: benchmark close < MA(long_ma_window) 且长均线 slope >= 0
- **BEAR**: benchmark close < MA(long_ma_window) 且长均线 slope < 0

长均线窗口 SHALL 由 `MarketFilterConfig.long_ma_window` 驱动，默认值为 `200`。

长均线 slope 定义为 `MA(long_ma_window)[t] - MA(long_ma_window)[t - slope_window]`，其中 `slope_window` 默认 20 个交易日。

市场状态 SHALL 存储为 `_market_state[T]` 数组（int8），在 precompute 阶段一次性计算。

#### Scenario: 默认仍使用 MA200
- **WHEN** `market_filter.long_ma_window` 未显式设置
- **THEN** 系统 SHALL 使用 `200` 作为长均线窗口

#### Scenario: 长均线窗口可配置
- **WHEN** `market_filter.long_ma_window = 160`
- **THEN** 系统 SHALL 使用 `MA160` 及其 slope 计算 `BULL / TRANS_DOWN / TRANS_UP / BEAR`

#### Scenario: 长均线数据不足
- **WHEN** 交易天数 < `long_ma_window + slope_window`，长均线或 slope 无法计算
- **THEN** 当日 `market_state` SHALL 默认为 `BULL`### Requirement: 交易模式映射

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
- `long_ma_window: int = 200` — legacy 长均线窗口
- `slope_window: int = 20` — 长均线斜率计算回看窗口
- `bull_multiplier: float = 1.5` — BULL 态 risk_budget trend_multiplier
- `light_multiplier: float = 0.6` — TREND_LIGHT 默认 multiplier
- `trans_down_multiplier: float | None = None` — `TRANS_DOWN` 专用 multiplier；为 `None` 时回退到 `light_multiplier`
- `trans_up_multiplier: float | None = None` — `TRANS_UP` 专用 multiplier；为 `None` 时回退到 `light_multiplier`
- `freeze_trans_up_entries: bool = False` — 是否在 `TRANS_UP` 阶段禁止新开仓
- `ema_light_fast: int = 5` — 轻趋势 EMA 快线周期
- `ema_light_slow: int = 20` — 轻趋势 EMA 慢线周期

配置 SHALL 在 `BacktestConfig` 中作为 `market_filter: MarketFilterConfig` 字段存在。

系统 SHALL 提供 `MarketFilterConfig` dataclass：
- `enabled: bool = False` — 总开关
- `long_ma_window: int = 200` — legacy 长均线窗口
- `slope_window: int = 20` — 长均线斜率计算回看窗口
- `bull_multiplier: float = 1.5` — BULL 态 risk_budget trend_multiplier
- `light_multiplier: float = 0.6` — TREND_LIGHT 默认 multiplier
- `trans_down_multiplier: float | None = None` — `TRANS_DOWN` 专用 multiplier；为 `None` 时回退到 `light_multiplier`
- `trans_up_multiplier: float | None = None` — `TRANS_UP` 专用 multiplier；为 `None` 时回退到 `light_multiplier`
- `freeze_trans_up_entries: bool = False` — 是否在 `TRANS_UP` 阶段禁止新开仓
- `ema_light_fast: int = 5` — 轻趋势 EMA 快线周期
- `ema_light_slow: int = 20` — 轻趋势 EMA 慢线周期

配置 SHALL 在 `BacktestConfig` 中作为 `market_filter: MarketFilterConfig` 字段存在。

#### Scenario: 过渡态 multiplier 分拆
- **WHEN** 用户显式设置 `trans_down_multiplier` 与 `trans_up_multiplier`
- **THEN** 系统 SHALL 在 `TRANS_DOWN` 与 `TRANS_UP` 使用各自 multiplier，而不是共享 `light_multiplier`

#### Scenario: 过渡态 multiplier 回退
- **WHEN** `trans_down_multiplier` 或 `trans_up_multiplier` 为 `None`
- **THEN** 对应状态 SHALL 回退使用 `light_multiplier`

#### Scenario: freeze_trans_up_entries 配置透传
- **WHEN** 用户在配置中设置 `freeze_trans_up_entries = true`
- **THEN** 参数 SHALL 经 API → loader → engine → signal_provider 完整透传### Requirement: daily_row 市场状态字段

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

### Requirement: MA200 状态机必须降级为显式 fallback 模式
`ma200-market-state` SHALL 不再被视为正式市场状态真相源，而 MUST 作为 `market-regime-framework` 未启用、特征不可用或用户显式指定时的兼容 fallback 模式。系统 MUST 在运行元数据中明确标识当前使用的是 `ma200_legacy`，避免与正式 regime framework 混淆。

`ma200-market-state` SHALL 不再被视为正式市场状态真相源，而 MUST 作为 `market-regime-framework` 未启用、特征不可用或用户显式指定时的兼容 fallback 模式。系统 MUST 在运行元数据中明确标识当前使用的是 `ma200_legacy`，避免与正式 regime framework 混淆。

#### Scenario: 用户显式选择 legacy 模式
- **WHEN** 用户在配置中指定 `regime_engine = ma200_legacy`
- **THEN** 系统 MUST 使用现有 MA200 四态逻辑，并在产物中标记 `regime_engine = ma200_legacy`

#### Scenario: 正式框架特征不可用时回退
- **WHEN** 正式市场状态框架因特征覆盖不足而无法运行，且配置允许回退
- **THEN** 系统 MUST 明确回退到 `ma200_legacy`，并记录回退原因### Requirement: MA200 fallback 输出必须带兼容语义标记
在 `ma200_legacy` 模式下，系统 SHALL 继续输出现有 `BULL / TRANS_UP / TRANS_DOWN / BEAR` 和 `TREND_MAIN / TREND_LIGHT / NO_TRADE`，但 MUST 同时输出：
- `regime_engine`
- `regime_semantics = legacy_price_filter`

#### Scenario: 前端展示区分 legacy 与正式框架
- **WHEN** 前端加载一条使用 MA200 fallback 的实验
- **THEN** 结果页 MUST 能识别该状态线属于 legacy 价格过滤器，而不是正式多因子 regime 框架

### Requirement: MA200 状态机作为 legacy compatibility engine 保留
系统 SHALL 将现有 `ma200-market-state` 明确定义为 `ma200_legacy` compatibility engine。

该 engine：

- 继续保持当前行为
- 继续可被正式主线调用
- 不得被本 change 直接删除或无提示替换

#### Scenario: 选择 ma200_legacy
- **WHEN** `regime_engine.engine = ma200_legacy`
- **THEN** 系统 SHALL 保持当前 `close vs MA200 + slope + legacy router` 行为不变

#### Scenario: weekly five-state 不覆盖 legacy
- **WHEN** 本 change 落地
- **THEN** `ma200_legacy` SHALL 仍然可以被配置显式选中，用于 A/B 对照与回退

### Requirement: MA200 fallback 输出必须带兼容语义标记
在 `ma200_legacy` 模式下，系统 SHALL 继续输出现有 `BULL / TRANS_UP / TRANS_DOWN / BEAR` 和 `TREND_MAIN / TREND_LIGHT / NO_TRADE`，但 MUST 同时输出：
- `regime_engine`
- `regime_semantics = legacy_price_filter`

#### Scenario: 前端展示区分 legacy 与正式框架
- **WHEN** 前端加载一条使用 MA200 fallback 的实验
- **THEN** 结果页 MUST 能识别该状态线属于 legacy 价格过滤器，而不是正式多因子 regime 框架

