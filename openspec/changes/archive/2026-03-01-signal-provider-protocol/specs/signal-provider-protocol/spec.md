## ADDED Requirements

### Requirement: SignalProvider 协议
引擎 SHALL 定义 `SignalProvider` 协议（Protocol），包含以下方法：
- `precompute(*, history, benchmark, raw_history, trading_days, strategy, ...) -> None`：在日循环前执行一次性预计算
- `day_signals(day, day_idx, ctx: DayContext) -> DaySignals`：生成当日卖出/买入信号

实现类 MUST 不直接修改 `DayContext` 中的引擎状态（positions, cash），信号通过返回值传递。
实现类 MAY 维护自身的内部可变状态（如 break_streak, signal matrices）。

#### Scenario: SMA 信号提供者
- **WHEN** 使用 SMA 策略（ma_type=SMA/EMA）
- **THEN** `precompute()` 构建 OHLC/feature/signal 矩阵和候选索引；`day_signals()` 通过矩阵索引生成信号

#### Scenario: Generic 信号提供者
- **WHEN** 使用通用策略（非 SMA 路径）
- **THEN** `precompute()` 构建 regime 查询和 ATR lookup；`day_signals()` 调用 `strategy.generate_signals()` 生成信号

---

### Requirement: DaySignals 数据类
引擎 SHALL 定义 `DaySignals` 数据类作为 `day_signals()` 的返回类型，包含：
- `sell_signals: list[Signal]` — 当日卖出信号（引擎退出 + 策略退出合并后）
- `buy_signals: list[Signal]` — 当日买入信号
- `exit_syms: set[str]` — 已触发退出的标的集合
- `strength_map: dict[str, float]` — 标的强度得分（用于排序）
- `mf_score_map: dict[str, float]` — 多因子得分（用于排序）
- `diagnostics: dict[str, Any]` — 当日诊断数据（漏斗计数、阻断原因等）
- `exit_counts: ExitCounts` — 引擎退出规则触发计数

#### Scenario: 诊断数据透传
- **WHEN** 信号提供者生成诊断数据
- **THEN** 诊断数据通过 `diagnostics` 字段传递到 daily_row，键名保持与现有 daily_row schema 一致

---

### Requirement: DayContext 数据类
引擎 SHALL 定义 `DayContext` 数据类作为引擎状态的只读快照传递给信号提供者：
- 持仓和成本信息：positions, position_avg_cost
- 财务状态：cash, nav, base_order_value, max_positions
- 价格索引：close_idx, open_idx
- 时间信息：next_day（用于查询次日开盘价）
- 风险状态：risk_on（当日大盘 regime 状态）

#### Scenario: 信号提供者读取上下文
- **WHEN** 信号提供者需要引擎状态进行信号生成
- **THEN** 通过 DayContext 获取，不直接引用引擎内部变量

---

### Requirement: 统一引擎循环
引擎 SHALL 提供 `_run_unified_loop()` 函数，接收 SignalProvider 实例和引擎配置，执行单一日循环：
1. 处理待成交订单（`_process_pending_fills`）
2. 计算 NAV/回撤/峰值
3. 检查 drawdown breaker
4. 调用 `provider.day_signals()` 获取卖出/买入信号
5. 调用 `build_rebalance_orders()` 生成订单
6. 记录 daily_row（38 列 + 诊断数据）
7. 入队次日订单

#### Scenario: SMA 路径使用统一循环
- **WHEN** `run_vector_portfolio_backtest_strict()` 检测到 SMA 策略
- **THEN** 创建 SMASignalProvider，调用 `_run_unified_loop()`，结果与旧 SMA 路径数值一致

#### Scenario: Generic 路径使用统一循环
- **WHEN** `run_vector_portfolio_backtest_strict()` 路由到 Generic 策略
- **THEN** 创建 GenericSignalProvider，调用 `_run_unified_loop()`，结果与旧 Generic 路径数值一致
