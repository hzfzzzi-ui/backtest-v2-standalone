## MODIFIED Requirements

### Requirement: Weekly five-state 只改变市场过滤与风险预算

当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 保持个股信号逻辑不变：

- 仍使用主线 `40日突破 + 40日个股残差动量排序`
- 不得切换到旧 `TREND_LIGHT -> EMA5/20` 替代分支

#### Scenario: 非对称预算模式不改变五档原始状态

- **WHEN** `regime_engine.engine = weekly_five_state` 且 `risk_budget_mode = asymmetric_budget`
- **THEN** 系统 SHALL 继续输出五档原始 `market_state_raw_name / market_state_smoothed_name / market_state_score`
- **THEN** 非对称模式仅影响执行预算与 `trade_mode`

#### Scenario: 非对称预算模式的 trade_mode

- **WHEN** `risk_budget_mode = asymmetric_budget`
- **THEN** `BULL_MAIN / TURN_STRONG / LIGHT_TREND` SHALL 输出 `trade_mode = TREND_MAIN`
- **THEN** `TURN_WEAK / DEFENSIVE` SHALL 输出 `trade_mode = NO_TRADE`

### Requirement: 最小 A/B 只允许预算模式变化

系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `weekly_five_state + five_state`
- `weekly_five_state + asymmetric_budget`

并保证 intended diff 限制在：

- `regime_engine.engine`
- `weekly_five_state.risk_budget_mode`

#### Scenario: A/B 配置一致

- **WHEN** 运行 weekly asymmetric budget A/B
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致
- **THEN** `weekly_five_state` 两组之间唯一 intended diff SHALL 仅为 `risk_budget_mode`
