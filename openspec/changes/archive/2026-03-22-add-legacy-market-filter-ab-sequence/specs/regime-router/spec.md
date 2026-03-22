## MODIFIED Requirements

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

若同时满足：
- `market_filter.enabled == true`
- `market_filter.freeze_trans_up_entries == true`
- `market_state == TRANS_UP`

则系统 MUST 继续保留 legacy 原始 `market_state / trade_mode` 输出，但在买入后处理层清空当日全部新买入信号；已有持仓退出规则 SHALL 保持不变。

#### Scenario: MA200 启用时趋势模式路由
- **WHEN** market_filter 启用且 trade_mode == TREND_MAIN
- **THEN** RegimeRouterSignalProvider 仅从 SMA 信号矩阵产生买入信号

#### Scenario: MA200 启用时轻趋势路由
- **WHEN** market_filter 启用且 trade_mode == TREND_LIGHT
- **THEN** RegimeRouterSignalProvider 仅从 EMA5/20 信号矩阵产生买入信号

#### Scenario: MA200 启用时 NO_TRADE
- **WHEN** market_filter 启用且 trade_mode == NO_TRADE
- **THEN** RegimeRouterSignalProvider 不产生买入信号，仅执行退出规则

#### Scenario: TRANS_UP 冻结新买入
- **WHEN** `market_filter.freeze_trans_up_entries == true` 且当日 `market_state == TRANS_UP`
- **THEN** 系统 SHALL 清空全部新买入信号
- **THEN** 不得改写 `market_state`
- **THEN** 已有持仓仍 SHALL 继续执行退出规则

#### Scenario: MA200 关闭时向后兼容
- **WHEN** market_filter 未启用
- **THEN** 使用现有 regime_on (MA60) 二值路由逻辑，MR 路径正常工作
