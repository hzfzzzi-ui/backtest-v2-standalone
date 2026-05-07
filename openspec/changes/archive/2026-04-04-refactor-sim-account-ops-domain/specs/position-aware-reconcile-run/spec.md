## MODIFIED Requirements

### Requirement: Position-aware reconcile MUST 只产出派生摘要与引用
系统 MUST 将 position-aware reconcile 的正式数据库落点收口为派生摘要与引用，而不是长期把完整建议面当作账户运营真相。

#### Scenario: reconcile 结果供上层查看
- **WHEN** 上层需要查看最近一次 reconcile 结果
- **THEN** 系统 MUST 能返回摘要、引用和状态
- **THEN** 上层 SHALL NOT 将完整 `action_sheet` 误当作底层账户状态真相
