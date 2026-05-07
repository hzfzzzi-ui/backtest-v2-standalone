## ADDED Requirements

### Requirement: ETF子系统必须以最终目标持仓作为正式执行输出
`cn-etf-beta-sleeve` MUST 在消费组合总控预算后形成最终 ETF 目标持仓，并且 SHALL 只把最终 ETF 目标持仓及最小原因摘要作为正式执行输入。ETF 内部预算拆分、模板权重、建仓节奏和研究诊断字段 SHALL NOT 成为执行内核的正式输入合同。

#### Scenario: ETF 子系统提交正式执行输入
- **WHEN** ETF 子系统完成某交易日的宽基配置构建
- **THEN** 输出 MUST 表达最终买卖 ETF 列表和每只 ETF 的最终目标权重
- **THEN** 输出 MAY 附带最小原因摘要
- **THEN** 输出 SHALL NOT 要求执行内核理解内部模板权重、建仓节奏或研究诊断字段

#### Scenario: ETF 内部中间语义存在
- **WHEN** ETF 子系统内部存在模板、节奏、恢复模式或诊断缺口语义
- **THEN** 这些语义 MAY 作为子系统内部解释或研究证据存在
- **THEN** 这些语义 SHALL NOT 被提升为正式执行输入真相
