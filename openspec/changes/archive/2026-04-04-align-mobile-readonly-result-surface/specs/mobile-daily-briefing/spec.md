## ADDED Requirements

### Requirement: daily briefing 正式对齐结果摘要语义
系统 SHALL 将 `mobile-daily-briefing` 的正式语义对齐到桌面结果摘要与事务摘要，而不是继续承担审批工具的主语义。

#### Scenario: briefing 正式来源于结果与事务摘要
- **WHEN** 系统生成移动端 briefing
- **THEN** briefing 内容 MUST 来源于正式结果摘要或事务摘要
