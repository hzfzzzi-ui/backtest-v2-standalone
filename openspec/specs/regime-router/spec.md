# regime-router

市况路由器 — 根据 regime detection 结果将信号生成委托给不同子策略。

## Requirements

### Requirement: RegimeDetector 独立组件

系统 SHALL 提供独立的 `RegimeDetector` 类，负责判断当前市况状态。
- 输入: 当日及之前的 benchmark 历史数据
- 输出: regime 状态枚举（TREND / MEAN_REVERT）
- 检测逻辑: benchmark close vs MA(regime_ma)
- 只使用当前 bar 及之前的数据（无未来函数）
- 数据不足时默认返回 TREND

#### Scenario: 牛市检测
- **WHEN** benchmark close > benchmark MA(regime_ma)
- **THEN** RegimeDetector 返回 TREND

#### Scenario: 非牛市检测
- **WHEN** benchmark close <= benchmark MA(regime_ma)
- **THEN** RegimeDetector 返回 MEAN_REVERT

#### Scenario: 数据不足
- **WHEN** benchmark 历史数据行数 < regime_ma
- **THEN** RegimeDetector 返回 TREND（默认）

### Requirement: RegimeRouter 路由壳

系统 SHALL 提供 `RegimeRouter` 类，实现 `Strategy.generate_signals()` 接口，内部持有：
- 一个 `RegimeDetector` 实例
- 一个趋势模式子策略（`trend_strategy: Strategy`）
- 一个轻趋势模式子策略（`mr_strategy: Strategy`）— 原 MR 槽位，现用于 TREND_LIGHT

RegimeRouter 的 `generate_signals()` 逻辑：
1. 调用 RegimeDetector 判断当前 regime
2. 若 regime = TREND → 委托 `trend_strategy.generate_signals()`
3. 若 regime = MEAN_REVERT → 委托 `mr_strategy.generate_signals()`
4. MR 模式产生的持仓在 regime 切回 TREND 时，MUST 继续由 MR 子策略的退出规则管理

当 MarketFilterConfig.enabled == True 时，RegimeRouter 的信号分发 SHALL 由 `_trade_mode[T]` 三态驱动：
1. trade_mode == TREND_MAIN → 委托 `trend_strategy` 的信号矩阵
2. trade_mode == TREND_LIGHT → 委托 `mr_strategy`（现为 EMA Cross）的信号矩阵
3. trade_mode == NO_TRADE → 不产生任何买入信号，仅处理退出

当 MarketFilterConfig.enabled == False 时，行为 SHALL 与改动前完全一致（MA60 二值路由）。

#### Scenario: 趋势模式路由
- **WHEN** RegimeDetector 返回 TREND 且无 MR 遗留持仓
- **THEN** RegimeRouter 仅调用 trend_strategy.generate_signals()

#### Scenario: MR 模式路由
- **WHEN** RegimeDetector 返回 MEAN_REVERT
- **THEN** RegimeRouter 仅调用 mr_strategy.generate_signals()

#### Scenario: MR 遗留持仓管理
- **WHEN** RegimeDetector 返回 TREND 但存在 MR 模式产生的未平仓持仓
- **THEN** RegimeRouter 对非 MR 持仓调用 trend_strategy，对 MR 持仓继续应用 mr_strategy 的退出规则（止损/超时），不产生新 MR 买入

#### Scenario: MA200 启用时趋势模式路由
- **WHEN** market_filter 启用且 trade_mode == TREND_MAIN
- **THEN** RegimeRouterSignalProvider 仅从 SMA 信号矩阵产生买入信号

#### Scenario: MA200 启用时轻趋势路由
- **WHEN** market_filter 启用且 trade_mode == TREND_LIGHT
- **THEN** RegimeRouterSignalProvider 仅从 EMA5/20 信号矩阵产生买入信号

#### Scenario: MA200 启用时 NO_TRADE
- **WHEN** market_filter 启用且 trade_mode == NO_TRADE
- **THEN** RegimeRouterSignalProvider 不产生买入信号，仅执行退出规则

#### Scenario: MA200 关闭时向后兼容
- **WHEN** market_filter 未启用
- **THEN** 使用现有 regime_on (MA60) 二值路由逻辑，MR 路径正常工作

### Requirement: 子策略可插拔

RegimeRouter 的 trend_strategy 和 mr_strategy MUST 接受任意实现了 `Strategy.generate_signals()` 接口的策略实例。
- trend_strategy 可以是 SMACrossStrategy、EMACrossStrategy 等
- mr_strategy 默认 SHALL 从 RSIReversalStrategy 变更为 EMACrossStrategy(fast=5, slow=20)（当 MA200 filter 启用时）
- 用户仍可通过配置指定其他策略
- 每个子策略独立管理自身的参数和状态

#### Scenario: SMA + RSI 组合
- **WHEN** 用户配置 trend_strategy=SMA_CROSS, mr_strategy=RSI_REVERSAL
- **THEN** 系统构造 RegimeRouter(trend=SMACrossStrategy(...), mr=RSIReversalStrategy(...))

#### Scenario: EMA + RSI 组合
- **WHEN** 用户配置 trend_strategy=EMA_CROSS, mr_strategy=RSI_REVERSAL
- **THEN** 系统构造 RegimeRouter(trend=EMACrossStrategy(...), mr=RSIReversalStrategy(...))

#### Scenario: 默认 mr_strategy 为 EMA5/20
- **WHEN** 用户配置 regime_router 且未显式指定 mr_strategy
- **THEN** mr_strategy SHALL 默认为 EMACrossStrategy(fast=5, slow=20)

#### Scenario: 用户可覆盖 mr_strategy
- **WHEN** 用户显式配置 mr_strategy=rsi_reversal
- **THEN** 系统 SHALL 使用用户指定的策略

### Requirement: Signal meta 字段兼容

RegimeRouter 产生的所有 Signal MUST 包含以下 meta 字段（与现有 adaptive_regime 保持兼容）：
- `regime_on`: bool
- `signal_mode`: "TREND" | "TREND_LIGHT" | "MEAN_REVERT"（新增 TREND_LIGHT）
- `market_state`: "BULL" | "TRANS_DOWN" | "TRANS_UP" | "BEAR"（新增，MA200 filter 启用时）
- `trade_mode`: "TREND_MAIN" | "TREND_LIGHT" | "NO_TRADE"（新增，MA200 filter 启用时）
- `benchmark_close`: float | None
- `benchmark_ma`: float | None
- 子策略特有的 meta 字段由子策略自行填充

#### Scenario: meta 字段完整性
- **WHEN** RegimeRouter 产生任意 Signal
- **THEN** Signal.meta 包含 regime_on、signal_mode、benchmark_close、benchmark_ma 四个字段

#### Scenario: TREND_LIGHT 信号 meta
- **WHEN** trade_mode == TREND_LIGHT 且产生买入信号
- **THEN** Signal.meta SHALL 包含 signal_mode="TREND_LIGHT"、market_state、trade_mode

