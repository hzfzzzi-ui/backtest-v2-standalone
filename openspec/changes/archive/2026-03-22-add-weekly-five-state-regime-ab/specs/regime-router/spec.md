## MODIFIED Requirements

### Requirement: Regime router 支持 engine 选择
系统 SHALL 允许 `regime-router` 根据 `regime_engine.engine` 在以下两种引擎之间切换：

- `ma200_legacy`
- `weekly_five_state`

#### Scenario: 使用 weekly_five_state
- **WHEN** `regime_engine.engine = weekly_five_state`
- **THEN** router SHALL 消费周度五态状态机的日频前向填充结果

### Requirement: Weekly five-state 只改变市场过滤与风险预算
当 `regime_engine.engine = weekly_five_state` 时，系统 MUST 保持个股信号逻辑不变：

- 仍使用主线 `40日突破 + 40日个股残差动量排序`
- 不得切换到旧 `TREND_LIGHT -> EMA5/20` 替代分支

#### Scenario: 非防守状态仍走主线信号
- **WHEN** `market_state_5` 属于 `BULL_MAIN / TURN_STRONG / LIGHT_TREND / TURN_WEAK`
- **THEN** 系统 SHALL 继续使用主线 breakout + residual 信号逻辑

#### Scenario: 防守状态阻止新开仓
- **WHEN** `market_state_5 = DEFENSIVE`
- **THEN** 系统 SHALL 阻止新的买入信号，但继续执行已有持仓退出规则

### Requirement: trade_mode 兼容输出
当 `regime_engine.engine = weekly_five_state` 时，系统 SHALL 继续输出兼容的 `trade_mode`：

- `TREND_MAIN`：对应 `BULL_MAIN / TURN_STRONG / LIGHT_TREND / TURN_WEAK`
- `NO_TRADE`：对应 `DEFENSIVE`

#### Scenario: 五态兼容 trade_mode
- **WHEN** weekly five-state 运行
- **THEN** 现有前后端消费链仍可从 `trade_mode` 判断是否允许开新仓

### Requirement: 最小 A/B 只允许 engine 变化
系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `weekly_five_state`

并保证唯一 intended diff 为 `regime_engine.engine`。

#### Scenario: A/B 配置一致
- **WHEN** 运行 weekly five-state A/B 实验
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致
