## MODIFIED Requirements

### Requirement: `candidate_plan` MUST 只作为内部或迁移期结构存在
系统 MAY 继续在子系统内部或迁移期保留 `candidate_plan`，但 `candidate_plan` SHALL NOT 再被定义为跨共享执行边界主合同。

#### Scenario: 子系统内部继续使用 candidate plan
- **WHEN** 某个子系统内部仍通过 `candidate_plan` 组织动作规划
- **THEN** 该结构 MAY 在子系统内部存在
- **THEN** 一旦跨入共享执行边界，正式对外交付物 MUST 转换为 `action_intent_v1`
