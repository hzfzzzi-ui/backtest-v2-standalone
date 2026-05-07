## ADDED Requirements

### Requirement: 账户层 runtime 必须输出 transition execution ownership 状态
账户层主 runtime MUST 对外输出 transition execution 的 owner、状态、原因码和参考诊断路径，作为统一的主解释。

#### Scenario: 主 runtime 输出 execution owner
- **WHEN** 生成 unified combo 主产物
- **THEN** `run_meta.account_allocator_runtime` MUST 包含 `transition_execution_owner`
- **AND** MUST 包含 `transition_execution_status`
- **AND** MUST 包含 `transition_execution_reason_code` 或 `transition_execution_reject_reason`

#### Scenario: reference combo 降为参考区
- **WHEN** `runtime_truth_source = account_allocator`
- **THEN** `combo/reference` 相关产物 MUST 标记为 `reference_only`
- **AND** 不得再与账户层 execution owner 平级并列为主叙事

