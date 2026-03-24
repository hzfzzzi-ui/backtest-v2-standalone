## ADDED Requirements

### Requirement: ResultsWorkbenchSnapshot 必须携带Governed A股状态与预算摘要
当结果属于 A 股 governed multi-sleeve 主线时，`ResultsWorkbenchSnapshot` MUST 携带最小的 regime 与 Governor 摘要，至少包括：
- `base_state`
- `effective_state`
- `coarse_state`
- `risk_budget_multiplier`
- `total_risk_budget`
- `sleeve_budgets_summary`

#### Scenario: 工作台渲染 governed 主线实验
- **WHEN** 页面壳加载 governed A 股实验结果
- **THEN** snapshot MUST 携带上述状态与预算摘要
- **THEN** 工作台 MUST 能基于 snapshot 展示最小的状态/预算解释信息

### Requirement: ResultsWorkbenchSnapshot 必须携带归因审计摘要
当结果属于 A 股 governed multi-sleeve 主线时，`ResultsWorkbenchSnapshot` MUST 携带 attribution 摘要，至少包括：
- `reason_code_summary`
- `override_active`
- `sleeve_decision_summary`

#### Scenario: 工作台渲染归因摘要
- **WHEN** 用户查看 governed 主线实验结果
- **THEN** 工作台 MUST 能通过 snapshot 判断是否存在人工 override
- **THEN** 工作台 MUST 能通过 snapshot 展示最小归因摘要而不直接重算研究逻辑

