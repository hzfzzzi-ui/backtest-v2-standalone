# signal-provider-protocol Specification

## Purpose
定义统一信号提供者协议、日度上下文与信号快照的数据契约，并约束其对多 alpha 组合运行时的兼容行为。
## Requirements
### Requirement: SignalProvider 协议
引擎 SHALL 定义 `SignalProvider` 协议（Protocol），包含以下方法：
- `precompute(*, history, benchmark, raw_history, trading_days, strategy, ...) -> None`：在日循环前执行一次性预计算
- `day_signals(day, day_idx, ctx: DayContext) -> DaySignals`：在单策略与多 alpha 组合场景下生成当日原始信号、组合后信号和最终卖出/买入信号

实现类 MUST 不直接修改 `DayContext` 中的引擎状态（positions, cash, holding_sources），信号通过返回值传递。
实现类 MAY 维护自身的内部可变状态（如 break_streak, signal matrices）。
实现类 MAY 调度多个 alpha 模块，但 MUST 在单个交易日内先生成原始 alpha 信号，再完成组合决策，最后返回供订单规划使用的最终信号列表。

#### Scenario: SMA 信号提供者
- **WHEN** 使用 SMA 策略（ma_type=SMA/EMA）
- **THEN** `precompute()` 构建 OHLC/feature/signal 矩阵和候选索引；`day_signals()` 通过矩阵索引生成单策略信号

#### Scenario: 多 alpha 信号提供者
- **WHEN** 使用启用了 `signal_generation.modules` 与 `signal_composition` 的组合策略路径
- **THEN** `day_signals()` SHALL 在同一交易日内同时返回原始 alpha 信号、组合后信号和最终买卖信号

### Requirement: DaySignals 数据类

引擎 SHALL 定义 `DaySignals` 数据类作为 `day_signals()` 的返回类型，包含：
- `sell_signals: list[Signal]`
- `buy_signals: list[Signal]`
- `raw_alpha_signals: list[Signal]`
- `composed_sell_signals: list[Signal]`
- `composed_buy_signals: list[Signal]`
- `exit_syms: set[str]`
- `strength_map: dict[str, float]`
- `mf_score_map: dict[str, float]`
- `diagnostics: dict[str, Any]`
- `exit_counts: ExitCounts`

其中 `diagnostics` SHALL 在现有稳定键之外，支持稳定透传 bull breakout veto 的诊断计数：

- `bull_breakout_quality_veto_applied`
- `bull_breakout_quality_veto_block_count`
- `bull_breakout_quality_veto_residual_block_count`
- `bull_breakout_quality_veto_margin_block_count`

引擎 SHALL 定义 `DaySignals` 数据类作为 `day_signals()` 的返回类型，包含：
- `sell_signals: list[Signal]`
- `buy_signals: list[Signal]`
- `raw_alpha_signals: list[Signal]`
- `composed_sell_signals: list[Signal]`
- `composed_buy_signals: list[Signal]`
- `exit_syms: set[str]`
- `strength_map: dict[str, float]`
- `mf_score_map: dict[str, float]`
- `diagnostics: dict[str, Any]`
- `exit_counts: ExitCounts`

其中 `diagnostics` SHALL 在现有稳定键之外，支持稳定透传 bull breakout veto 的诊断计数：

- `bull_breakout_quality_veto_applied`
- `bull_breakout_quality_veto_block_count`
- `bull_breakout_quality_veto_residual_block_count`
- `bull_breakout_quality_veto_margin_block_count`

#### Scenario: bull breakout veto 诊断透传
- **WHEN** provider 在当日对 breakout 候选执行 bull breakout quality veto
- **THEN** `DaySignals.diagnostics` SHALL 包含上述 4 个稳定键
- **THEN** 缺省时这些键 SHALL 回填为 `false / 0`

#### Scenario: veto 阈值进入信号 meta
- **WHEN** bull breakout veto 启用且候选未被阻断
- **THEN** 该买入信号 `Signal.meta` SHALL 包含：
  - `bull_breakout_quality_veto_enabled`
  - `bull_breakout_quality_veto_min_residual_strength_score`
  - `bull_breakout_quality_veto_min_breakout_margin_score`### Requirement: DayContext 数据类
引擎 SHALL 定义 `DayContext` 数据类作为引擎状态的只读快照传递给信号提供者：
- 持仓和成本信息：positions, position_avg_cost
- 持仓来源信息：holding_sources（按标的暴露 `entry_alpha_id`、`entry_sleeve_id`、`entry_reason_code`、`entry_date`）
- 财务状态：cash, nav, base_order_value, max_positions
- 价格索引：close_idx, open_idx
- 时间信息：next_day（用于查询次日开盘价）
- 风险状态：risk_on（当日大盘 regime 状态）

#### Scenario: 信号提供者读取来源上下文
- **WHEN** 来源感知退出逻辑需要判断当前持仓属于哪个 alpha
- **THEN** 信号提供者 SHALL 通过 `DayContext.holding_sources` 读取
- **THEN** 信号提供者 SHALL 不直接引用引擎内部可变状态

### Requirement: 统一引擎循环

引擎 SHALL 提供 `_run_unified_loop()` 函数，接收 `SignalProvider` 实例和引擎配置，执行单一日循环。

当 provider 路径为 breakout runtime 时，结果指标 SHALL 透传 bull breakout veto 的稳定计数器：

- `bull_breakout_quality_veto_block_count`
- `bull_breakout_quality_veto_residual_block_count`
- `bull_breakout_quality_veto_margin_block_count`

引擎 SHALL 提供 `_run_unified_loop()` 函数，接收 `SignalProvider` 实例和引擎配置，执行单一日循环。

当 provider 路径为 breakout runtime 时，结果指标 SHALL 透传 bull breakout veto 的稳定计数器：

- `bull_breakout_quality_veto_block_count`
- `bull_breakout_quality_veto_residual_block_count`
- `bull_breakout_quality_veto_margin_block_count`

#### Scenario: veto 计数进入 run_meta / metrics
- **WHEN** breakout provider 启用 bull breakout veto 并完成回测
- **THEN** `metrics` 与 `run_meta.json.counters` SHALL 包含上述 3 个计数器### Requirement: 热点 provider facade 必须允许外部 state、precompute 和 route 模块
系统 MUST 允许热点 signal provider 通过 facade 调度外部 state owner、precompute 模块和 day route 模块，只要对外仍保持既有 `SignalProvider` 协议不变。provider facade SHALL NOT 重新退化为同时承载全部状态、预计算和 route 行为的单文件 owner。

#### Scenario: Provider facade 调度预计算
- **WHEN** 热点 provider 执行 `precompute()`
- **THEN** facade MAY 调度外部 precompute 模块完成重型矩阵与诊断准备
- **THEN** 对外 `SignalProvider.precompute()` 合同 MUST 保持不变

#### Scenario: Provider facade 调度逐日路由
- **WHEN** 热点 provider 执行 `day_signals()`
- **THEN** facade MAY 调度外部 route 模块生成当日信号
- **THEN** 对外 `DaySignals` 语义 MUST 保持不变

### Requirement: SignalProvider 和 route registry 必须显式消费 asset profile
系统 MUST 要求 signal provider façade、route registry 和 runtime route 选择显式消费 canonical `asset_profile` 或 `market_profile`。这些模块 SHALL NOT 再把 A 股作为隐式全局前提。

#### Scenario: 运行当前 A 股 provider
- **WHEN** runtime route 选择当前 A 股 provider
- **THEN** route 选择 MUST 基于 canonical A 股 asset profile
- **THEN** 选择结果 MUST 保持当前 `V10.1` provider 行为不变

#### Scenario: 运行未支持资产
- **WHEN** route registry 收到尚未实现的 asset profile
- **THEN** 系统 MUST 明确返回 unsupported error
- **THEN** 系统 SHALL NOT 静默复用 A 股 provider

### Requirement: Provider façade 不得继续内嵌资产 family 的隐式默认
系统 MUST 要求 provider façade 的 `precompute()` 和 `day_signals()` 入口显式可见资产上下文。与资产 family 强绑定的约束和 helper MUST 通过 profile/adapter 注入，而不是硬编码为默认全局行为。

#### Scenario: A 股特有约束被隔离
- **WHEN** provider 需要使用 A 股特有的 lot、停牌或 benchmark 规则
- **THEN** 这些规则 MUST 通过 asset/market profile 或对应 helper 提供
- **THEN** façade 文件 SHALL NOT 继续把这些规则写成无条件全局逻辑

### Requirement: 日级信号协议必须保留候选边界所需的最小元信息
`DaySignals` 中进入候选边界层的买入候选 MUST 保留进行上游边界裁决所需的最小元信息，包括 `owner_system`、`sleeve_id`、排序分数和正式原因摘要。信号协议 SHALL 允许上游候选边界层消费这些信息，但 SHALL NOT 要求执行内核直接理解它们的子系统语义。

#### Scenario: 个股多信号路径产出候选信号
- **WHEN** 个股多信号路径返回 `DaySignals.buy_signals`
- **THEN** 每条候选信号 MUST 带有候选边界层所需的最小元信息
- **THEN** 这些元信息 MUST 足以支持上游候选边界层完成名额和兼容裁决

#### Scenario: 执行内核消费最终候选
- **WHEN** 共享执行开始订单规划
- **THEN** 执行内核 MAY 读取统一后的正式原因摘要
- **THEN** 执行内核 SHALL NOT 直接依赖子系统私有兼容裁决配置
