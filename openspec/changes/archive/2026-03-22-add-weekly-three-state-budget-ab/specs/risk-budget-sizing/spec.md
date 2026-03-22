## MODIFIED Requirements

### Requirement: Risk budget sizing 支持状态预算乘子

系统 SHALL 允许 `risk-budget-sizing` 消费 `regime engine` 输出的 `risk_budget_multiplier`。

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 支持两种预算模式：

- `five_state`
- `three_state`

#### Scenario: weekly_five_state 五档预算模式

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = five_state`
- **THEN** 系统 SHALL 使用原五档预算映射：
  - `BULL_MAIN -> 1.00`
  - `TURN_STRONG -> 0.70`
  - `LIGHT_TREND -> 0.40`
  - `TURN_WEAK -> 0.15`
  - `DEFENSIVE -> 0.00`

#### Scenario: weekly_five_state 三档预算模式

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = three_state`
- **THEN** 系统 SHALL 将五档原始状态折叠为三档预算 bucket：
  - `BULL_MAIN / TURN_STRONG -> RISK_ON -> 1.00`
  - `LIGHT_TREND -> NEUTRAL -> 0.40`
  - `TURN_WEAK / DEFENSIVE -> RISK_OFF -> 0.00`

#### Scenario: 三档预算模式不保留 TURN_WEAK 低仓预算

- **WHEN** `risk_budget_mode = three_state`
- **THEN** `TURN_WEAK` MUST 不再映射到 `0.15`
- **THEN** `TURN_WEAK` MUST 归入 `RISK_OFF`

#### Scenario: 默认仍为五档预算模式

- **WHEN** 用户未显式设置 `risk_budget_mode`
- **THEN** 系统 SHALL 默认使用 `five_state`
