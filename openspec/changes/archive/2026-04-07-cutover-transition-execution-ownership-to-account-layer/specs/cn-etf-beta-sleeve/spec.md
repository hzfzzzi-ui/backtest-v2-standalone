## ADDED Requirements

### Requirement: ETF 执行链必须消费账户层 transition handoff
当账户层 handoff 处于 active 状态时，ETF 执行链 MUST 从账户层 handoff 进入 `carry / de-risk / cash release / budget handoff` 执行流程，而不是继续以旧 weak-state patch 作为主入口。

#### Scenario: ETF 在 risk_on_to_defensive 中消费账户层 handoff
- **WHEN** 账户层 handoff 为 `risk_on_to_defensive`
- **THEN** ETF 执行入口 MUST 识别并消费该 handoff
- **AND** `day_controls`、`candidate_plan`、`accounting` MUST 产出账户层 execution consumption 状态

#### Scenario: 旧 weak-state 路径仅保留 diagnostics
- **WHEN** ETF 执行链同时存在旧 weak-state 路径证据
- **THEN** 这些证据 MUST 只进入 diagnostics/reference
- **AND** 不得继续决定主执行状态或主 reject 结果
