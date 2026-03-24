## ADDED Requirements

### Requirement: Risk budget sizing 必须为Governor输出总预算与sleeve预算
当 A 股子系统启用统一总控时，`risk-budget-sizing` MUST 支持输出可供 Governor 消费和下发的两级预算：
- `total_risk_budget`
- `sleeve_budgets`

系统 MUST 允许在保持既有风险预算公式的同时，将其从“单策略预算”扩展为“全组合总预算 + sleeve 预算”的正式 contract。

#### Scenario: 风险预算输出总预算与sleeve预算
- **WHEN** Governor 模式启用且系统完成当日预算计算
- **THEN** 预算输出 MUST 同时包含全组合总预算和至少一个 sleeve 预算映射

### Requirement: Risk budget sizing 必须明确总预算优先于本地sizing
`risk-budget-sizing` MUST 明确总预算优先级高于任意 sleeve 本地 sizing 结果。股票 sleeve 与 ETF sleeve MAY 在既有公式内继续执行本地 sizing，但 SHALL NOT 覆盖 Governor 下发的全组合预算上限。

#### Scenario: 本地 sizing 与总预算冲突
- **WHEN** 某一 sleeve 的本地 sizing 结果超过 Governor 允许的预算
- **THEN** 系统 MUST 以 Governor 预算为准
- **THEN** 系统 MUST 记录相应的预算压缩或拒单原因

### Requirement: Risk budget sizing 必须输出可归因预算字段
当系统启用 Governor 模式时，预算产物 MUST 至少输出：
- `total_risk_budget`
- `sleeve_budget_used`
- `drawdown_state`
- `budget_reason_codes`

#### Scenario: 预算结果进入产物
- **WHEN** A 股实验完成并输出标准产物
- **THEN** 产物 MUST 能回答“今天的总预算为什么是这个值”
- **THEN** 产物 MUST 能回答“某个 sleeve 为什么没有吃满本地 sizing”

