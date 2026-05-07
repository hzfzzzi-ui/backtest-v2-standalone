# daily-funnel-schema Specification

## Purpose

TBD -- Define and enforce a unified daily_row schema across SMA and Generic engine paths, including core fields, sell/buy funnel counters, redundancy removal, and extensible diagnostics.
## Requirements
### Requirement: 统一 daily_row 引擎核心字段
引擎 SHALL 在每个交易日输出以下核心字段，两条路径（SMA / Generic）MUST 保持一致：

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | str (ISO) | 交易日期 |
| `nav` | float | 净值 |
| `cash` | float | 可用现金 |
| `positions_count` | int | 持仓数 |
| `daily_return` | float | 日收益率 |
| `drawdown` | float | 回撤比率 |
| `gross_exposure` | float | 敞口比率 |
| `turnover_pct` | float | 换手率 |
| `top5_positions_json` | str (JSON) | 前5大持仓 |

引擎 MUST NOT 输出与上述字段同值的冗余字段（如 `positions_count_end_of_day`、`available_cash`）。

#### Scenario: SMA 路径输出核心字段
- **WHEN** SMA 路径完成一个交易日的 NAV 计算
- **THEN** `daily_row` 包含上述 9 个核心字段且无冗余同名字段

#### Scenario: Generic 路径输出核心字段
- **WHEN** Generic 路径完成一个交易日的 NAV 计算
- **THEN** `daily_row` 包含与 SMA 路径完全相同的 9 个核心字段

---

### Requirement: 统一卖出漏斗字段
引擎 SHALL 在每个交易日输出卖出漏斗计数，反映从持仓到实际卖出的全路径：

| 字段 | 类型 | 说明 |
|------|------|------|
| `positions_before_sell` | int | 卖出决策前的持仓数 |
| `sells_executed_count` | int | 实际执行的卖出信号数 |
| `positions_after_sell` | int | 卖出后的持仓数 |

两条路径 MUST 输出相同的卖出漏斗字段，且值 MUST 反映实际的信号/执行计数。

#### Scenario: SMA 路径卖出漏斗完整
- **WHEN** SMA 路径处理完卖出信号
- **THEN** `positions_before_sell` 等于当日卖出决策前的实际持仓数量，`sells_executed_count` 等于通过所有过滤的卖出信号数量，`positions_after_sell = positions_before_sell - sells_executed_count`

#### Scenario: Generic 路径补齐卖出漏斗
- **WHEN** Generic 路径处理完策略返回的卖出信号
- **THEN** 输出与 SMA 路径相同的 3 个卖出漏斗字段，值反映实际执行情况（不再写 0 或省略）

---

### Requirement: 统一买入漏斗字段
引擎 SHALL 在每个交易日输出买入漏斗计数，反映从原始信号到最终成交的全路径过滤，并将这些字段作为 `stage_funnel` 聚合的唯一真相源。

| 字段 | 类型 | 说明 |
|------|------|------|
| `raw_buy_signal_count` | int | 策略产生的原始买入信号数 |
| `buy_candidate_count` | int \| null | 通过可交易性或候选集过滤后的信号数 |
| `after_held_filter_count` | int \| null | 排除已持有、冷却期或最小持有约束后的信号数 |
| `after_slot_filter_count` | int \| null | 排除无空位或 sleeve budget 后的信号数 |
| `after_cash_lot_count` | int \| null | 排除资金或整手不足后的信号数 |
| `buy_slots_before_buy` | int | 当日可用买入槽位 |

引擎 MUST 按正式 owner 写入这些字段：

- provider diagnostics 负责其真正知道的前序阶段计数
- 订单规划或 `debug_plan` 负责 slot/cash/lot 约束后的阶段计数
- `daily_accounting` 负责按正式来源收口到 `daily_row`

当某条运行路径无法为某个阶段提供可靠计数时，引擎 MUST 保留该字段为 `null` 或等价空值，供下游聚合显式标记 unavailable。引擎 MUST NOT 使用后置阶段数量、最终 `buy_signals` 长度、`selected_symbols` 长度或其他回退值伪装前序阶段计数。

#### Scenario: SMA 路径买入漏斗完整
- **WHEN** SMA 路径完成买入信号过滤和订单构建
- **THEN** `daily_row` SHALL 输出 `raw_buy_signal_count`、`buy_candidate_count`、`after_held_filter_count`、`after_slot_filter_count`、`after_cash_lot_count`、`buy_slots_before_buy`
- **THEN** 漏斗字段递减关系 SHALL 成立：`raw_buy_signal_count >= buy_candidate_count >= after_held_filter_count >= after_slot_filter_count >= after_cash_lot_count`

#### Scenario: stage pipeline 路径从正式来源收口计数
- **WHEN** V10.1 stage pipeline 路径同时拥有 provider diagnostics 与订单规划 `debug_plan`
- **THEN** `daily_accounting` SHALL 优先使用这些正式来源写入买入漏斗字段
- **THEN** `after_slot_filter_count` 与 `after_cash_lot_count` SHALL 反映真实约束后的阶段数量，而不是机械复用 `len(day_signals.buy_signals)`

#### Scenario: 阶段计数缺失时保留空值
- **WHEN** 某条运行路径无法为 `buy_candidate_count`、`after_held_filter_count`、`after_slot_filter_count` 或 `after_cash_lot_count` 提供可靠计数
- **THEN** 对应 `daily_row` 字段 SHALL 保持 `null` 或等价空值
- **THEN** 引擎 SHALL NOT 用更后置阶段的数量回填这些字段

### Requirement: 删除冗余字段
引擎 MUST 删除以下 SMA 路径中的冗余字段（与已有字段同值）：

| 待删除字段 | 对应已有字段 | 说明 |
|-----------|------------|------|
| `positions_count_end_of_day` | `positions_count` | 同一时刻取值，完全相同 |
| `candidates_after_held_filter_count` | `after_held_filter_count` | 同值不同名 |
| `buy_slots_after_sell` | `buy_slots_before_buy` | 同值不同名 |
| `buy_slots_calculated` | `buy_slots_before_buy` | 同值不同名 |

删除后，`_compute_metrics()` 中若引用这些字段名 MUST 同步更新为保留的字段名。

#### Scenario: 冗余字段不再出现在 daily_row
- **WHEN** 任一路径完成一个交易日的 daily_row 构建
- **THEN** daily_row dict 中不包含 `positions_count_end_of_day`、`candidates_after_held_filter_count`、`buy_slots_after_sell`、`buy_slots_calculated` 这 4 个 key

#### Scenario: _compute_metrics 正常运行
- **WHEN** `_compute_metrics()` 处理删除冗余字段后的 daily_df
- **THEN** 不抛出 KeyError，所有指标计算结果与删除前一致

---

### Requirement: 策略诊断字段保持可扩展
策略诊断字段（如 `mean_order_value_scale`、`mf_*` 系列、`trend_*` 系列）SHALL 继续由各路径按需输出。这些字段不强制两路径一致——不同策略可以输出不同的诊断字段。

Generic 路径已有的诊断字段（`candidates_count`、`selected_count`、`mean_order_value_scale`、`mf_*`系列等）MUST 继续输出。

#### Scenario: SMA 路径输出 SMA 特有诊断
- **WHEN** SMA 路径运行
- **THEN** 输出 `base_trend_on_rate`、`quality_trend_on_rate`、`trend_slope_block_count`、`trend_continuity_block_count` 等 SMA 特有诊断字段

#### Scenario: Generic 路径输出通用诊断
- **WHEN** Generic 路径运行
- **THEN** 输出 `candidates_count`、`selected_count`、`mf_*` 系列等已有诊断字段，不强制输出 SMA 特有字段

### Requirement: 买入漏斗缺口必须可被下游识别
系统 SHALL 让下游 artifact 聚合层能够从 `daily_row` 明确区分“真实阶段计数为 0”和“该阶段当前未单独计数”。为此，买入漏斗相关字段在写入 `daily_row` 时 MUST 保留空值语义，不得在引擎层被统一数值化为 `0`。

系统 SHALL 让下游 artifact 聚合层能够从 `daily_row` 明确区分“真实阶段计数为 0”和“该阶段当前未单独计数”。为此，买入漏斗相关字段在写入 `daily_row` 时 MUST 保留空值语义，不得在引擎层被统一数值化为 `0`。

#### Scenario: 真实零值阶段
- **WHEN** 某个买入漏斗阶段在当日真实发生且计数结果为 `0`
- **THEN** `daily_row` SHALL 写入数值 `0`
- **THEN** 下游系统 SHALL 将该阶段识别为真实零值，而不是 unavailable

#### Scenario: 未单独计数阶段
- **WHEN** 某个买入漏斗阶段在当前运行路径没有可靠 owner 或没有正式诊断来源
- **THEN** `daily_row` SHALL 保留该字段为空
- **THEN** 下游 artifact 聚合 SHALL 能够据此将该阶段标记为 unavailable

#### Scenario: SMA 路径买入漏斗完整
- **WHEN** SMA 路径完成买入信号过滤和订单构建
- **THEN** `daily_row` SHALL 输出 `raw_buy_signal_count`、`buy_candidate_count`、`after_held_filter_count`、`after_slot_filter_count`、`after_cash_lot_count`、`buy_slots_before_buy`
- **THEN** 漏斗字段递减关系 SHALL 成立：`raw_buy_signal_count >= buy_candidate_count >= after_held_filter_count >= after_slot_filter_count >= after_cash_lot_count`

#### Scenario: stage pipeline 路径从正式来源收口计数
- **WHEN** V10.1 stage pipeline 路径同时拥有 provider diagnostics 与订单规划 `debug_plan`
- **THEN** `daily_accounting` SHALL 优先使用这些正式来源写入买入漏斗字段
- **THEN** `after_slot_filter_count` 与 `after_cash_lot_count` SHALL 反映真实约束后的阶段数量，而不是机械复用 `len(day_signals.buy_signals)`

#### Scenario: 阶段计数缺失时保留空值
- **WHEN** 某条运行路径无法为 `buy_candidate_count`、`after_held_filter_count`、`after_slot_filter_count` 或 `after_cash_lot_count` 提供可靠计数
- **THEN** 对应 `daily_row` 字段 SHALL 保持 `null` 或等价空值
- **THEN** 引擎 SHALL NOT 用更后置阶段的数量回填这些字段
