## MODIFIED Requirements

### Requirement: 移动摘要 MUST 基于事务域摘要视图生成
系统 MUST 将移动端每日摘要定义为事务域摘要视图的消费结果，而不是将 `daily_briefing` 文件产物本身定义为底层运营真相。

#### Scenario: 生成当日移动摘要
- **WHEN** 系统生成移动端只读摘要
- **THEN** 摘要内容 MUST 来源于事务域中的正式状态与汇总
- **THEN** 摘要文件或缓存 MAY 存在，但 SHALL NOT 替代事务域数据库真相
