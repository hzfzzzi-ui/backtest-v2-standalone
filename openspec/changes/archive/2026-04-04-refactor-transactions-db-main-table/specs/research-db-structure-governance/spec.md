## ADDED Requirements

### Requirement: transactions 生命周期主表属于业务事务域正式对象
系统 SHALL 在数据库结构治理中明确 `transactions` 生命周期主表属于业务事务域正式对象，并与研究数据域、实验域分离。

#### Scenario: 事务主表域归属清晰
- **WHEN** 文档或实现声明数据库对象的正式归属
- **THEN** `transactions` 生命周期主表 MUST 被归类到业务事务域
