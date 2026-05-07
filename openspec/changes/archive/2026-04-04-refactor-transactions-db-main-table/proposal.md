## Why

当前 `mobile_ops` 生命周期已经被统一服务收口，但正式真相仍然停留在文件域服务化阶段，`transactions` 还没有成为业务事务域中的数据库生命周期主表。继续保留这种状态，会让审批、执行、成交、失败原因和事务审计长期分裂在数据库设计与文件兼容壳之间。

## What Changes

- 将 `transactions` 正式收口为业务事务域中的完整生命周期主表，覆盖审批、提交、成交、拒绝、撤销等状态。
- 把 `approval_source`、`source_intent_id`、`failure_reason_codes` 固定为生命周期主表的正式字段，而不是 compat 派生字段。
- 把移动端审批、执行跟踪、每日摘要统一改为消费数据库事务真相，文件产物只保留迁移期 compat。
- 明确事务域数据库迁移顺序、回退方式和 compat 退出条件。

## Capabilities

### New Capabilities
- `transactions-lifecycle-main-table`: 定义业务事务域中完整交易生命周期主表及其正式字段与迁移约束。

### Modified Capabilities
- `mobile-order-approval`: 审批正式写入与读取路径改为事务生命周期主表。
- `mobile-execution-tracking`: 执行状态推进与展示正式消费事务生命周期主表。
- `mobile-daily-briefing`: 每日摘要正式消费事务生命周期摘要，而不是文件主真相。
- `research-db-structure-governance`: 业务事务域新增 `transactions` 生命周期主表的正式定位。

## Impact

- 影响模块：`backend/core/services/mobile_*`、`backend/api/transactions`、事务域数据库访问层、移动端摘要与执行状态面板。
- 影响数据：事务生命周期状态、审批来源痕迹、失败原因、compat 文件写出策略。
- 风险：迁移期数据库主表与文件 compat 双写不一致；旧移动端读取面仍依赖文件结构。
