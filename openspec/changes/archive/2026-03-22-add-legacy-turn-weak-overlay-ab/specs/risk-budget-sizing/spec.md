## MODIFIED Requirements

### Requirement: Risk budget sizing 支持 legacy overlay 归零

系统 SHALL 允许 `risk-budget-sizing` 在 `ma200_legacy` 模式下消费一个辅助 veto overlay。

#### Scenario: TURN_WEAK overlay 命中时预算归零

- **WHEN** `regime_engine.engine = ma200_legacy`
- **AND** `legacy_turn_weak_overlay.enabled = true`
- **AND** 辅助 weekly 状态为 `TURN_WEAK`
- **THEN** `risk_budget_multiplier` MUST 为 `0.00`

#### Scenario: 非 TURN_WEAK 日保持 legacy 原预算

- **WHEN** `regime_engine.engine = ma200_legacy`
- **AND** `legacy_turn_weak_overlay.enabled = true`
- **AND** 辅助 weekly 状态不为 `TURN_WEAK`
- **THEN** 系统 MUST 保持 legacy 原有预算映射
