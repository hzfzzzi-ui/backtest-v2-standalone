## ADDED Requirements

### Requirement: ETF beta sleeve 必须优先消费账户层 transition handoff
当 `runtime_truth_source = account_allocator` 且账户层提供 `transition_action_handoff` 时，ETF beta sleeve SHALL 以该 handoff 为主执行输入。旧的 weak-state redeploy、cash-drip、materialization 路径 SHALL 降级为 diagnostics/reference，不得继续承接主执行语义。

#### Scenario: ETF 执行链优先读取账户层 handoff
- **WHEN** ETF beta sleeve 收到账户层 `transition_action_handoff`
- **THEN** ETF 执行链 MUST 优先消费该 handoff
- **THEN** 旧 weak-state 局部路径 SHALL 只保留 diagnostics/reference 角色

### Requirement: ETF beta sleeve 必须显式记录账户层 handoff 的消费结果
ETF beta sleeve 在消费账户层 `transition_action_handoff` 时，MUST 在运行产物中记录已消费、被拒绝、未触发以及 fallback 到 diagnostics/reference 的状态。

#### Scenario: ETF 运行产物保留 handoff 消费结果
- **WHEN** ETF beta sleeve 处理账户层 transition handoff
- **THEN** 运行产物 MUST 记录 handoff 消费结果
- **THEN** 运行产物 MUST 记录拒绝原因或 diagnostics 降级说明
