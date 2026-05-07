## ADDED Requirements

### Requirement: 账户层 runtime cutover 必须覆盖执行输入层
当 `runtime_truth_source = account_allocator` 时，系统 SHALL 要求执行层优先消费账户层 `state_transition_runtime` 与 `transition_action_handoff`，而不是只在 explain、audit 或前端展示账户层状态切换。

#### Scenario: runtime 主真相进入执行层
- **WHEN** 账户层 runtime 已成为主真相
- **THEN** 执行层 MUST 接收账户层 transition runtime 作为正式输入
- **THEN** 账户层状态切换 SHALL 不再停留在 explain-only 语义

### Requirement: reference combo 不得重新获得执行解释权
当 `runtime_truth_source = account_allocator` 时，旧 `combo/reference` MAY 作为 benchmark 或 diagnostics 保留，但 SHALL NOT 重新成为执行决策的主解释来源。

#### Scenario: 读取 reference combo 时保持执行边界
- **WHEN** query、audit 或 frontend 读取 reference combo
- **THEN** 系统 MAY 展示其 reference 信息
- **THEN** 执行链与主叙事仍 MUST 以账户层 transition consumption 为准
