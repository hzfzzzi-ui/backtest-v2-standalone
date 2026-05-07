## MODIFIED Requirements

### Requirement: 正式审计必须区分候选规划层与纯执行内核层
系统 MUST 在正式审计中区分候选边界层、候选规划层和纯执行内核层的拒绝来源。进入纯执行内核后产生的现金、整手、持仓名额和订单合并拒绝， SHALL 与候选规划层拒绝分开记录。

#### Scenario: 计划层与执行层同时存在拒绝
- **WHEN** 某交易日同时出现候选规划层拒绝和执行内核层拒绝
- **THEN** 正式审计 MUST 分别记录这两层摘要
- **THEN** 审计结果 SHALL NOT 把执行层拒绝误记为候选规划层拒绝

#### Scenario: stage 主路径缺少候选规划正式产物
- **WHEN** 执行阶段缺少正式的 `candidate_plan_v1`
- **THEN** 审计 MUST 能把该问题归因为边界接线失败
- **THEN** 审计 SHALL NOT 用执行拒绝或空订单静默掩盖该问题
