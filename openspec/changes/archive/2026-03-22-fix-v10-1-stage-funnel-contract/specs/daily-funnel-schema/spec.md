## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: 买入漏斗缺口必须可被下游识别
系统 SHALL 让下游 artifact 聚合层能够从 `daily_row` 明确区分“真实阶段计数为 0”和“该阶段当前未单独计数”。为此，买入漏斗相关字段在写入 `daily_row` 时 MUST 保留空值语义，不得在引擎层被统一数值化为 `0`。

#### Scenario: 真实零值阶段
- **WHEN** 某个买入漏斗阶段在当日真实发生且计数结果为 `0`
- **THEN** `daily_row` SHALL 写入数值 `0`
- **THEN** 下游系统 SHALL 将该阶段识别为真实零值，而不是 unavailable

#### Scenario: 未单独计数阶段
- **WHEN** 某个买入漏斗阶段在当前运行路径没有可靠 owner 或没有正式诊断来源
- **THEN** `daily_row` SHALL 保留该字段为空
- **THEN** 下游 artifact 聚合 SHALL 能够据此将该阶段标记为 unavailable
