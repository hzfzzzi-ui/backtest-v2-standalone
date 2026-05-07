## ADDED Requirements

### Requirement: sim_account 正式对象属于业务事务域
系统 SHALL 在数据库结构治理中明确 `accounts`、`holdings_snapshots`、`cash_ledger`、`sync_logs` 属于业务事务域正式对象。

#### Scenario: sim_account 对象域归属明确
- **WHEN** 文档或实现声明 `sim_account` 相关对象的正式归属
- **THEN** 这些对象 MUST 被归类到业务事务域
