## ADDED Requirements

### Requirement: 审批正式写入事务生命周期主表
系统 SHALL 将移动端审批的正式写入路径切换到 `transactions` 生命周期主表，并将 compat `approval_tickets` 文件降级为迁移期兼容产物。

#### Scenario: 审批创建后生成正式事务记录
- **WHEN** 用户在移动端确认一笔交易审批
- **THEN** 系统 MUST 先生成或更新对应的事务生命周期主表记录
