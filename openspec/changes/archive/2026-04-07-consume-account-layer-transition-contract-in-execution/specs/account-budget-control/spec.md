## ADDED Requirements

### Requirement: 账户预算控制必须输出 transition action handoff
系统 SHALL 在 steady-state budget 之外，输出可被执行层消费的 `transition_action_handoff`，至少包括 `carry rules`、`de-risk rules`、`cash release rules` 与 `budget handoff rules`。

#### Scenario: 预算控制输出状态切换动作
- **WHEN** 账户层完成 budget control 计算
- **THEN** 系统 MUST 同时生成 steady-state budget 与 `transition_action_handoff`
- **THEN** 执行层 SHALL 能消费该 handoff 作为正式输入

### Requirement: 预算控制必须显式标注 handoff 的消费状态
系统 MUST 在 runtime 产物中标注 `transition_action_handoff` 的消费状态，包括已消费、未消费、被拒绝或 reference-only diagnostics。

#### Scenario: 账户预算 handoff 在产物中可审计
- **WHEN** 运行产物写出账户预算控制结果
- **THEN** 系统 MUST 给出 handoff 的消费状态
- **THEN** 系统 MUST 给出对应的原因码或 reference 说明
