## ADDED Requirements

### Requirement: 每日摘要正式来源于事务生命周期摘要
系统 SHALL 将移动端每日摘要定义为事务生命周期真相的摘要投影，而不是将 briefing 文件本身定义为底层正式真相。

#### Scenario: 每日摘要回显事务状态汇总
- **WHEN** 系统生成某个交易日的移动端摘要
- **THEN** 摘要内容 MUST 来源于正式事务生命周期摘要
