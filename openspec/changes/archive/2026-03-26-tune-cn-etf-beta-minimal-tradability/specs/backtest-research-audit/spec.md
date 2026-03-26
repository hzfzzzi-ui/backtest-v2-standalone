## ADDED Requirements

### Requirement: Research audit 必须评估 ETF beta 的最小可交易 smoke
`backtest-research-audit` MUST 为 `cn_etf_beta` 增加最小可交易 smoke gate。该 gate SHALL 同时检查：

- ETF provider/read path 真值
- ETF beta sleeve 解释链
- 非零 `orders`
- 非零 `trades`

#### Scenario: ETF beta smoke 具备最小可交易证据
- **WHEN** 研究审计处理 `cn_etf_beta` 的正式 smoke 产物
- **THEN** 系统 MUST 将路径真值、ETF sleeve 解释链和最小可交易证据作为同一 gate 评估
- **THEN** 若 `orders` 或 `trades` 为零，审计 SHALL 返回 `FAIL` 或 `WARN`，而不是继续返回 `PASS`

### Requirement: Research audit 必须暴露 ETF beta 的失败原因摘要
当 `cn_etf_beta` 的最小可交易 smoke 未通过时，`backtest-research-audit` MUST 输出可归因失败摘要，至少覆盖：

- `no_deployable_slots`
- `budget_reduced_to_zero`
- `not_rebalance_day`
- `absolute_filter_blocked`
- `selector_generated_no_orders`

#### Scenario: ETF beta smoke 失败时给出可归因结论
- **WHEN** ETF beta smoke 未达到最小可交易门槛
- **THEN** 研究审计 MUST 在 gate evidence 中输出失败原因摘要
- **THEN** 结论 SHALL 能区分是 Governor 问题、selector 问题还是调仓频率问题
