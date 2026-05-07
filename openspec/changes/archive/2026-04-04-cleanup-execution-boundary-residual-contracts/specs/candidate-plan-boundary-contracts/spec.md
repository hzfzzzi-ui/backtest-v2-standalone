## ADDED Requirements

### Requirement: candidate_plan 只允许作为内部或迁移结构存在
系统 SHALL 将 `candidate_plan` 定位为子系统内部结构或迁移期 compat 结构，不得继续把它作为共享执行边界主合同。

#### Scenario: candidate_plan 不再定义共享边界
- **WHEN** 系统描述共享执行边界输入
- **THEN** `candidate_plan` MUST 不再被列为正式共享合同
