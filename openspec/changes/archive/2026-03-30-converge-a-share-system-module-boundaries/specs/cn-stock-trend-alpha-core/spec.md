## ADDED Requirements

### Requirement: 个股子系统必须以最终目标持仓作为正式执行输出
`cn-stock-trend-alpha-core` MUST 在消费组合总控预算后形成最终目标持仓，并且 SHALL 只把最终目标持仓及最小原因摘要作为正式执行输入。个股内部排序、残差评分、候选池细节和研究诊断字段 SHALL NOT 成为执行内核的正式输入合同。

#### Scenario: 个股子系统提交正式执行输入
- **WHEN** 个股子系统完成某交易日的买卖与持仓构建
- **THEN** 输出 MUST 表达最终买卖标的和最终目标权重
- **THEN** 输出 MAY 附带最小原因摘要
- **THEN** 输出 SHALL NOT 要求执行内核理解残差排名、候选池中间项或研究诊断字段

#### Scenario: 个股内部研究字段存在
- **WHEN** 个股子系统内部存在排序分数、候选池过滤原因或其他研究字段
- **THEN** 这些字段 MAY 进入研究诊断层
- **THEN** 这些字段 SHALL NOT 被定义为正式执行合同的一部分
