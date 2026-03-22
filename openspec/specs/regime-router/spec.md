# regime-router

## Purpose
定义市场状态路由、兼容 trade_mode 输出、legacy overlay 与正式 regime engine 接入的统一合同，确保不同过滤器只在受控边界内影响执行层。

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

#### Scenario: TRANS_UP 冻结新买入
- **WHEN** `market_filter.freeze_trans_up_entries == true` 且当日 `market_state == TRANS_UP`
- **THEN** 系统 SHALL 清空全部新买入信号
- **THEN** 不得改写 `market_state`
- **THEN** 已有持仓仍 SHALL 继续执行退出规则

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

### Requirement: Regime router 支持 legacy 执行层 veto overlay

系统 SHALL 允许 `ma200_legacy` 保持原始状态判定不变，同时可选接入一个辅助 veto overlay。

#### Scenario: legacy overlay 不改变原始状态输出

- **WHEN** `regime_engine.engine = ma200_legacy` 且启用 `legacy_turn_weak_overlay`
- **THEN** 系统 SHALL 保持 legacy 原始 `market_state / trade_mode` 语义不变
- **THEN** overlay 仅影响执行层 `trade_mode / risk_budget_multiplier`

#### Scenario: overlay 命中 TURN_WEAK 时关闭交易

- **WHEN** `regime_engine.engine = ma200_legacy` 且启用 `legacy_turn_weak_overlay`
- **AND** 辅助 weekly 状态为 `TURN_WEAK`
- **THEN** 执行层 SHALL 输出 `trade_mode = NO_TRADE`

### Requirement: 最小 A/B 只允许 legacy overlay 变化

系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `ma200_legacy + turn_weak_zero_overlay`

#### Scenario: A/B 配置一致

- **WHEN** 运行 legacy turn_weak overlay A/B
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致
- **THEN** 唯一 intended diff SHALL 仅为 legacy overlay 的启用状态

### Requirement: Weekly five-state 只改变市场过滤与风险预算

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 保持个股信号逻辑不变：

- 仍使用主线 `40日突破 + 40日个股残差动量排序`
- 不得切换到旧 `TREND_LIGHT -> EMA5/20` 替代分支

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 保持个股信号逻辑不变：

- 仍使用主线 `40日突破 + 40日个股残差动量排序`
- 不得切换到旧 `TREND_LIGHT -> EMA5/20` 替代分支

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 保持个股信号逻辑不变：

- 仍使用主线 `40日突破 + 40日个股残差动量排序`
- 不得切换到旧 `TREND_LIGHT -> EMA5/20` 替代分支

#### Scenario: 非对称预算模式不改变五档原始状态

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = asymmetric_budget`
- **THEN** 系统 SHALL 继续输出五档原始 `market_state_raw_name / market_state_smoothed_name / market_state_score`
- **THEN** 非对称模式仅影响执行预算与 `trade_mode`

#### Scenario: 非对称预算模式的 trade_mode

- **WHEN** `risk_budget_mode = asymmetric_budget`
- **THEN** `BULL_MAIN / TURN_STRONG / LIGHT_TREND` SHALL 输出 `trade_mode = TREND_MAIN`
- **THEN** `TURN_WEAK / DEFENSIVE` SHALL 输出 `trade_mode = NO_TRADE`

#### Scenario: 非防守状态仍走主线信号
- **WHEN** `market_state_5` 属于 `BULL_MAIN / TURN_STRONG / LIGHT_TREND / TURN_WEAK`
- **THEN** 系统 SHALL 继续使用主线 breakout + residual 信号逻辑

#### Scenario: 防守状态阻止新开仓
- **WHEN** `market_state_5 = DEFENSIVE`
- **THEN** 系统 SHALL 阻止新的买入信号，但继续执行已有持仓退出规则

### Requirement: 最小 A/B 只允许预算模式变化

系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `weekly_five_state + five_state`
- `weekly_five_state + asymmetric_budget`

并保证 intended diff 限制在：

- `regime_engine.engine`
- `weekly_five_state.risk_budget_mode`

#### Scenario: A/B 配置一致

- **WHEN** 运行 weekly asymmetric budget A/B
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致
- **THEN** `weekly_five_state` 两组之间唯一 intended diff SHALL 仅为 `risk_budget_mode`

#### Scenario: 三档预算模式不改变原始状态输出

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = three_state`
- **THEN** 系统 SHALL 继续输出原始五档 `market_state_raw_name / market_state_smoothed_name`
- **THEN** 系统 SHALL 继续输出原始 `market_state_score`
- **THEN** 三档仅用于执行预算与可交易控制

#### Scenario: 三档预算模式的 trade_mode 兼容输出

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = three_state`
- **THEN** `BULL_MAIN / TURN_STRONG / LIGHT_TREND` SHALL 输出兼容 `trade_mode = TREND_MAIN`
- **THEN** `TURN_WEAK / DEFENSIVE` SHALL 输出兼容 `trade_mode = NO_TRADE`

### Requirement: Regime router 支持 engine 选择
系统 SHALL 允许 `regime-router` 根据 `regime_engine.engine` 在以下两种引擎之间切换：

- `ma200_legacy`
- `weekly_five_state`

#### Scenario: 使用 weekly_five_state
- **WHEN** `regime_engine.engine = weekly_five_state`
- **THEN** router SHALL 消费周度五态状态机的日频前向填充结果

### Requirement: trade_mode 兼容输出
当 `regime_engine.engine = weekly_five_state` 时，系统 SHALL 继续输出兼容的 `trade_mode`：

- `TREND_MAIN`：对应 `BULL_MAIN / TURN_STRONG / LIGHT_TREND / TURN_WEAK`
- `NO_TRADE`：对应 `DEFENSIVE`

#### Scenario: 五态兼容 trade_mode
- **WHEN** weekly five-state 运行
- **THEN** 现有前后端消费链仍可从 `trade_mode` 判断是否允许开新仓

### Requirement: 最小 A/B 只允许 engine 变化
系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `weekly_five_state`

并保证唯一 intended diff 为 `regime_engine.engine`。

#### Scenario: A/B 配置一致
- **WHEN** 运行 weekly five-state A/B 实验
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致

### Requirement: 最小 A/B 只允许预算模式变化

系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `weekly_five_state + five_state budget`
- `weekly_five_state + three_state budget`

并保证 intended diff 限制在：

- `regime_engine.engine`
- `weekly_five_state.risk_budget_mode`

#### Scenario: A/B 配置一致

- **WHEN** 运行 weekly three-state budget A/B
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致

### Requirement: RegimeRouter 必须消费正式 regime engine 输出
当 `market-regime-framework` 启用时，`regime-router` SHALL 以正式 regime engine 的输出作为唯一状态输入，至少消费以下字段：
- `market_state`
- `regime_confidence`
- `regime_duration_bars`
- `regime_transition_reason`
- `feature_availability`

`regime-router` MUST 不再假设 `market_state` 仅由 `close vs MA200 + slope` 唯一决定。

#### Scenario: Router 使用正式状态输入
- **WHEN** 正式市场状态框架启用
- **THEN** RegimeRouter MUST 从正式 regime engine 读取状态与置信度，而不是自行重算简化均线状态

### Requirement: trade_mode 必须由状态、置信度和 persistence 联合生成
当正式市场状态框架启用时，`trade_mode` SHALL 由 `market_state`、`regime_confidence`、`regime_duration_bars` 与执行确认条件联合决定，而不是简单的一对一映射。系统 MUST 允许表达：
- `market_state = TRANS_UP` 但 `trade_mode = NO_TRADE`
- `market_state = TRANS_DOWN` 但 `trade_mode = TREND_LIGHT`

#### Scenario: 低置信度 TRANS_UP 不开启交易
- **WHEN** `market_state = TRANS_UP` 且 `regime_confidence` 低于配置阈值
- **THEN** trade_mode MUST 保持 `NO_TRADE`

#### Scenario: 高置信度过渡态允许轻仓交易
- **WHEN** `market_state` 为过渡态且满足 persistence 与执行确认条件
- **THEN** trade_mode MAY 进入 `TREND_LIGHT`

### Requirement: RegimeRouter 必须输出状态到信号与日度产物
当正式市场状态框架启用时，RegimeRouter 产生的信号和日度产物 MUST 带出正式状态语义，用于前端显示与审计。至少包括：
- `market_state`
- `trade_mode`
- `regime_confidence`
- `regime_engine`

#### Scenario: 信号 meta 携带正式状态
- **WHEN** RegimeRouter 产生任意 BUY/SELL 信号
- **THEN** Signal.meta MUST 包含当前正式状态字段与 `regime_engine`

