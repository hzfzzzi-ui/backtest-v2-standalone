## ADDED Requirements

### Requirement: 共享执行边界不得继续并列暴露旧过渡合同
系统 SHALL 将共享执行边界的正式对外合同限制为 `subsystem_budget_v1 / action_intent_v1 / risk_override_v1 / target_book_v1 / execution_audit_v1`，旧 `ExecutionIntent / CandidatePlan / TargetBook` 不得继续作为并列正式边界对象暴露。

#### Scenario: 正式共享边界只认正式合同
- **WHEN** 文档、导出层或主路径声明共享执行边界的正式合同集合
- **THEN** 其中 MUST 不包含旧过渡合同
