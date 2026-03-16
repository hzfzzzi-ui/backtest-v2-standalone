## ADDED Requirements

### Requirement: 默认 runtime route 必须拆为阶段 façade
系统 MUST 将默认 vector runtime route 拆成稳定 façade 与独立阶段模块。`strict_runtime_default.py` SHALL 只保留 façade 编排职责，具体实现 MUST 按 `input`、`benchmark`、`signal`、`daily-loop` 和 `result` 五个阶段外提。

#### Scenario: 默认 route 进入主流程
- **WHEN** 默认 route 执行一次 `run_vector_portfolio_backtest_default_route`
- **THEN** façade MUST 按固定顺序调度输入、基准、信号、逐日循环和结果汇总阶段
- **THEN** façade 文件 SHALL NOT 再直接承载完整阶段实现

#### Scenario: 拆分后验证默认 route
- **WHEN** 系统完成默认 route 阶段拆分
- **THEN** `baseline_V10.1 -> exp_20260314_144548534_7db9` 的关键结果 MUST 与拆分前完全一致
- **THEN** 拆分 SHALL NOT 改变执行时点、成交规则或统计口径

### Requirement: Signal Provider 热点必须拆为 façade + config/state + routes
系统 MUST 将热点 signal provider 拆为 façade、参数快照、运行时状态和 route/precompute 模块。`regime_router_signal_provider.py` 与 `breakout_signal_provider.py` SHALL NOT 继续把 façade、运行时 ndarray 状态和 route 行为长期混在单文件中。

#### Scenario: RegimeRouter provider 预计算
- **WHEN** `RegimeRouterSignalProvider.precompute()` 被调用
- **THEN** provider façade MUST 将重型预计算逻辑委托给专用 precompute 模块
- **THEN** façade SHALL 只维护稳定协议和调度边界

#### Scenario: Breakout provider 逐日信号
- **WHEN** `BreakoutTrendProvider.day_signals()` 被调用
- **THEN** provider façade MUST 基于集中 state/config 调度 route 逻辑
- **THEN** façade SHALL NOT 继续依赖分散在 `self` 上的大量隐式状态字段

### Requirement: 热点拆分必须先收 state owner 再迁逻辑
系统 MUST 先为热点 runtime/provider 文件建立集中 state 或 config owner，再迁移 `precompute`、`day route` 或阶段实现。系统 SHALL NOT 仅通过继续抽零散 helper 来伪装完成模块化。

#### Scenario: Provider 开始模块化
- **WHEN** 某个 provider 热点开始拆分
- **THEN** 系统 MUST 先定义统一的 state/config owner
- **THEN** 后续 route 或 precompute 模块 MUST 通过该 owner 访问共享状态
