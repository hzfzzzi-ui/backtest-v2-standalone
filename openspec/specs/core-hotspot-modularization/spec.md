# core-hotspot-modularization Specification

## Purpose
约束默认 runtime route 和热点 signal provider 的模块化方式，确保热点文件拆分为 facade 与阶段模块后仍保持 `baseline_V10.1` 行为稳定。
## Requirements
### Requirement: 默认 runtime route 必须拆为阶段 facade
系统 MUST 将默认 vector runtime route 拆成稳定 facade 与独立阶段模块。`strict_runtime_default.py` SHALL 只保留 facade 编排职责，具体实现 MUST 按 `input`、`benchmark`、`signal`、`daily-loop` 和 `result` 五个阶段外提。

#### Scenario: 默认 route 进入主流程
- **WHEN** 默认 route 执行一次 `run_vector_portfolio_backtest_default_route`
- **THEN** facade MUST 按固定顺序调度输入、基准、信号、逐日循环和结果汇总阶段
- **THEN** facade 文件 SHALL NOT 再直接承载完整阶段实现

#### Scenario: 拆分后验证默认 route
- **WHEN** 系统完成默认 route 阶段拆分
- **THEN** `baseline_V10.1 -> exp_20260314_144548534_7db9` 的关键结果 MUST 与拆分前完全一致
- **THEN** 拆分 SHALL NOT 改变执行时点、成交规则或统计口径

### Requirement: Signal provider 热点必须拆为 facade 加 state/config 加 routes
系统 MUST 将热点 signal provider 拆为 facade、参数快照、运行时状态和 route/precompute 模块。`regime_router_signal_provider.py` 与 `breakout_signal_provider.py` SHALL NOT 继续把 facade、运行时 ndarray 状态和 route 行为长期混在单文件中。

#### Scenario: RegimeRouter provider 预计算
- **WHEN** `RegimeRouterSignalProvider.precompute()` 被调用
- **THEN** provider facade MUST 将重型预计算逻辑委托给专用 precompute 模块
- **THEN** facade SHALL 只维护稳定协议和调度边界

#### Scenario: Breakout provider 逐日信号
- **WHEN** `BreakoutTrendProvider.day_signals()` 被调用
- **THEN** provider facade MUST 基于集中 state/config 调度 route 逻辑
- **THEN** facade SHALL NOT 继续依赖分散在 `self` 上的大量隐式状态字段

### Requirement: 热点拆分必须先收 state owner 再迁逻辑
系统 MUST 先为热点 runtime/provider 文件建立集中 state 或 config owner，再迁移 `precompute`、`day route` 或阶段实现。系统 SHALL NOT 仅通过继续抽零散 helper 来伪装完成模块化。

#### Scenario: Provider 开始模块化
- **WHEN** 某个 provider 热点开始拆分
- **THEN** 系统 MUST 先定义统一的 state/config owner
- **THEN** 后续 route 或 precompute 模块 MUST 通过该 owner 访问共享状态

### Requirement: Default runtime daily loop 不得继续承担最终 diagnostics 口径
系统 MUST 将 default runtime daily loop 收口为执行主循环与原始事件汇总 owner。`strict_runtime_daily_loop.py` SHALL NOT 继续直接定义最终 buy funnel、stage note 或 surface-facing diagnostics 口径。

系统 MUST 将 default runtime daily loop 收口为执行主循环与原始事件汇总 owner。`strict_runtime_daily_loop.py` SHALL NOT 继续直接定义最终 buy funnel、stage note 或 surface-facing diagnostics 口径。

#### Scenario: default runtime 日循环执行
- **WHEN** `strict_runtime_daily_loop.py` 完成某个交易日的执行处理
- **THEN** 它 MUST 只输出执行原始事件、debug plan 和 diagnostics input
- **THEN** 最终 diagnostics 归一化 MUST 由独立 diagnostics builder 完成

#### Scenario: 继续拆 daily loop 热点
- **WHEN** 后续继续拆分 default runtime daily loop
- **THEN** 系统 SHALL NOT 因结构调整改变 diagnostics 最终值
- **THEN** diagnostics contract MUST 成为保护执行本体不被诊断逻辑反向污染的边界### Requirement: core 热点文件必须按职责持续拆分且不得改变 V10.1 结果
系统 MUST 对 `backend/core` 中的大型热点文件进行职责拆分，包括但不限于 helper 抽离、类型收口、纯函数搬移和模块边界澄清。该拆分 SHALL NOT 改变 `baseline_V10.1 -> exp_20260314_144548534_7db9` 的执行时点、成交规则、绩效结果和 counters。

#### Scenario: 拆分 engine_vector 热点文件
- **WHEN** 系统拆分 `breakout_signal_provider.py`、`strict_runtime_impl.py` 或同等级热点文件
- **THEN** 拆分 MUST 只移动纯逻辑、类型或 helper
- **THEN** 拆分后 `baseline_V10.1` 的 perf 和 counters MUST 保持不变

#### Scenario: 拆分 portfolio 或 service 热点文件
- **WHEN** 系统拆分 `portfolio_builder.py`、`market_snapshot_service.py` 或其他热点文件
- **THEN** 新边界 MUST 让职责更单一、依赖方向更清晰
- **THEN** 该拆分 SHALL NOT 顺手引入新的研究行为变化

### Requirement: core 热点拆分必须优先服务多资产扩展
系统 MUST 让 `backend/core` 热点拆分优先消除会阻碍多资产接入的耦合点，例如把当前 A 股特化展示逻辑、历史配置语义或研究级临时逻辑继续固化在核心主干中。

#### Scenario: 新资产需要复用现有核心模块
- **WHEN** 后续资产类型需要复用某个核心模块
- **THEN** 拆分后的模块 MUST 提供清晰的输入输出与单一职责
- **THEN** 新资产接入 SHALL NOT 被旧耦合结构阻塞
