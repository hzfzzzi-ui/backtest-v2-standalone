## MODIFIED Requirements

### Requirement: Runtime compatibility MUST 明确处理 unresolved、终止尾段与低可信记录
系统 MUST 为 runtime compatibility 层定义 unresolved、`delist_tail_confirmed`、synthetic fill、低可信 `pre_close`、低可信 `turnover_rate` 等记录的消费规则。若某类记录不满足 runtime gate，系统 MUST 将其排除或降级，而不是无差别提供给策略。

#### Scenario: unresolved 记录进入 runtime
- **WHEN** canonical 中存在 `source_unresolved` 记录
- **THEN** runtime compatibility MUST 按规则排除或显式降级该记录
- **THEN** 系统 MUST 能审计该排除或降级行为

#### Scenario: 终止尾段进入 runtime
- **WHEN** canonical 中存在 `delist_tail_confirmed` 记录
- **THEN** runtime compatibility MUST 将该记录排除在默认消费集合之外
- **THEN** 系统 MUST 单列该排除原因，而不是把它计入 `runtime_eligible`

#### Scenario: 低可信字段进入 runtime
- **WHEN** 某 canonical 行包含低可信关键字段
- **THEN** runtime compatibility MUST 按 compat 规则决定是否消费
- **THEN** 决策结果 MUST 可被门禁和报告追溯
