## ADDED Requirements

### Requirement: 账户层 budget control 必须定义 transition execution handoff 优先级
账户层 budget control MUST 明确定义 transition execution 的 handoff 优先级，执行层不得在同一阶段继续使用旧 weak-state 路径作为主预算消费入口。

#### Scenario: budget handoff 成为唯一主预算消费入口
- **WHEN** 账户层 handoff 处于 active 状态
- **THEN** 执行链 MUST 以账户层 handoff 为唯一主 budget 消费入口
- **AND** 旧 `cash_drip`、`materialization` 等弱势路径只能进入 reference 区

#### Scenario: 主 reject 原因必须来自账户层 handoff
- **WHEN** handoff 进入执行但被拒绝
- **THEN** 主 reject 原因 MUST 来自账户层 transition execution 字段
- **AND** 不得继续把旧 weak-state reject 作为主结论

