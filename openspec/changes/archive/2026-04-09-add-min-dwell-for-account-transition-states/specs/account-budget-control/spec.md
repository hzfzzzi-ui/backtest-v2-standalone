## MODIFIED Requirements

### Requirement: 账户层预算控制消费有效状态
账户层预算控制 MUST 使用经过最短停留策略处理后的 `effective_state_5`，而不是直接使用 raw state。

#### Scenario: 预算控制消费抗抖后的状态
- **GIVEN** raw state 被最短停留策略抑制
- **WHEN** 系统计算账户层预算
- **THEN** 系统 MUST 以 `effective_state_5` 作为预算状态输入
- **AND** MUST 保留 raw state 作为诊断字段
