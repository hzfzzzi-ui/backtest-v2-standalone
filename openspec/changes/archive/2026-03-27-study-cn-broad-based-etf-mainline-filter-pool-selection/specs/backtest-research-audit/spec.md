## ADDED Requirements

### Requirement: research audit 必须显式回答宽基ETF主瓶颈位于哪一层
当实验属于宽基 ETF 独立主线瓶颈 study 时，`research_audit` MUST 能显式回答主瓶颈主要位于 `absolute_filter`、`candidate_pool`、`selection_chain` 中的哪一层，而不是只给单一的 under-deploy 结论。

#### Scenario: audit 能指出主瓶颈层
- **WHEN** 用户查看宽基 ETF 主线瓶颈 study 的 `audit.json`
- **THEN** 审计结果 MUST 至少暴露 `absolute_filter`、`candidate_pool`、`selection_chain` 三层摘要
- **THEN** 审计结果 MUST 能指出每层导致的拒绝或未部署统计

### Requirement: research audit 必须输出绝对过滤瓶颈统计
当实验属于宽基 ETF 主线瓶颈 study 时，`research_audit` MUST 输出绝对过滤导致的拒绝天数、拒绝 reason counts、过滤后可选资产数统计，以及这些统计与最终 `UNDERDEPLOYED` 结论之间的关系。

#### Scenario: audit 输出绝对过滤拒绝统计
- **WHEN** 绝对过滤导致部分或全部 ETF 被排除
- **THEN** `research_audit` MUST 输出绝对过滤拒绝统计
- **THEN** `research_audit` MUST 说明这些拒绝是否直接导致最终未部署或低部署

### Requirement: research audit 必须输出候选池与选择链路瓶颈统计
当实验属于宽基 ETF 主线瓶颈 study 时，`research_audit` MUST 输出候选池 profile 摘要、selection winner/reject 统计，以及 deployability 之前和之后各自丢失了多少有效候选。

#### Scenario: audit 输出候选池和选择链路统计
- **WHEN** 宽基 ETF 主线完成一次 study 运行
- **THEN** `research_audit` MUST 输出候选池覆盖摘要和 selection chain 统计
- **THEN** `research_audit` MUST 能区分“没有合格候选”和“有候选但最终没被选中”两类问题
