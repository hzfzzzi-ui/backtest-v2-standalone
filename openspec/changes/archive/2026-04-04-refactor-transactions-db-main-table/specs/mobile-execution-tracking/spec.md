## ADDED Requirements

### Requirement: 执行跟踪正式消费事务生命周期主表
系统 SHALL 让移动执行跟踪正式消费 `transactions` 生命周期主表中的状态推进结果，而不是把 `execution_events` 文件作为长期正式读取源。

#### Scenario: 执行状态查询读取事务主表
- **WHEN** 移动端请求某笔交易的执行跟踪状态
- **THEN** 系统 MUST 从事务生命周期主表或其正式摘要中返回状态
