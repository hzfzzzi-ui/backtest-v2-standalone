## MODIFIED Requirements

### Requirement: Regime router 支持 legacy 执行层 veto overlay

系统 SHALL 允许 `ma200_legacy` 保持原始状态判定不变，同时可选接入一个辅助 veto overlay。

#### Scenario: legacy overlay 不改变原始状态输出

- **WHEN** `regime_engine.engine = ma200_legacy` 且启用 `legacy_turn_weak_overlay`
- **THEN** 系统 SHALL 保持 legacy 原始 `market_state / trade_mode` 语义不变
- **THEN** overlay 仅影响执行层 `trade_mode / risk_budget_multiplier`

#### Scenario: overlay 命中 TURN_WEAK 时关闭交易

- **WHEN** `regime_engine.engine = ma200_legacy` 且启用 `legacy_turn_weak_overlay`
- **AND** 辅助 weekly 状态为 `TURN_WEAK`
- **THEN** 执行层 SHALL 输出 `trade_mode = NO_TRADE`

### Requirement: 最小 A/B 只允许 legacy overlay 变化

系统 SHALL 支持以 `baseline_V10.2` 为壳进行最小 A/B，对比：

- `ma200_legacy`
- `ma200_legacy + turn_weak_zero_overlay`

#### Scenario: A/B 配置一致

- **WHEN** 运行 legacy turn_weak overlay A/B
- **THEN** 股票池、数据角色、个股信号、退出逻辑与仓位框架 SHALL 保持一致
- **THEN** 唯一 intended diff SHALL 仅为 legacy overlay 的启用状态
