## MODIFIED Requirements

### Requirement: Risk budget sizing 支持状态预算乘子
系统 SHALL 允许 `risk-budget-sizing` 消费由 regime engine 输出的 `risk_budget_multiplier`。

当 `regime_engine.engine = weekly_five_state` 时：

- `BULL_MAIN` -> `1.00`
- `TURN_STRONG` -> `0.70`
- `LIGHT_TREND` -> `0.40`
- `TURN_WEAK` -> 默认 `0.15`
- `DEFENSIVE` -> `0.00`

#### Scenario: 风险预算随状态缩放
- **WHEN** weekly five-state 运行
- **THEN** 组合风险预算 SHALL 乘以状态预算乘子

### Requirement: TURN_WEAK 预算保持低自由度
系统 SHALL 仅允许 `TURN_WEAK` 风险预算在 `0.10~0.20` 范围内微调，默认值为 `0.15`。

#### Scenario: TURN_WEAK 默认预算
- **WHEN** 用户未显式配置
- **THEN** `TURN_WEAK` 风险预算 SHALL 默认为 `0.15`

### Requirement: DEFENSIVE 预算为零
当 `market_state_5 = DEFENSIVE` 时，系统 MUST 将状态预算乘子设为 `0.00`，从而禁止新开仓。

#### Scenario: 防守状态零预算
- **WHEN** `market_state_5 = DEFENSIVE`
- **THEN** `risk_budget_multiplier = 0.00`
