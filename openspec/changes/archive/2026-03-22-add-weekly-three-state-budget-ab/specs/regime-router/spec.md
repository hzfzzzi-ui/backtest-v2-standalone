## MODIFIED Requirements

### Requirement: Weekly five-state 只改变市场过滤与风险预算

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 保持个股信号逻辑不变：

- 仍使用主线 `40日突破 + 40日个股残差动量排序`
- 不得切换到旧 `TREND_LIGHT -> EMA5/20` 替代分支

#### Scenario: 三档预算模式不改变原始状态输出

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = three_state`
- **THEN** 系统 SHALL 继续输出原始五档 `market_state_raw_name / market_state_smoothed_name`
- **THEN** 系统 SHALL 继续输出原始 `market_state_score`
- **THEN** 三档仅用于执行预算与可交易控制

#### Scenario: 三档预算模式的 trade_mode 兼容输出

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = three_state`
- **THEN** `BULL_MAIN / TURN_STRONG / LIGHT_TREND` SHALL 输出兼容 `trade_mode = TREND_MAIN`
- **THEN** `TURN_WEAK / DEFENSIVE` SHALL 输出兼容 `trade_mode = NO_TRADE`

### Requirement: 最小 A/B 只允许预算模式变化

系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `weekly_five_state + five_state budget`
- `weekly_five_state + three_state budget`

并保证 intended diff 限制在：

- `regime_engine.engine`
- `weekly_five_state.risk_budget_mode`

#### Scenario: A/B 配置一致

- **WHEN** 运行 weekly three-state budget A/B
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致
