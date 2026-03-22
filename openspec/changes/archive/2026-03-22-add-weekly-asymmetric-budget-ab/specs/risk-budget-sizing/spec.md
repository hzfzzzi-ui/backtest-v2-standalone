## MODIFIED Requirements

### Requirement: Risk budget sizing 支持状态预算乘子

系统 SHALL 允许 `risk-budget-sizing` 消费 `regime engine` 输出的 `risk_budget_multiplier`。

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 支持以下预算模式：

- `five_state`
- `three_state`
- `asymmetric_budget`

#### Scenario: weekly_five_state 非对称预算模式

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = asymmetric_budget`
- **THEN** 系统 SHALL 使用非对称预算映射：
  - `BULL_MAIN -> 1.00`
  - `TURN_STRONG -> 0.70`
  - `LIGHT_TREND -> 0.40`
  - `TURN_WEAK -> 0.00`
  - `DEFENSIVE -> 0.00`

#### Scenario: TURN_WEAK 在非对称模式下关闭预算

- **WHEN** `risk_budget_mode = asymmetric_budget` 且 `market_state_5 = TURN_WEAK`
- **THEN** `risk_budget_multiplier` MUST 为 `0.00`

#### Scenario: TURN_STRONG 在非对称模式下不升到满仓

- **WHEN** `risk_budget_mode = asymmetric_budget` 且 `market_state_5 = TURN_STRONG`
- **THEN** `risk_budget_multiplier` MUST 保持 `0.70`
- **THEN** 系统 MUST 不得将其抬升为 `1.00`
