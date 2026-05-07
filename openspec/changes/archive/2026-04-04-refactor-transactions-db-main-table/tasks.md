## 1. 生命周期主表定义

- [x] 1.1 定义 `transactions` 生命周期主表的正式字段、状态集合与审计回显。（DoD: proposal/design/specs 对齐同一字段边界；验证: `openspec validate refactor-transactions-db-main-table` 通过；风险: 状态集合与现有移动端执行状态不兼容）
- [x] 1.2 固定 `approval_source / source_intent_id / failure_reason_codes` 为正式字段。（DoD: specs 明确必返语义与场景；验证: delta spec 覆盖审批、失败、回退三类场景；风险: 旧 compat 字段命名残留）

## 2. 移动端消费面切换

- [x] 2.1 将 `mobile-order-approval` 正式写入/读取切到事务生命周期主表。（DoD: spec 要求审批不再依赖文件主真相；验证: 审批场景 spec 完整；风险: 旧工具仍读 `approval_tickets`）
- [x] 2.2 将 `mobile-execution-tracking` 与 `mobile-daily-briefing` 正式消费切到事务生命周期摘要。（DoD: spec 明确摘要来自事务真相；验证: 跟踪/briefing 场景覆盖；风险: briefing 仍被误当主真相）

## 3. 迁移与回退

- [x] 3.1 明确 compat 文件双写、退出条件与回退顺序。（DoD: design/tasks 写清双写期与退出门槛；验证: 回退步骤可读；风险: 兼容壳退出过早）
- [x] 3.2 补充数据库域定位说明，保证事务主表进入正式业务事务域。（DoD: `research-db-structure-governance` delta spec 完整；验证: OpenSpec validate 通过；风险: 文档与事务域实际设计漂移）

