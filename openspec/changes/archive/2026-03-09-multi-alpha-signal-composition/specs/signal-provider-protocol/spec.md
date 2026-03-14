## MODIFIED Requirements

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

---

### Requirement: DaySignals 数据类
引擎 SHALL 定义 `DaySignals` 数据类作为 `day_signals()` 的返回类型，包含：
- `sell_signals: list[Signal]` — 当日最终卖出信号（供仓位控制和订单规划使用）
- `buy_signals: list[Signal]` — 当日最终买入信号（供仓位控制和订单规划使用）
- `raw_alpha_signals: list[Signal]` — `S6a` 生成的原始 alpha 信号
- `composed_sell_signals: list[Signal]` — `S6b` 生成的组合后卖出信号
- `composed_buy_signals: list[Signal]` — `S6b` 生成的组合后买入信号
- `exit_syms: set[str]` — 已触发退出的标的集合
- `strength_map: dict[str, float]` — 标的强度得分（用于排序）
- `mf_score_map: dict[str, float]` — 多因子得分（用于排序）
- `diagnostics: dict[str, Any]` — 当日诊断数据（漏斗计数、组合决策、阻断原因等）
- `exit_counts: ExitCounts` — 引擎退出规则触发计数

在单策略路径下，`raw_alpha_signals`、`composed_sell_signals`、`composed_buy_signals` MAY 为空列表，但 `buy_signals` 与 `sell_signals` 的现有语义 MUST 保持不变。

#### Scenario: 诊断数据透传
- **WHEN** 信号提供者生成组合层诊断数据
- **THEN** 诊断数据 SHALL 通过 `diagnostics` 字段传递到 daily_row 或审计产物
- **THEN** 诊断键名 SHALL 保持稳定并可供 UI 校验

#### Scenario: 单策略兼容
- **WHEN** 当前运行路径未启用多 alpha 组合
- **THEN** `buy_signals` 与 `sell_signals` SHALL 继续表示最终订单输入信号
- **THEN** 新增的组合信号字段 SHALL 不改变单策略结果

---

### Requirement: DayContext 数据类
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

---

### Requirement: 统一引擎循环
引擎 SHALL 提供 `_run_unified_loop()` 函数，接收 `SignalProvider` 实例和引擎配置，执行单一日循环：
1. 处理待成交订单（`_process_pending_fills`）
2. 计算 NAV/回撤/峰值
3. 检查 drawdown breaker
4. 调用 `provider.day_signals()` 获取原始信号、组合后信号和最终卖出/买入信号
5. 调用 `build_rebalance_orders()` 基于最终买卖信号生成订单
6. 记录 daily_row、审计字段和组合诊断数据
7. 入队次日订单

#### Scenario: SMA 路径使用统一循环
- **WHEN** `run_vector_portfolio_backtest_strict()` 检测到 SMA 策略
- **THEN** 创建 `SMASignalProvider`，调用 `_run_unified_loop()`，结果与旧 SMA 路径数值一致

#### Scenario: 多 alpha 路径使用统一循环
- **WHEN** `run_vector_portfolio_backtest_strict()` 路由到启用组合配置的策略路径
- **THEN** 统一循环 SHALL 记录组合层诊断并将最终信号交给订单规划
- **THEN** 组合层 SHALL 不改变 `t` 日信号、`t+1` 执行的交易时钟
