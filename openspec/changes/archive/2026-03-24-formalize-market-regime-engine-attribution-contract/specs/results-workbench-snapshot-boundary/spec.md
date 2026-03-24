## MODIFIED Requirements

### Requirement: ResultsWorkbenchSnapshot 必须携带Governed A股状态与预算摘要
当结果属于 Governed A 股主线时，`ResultsWorkbenchSnapshot` MUST 携带最小 regime/governor 摘要，且这些摘要 MUST 来自正式 regime payload 与 Governor 证据链。

最小摘要至少包含：

- `base_state_5`
- `effective_state_5`
- `coarse_state`
- `effective_coarse_state`
- `regime_confidence`
- `regime_transition_reason`
- `risk_budget_multiplier`
- `defense_bias`
- `total_risk_budget`
- `total_exposure_cap`
- `budget_reason_codes`

前端 SHALL NOT 仅根据 `market_state` 或 `trade_mode` 自行推断上述语义。

#### Scenario: Governed A股 snapshot 暴露正式状态摘要
- **WHEN** 结果工作台加载 Governed A 股实验 snapshot
- **THEN** snapshot MUST 直接提供正式 regime/governor 摘要，而不是要求前端自行拼装

### Requirement: ResultsWorkbenchSnapshot 必须携带归因审计摘要
当结果属于 Governed A 股主线时，`ResultsWorkbenchSnapshot` MUST 携带最小 attribution 摘要，至少包含：

- `reason_codes`
- `subscores.technical`
- `subscores.sentiment`
- `subscores.macro_global`
- `manual_override.active`
- `manual_override.reason`
- `manual_override.scope`

该摘要 SHALL 用于支持后续 Governor / Regime / Attribution 可视化，而不是只保留在 debug 文件中。

#### Scenario: snapshot 足以支持前端解释状态来源
- **WHEN** 前端渲染 Governed A 股结果概览
- **THEN** snapshot MUST 足以展示状态来源、预算原因和是否存在人工干预
