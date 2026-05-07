## MODIFIED Requirements

### Requirement: 运行时跨共享执行边界 MUST 只使用正式执行合同
系统 MUST 将跨共享执行边界的正式合同收口为 `action_intent_v1`、`risk_override_v1`、`target_book_v1` 与 `execution_audit`。共享执行边界 SHALL NOT 继续把 `candidate_plan` 或过渡 `target_book` 当成主输入语义。

#### Scenario: 子系统提交普通动作
- **WHEN** 某个子系统向共享执行层提交普通买卖动作
- **THEN** 提交物 MUST 是 `action_intent_v1`
- **THEN** 共享执行层 SHALL NOT 要求上游继续提供过渡 `candidate_plan` 作为正式主输入

### Requirement: `execution_audit` MUST 回显所有阻断与裁剪
系统 MUST 将阻断、覆盖、截断、整手取整和优先级跳过正式记录到 `execution_audit`。

#### Scenario: 高优先级动作因整手取整变成 0 手
- **WHEN** 某个普通动作在执行层因整手取整变成 0 手
- **THEN** 该动作 MUST 被拒绝并进入 `execution_audit`
- **THEN** 系统 SHALL NOT 静默丢弃该动作
