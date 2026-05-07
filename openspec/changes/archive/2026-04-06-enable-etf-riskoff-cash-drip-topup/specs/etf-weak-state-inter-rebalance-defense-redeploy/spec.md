## ADDED Requirements

### Requirement: weak-state inter-rebalance defense redeploy 的 `RISK_OFF` 分支必须支持 cash-drip top-up
当 weak-state inter-rebalance defense redeploy 运行于 `RISK_OFF` 时，系统 MUST 支持基于可用现金的 drip top-up。该路径 SHALL 允许小额 clip，而不是继续把 `RISK_OFF` 视为只有在 deploy gap 足够大时才值得执行的路径。

#### Scenario: `RISK_OFF` 分支进入 cash-drip top-up
- **WHEN** weak-state inter-rebalance defense redeploy 被激活
- **AND** `effective_state_5 = RISK_OFF`
- **AND** 当前正式目标仍有未完成缺口
- **AND** 存在满足最小可执行单位的可用现金
- **THEN** 系统 MUST 允许进入 cash-drip top-up
- **THEN** 运行 explain MUST 明确该次执行属于 `RISK_OFF cash-drip top-up`
