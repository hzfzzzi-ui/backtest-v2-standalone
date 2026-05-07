## ADDED Requirements

### Requirement: 事务域 MUST 以 `transactions` 作为完整交易生命周期主表
系统 MUST 在业务事务域中提供 `transactions` 作为完整交易生命周期主表。审批、提交、成交、拒绝、撤销等状态 MUST 归入该主表的正式状态机，而不是长期拆散到文件产物路径。

#### Scenario: 审批进入事务生命周期
- **WHEN** 用户在移动端或桌面端确认一笔交易动作
- **THEN** 系统 MUST 创建或更新一条 `transactions` 生命周期记录
- **THEN** 该记录 MUST 包含 `account_id`、`symbol`、`side`、`requested_qty`、`approval_source`

### Requirement: 事务生命周期主表 MUST 保留来源痕迹与失败原因
`transactions` 生命周期主表 MUST 正式保留来源痕迹与失败原因，至少包括 `source_intent_id`、`approval_source`、`failure_reason_codes`。

#### Scenario: 执行失败回显原因
- **WHEN** 一笔已审批动作在提交或成交阶段失败
- **THEN** `transactions` 记录 MUST 回显失败状态与 `failure_reason_codes`
- **THEN** 追踪方 SHALL NOT 需要回读独立文件事件流才能理解失败原因
