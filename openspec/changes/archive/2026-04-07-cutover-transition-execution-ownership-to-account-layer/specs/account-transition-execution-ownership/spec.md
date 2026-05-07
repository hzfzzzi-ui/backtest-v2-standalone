## ADDED Requirements

### Requirement: 账户层 transition execution owner 必须是唯一主执行 owner
当 `runtime_truth_source = account_allocator` 且存在 `transition_action_handoff` 时，系统 MUST 将账户层 transition execution controller 视为唯一主执行 owner。旧 weak-state 执行路径不得再产出主执行结论，只能进入 diagnostics/reference。

#### Scenario: risk_on_to_defensive handoff 接管主执行
- **WHEN** 账户层 runtime 输出 `transition_action_handoff.transition_kind = risk_on_to_defensive`
- **THEN** 执行链 MUST 优先消费账户层 handoff
- **AND** 主执行状态 MUST 标记为账户层 owner
- **AND** 旧 weak-state 路径不得再作为主 owner 给出 reject 或 success 结论

#### Scenario: 未实现 transition family 仍由账户层显式声明
- **WHEN** 当前 transition family 尚未实现真实执行
- **THEN** 账户层 runtime MUST 显式输出 `reference_only` 或 `not_implemented`
- **AND** 不得静默回退到旧 ETF weak-state 语义

### Requirement: 旧 weak-state 路径必须降级为 diagnostics/reference
系统 MUST 保留旧 weak-state 路径的诊断能力，但它们只能作为 reference 证据，不得继续争夺主执行 owner。

#### Scenario: 旧路径仍可见但不再主导
- **WHEN** 旧 `state_edge_cash_release` 或 `riskoff_cash_drip_topup` 产生 reject
- **THEN** reject 信息 MUST 仅出现在 diagnostics/reference 区
- **AND** 主执行状态 MUST 仍归属于账户层 transition execution owner

