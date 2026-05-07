## ADDED Requirements

### Requirement: reconcile 正式输出为摘要索引
系统 SHALL 将 `position-aware-reconcile-run` 的正式数据库输出限制为 `reconcile_summary` 及必要引用，不得将完整派生 payload 升格为事务域底层真相。

#### Scenario: reconcile 正式输出不包含完整 payload 主真相
- **WHEN** 系统记录一次 reconcile 结果
- **THEN** 正式事务域对象 MUST 只保留摘要与引用
