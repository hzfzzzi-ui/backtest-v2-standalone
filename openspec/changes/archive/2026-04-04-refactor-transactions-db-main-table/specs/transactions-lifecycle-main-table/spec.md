## ADDED Requirements

### Requirement: transactions 成为完整生命周期主表
系统 SHALL 将 `transactions` 定义为业务事务域中的完整交易生命周期主表，正式覆盖审批、提交、成交、拒绝、撤销等状态，而不再把文件型 `approval_tickets` 或 `execution_events` 视为长期正式真相。

#### Scenario: 生命周期状态以主表为准
- **WHEN** 系统需要查询某笔移动审批对应的当前交易状态
- **THEN** 正式读取路径 MUST 来自 `transactions` 生命周期主表

### Requirement: 生命周期主表固定最小正式字段
系统 SHALL 在 `transactions` 生命周期主表中固定最小正式字段，包括生命周期状态、账户/标的关联、成交字段、`approval_source`、`source_intent_id` 与 `failure_reason_codes`。

#### Scenario: 失败交易仍可回显正式原因
- **WHEN** 某笔交易进入拒绝或失败状态
- **THEN** 系统 MUST 能从正式字段中回显失败原因与审批来源痕迹

### Requirement: compat 文件只作为迁移壳
系统 SHALL 允许迁移期继续写出 compat 文件，但 compat 文件 MUST 仅作为过渡壳，不得重新成为事务域正式主真相。

#### Scenario: 兼容写出不改变正式读取路径
- **WHEN** 系统在迁移期同时写出数据库记录与 compat 文件
- **THEN** 正式读取路径 MUST 仍以生命周期主表为准
