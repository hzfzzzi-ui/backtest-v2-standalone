## ADDED Requirements

### Requirement: Breakout Failure / Exit Fragility Catalog
系统 MUST 提供 `RESEARCH_ONLY` 的 breakout failure / exit fragility catalog，定义主线失败风险、脆弱性上下文与解释边界。

#### Scenario: Catalog exposes canonical failure and fragility factors
- **WHEN** 研究层请求 breakout failure / exit fragility catalog
- **THEN** catalog MUST 返回 canonical failure-risk / fragility 因子定义
- **AND** 每个因子 MUST 包含名称、说明、方向约定、as-of 约束和与退出语义的关系
- **AND** catalog MUST 明确此能力不改变正式 runtime exit 行为
