## MODIFIED Requirements

### Requirement: 正式审计不得暴露 sleeve_budget 历史别名
系统 MUST 在正式审计中只保留当前架构定义的三层正式摘要：`candidate_boundary`、`candidate_plan`、`execution_kernel`。正式产物 SHALL NOT 再暴露 `sleeve_budget` 作为候选边界的历史别名。

#### Scenario: 写入正式 audit row
- **WHEN** 系统为某个交易日写入正式 audit row
- **THEN** 产物 MUST 包含 `candidate_boundary`、`candidate_plan` 和 `execution_kernel`
- **THEN** 产物 SHALL NOT 包含 `sleeve_budget`
