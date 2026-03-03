# regime-router (delta)

MA200 市场过滤器对 regime-router 的改动。

## MODIFIED Requirements

### Requirement: RegimeRouter 路由壳

系统 SHALL 提供 `RegimeRouter` 类，实现 `Strategy.generate_signals()` 接口，内部持有：
- 一个 `RegimeDetector` 实例
- 一个趋势模式子策略（`trend_strategy: Strategy`）
- 一个轻趋势模式子策略（`mr_strategy: Strategy`）— 原 MR 槽位，现用于 TREND_LIGHT

当 MarketFilterConfig.enabled == True 时，RegimeRouter 的信号分发 SHALL 由 `_trade_mode[T]` 三态驱动：
1. trade_mode == TREND_MAIN → 委托 `trend_strategy` 的信号矩阵
2. trade_mode == TREND_LIGHT → 委托 `mr_strategy`（现为 EMA Cross）的信号矩阵
3. trade_mode == NO_TRADE → 不产生任何买入信号，仅处理退出

当 MarketFilterConfig.enabled == False 时，行为 SHALL 与改动前完全一致（MA60 二值路由）。

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

#### Scenario: 默认 mr_strategy 为 EMA5/20
- **WHEN** 用户配置 regime_router 且未显式指定 mr_strategy
- **THEN** mr_strategy SHALL 默认为 EMACrossStrategy(fast=5, slow=20)

#### Scenario: 用户可覆盖 mr_strategy
- **WHEN** 用户显式配置 mr_strategy=rsi_reversal
- **THEN** 系统 SHALL 使用用户指定的策略

### Requirement: Signal meta 字段兼容

RegimeRouter 产生的所有 Signal MUST 包含以下 meta 字段：
- `regime_on`: bool
- `signal_mode`: "TREND" | "TREND_LIGHT" | "MEAN_REVERT"（新增 TREND_LIGHT）
- `market_state`: "BULL" | "TRANS_DOWN" | "TRANS_UP" | "BEAR"（新增）
- `trade_mode`: "TREND_MAIN" | "TREND_LIGHT" | "NO_TRADE"（新增）
- 子策略特有的 meta 字段由子策略自行填充

#### Scenario: TREND_LIGHT 信号 meta
- **WHEN** trade_mode == TREND_LIGHT 且产生买入信号
- **THEN** Signal.meta SHALL 包含 signal_mode="TREND_LIGHT"、market_state、trade_mode

## REMOVED Requirements

### Requirement: RSIReversalStrategy 独立提取
**Reason**: MR 路径在 MA200 过滤器启用时被完全废弃。RSIReversalStrategy 类保留但不再作为 RegimeRouter 的默认 mr_strategy。
**Migration**: mr_strategy 槽位默认改为 EMACrossStrategy(fast=5, slow=20)。如需使用 RSI MR，用户可在配置中显式指定 mr_strategy=rsi_reversal。
