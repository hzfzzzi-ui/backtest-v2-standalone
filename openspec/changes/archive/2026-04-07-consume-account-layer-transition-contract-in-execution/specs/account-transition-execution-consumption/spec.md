## ADDED Requirements

### Requirement: 执行层必须消费账户层 transition action handoff
系统 SHALL 将账户层 `transition_action_handoff` 视为执行层的正式输入。执行层 MUST 根据 handoff 中的 `carry / de-risk / cash release / budget handoff` 动作决定执行行为，而不是继续以局部 weak-state patch 作为主输入。

#### Scenario: `risk_on -> defensive` 使用账户层 handoff 进入执行链
- **WHEN** 账户层状态切换属于 `risk_on -> defensive`
- **THEN** 执行层 MUST 读取账户层 `transition_action_handoff`
- **THEN** 执行层 MUST 以 handoff 动作为优先执行输入

### Requirement: 统一 handoff 必须覆盖全部状态切换族
系统 MUST 为全部状态切换族输出统一的 `transition_action_handoff`，即使当前实现仅消费其中一部分，也 SHALL 明确给出 `no_op`、`carry_forward` 或等价的保守动作。

#### Scenario: 未优先实现的 transition family 仍有显式 handoff
- **WHEN** 当前状态切换不属于第一优先实现的 transition family
- **THEN** 账户层仍 MUST 输出对应的 `transition_action_handoff`
- **THEN** 执行层 SHALL 记录该 handoff 当前是否已消费或是否为 `no_op`

### Requirement: 执行诊断必须区分账户层消费与旧局部路径
当账户层 `transition_action_handoff` 存在时，系统 MUST 在运行产物中区分“账户层 handoff 已消费”“账户层 handoff 被拒绝”“旧 weak-state 路径仅作 diagnostics”三类状态。

#### Scenario: 运行产物保留消费状态与拒绝原因
- **WHEN** 执行层处理账户层 `transition_action_handoff`
- **THEN** 运行产物 MUST 记录 handoff 是否已消费
- **THEN** 运行产物 MUST 记录拒绝原因或 diagnostics/reference 降级状态
