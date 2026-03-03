# Capability: daily-funnel-schema

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
引擎 SHALL 在每个交易日输出买入漏斗计数，反映从原始信号到最终成交的全路径过滤：

| 字段 | 类型 | 说明 |
|------|------|------|
| `raw_buy_signal_count` | int | 原始买入信号数（策略产生） |
| `after_held_filter_count` | int | 排除已持有后的信号数 |
| `after_slot_filter_count` | int | 排除无空位后的信号数 |
| `after_cash_lot_count` | int | 排除资金/手数不足后的信号数（最终成交数） |
| `buy_slots_before_buy` | int | 当日可用买入槽位 |

两条路径 MUST 输出相同的买入漏斗字段。

#### Scenario: SMA 路径买入漏斗完整
- **WHEN** SMA 路径完成买入信号过滤和订单构建
- **THEN** 漏斗字段递减关系成立：`raw_buy_signal_count >= after_held_filter_count >= after_slot_filter_count >= after_cash_lot_count`

#### Scenario: Generic 路径补齐买入漏斗
- **WHEN** Generic 路径完成策略信号过滤和订单构建
- **THEN** 输出与 SMA 路径相同的 5 个买入漏斗字段，值从策略信号和 `build_rebalance_orders` 的 `debug_plan` 中提取

---

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
