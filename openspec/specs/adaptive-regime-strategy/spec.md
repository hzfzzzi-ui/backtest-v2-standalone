# adaptive-regime-strategy

## Purpose

定义自适应 regime 策略的可插拔双模式架构要求，明确趋势模式与均值回归模式的路由、参数和兼容行为。

## Requirements

### Requirement: 双模式信号路由

策略 MUST 支持两种运行模式，根据 regime 状态自动切换：
- **趋势模式 (TREND)**: 当 `regime_on = True`（benchmark > benchmark_MA）时激活
  - 信号逻辑: 委托给 trend_strategy 子策略实例（而非硬编码 SMA）
  - 默认 trend_strategy: SMACrossStrategy
- **均值回归模式 (MEAN_REVERT)**: 当 `regime_on = False` 时激活
  - 信号逻辑: 委托给 mr_strategy 子策略实例（而非硬编码 RSI）
  - 默认 mr_strategy: RSIReversalStrategy
  - 附加退出: 持仓超过 `mr_max_hold_days` 天强制卖出（由 mr_strategy 内部管理）
  - 附加退出: 亏损超过 `mr_stop_loss_pct` 强制卖出（由 mr_strategy 内部管理）

#### Scenario: 默认配置等价
- **WHEN** 用户使用默认参数（trend=SMA 5/20, mr=RSI 6/20/80）
- **THEN** 行为与重构前的 AdaptiveRegimeStrategy 完全一致

#### Scenario: 自定义趋势策略
- **WHEN** 用户配置 trend_strategy=EMA_CROSS
- **THEN** 趋势模式使用 EMA 金叉/死叉信号

### Requirement: 策略参数

系统 MUST 定义 adaptive regime 策略的分层参数表，并明确 regime、trend、mr 与 common 参数组的默认值和语义。

| 参数组 | 参数 | 默认值 | 说明 |
|-------|------|-------|------|
| regime | regime_ma | 60 | Regime 检测 MA 周期 |
| regime | benchmark_symbol | 000300.SH | Regime 检测基准指数 |
| trend | strategy | SMA_CROSS | 趋势模式子策略名称 |
| trend | fast | 5 | 趋势模式快均线周期 |
| trend | slow | 20 | 趋势模式慢均线周期 |
| mr | strategy | RSI_REVERSAL | MR 模式子策略名称 |
| mr | rsi_period | 6 | RSI 周期 |
| mr | rsi_buy_threshold | 20 | RSI 买入阈值 |
| mr | rsi_sell_threshold | 80 | RSI 卖出阈值 |
| mr | mr_max_hold_days | 5 | 最大持仓天数 |
| mr | mr_stop_loss_pct | 0.03 | 止损百分比 |
| common | order_size | 1000 | 默认下单数量 |

#### Scenario: 分层参数解析
- **WHEN** 后端收到 regime + trend + mr 三组参数
- **THEN** 分别传递给 RegimeDetector、trend_strategy、mr_strategy 构造函数
