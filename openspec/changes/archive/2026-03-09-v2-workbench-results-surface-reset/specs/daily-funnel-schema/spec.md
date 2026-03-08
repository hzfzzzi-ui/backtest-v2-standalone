## MODIFIED Requirements

### Requirement: 统一买入漏斗字段
引擎 SHALL 在每个交易日输出买入漏斗计数，反映从原始信号到最终成交的全路径过滤：

| 字段 | 类型 | 说明 |
|------|------|------|
| `raw_buy_signal_count` | int | 原始买入信号数（策略产生） |
| `after_held_filter_count` | int | 排除已持有后的信号数 |
| `after_slot_filter_count` | int | 排除无空位后的信号数 |
| `after_cash_lot_count` | int | 排除资金/手数不足后的信号数（最终成交数） |
| `buy_slots_before_buy` | int | 当日可用买入槽位 |

此外，系统 MUST 为结果页提供按 stage 可解释的买入漏斗统计产物，至少覆盖：
- 股票池输入量
- 市场/行业/个股趋势过滤后的剩余量
- 排序与入场确认后的剩余量
- 组合构建进入候选量
- 最终下单量

两条路径 MUST 输出相同的买入漏斗字段。

#### Scenario: SMA 路径买入漏斗完整
- **WHEN** SMA 路径完成买入信号过滤和订单构建
- **THEN** 漏斗字段递减关系成立，`raw_buy_signal_count >= after_held_filter_count >= after_slot_filter_count >= after_cash_lot_count`

#### Scenario: Generic 路径补齐买入漏斗
- **WHEN** Generic 路径完成策略信号过滤和订单构建
- **THEN** 输出与 SMA 路径相同的 5 个买入漏斗字段，值从策略信号和 `build_rebalance_orders` 的 `debug_plan` 中提取

#### Scenario: 结果页存在 stage 级买入漏斗产物
- **WHEN** 某次实验完成并产出结果
- **THEN** 系统 SHALL 提供可供前端直接读取的 stage 级买入漏斗统计
- **THEN** 前端 MUST NOT 通过现有总量字段自行推断 9 个 stage 的中间计数

### Requirement: 统一卖出漏斗字段
引擎 SHALL 在每个交易日输出卖出漏斗计数，反映从持仓到实际卖出的全路径：

| 字段 | 类型 | 说明 |
|------|------|------|
| `positions_before_sell` | int | 卖出决策前的持仓数 |
| `sells_executed_count` | int | 实际执行的卖出信号数 |
| `positions_after_sell` | int | 卖出后的持仓数 |

两条路径 MUST 输出相同的卖出漏斗字段，且值 MUST 反映实际的信号/执行计数。系统 ALSO MUST 产出按频次聚合的卖出 reason 统计，以支持结果页从高频到低频展示卖出原因。

#### Scenario: SMA 路径卖出漏斗完整
- **WHEN** SMA 路径处理完卖出信号
- **THEN** `positions_before_sell` 等于当日卖出决策前的实际持仓数量，`sells_executed_count` 等于通过所有过滤的卖出信号数量，`positions_after_sell = positions_before_sell - sells_executed_count`

#### Scenario: Generic 路径补齐卖出漏斗
- **WHEN** Generic 路径处理完策略返回的卖出信号
- **THEN** 输出与 SMA 路径相同的 3 个卖出漏斗字段，值反映实际执行情况（不再写 0 或省略）

#### Scenario: 卖出原因按频次排序可读
- **WHEN** 前端读取卖出原因统计产物
- **THEN** 产物 SHALL 至少包含 `reason_code` 与 `count`
- **THEN** 前端 SHALL 可以按 `count` 从高到低展示卖出原因
